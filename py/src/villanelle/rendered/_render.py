"""The rendered tree of one graph (spec 7.0-7.2, 7.5): ``render(graph)``, the rendered layer's entry point, and
``Rendered`` with its addresses and ``diff``. ``render`` builds on the low level's public objects only (owner,
2026-10-29): it reads ``graph.expand()`` and ``graph.root.resolved_path``, never a package-internal module or member
of the low level (checked by tests/test_layers.py). It never looks a name up (design rule 3: the binding is the one
home of that rule) and reads no file. A port of ts/src/rendered/."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypeAlias, final

from villanelle._api import rendered as api
from villanelle._api.errors import DiagnosticError
from villanelle._api.rendered import Added, AddressStep, Change, Changed, KeyRule, Removed, Unknown
from villanelle._api.shared import DirectiveOrigin, SourcePosition, SourceSpan
from villanelle._origin import Place
from villanelle._report import LocatedDiagnostic, check_program_code
from villanelle.rendered._tree import Address, Directive, RenderedBlock
from villanelle.written import DocumentGraph, UnreadableExpansion

_START = SourcePosition(0, 0, 0)


@final
class Rendered(api.Rendered):
    __slots__ = ("_block", "_diagnostics", "_graph", "_origin", "_unreadable")

    def __init__(
        self,
        block: RenderedBlock,
        unreadable: tuple[UnreadableExpansion, ...],
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
    def block(self) -> RenderedBlock:
        return self._block

    @property
    def unreadable(self) -> tuple[UnreadableExpansion, ...]:
        return self._unreadable

    @property
    def origin(self) -> DirectiveOrigin:
        return self._origin

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        return self._diagnostics

    @property
    def graph(self) -> DocumentGraph:
        """The graph it was rendered from."""
        return self._graph

    def addresses(self, *, key: KeyRule | None = None) -> Mapping[Directive, Address]:
        out: dict[Directive, Address] = {}

        def name(container: Sequence[Directive], parent: tuple[AddressStep, ...]) -> None:
            occurrences: dict[tuple[str, str | None], int] = {}
            for directive in container:
                key_text = None if key is None else key(directive)
                if key_text is not None and not isinstance(key_text, str):
                    raise TypeError(
                        f"a key rule returns a str or None, not {type(key_text).__name__}: {directive.name}"
                    )
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

    def diff(self, after: Rendered, /, *, key: KeyRule | None = None) -> tuple[Change, ...]:
        if not isinstance(after, Rendered):
            raise TypeError(f"diff() argument 'after' must be a Rendered, not {type(after).__name__}")
        old = self.addresses(key=key)
        new = after.addresses(key=key)
        gone: list[Change] = []
        came: list[Change] = []
        _compare_before(self._block, after.block, bool(after.unreadable), old, new, gone)
        _compare_after(after.block, self._block, new, old, came)
        return (*gone, *came)

    def error(self, message: str, *, code: str) -> DiagnosticError:
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.place, self._origin.via))


def render(graph: DocumentGraph, /) -> Rendered:
    if not callable(getattr(graph, "expand", None)):
        raise TypeError(
            "render() argument 'graph' must be a document graph (an object with an expand method), "
            f"not {type(graph).__name__}"
        )
    expansion = graph.expand()
    block = RenderedBlock(tuple(Directive(directive, None) for directive in expansion.block))
    origin = DirectiveOrigin(Place(graph.root.resolved_path, SourceSpan(_START, _START)), ())
    return Rendered(block, expansion.unreadable, origin, expansion.diagnostics, graph)


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
