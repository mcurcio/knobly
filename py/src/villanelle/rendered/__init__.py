"""``villanelle.rendered``: the middle layer, the rendered tree (spec 7). It builds on the low level and has its own
types: ``render(graph)`` takes a ``DocumentGraph`` and returns a ``Rendered`` whose directives hold ``Argument``s
(shared ``ExpandedValue``s plus links to the written values). Nothing below this layer imports it (spec 5, "Layer
direction"; checked by tests/test_layers.py)."""

from villanelle.rendered._render import Added, Change, Changed, Removed, Rendered, Unknown, render
from villanelle.rendered._tree import Address, AddressStep, Argument, Directive, KeyRule, Unreadable

__all__ = [
    "Added",
    "Address",
    "AddressStep",
    "Argument",
    "Change",
    "Changed",
    "Directive",
    "KeyRule",
    "Removed",
    "Rendered",
    "Unknown",
    "Unreadable",
    "render",
]
