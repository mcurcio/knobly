"""The rendered tree of one graph (spec 7.0-7.2, 7.5): ``render(graph)``, the rendered layer's entry point, and
``Rendered`` with its addresses and ``diff``. ``render`` walks the graph's binding (``binding.items``) and builds each
directive with its arguments from ``arguments_at``; it never looks a name up (design rule 3: the binding is the one
home of that rule) and reads no file. A port of ts/src/rendered/."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeAlias, final

from villanelle.diagnostics import DiagnosticError
from villanelle.origin import DirectiveOrigin, Place
from villanelle.rendered._tree import Address, AddressStep, Argument, Directive, KeyRule, Unreadable, walk_block
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.span import SourcePosition, SourceSpan
from villanelle.written import _document, _graph
from villanelle.written._bind import BoundItem, BoundUnreadable, BoundValue
from villanelle.written.model import DocumentGraph, WrittenDirective

_START = SourcePosition(0, 0, 0)


@final
class Rendered:
    """The rendered tree of one graph. Problems are diagnostics; the root file owns the top level, as a directive its
    block."""

    __slots__ = ("_block", "_diagnostics", "_graph", "_origin", "_unreadable")

    def __init__(
        self,
        block: tuple[Directive, ...],
        unreadable: tuple[Unreadable, ...],
        origin: DirectiveOrigin,
        diagnostics: tuple[LocatedDiagnostic, ...],
        graph: DocumentGraph,
    ) -> None:
        """Made by ``render`` only."""
        self._block = block
        self._unreadable = unreadable
        self._origin = origin
        self._diagnostics = diagnostics
        self._graph = graph

    @property
    def block(self) -> tuple[Directive, ...]:
        """The top-level readable directives, expanded."""
        return self._block

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """Top-level statements that could not be read (R6: their siblings stay)."""
        return self._unreadable

    @property
    def origin(self) -> DirectiveOrigin:
        """The root file at 0:0, zero width: where a problem with no line of its own is placed."""
        return self._origin

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """PR 3's content and order (D11): every file's syntax diagnostics (documents in order), then the walk's
        problems in walk order."""
        return self._diagnostics

    @property
    def graph(self) -> DocumentGraph:
        """The graph it was rendered from."""
        return self._graph

    def walk(self, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]:
        """Every directive, depth-first in written order. ``descend``, when given, is asked of each directive
        yielded; False passes over its block. Stop early with ``break``."""
        return walk_block(self._block, descend)

    def addresses(self, *, key: KeyRule | None = None) -> Mapping[Directive, Address]:
        """Every directive's address under ``key``, in walk order (the mapping's order). The key rule is called once
        per directive, parents before children; what it raises propagates. The one home of the address rule (D4);
        ``diff`` uses it. Without a key rule, a directive is named by its position among same-name siblings."""
        out: dict[Directive, Address] = {}

        def name(container: Sequence[Directive], parent: tuple[AddressStep, ...]) -> None:
            occurrences: dict[tuple[str, str | None], int] = {}
            for directive in container:
                key_text = None if key is None else key(directive)
                slot = (directive.name, key_text)
                occurrence = occurrences.get(slot, 0)
                occurrences[slot] = occurrence + 1
                steps = (*parent, AddressStep(directive.name, key_text, occurrence))
                out[directive] = Address(steps)
                block = directive.block
                if block is not None:
                    name(block, steps)

        name(self._block, ())
        return MappingProxyType(out)

    def diff(self, after: Rendered, /, *, key: KeyRule | None = None) -> list[Change]:
        """What differs from this render to ``after``, by address under ``key`` (D4): removed and unknown in this
        render's walk order, then added and changed in ``after``'s. A directive missing from ``after`` is Unknown, not
        Removed, when its block in ``after`` (or the top level) holds an unreadable statement. Raises whatever the key
        rule raises."""
        old = self.addresses(key=key)
        new = after.addresses(key=key)
        gone: list[Change] = []
        came: list[Change] = []
        _compare_before(self._block, after._block, bool(after._unreadable), old, new, gone)
        _compare_after(after._block, self._block, new, old, came)
        return gone + came

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error for a problem of the whole file, such as a required top-level directive left out."""
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.place, self._origin.via))


