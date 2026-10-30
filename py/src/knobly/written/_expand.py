"""The expansion (spec 6.10): the graph's one derivation (``_bind``) as the public snapshot ``DocumentGraph.expand()``
returns, so the rendered layer builds on the low level's public objects only (owner, 2026-10-29: "The middle layer of
objects can build on the lower layer domains"). Private."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from knobly._api.shared import DirectiveOrigin
from knobly._api.written import DirectiveExpansion, Expansion, UnreadableExpansion
from knobly._origin import Place
from knobly.written import _document, _graph
from knobly.written._bind import Binding, BoundDirective, BoundItem
from knobly.written._model import DocumentGraph, ExpansionBlock, WrittenDirective
from knobly.written._value import ExpandedValue


def expand(graph: DocumentGraph) -> Expansion:
    """The current derivation as an expansion: the top level, then the graph's one diagnostics list."""
    binding = _graph.binding(graph)
    block, unreadable = _items(binding, binding.items)
    return Expansion(block=block, unreadable=unreadable, diagnostics=_graph.diagnostics(graph))


@dataclass(slots=True)
class _Open:
    """One block being made: its items left, what is made so far, and the directive it belongs to (None at the top
    level), made once the block is."""

    items: Iterator[BoundItem]
    owner: tuple[WrittenDirective, tuple[ExpandedValue, ...], DirectiveOrigin] | None
    block: list[DirectiveExpansion] = field(default_factory=list)
    unreadable: list[UnreadableExpansion] = field(default_factory=list)


def _items(binding: Binding, items: Sequence[BoundItem]) -> tuple[ExpansionBlock, tuple[UnreadableExpansion, ...]]:
    """The top level's block and unreadable statements. A loop over a stack of open blocks, not a recursion: the
    expanded tree may be MAX_EXPANDED_NESTING deep (spec 2.5)."""
    stack = [_Open(iter(items), None)]
    while True:
        open_ = stack[-1]
        item = next(open_.items, None)
        if item is None:
            stack.pop()
            block, unreadable = ExpansionBlock(tuple(open_.block)), tuple(open_.unreadable)
            if open_.owner is None:
                return block, unreadable
            written, values, origin = open_.owner
            made = DirectiveExpansion(written=written, values=values, block=block, origin=origin, unreadable=unreadable)
            stack[-1].block.append(made)
            continue
        statement = item.copy.statement
        doc, node = statement._doc, statement._node
        if not isinstance(item, BoundDirective):
            place = _document.place(doc, (node.start, node.end))
            origin = DirectiveOrigin(place, item.copy.via)
            open_.unreadable.append(UnreadableExpansion(reason=item.reason, written=statement, origin=origin))
            continue
        assert isinstance(statement, WrittenDirective), "a readable copy is a written directive's"
        values = tuple(value for written in statement._value_list for value in binding.arguments_at(written, item.copy))
        name = doc._syntax.tokens[node.start]
        origin = DirectiveOrigin(Place(doc._path, name.span), item.copy.via)
        if item.children is None:
            made = DirectiveExpansion(written=statement, values=values, block=None, origin=origin, unreadable=())
            open_.block.append(made)
        else:
            stack.append(_Open(iter(item.children), (statement, values, origin)))
