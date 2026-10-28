"""Render (round 12 slices.md S1/S3): the rendered tree (PR 3's loaded tree, renamed) built from one binding. It walks
``binding.items`` and builds each directive with its arguments from ``arguments_at``. It never looks a name up
(design rule 3: the binding is the one home of that rule) and reads no file. Private; a port of
ts/src/load/render.ts (it replaces ``_expand.py``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from villanelle.directives import Directive, Unreadable
from villanelle.origin import DirectiveOrigin, Place
from villanelle.span import SourcePosition, SourceSpan
from villanelle.written import _document, _graph
from villanelle.written._bind import BoundItem, BoundUnreadable
from villanelle.written.model import DocumentGraph, WrittenDirective

if TYPE_CHECKING:
    from villanelle.processor import Processor, Rendered

_START = SourcePosition(0, 0, 0)


def render(graph: DocumentGraph, processor: Processor) -> Rendered:
    """The rendered tree of the graph's current texts and handed-in values."""
    from villanelle.processor import Rendered

    binding = _graph.binding(graph)
    made: list[Directive] = []

    def build(
        items: list[BoundItem], parent: Directive | None, body: list[Directive], unreadable: list[Unreadable]
    ) -> None:
        for item in items:
            statement = item.copy.statement
            doc = statement._doc
            node = statement._node
            if isinstance(item, BoundUnreadable):
                written = _document.place(doc, (node.start, node.end))
                unreadable.append(Unreadable(item.reason, DirectiveOrigin(written, item.copy.via), statement))
                continue
            assert isinstance(statement, WrittenDirective)
            args = tuple(a for value in statement._value_list for a in binding.arguments_at(value, item.copy))
            name = doc._syntax.tokens[node.start]
            origin = DirectiveOrigin(Place(doc._path, name.span), item.copy.via)
            directive = Directive(name.text, args, item.children is not None, parent, origin, statement)
            made.append(directive)
            body.append(directive)
            if item.children is not None:
                build(item.children, directive, *directive._contents())

    body: list[Directive] = []
    unreadable: list[Unreadable] = []
    build(binding.items, None, body, unreadable)
    for directive in made:
        directive._freeze()
    origin = DirectiveOrigin(Place(graph.root.resolved_path, SourceSpan(_START, _START)), ())
    diagnostics = (*_graph.syntax_diagnostics(graph), *binding.diagnostics)
    return Rendered(processor, tuple(body), tuple(unreadable), origin, diagnostics, graph)
