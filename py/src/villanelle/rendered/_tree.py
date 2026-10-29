"""The rendered tree's nodes (spec 7; R15 tier 2): what a program walks after ``render``. Model: the standard ``ast``
module. Nodes are read-only objects with ``__match_args__``, read with ``match``; ``walk()`` iterates a subtree as
``ast.walk`` does (here in written order); every node carries where it came from. Directives and values are expanded
(variables replaced, snippets and extension files spliced in). These are the rendered layer's own types: they build
on the shared ``ExpandedValue`` and name low-level handles (``written``), never the other way round."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import TypeAlias, cast, final

from villanelle._api.kinds import UnreadableReason
from villanelle.errors import DiagnosticError
from villanelle.origin import DirectiveOrigin, Origin
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.value import ExpandedIndex, ExpandedList, ExpandedSlice, ExpandedString, ExpandedWord
from villanelle.written import (
    DirectiveExpansion,
    ReferenceResolution,
    Statement,
    UnreadableExpansion,
    ValueExpansion,
    WrittenDirective,
    WrittenValue,
)


class _Links:
    """What every argument adds to its expanded value (spec 7.3): three links to the low level, ``written``,
    ``definition`` and ``chain``, and ``list()`` narrowed to arguments. Private: the public type is the union
    ``Argument``."""

    __slots__ = ()

    _written: WrittenValue
    _definition: WrittenValue | None
    _chain: tuple[ReferenceResolution, ...]

    @property
    def written(self) -> WrittenValue:
        """The written value on the same line: for a value that came through a variable, the ``$name`` there
        (``chain[0].reference``; a list item shares its list's); otherwise the value itself. Never None. Editing it
        edits that one written line, which every copy of the line shares: a file included twice has one line read in
        both copies (``written.statement.copies()``), so the edit shows in both. To change one copy only, edit what
        that copy is given instead (its include block's ``set``, at the include step of ``chain``). A live handle: the
        argument itself is a snapshot of one render."""
        return self._written

    @property
    def definition(self) -> WrittenValue | None:
        """The written value at the end of its chain (for ``$pixels``, the ``2284`` of its ``set``); None for an
        override. Editing it changes every use."""
        return self._definition

    @property
    def chain(self) -> tuple[ReferenceResolution, ...]:
        """One per variable step of ``origin.via``, from this value's own line toward where it is written (D7):
        ``[0]`` is the ``$name`` written on the directive's line. Empty for a value written where it is read."""
        return self._chain

    def list(self) -> tuple[Argument, ...]:
        """A list's items, each an argument with its own origin. E4002 for any other kind."""
        return cast("tuple[Argument, ...]", ExpandedList.list(cast("ExpandedList", self)))


@final
class WordArgument(_Links, ExpandedWord):
    """A word value of a directive. Match it: ``case WordArgument("true"):``."""

    __match_args__ = ("text",)
    __slots__ = ("_chain", "_definition", "_written")

    def __init__(
        self,
        text: str,
        origin: Origin,
        *,
        written: WrittenValue,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """Made by ``render`` only."""
        super().__init__(text, origin)
        self._written = written
        self._definition = definition
        self._chain = chain


@final
class StringArgument(_Links, ExpandedString):
    """A string value of a directive; ``string()`` is its decoded text. Its match field is ``text``, the canonical
    text with its quotes: ``case StringArgument('"10.0.60.30"'):``, or read ``string()`` in a guard."""

    __match_args__ = ("text",)
    __slots__ = ("_chain", "_definition", "_written")

    def __init__(
        self,
        value: str,
        origin: Origin,
        *,
        written: WrittenValue,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """Made by ``render`` only. ``value`` is the decoded text."""
        super().__init__(value, origin)
        self._written = written
        self._definition = definition
        self._chain = chain


@final
class ListArgument(_Links, ExpandedList):
    """A list value of a directive: its ``items`` are arguments, each with its own origin and links."""

    __match_args__ = ("items",)
    __slots__ = ("_chain", "_definition", "_written")

    def __init__(
        self,
        items: tuple[Argument, ...],
        origin: Origin,
        *,
        written: WrittenValue,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """Made by ``render`` only."""
        super().__init__(items, origin)
        self._written = written
        self._definition = definition
        self._chain = chain

    @property
    def items(self) -> tuple[Argument, ...]:
        return cast("tuple[Argument, ...]", self._items)


@final
class SliceArgument(_Links, ExpandedSlice):
    """A slice value of a directive."""

    __match_args__ = ("name", "start", "end")
    __slots__ = ("_chain", "_definition", "_written")

    def __init__(
        self,
        name: str,
        start: int | None,
        end: int | None,
        origin: Origin,
        *,
        written: WrittenValue,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """Made by ``render`` only."""
        super().__init__(name, start, end, origin)
        self._written = written
        self._definition = definition
        self._chain = chain


@final
class IndexArgument(_Links, ExpandedIndex):
    """An index value of a directive."""

    __match_args__ = ("name", "index")
    __slots__ = ("_chain", "_definition", "_written")

    def __init__(
        self,
        name: str,
        index: int,
        origin: Origin,
        *,
        written: WrittenValue,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """Made by ``render`` only."""
        super().__init__(name, index, origin)
        self._written = written
        self._definition = definition
        self._chain = chain


Argument: TypeAlias = WordArgument | StringArgument | ListArgument | SliceArgument | IndexArgument
"""One value of a directive, after expansion (spec 7.3): the expanded value of its kind plus its links to the low
level. Match it by class: ``case WordArgument("true"):``."""


def argument_of(expansion: ValueExpansion) -> Argument:
    """The argument of one value expansion: the variant of its value's kind, with the expansion's links. Private to
    the rendered layer."""
    value = expansion.value
    written, definition, chain = expansion.written, expansion.definition, expansion.chain
    match value:
        case ExpandedList():
            items = tuple(argument_of(item) for item in expansion.items)
            return ListArgument(items, value.origin, written=written, definition=definition, chain=chain)
        case ExpandedString():
            return StringArgument(value.string(), value.origin, written=written, definition=definition, chain=chain)
        case ExpandedSlice():
            return SliceArgument(
                value.name, value.start, value.end, value.origin, written=written, definition=definition, chain=chain
            )
        case ExpandedIndex():
            return IndexArgument(
                value.name, value.index, value.origin, written=written, definition=definition, chain=chain
            )
        case ExpandedWord():
            return WordArgument(value.text, value.origin, written=written, definition=definition, chain=chain)


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


@final
@dataclass(frozen=True, slots=True, match_args=False)
class Unreadable:
    """A statement of a block (or of the top level) that could not be read, kept in its place so a reader and ``diff``
    know the block is incomplete. It has no name or address: what it would have been is unknown."""

    __match_args__ = ("reason",)

    reason: UnreadableReason
    """Why: ``syntax`` (the parser could not read it), ``expansion`` (a variable, ``set``, ``snippet`` or ``use``
    failed), ``value`` (a value broke a value rule checked at load) or ``extension`` (an extension line failed)."""
    origin: DirectiveOrigin
    written: Statement
    """The statement that could not be read here."""


def unreadable_of(expansion: UnreadableExpansion) -> Unreadable:
    """The rendered unreadable of one unreadable expansion. Private to the rendered layer."""
    return Unreadable(expansion.reason, expansion.origin, expansion.statement)


@final
class Directive:
    """One directive after expansion. ``set``, ``snippet``, ``use`` and extension directives never appear: their results
    do, in their place. Match it: ``case vl.Directive("node", [kind, node_id, *rest], block):``. Its address is
    ``rendered.addresses(key=...)[directive]`` (D4)."""

    __match_args__ = ("name", "values", "block")
    __slots__ = ("_block", "_name", "_origin", "_parent", "_unreadable", "_values", "_written")

    def __init__(self, expansion: DirectiveExpansion, parent: Directive | None) -> None:
        """Made by ``render`` only, from one directive copy of the graph's expansion: its block's directives are made
        with it, each with this one as its parent."""
        self._name = expansion.statement.name
        self._values = tuple(argument_of(value) for value in expansion.values)
        self._parent = parent
        self._origin = expansion.origin
        self._written = expansion.statement
        self._block = None if expansion.block is None else tuple(Directive(child, self) for child in expansion.block)
        self._unreadable = tuple(unreadable_of(u) for u in expansion.unreadable)

    def __repr__(self) -> str:
        return f"Directive({self._name!r}, {[a.text for a in self._values]!r})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def values(self) -> tuple[Argument, ...]:
        """Its values, expanded."""
        return self._values

    @property
    def block(self) -> tuple[Directive, ...] | None:
        """The block's readable directives; None when written without a block."""
        return self._block

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """The block's statements that could not be read; empty when there is no block or all were read."""
        return self._unreadable

    @property
    def parent(self) -> Directive | None:
        """The enclosing directive; None at the top level."""
        return self._parent

    @property
    def origin(self) -> DirectiveOrigin:
        """Where its name was written, and the uses and includes that brought it here."""
        return self._origin

    @property
    def written(self) -> WrittenDirective:
        """The written directive this is a copy of (closes vil-uji): the same handle for every copy of one line."""
        return self._written

    def walk(self, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]:
        """Every directive in its block, at any depth (not itself), depth-first in written order. ``descend``, when
        given, is asked of each directive yielded; False passes over its block. Stop early with ``break``."""
        return walk_block(self._block or (), descend)

    def closest(self, predicate: Callable[[Directive], bool], /) -> Directive | None:
        """This directive or its nearest enclosing one that matches, as the DOM's ``Element.closest``."""
        directive: Directive | None = self
        while directive is not None and not predicate(directive):
            directive = directive.parent
        return directive

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error placed on this directive's name. Raises ValueError when ``code`` has no "/"."""
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.place, self._origin.via))


KeyRule: TypeAlias = Callable[[Directive], "str | None"]
"""The program's rule for naming a directive among its siblings, so it keeps its address when lines move (D5: it
takes the rendered directive). Called once per directive, parents before children, in walk order, by
``Rendered.addresses`` and ``Rendered.diff``; what it raises propagates. rasl:
``lambda d: d.values[1].text if d.name == "node" and d.parent and d.parent.name == "graph" else None``."""


def walk_block(block: Sequence[Directive], descend: Callable[[Directive], bool] | None) -> Iterator[Directive]:
    """The one home of the walk: every directive under ``block``, depth-first in written order. Private to the
    rendered layer."""
    stack: list[Iterator[Directive]] = [iter(block)]
    while stack:
        directive = next(stack[-1], None)
        if directive is None:
            stack.pop()
            continue
        yield directive
        inner = directive.block
        if inner and (descend is None or descend(directive)):
            stack.append(iter(inner))
