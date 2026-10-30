"""The expansion (spec 6.10): the graph's one derivation (``_bind``) as the public snapshot ``DocumentGraph.expand()``
returns, so the rendered layer builds on the low level's public objects only (owner, 2026-10-29: "The middle layer of
objects can build on the lower layer domains"). Private."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle._api.shared import DirectiveOrigin
from villanelle._api.written import DirectiveExpansion, Expansion, UnreadableExpansion
from villanelle._origin import Place
from villanelle.written import _document, _graph
from villanelle.written._bind import Binding, BoundDirective, BoundItem
from villanelle.written._model import DocumentGraph, ExpansionBlock, WrittenDirective


def expand(graph: DocumentGraph) -> Expansion:
    """The current derivation as an expansion: the top level, then the graph's one diagnostics list."""
    binding = _graph.binding(graph)
    block, unreadable = _items(binding, binding.items)
    return Expansion(block=block, unreadable=unreadable, diagnostics=_graph.diagnostics(graph))


def _items(binding: Binding, items: Sequence[BoundItem]) -> tuple[ExpansionBlock, tuple[UnreadableExpansion, ...]]:
    block: list[DirectiveExpansion] = []
    unreadable: list[UnreadableExpansion] = []
    for item in items:
        statement = item.copy.statement
        doc, node = statement._doc, statement._node
        if not isinstance(item, BoundDirective):
            place = _document.place(doc, (node.start, node.end))
            origin = DirectiveOrigin(place, item.copy.via)
            unreadable.append(UnreadableExpansion(reason=item.reason, written=statement, origin=origin))
            continue
        assert isinstance(statement, WrittenDirective), "a readable copy is a written directive's"
        values = tuple(value for written in statement._value_list for value in binding.arguments_at(written, item.copy))
        name = doc._syntax.tokens[node.start]
        origin = DirectiveOrigin(Place(doc._path, name.span), item.copy.via)
        inner: ExpansionBlock | None = None
        inner_unreadable: tuple[UnreadableExpansion, ...] = ()
        if item.children is not None:
            inner, inner_unreadable = _items(binding, item.children)
        block.append(
            DirectiveExpansion(
                written=statement, values=values, block=inner, origin=origin, unreadable=inner_unreadable
            )
        )
    return ExpansionBlock(tuple(block)), tuple(unreadable)
