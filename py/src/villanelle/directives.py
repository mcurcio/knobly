"""The directive layer (R15 tier 2): what a program walks after a load. Model: the standard ``ast`` module. Nodes are
read-only objects with ``__match_args__``, read with ``match``; ``walk()`` iterates a subtree as ``ast.walk`` does
(here in written order); every node carries where it came from. Directives and values are expanded (variables
replaced, snippets and extension files spliced in)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias, final

from villanelle.diagnostics import DiagnosticError
from villanelle.origin import DirectiveOrigin, Origin
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

    @property
    def kind(self) -> ValueKind:
        raise NotImplementedError("Argument.kind")

    @property
    def text(self) -> str:
        """The canonical text, the same in both languages (slices.md "Canonical text"). Comments and line breaks are
        never part of it. Two values are the same exactly when their texts are equal."""
        raise NotImplementedError("Argument.text")

    @property
    def origin(self) -> Origin:
        raise NotImplementedError("Argument.origin")

    def as_word(self) -> str:
        """A bare word. Raises DiagnosticError E4002 for any other kind."""
        raise NotImplementedError("Argument.as_word")

    def as_str(self) -> str:
        """A word or a string, decoded. Raises DiagnosticError E4002 for a list, slice or index."""
        raise NotImplementedError("Argument.as_str")

    def as_number(self) -> int | float:
        """A word spelling a NumberText: int without fraction or exponent, else float. E4002, E4004."""
        raise NotImplementedError("Argument.as_number")

    def as_int(self) -> int:
        """A word spelling an IntegerText. E4002, E4005."""
        raise NotImplementedError("Argument.as_int")

    def as_bool(self) -> bool:
        """The word ``true`` or ``false``. E4002, E4006."""
        raise NotImplementedError("Argument.as_bool")

    def as_list(self) -> tuple[Argument, ...]:
        """A list's items, each with its own origin. E4002 for any other kind."""
        raise NotImplementedError("Argument.as_list")

    def as_slice(self) -> SliceValue | IndexValue:
        """A slice or an index. E4002 for any other kind."""
        raise NotImplementedError("Argument.as_slice")

    def plain(self) -> PlainValue:
        """Any value by the one rule: a string is its str; a word is a number if it spells a NumberText, a bool if
        ``true``/``false``, else its str; a list is a tuple of its items read the same way; a slice or an index is its
        value. Never raises."""
        raise NotImplementedError("Argument.plain")

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report, placed on this value (for a handed-in value: on the ``$name`` that used
        it). Raises ValueError at once when ``code`` has no "/" (villanelle's codes are its own)."""
        raise NotImplementedError("Argument.error")


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
        raise NotImplementedError("Address.text")

    @property
    def parent(self) -> Address | None:
        """The enclosing directive's address; None at the top level."""
        raise NotImplementedError("Address.parent")

    def __str__(self) -> str:
        """For people: ``graph > node "leds" > max_count`` (slices.md "Address")."""
        raise NotImplementedError("Address.__str__")


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

    @property
    def name(self) -> str:
        raise NotImplementedError("Directive.name")

    @property
    def args(self) -> tuple[Argument, ...]:
        raise NotImplementedError("Directive.args")

    @property
    def body(self) -> tuple[Directive, ...] | None:
        """The block's readable directives; None when written without a block."""
        raise NotImplementedError("Directive.body")

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """The block's statements that could not be read; empty when there is no block or all were read."""
        raise NotImplementedError("Directive.unreadable")

    @property
    def parent(self) -> Directive | None:
        """The enclosing directive; None at the top level."""
        raise NotImplementedError("Directive.parent")

    @property
    def address(self) -> Address:
        raise NotImplementedError("Directive.address")

    @property
    def origin(self) -> DirectiveOrigin:
        """Where its name was written, and the uses and includes that brought it here."""
        raise NotImplementedError("Directive.origin")

    @property
    def node(self) -> Node:
        """Its directive node in the tier-1 tree of the file ``origin.written`` names (for editing, vil-uji)."""
        raise NotImplementedError("Directive.node")

    def closest(self, predicate: Callable[[Directive], bool], /) -> Directive | None:
        """This directive or its nearest enclosing one that matches, as the DOM's ``Element.closest``."""
        raise NotImplementedError("Directive.closest")

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error placed on this directive's name. Raises ValueError when ``code`` has no "/"."""
        raise NotImplementedError("Directive.error")


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
    raise NotImplementedError("walk")
