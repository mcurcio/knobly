"""``knobly.rendered``: the middle layer, the rendered tree (spec 7). It builds on the low level's public objects
only: ``render(graph)`` reads ``graph.expand()`` and returns a ``Rendered`` whose directives hold the expansion's own
expanded values and unreadable expansions, adding names, parents, blocks that walk, addresses and ``diff``. Nothing
below this layer imports it, and it imports nothing private of the low level (spec 5, "Layer direction")."""

# The records (AddressStep, Added ... Unknown), the Change union and KeyRule are generated from spec/schema/api.json
# (knobly._api.rendered). The rendered layer holds the expansion's own objects (kno-umh.8). tests/test_layers.py
# checks the layer direction.

from knobly import _docs
from knobly._api.kinds import ChangeKind
from knobly._api.rendered import Added, AddressStep, Change, Changed, KeyRule, Removed, Unknown
from knobly.rendered._render import Rendered, render
from knobly.rendered._tree import Address, Directive, RenderedBlock

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

_docs.document(__name__)
