"""``villanelle.rendered``: the middle layer, the rendered tree (spec 7). It builds on the low level's public objects
only and has its own types: ``render(graph)`` reads ``graph.expand()`` and returns a ``Rendered`` whose directives
hold arguments (one class per value kind, each the shared expanded value of its kind plus links to the written
values). Nothing below this layer imports it, and it imports nothing private of the low level (spec 5, "Layer
direction"; both checked by tests/test_layers.py)."""

from villanelle.rendered._render import Added, Change, Changed, Removed, Rendered, Unknown, render
from villanelle.rendered._tree import (
    Address,
    AddressStep,
    Argument,
    Directive,
    IndexArgument,
    KeyRule,
    ListArgument,
    SliceArgument,
    StringArgument,
    Unreadable,
    WordArgument,
)

__all__ = [
    "Added",
    "Address",
    "AddressStep",
    "Argument",
    "Change",
    "Changed",
    "Directive",
    "IndexArgument",
    "KeyRule",
    "ListArgument",
    "Removed",
    "Rendered",
    "SliceArgument",
    "StringArgument",
    "Unknown",
    "Unreadable",
    "WordArgument",
    "render",
]
