"""``villanelle.rendered``: the middle layer, the rendered tree (spec 7). It builds on the low level's public objects
only: ``render(graph)`` reads ``graph.expand()`` and returns a ``Rendered`` whose directives hold the expansion's own
expanded values and unreadable expansions (vil-umh.8), adding names, parents, blocks that walk, addresses and
``diff``. Nothing below this layer imports it, and it imports nothing private of the low level (spec 5, "Layer
direction"; both checked by tests/test_layers.py). The records (``AddressStep``, ``Added`` ... ``Unknown``), the
``Change`` union and ``KeyRule`` are generated from spec/schema/api.json (``villanelle._api.rendered``)."""

from villanelle._api.kinds import ChangeKind
from villanelle._api.rendered import Added, AddressStep, Change, Changed, KeyRule, Removed, Unknown
from villanelle.rendered._render import Rendered, render
from villanelle.rendered._tree import Address, Directive, RenderedBlock

__all__ = [
    "Added",
    "Address",
    "AddressStep",
    "Change",
    "ChangeKind",
    "Changed",
    "Directive",
    "KeyRule",
    "Removed",
    "Rendered",
    "RenderedBlock",
    "Unknown",
    "render",
]
