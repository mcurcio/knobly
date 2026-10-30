"""The rendered tree of one graph (spec 7.0-7.2, 7.5): ``render(graph)``, the rendered layer's entry point, and
``Rendered`` with its addresses and ``diff``. ``render`` builds on the low level's public objects only (owner,
2026-10-29): it reads ``graph.expand()`` and ``graph.root.resolved_path``, never a package-internal module or member
of the low level (checked by tests/test_layers.py). It never looks a name up (design rule 3: the binding is the one
home of that rule) and reads no file. A port of ts/src/rendered/."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import TypeAlias, final

from knobly._api import rendered as api
from knobly._api.errors import DiagnosticError
from knobly._api.rendered import Added, AddressStep, Change, Changed, KeyRule, Removed, Unknown
from knobly._api.shared import DirectiveOrigin, SourcePosition, SourceSpan
from knobly._origin import Place
from knobly._report import LocatedDiagnostic, check_program_code
from knobly.rendered._tree import Address, Directive, RenderedBlock, rendered_block
from knobly.written import DocumentGraph, UnreadableExpansion

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
        return self._graph

    def addresses(self, *, key: KeyRule | None = None) -> Mapping[Directive, Address]:
        # In walk order. A loop over a stack of open blocks, not a recursion: the tree may be MAX_EXPANDED_NESTING
        # deep (spec 2.5).
        out: dict[Directive, Address] = {}
        # Per open block: its directives left, its address steps, and how often each name and key occurred in it.
        stack: list[tuple[Iterator[Directive], tuple[AddressStep, ...], dict[tuple[str, str | None], int]]] = [
            (iter(self._block), (), {})
        ]
        while stack:
            container, parent, occurrences = stack[-1]
            directive = next(container, None)
            if directive is None:
                stack.pop()
                continue
            key_text = None if key is None else key(directive)
            if key_text is not None and not isinstance(key_text, str):
                raise TypeError(f"a key rule returns a str or None, not {type(key_text).__name__}: {directive.name}")
            slot = (directive.name, key_text)
            occurrence = occurrences.get(slot, 0)
            occurrences[slot] = occurrence + 1
            steps = (*parent, AddressStep(directive.name, key_text, occurrence))
            out[directive] = Address(steps)
            block = directive.block
            if block is not None:
                stack.append((iter(block), steps, {}))
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
    block = rendered_block(expansion.block)
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
    """Removed and unknown, in ``before``'s walk order. ``incomplete``: ``after``'s container holds an unreadable. A
    loop over a stack of matched blocks, not a recursion (spec 2.5: up to MAX_EXPANDED_NESTING deep)."""
    stack = [(iter(before), {new[d]: d for d in after}, incomplete)]
    while stack:
        container, by_address, gaps = stack[-1]
        directive = next(container, None)
        if directive is None:
            stack.pop()
            continue
        address = old[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Unknown(address, directive) if gaps else Removed(address, directive))
        else:
            stack.append((iter(directive.block or ()), {new[d]: d for d in match.block or ()}, bool(match.unreadable)))


def _compare_after(
    after: Sequence[Directive], before: Sequence[Directive], new: _Addresses, old: _Addresses, into: list[Change]
) -> None:
    """Added and changed, in ``after``'s walk order; a loop, as ``_compare_before``."""
    stack = [(iter(after), {old[d]: d for d in before})]
    while stack:
        container, by_address = stack[-1]
        directive = next(container, None)
        if directive is None:
            stack.pop()
            continue
        address = new[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Added(address, directive))
            continue
        if _changed(match, directive):
            into.append(Changed(address, match, directive))
        stack.append((iter(directive.block or ()), {old[d]: d for d in match.block or ()}))


def _changed(before: Directive, after: Directive) -> bool:
    """Its own values' canonical texts, or whether it has a block, differ (slices.md §1.5)."""
    texts = [a.text for a in before.values] != [a.text for a in after.values]
    return texts or (before.block is None) != (after.block is None)
