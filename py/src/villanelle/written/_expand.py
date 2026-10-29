"""The expansion (spec 6.10): the graph's one derivation (``_bind``) as the public snapshot ``DocumentGraph.expand()``
returns, so the rendered layer builds on the low level's public objects only (owner, 2026-10-29: "The middle layer of
objects can build on the lower layer domains"). Private."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle.origin import DirectiveOrigin, Place
from villanelle.written import _document, _graph
from villanelle.written._bind import Binding, BoundDirective, BoundItem, BoundValue
from villanelle.written.model import (
    DirectiveExpansion,
    DocumentGraph,
    Expansion,
    UnreadableExpansion,
    ValueExpansion,
    WrittenDirective,
)


def expand(graph: DocumentGraph) -> Expansion:
    """The current derivation as an expansion: the top level, then the diagnostics (syntax per document, then the
    walk's in walk order, render's codes included)."""
    binding = _graph.binding(graph)
    block, unreadable = _items(binding, binding.items)
    diagnostics = (*_graph.syntax_diagnostics(graph), *binding.diagnostics)
    return Expansion(block, unreadable, diagnostics)


def _items(
    binding: Binding, items: Sequence[BoundItem]
) -> tuple[tuple[DirectiveExpansion, ...], tuple[UnreadableExpansion, ...]]:
    block: list[DirectiveExpansion] = []
    unreadable: list[UnreadableExpansion] = []
    for item in items:
        statement = item.copy.statement
        doc, node = statement._doc, statement._node
        if not isinstance(item, BoundDirective):
            place = _document.place(doc, (node.start, node.end))
            unreadable.append(UnreadableExpansion(statement, item.reason, DirectiveOrigin(place, item.copy.via)))
            continue
        assert isinstance(statement, WrittenDirective), "a readable copy is a written directive's"
        values = tuple(
            _value(bound) for value in statement._value_list for bound in binding.arguments_at(value, item.copy)
        )
        name = doc._syntax.tokens[node.start]
        origin = DirectiveOrigin(Place(doc._path, name.span), item.copy.via)
        inner: tuple[DirectiveExpansion, ...] | None = None
        inner_unreadable: tuple[UnreadableExpansion, ...] = ()
        if item.children is not None:
            inner, inner_unreadable = _items(binding, item.children)
        block.append(DirectiveExpansion(statement, origin, values, inner, inner_unreadable))
    return tuple(block), tuple(unreadable)


def _value(bound: BoundValue) -> ValueExpansion:
    """One bound value with its links (spec 7.3): ``written`` is the ``$name`` on the same line when it came through a
    variable (a list item shares its list's), else the value itself, its own definition."""
    written = bound.chain[0].reference if bound.chain else bound.definition
    assert written is not None, "a value read where it is written has a definition"
    items = tuple(_value(item) for item in bound.value) if isinstance(bound.value, tuple) else ()
    return ValueExpansion(bound.expanded, written, bound.definition, bound.chain, items)