def render(graph: DocumentGraph, /) -> Rendered:
    """The rendered tree of the graph's current texts and overrides: variables substituted, snippets used, included
    files spliced in. Pure: reads no file; an unread include copy renders as nothing (its edge is in
    ``graph.unread()``). Raises TypeError for anything but a document graph from a processor's load."""
    if not isinstance(graph, DocumentGraph):
        raise TypeError("render takes a document graph from a processor's load")
    binding = _graph.binding(graph)
    made: list[Directive] = []

    def build(
        items: list[BoundItem], parent: Directive | None, block: list[Directive], unreadable: list[Unreadable]
    ) -> None:
        for item in items:
            statement = item.copy.statement
            doc = statement._doc
            node = statement._node
            if isinstance(item, BoundUnreadable):
                place = _document.place(doc, (node.start, node.end))
                unreadable.append(Unreadable(item.reason, DirectiveOrigin(place, item.copy.via), statement))
                continue
            assert isinstance(statement, WrittenDirective)
            values = tuple(
                _argument(bound) for value in statement._value_list for bound in binding.arguments_at(value, item.copy)
            )
            name = doc._syntax.tokens[node.start]
            origin = DirectiveOrigin(Place(doc._path, name.span), item.copy.via)
            directive = Directive(name.text, values, item.children is not None, parent, origin, statement)
            made.append(directive)
            block.append(directive)
            if item.children is not None:
                build(item.children, directive, *directive._contents())

    block: list[Directive] = []
    unreadable: list[Unreadable] = []
    build(binding.items, None, block, unreadable)
    for directive in made:
        directive._freeze()
    origin = DirectiveOrigin(Place(graph.root.resolved_path, SourceSpan(_START, _START)), ())
    diagnostics = (*_graph.syntax_diagnostics(graph), *binding.diagnostics)
    return Rendered(tuple(block), tuple(unreadable), origin, diagnostics, graph)


def _argument(bound: BoundValue) -> Argument:
    """A bound value as a rendered argument (spec 7.3): ``written`` is the ``$name`` on the same line when it came
    through a variable (a list item shares its list's), else the value itself, its own definition."""
    value = bound.value
    held = tuple(_argument(item) for item in value) if isinstance(value, tuple) else value
    written = bound.chain[0].reference if bound.chain else bound.definition
    assert written is not None, "a value read where it is written has a definition"
    return Argument(bound.kind, held, bound.origin, written=written, definition=bound.definition, chain=bound.chain)


@final
@dataclass(frozen=True, slots=True)
class Added:
    address: Address
    after: Directive


@final
@dataclass(frozen=True, slots=True)
class Removed:
    address: Address
    before: Directive


@final
@dataclass(frozen=True, slots=True)
class Changed:
    """Same address; its own values (by text) or whether it has a block differ."""

    address: Address
    before: Directive
    after: Directive


@final
@dataclass(frozen=True, slots=True)
class Unknown:
    """It was in ``before``; in ``after`` its block holds an unreadable statement that may be it."""

    address: Address
    before: Directive


Change: TypeAlias = Added | Removed | Changed | Unknown
"""One difference between two renders. An added, removed or unknown directive is listed alone, never with the
directives inside it (``walk`` it); a changed one's block is compared at its own addresses."""

_Addresses: TypeAlias = Mapping[Directive, Address]


def _compare_before(
    before: Sequence[Directive],
    after: Sequence[Directive],
    incomplete: bool,
    old: _Addresses,
    new: _Addresses,
    into: list[Change],
) -> None:
    """Removed and unknown, in ``before``'s walk order. ``incomplete``: ``after``'s container holds an unreadable."""
    by_address = {new[d]: d for d in after}
    for directive in before:
        address = old[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Unknown(address, directive) if incomplete else Removed(address, directive))
        else:
            _compare_before(directive.block or (), match.block or (), bool(match.unreadable), old, new, into)


def _compare_after(
    after: Sequence[Directive], before: Sequence[Directive], new: _Addresses, old: _Addresses, into: list[Change]
) -> None:
    """Added and changed, in ``after``'s walk order."""
    by_address = {old[d]: d for d in before}
    for directive in after:
        address = new[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Added(address, directive))
            continue
        if _changed(match, directive):
            into.append(Changed(address, match, directive))
        _compare_after(directive.block or (), match.block or (), new, old, into)


def _changed(before: Directive, after: Directive) -> bool:
    """Its own values' canonical texts, or whether it has a block, differ (slices.md §1.5)."""
    texts = [a.text for a in before.values] != [a.text for a in after.values]
    return texts or (before.block is None) != (after.block is None)
