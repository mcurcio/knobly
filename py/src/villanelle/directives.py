"""The directive layer (R15 tier 2): what a program walks after a load. Model: the standard ``ast`` module. Nodes are
read-only objects with ``__match_args__``, read with ``match``; ``walk()`` iterates a subtree as ``ast.walk`` does
(here in written order); every node carries where it came from. Directives and values are expanded (variables
replaced, snippets and extension files spliced in)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias, final

from villanelle import _values
from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.origin import DirectiveOrigin, Origin, Place, Step
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.syntax._recovery import message_of
from villanelle.syntax.cst import Node
from villanelle.value import IndexValue, SliceValue, ValueKind

if TYPE_CHECKING:
    from villanelle.processor import Loaded

PlainValue: TypeAlias = "int | float | bool | str | SliceValue | IndexValue | tuple[PlainValue, ...]"
"""A value by villanelle's one rule. Quoting means text: ``"8080"`` and ``"true"`` are str; only a bare word is read
as a number (NumberText) or as true/false (BooleanText)."""


@final
class Argument:
    """One value of a directive, after expansion: a ``$name`` has already become its value(s). Invariants checked at
    load, so readers never meet them: a string's escapes are the six of EscapeText; a slice bound is an IntegerText.
    Match it: ``case vl.Argument("word", "true"):``."""

    __match_args__ = ("kind", "text")
    __slots__ = ("_kind", "_origin", "_text", "_value")

    def __init__(self, kind: ValueKind, value: ArgumentValue, origin: Origin) -> None:
        """Made by the load only. ``value`` by kind: a word's text, a string's decoded text, a list's items, a
        SliceValue or an IndexValue."""
        self._kind = kind
        self._value = value
        self._origin = origin
        self._text = _canonical_text(kind, value)

    def __repr__(self) -> str:
        return f"Argument({self._kind.value!r}, {self._text!r})"

    def _rebase(self, drop: int, append: tuple[Step, ...]) -> Argument:
        """The same value having travelled further: the last ``drop`` steps of its origin (and of each list item's)
        are replaced by ``append``. A variable's value is stored with ``drop`` = the ``set`` line's own steps, and read
        with ``append`` = the variable step and the reading place's steps. Private to the load layer."""
        via = self._origin.via
        origin = Origin(self._origin.written, via[: len(via) - drop] + append)
        value = self._value
        if isinstance(value, tuple):
            value = tuple(item._rebase(drop, append) for item in value)
        return Argument(self._kind, value, origin)

    @property
    def kind(self) -> ValueKind:
        return self._kind

    @property
    def text(self) -> str:
        """The canonical text, the same in both languages (slices.md "Canonical text"). Comments and line breaks are
        never part of it. Two values are the same exactly when their texts are equal."""
        return self._text

    @property
    def origin(self) -> Origin:
        return self._origin

    def as_word(self) -> str:
        """A bare word. Raises DiagnosticError E4002 for any other kind."""
        return self._word("a word")

    def as_str(self) -> str:
        """A word or a string, decoded. Raises DiagnosticError E4002 for a list, slice or index."""
        if isinstance(self._value, str):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a word or a string, not a {self._kind}")

    def as_number(self) -> int | float:
        """A word spelling a NumberText: int without fraction or exponent, else float. E4002, E4004."""
        number = _values.number_of(self._word("a number"))
        if number is None:
            raise self._problem(DiagnosticCode.NOT_A_NUMBER, self._text)
        return number

    def as_int(self) -> int:
        """A word spelling an IntegerText. E4002, E4005."""
        integer = _values.integer_of(self._word("an integer"))
        if integer is None:
            raise self._problem(DiagnosticCode.NOT_AN_INTEGER, self._text)
        return integer

    def as_bool(self) -> bool:
        """The word ``true`` or ``false``. E4002, E4006."""
        boolean = _values.boolean_of(self._word("true or false"))
        if boolean is None:
            raise self._problem(DiagnosticCode.NOT_A_BOOLEAN, self._text)
        return boolean

    def as_list(self) -> tuple[Argument, ...]:
        """A list's items, each with its own origin. E4002 for any other kind."""
        if isinstance(self._value, tuple):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a list, not a {self._kind}")

    def as_slice(self) -> SliceValue | IndexValue:
        """A slice or an index. E4002 for any other kind."""
        if isinstance(self._value, SliceValue | IndexValue):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a slice or an index, not a {self._kind}")

    def plain(self) -> PlainValue:
        """Any value by the one rule: a string is its str; a word is a number if it spells a NumberText, a bool if
        ``true``/``false``, else its str; a list is a tuple of its items read the same way; a slice or an index is its
        value. Never raises."""
        value = self._value
        if isinstance(value, tuple):
            return tuple(item.plain() for item in value)
        if self._kind is ValueKind.WORD and isinstance(value, str):
            number = _values.number_of(value)
            if number is not None:
                return number
            boolean = _values.boolean_of(value)
            return value if boolean is None else boolean
        return value

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report, placed on this value (for a handed-in value: on the ``$name`` that used
        it). Raises ValueError at once when ``code`` has no "/" (villanelle's codes are its own)."""
        check_program_code(code)
        return value_error(self, code, message)

    def _word(self, wanted: str) -> str:
        if self._kind is ValueKind.WORD and isinstance(self._value, str):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected {wanted}, not a {self._kind}")

    def _problem(self, code: DiagnosticCode, detail: str) -> DiagnosticError:
        return value_error(self, code, f"{message_of(code)}: {detail}")


def value_error(argument: Argument, code: DiagnosticCode | str, message: str) -> DiagnosticError:
    """A located error placed on a value. A handed-in value is written in no file: the problem is placed on the
    ``$name`` that used it (``via[0]``) and the message names the variable. Private to the package."""
    written, via = argument.origin.written, argument.origin.via
    if isinstance(written, Place):
        return DiagnosticError(LocatedDiagnostic(code, message, written, via))
    return DiagnosticError(LocatedDiagnostic(code, f"{message} (handed-in ${written.variable})", via[0].at, via[1:]))


ArgumentValue: TypeAlias = "str | tuple[Argument, ...] | SliceValue | IndexValue"
"""What an argument holds, by kind (private to the load layer)."""


def _canonical_text(kind: ValueKind, value: ArgumentValue) -> str:
    """The canonical text of a value (slices.md §1.3)."""
    if isinstance(value, tuple):
        return _values.canonical_list(item.text for item in value)
    if isinstance(value, SliceValue):
        return _values.canonical_slice(value.name, value.start, value.end)
    if isinstance(value, IndexValue):
        return _values.canonical_index(value.name, value.index)
    return _values.canonical_string(value) if kind is ValueKind.STRING else value


@dataclass(frozen=True, slots=True)
class AddressStep:
    name: str
    key: str | None
    """What the key rule returned for this directive; None when it returned nothing or there is no rule."""
    occurrence: int
    """0-based, among earlier siblings with the same name and key."""


@final
@dataclass(frozen=True, slots=True)
class Address:
    """Where a directive lands in the expanded tree: its identity across loads. Hashable; unique within one load. A file
    included at two places, or a snippet used twice, lands at two addresses (R21: "Allowed, per place")."""

    steps: tuple[AddressStep, ...]
    """From the top level down to this directive."""

    @property
    def text(self) -> str:
        """The canonical string, the same bytes as TypeScript: ``json.dumps([[s.name, s.key, s.occurrence] for s in
        steps], ensure_ascii=False, separators=(",", ":"))``."""
        return json.dumps(
            [[s.name, s.key, s.occurrence] for s in self.steps], ensure_ascii=False, separators=(",", ":")
        )

    @property
    def parent(self) -> Address | None:
        """The enclosing directive's address; None at the top level."""
        return Address(self.steps[:-1]) if len(self.steps) > 1 else None

    def __str__(self) -> str:
        """For people: ``graph > node "leds" > max_count`` (slices.md "Address")."""
        return " > ".join(
            s.name
            + ("" if s.key is None else " " + json.dumps(s.key, ensure_ascii=False))
            + ("" if s.occurrence == 0 else f" #{s.occurrence}")
            for s in self.steps
        )


class UnreadableKind(StrEnum):
    SYNTAX = "syntax"
    """The parser could not read the statement (an error node, R6)."""
    EXPANSION = "expansion"
    """A variable, ``set``, ``snippet`` or ``use`` failed (unknown name, wrong arity, cycle, limits)."""
    VALUE = "value"
    """A value broke a value rule checked at load (a non-integer slice bound, an unknown escape)."""
    EXTENSION = "extension"
    """An extension directive failed (bad path, file not found, the source failed)."""


@dataclass(frozen=True, slots=True)
class Unreadable:
    """A statement of a block (or of the top level) that could not be read, kept in its place so a reader and ``diff``
    know the block is incomplete. It has no name or address: what it would have been is unknown."""

    kind: UnreadableKind
    origin: DirectiveOrigin
    node: Node
    """Its tier-1 node in the file ``origin.written`` names: the error node, or the directive node that failed."""


@final
class Directive:
    """One directive after expansion. ``set``, ``snippet``, ``use`` and extension directives never appear: their results
    do, in their place. Match it: ``case vl.Directive("node", [kind, node_id, *rest], body):``."""

    __match_args__ = ("name", "args", "body")
    __slots__ = ("_address", "_args", "_body", "_key_input", "_name", "_node", "_origin", "_parent", "_unreadable")

    def __init__(
        self,
        name: str,
        args: tuple[Argument, ...],
        has_block: bool,
        parent: Directive | None,
        address: Address,
        origin: DirectiveOrigin,
        node: Node,
        key_input: KeyInput,
    ) -> None:
        """Made by the load only, which fills the block while it expands it and then calls ``_freeze``."""
        self._name = name
        self._args = args
        self._body: list[Directive] | tuple[Directive, ...] | None = [] if has_block else None
        self._unreadable: list[Unreadable] | tuple[Unreadable, ...] = []
        self._parent = parent
        self._address = address
        self._origin = origin
        self._node = node
        self._key_input = key_input
        """What the key rule saw of this directive (private to the load layer)."""

    def __repr__(self) -> str:
        return f"Directive({self._name!r}, {[a.text for a in self._args]!r}, address={str(self._address)!r})"

    def _contents(self) -> tuple[list[Directive], list[Unreadable]]:
        """The block's lists while the load fills them. Private to the load layer."""
        assert isinstance(self._body, list) and isinstance(self._unreadable, list)
        return self._body, self._unreadable

    def _freeze(self) -> None:
        """End of the load: the block becomes read-only. Private to the load layer."""
        if self._body is not None:
            self._body = tuple(self._body)
        self._unreadable = tuple(self._unreadable)

    @property
    def name(self) -> str:
        return self._name

    @property
    def args(self) -> tuple[Argument, ...]:
        return self._args

    @property
    def body(self) -> tuple[Directive, ...] | None:
        """The block's readable directives; None when written without a block."""
        return None if self._body is None else tuple(self._body)

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """The block's statements that could not be read; empty when there is no block or all were read."""
        return tuple(self._unreadable)

    @property
    def parent(self) -> Directive | None:
        """The enclosing directive; None at the top level."""
        return self._parent

    @property
    def address(self) -> Address:
        return self._address

    @property
    def origin(self) -> DirectiveOrigin:
        """Where its name was written, and the uses and includes that brought it here."""
        return self._origin

    @property
    def node(self) -> Node:
        """Its directive node in the tier-1 tree of the file ``origin.written`` names (for editing, vil-uji)."""
        return self._node

    def closest(self, predicate: Callable[[Directive], bool], /) -> Directive | None:
        """This directive or its nearest enclosing one that matches, as the DOM's ``Element.closest``."""
        directive: Directive | None = self
        while directive is not None and not predicate(directive):
            directive = directive._parent
        return directive

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error placed on this directive's name. Raises ValueError when ``code`` has no "/"."""
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.written, self._origin.via))


@final
@dataclass(frozen=True, slots=True)
class KeyInput:
    """What the key rule sees of one directive: its expanded header, before its block is expanded."""

    name: str
    args: tuple[Argument, ...]
    has_block: bool
    parent: KeyInput | None
    """The enclosing directive as the key rule saw it; None at the top level."""


KeyRule: TypeAlias = Callable[[KeyInput], "str | None"]
"""The program's rule for naming a directive among its siblings, so it keeps its address when lines move. Called once
per readable directive, parents before children, in expansion order; an exception it raises ends the load. rasl:
``lambda d: d.args[1].text if d.name == "node" and d.parent and d.parent.name == "graph" else None``."""


def walk(node: Loaded | Directive, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]:
    """Every directive under ``node`` (not ``node`` itself), depth-first in written order. ``descend``, when given, is
    asked of each directive yielded; False passes over its block. Stop early with ``break``."""
    stack: list[Iterator[Directive]] = [iter(node.body or ())]
    while stack:
        directive = next(stack[-1], None)
        if directive is None:
            stack.pop()
            continue
        yield directive
        if directive.body and (descend is None or descend(directive)):
            stack.append(iter(directive.body))
