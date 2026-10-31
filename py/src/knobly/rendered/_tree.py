"""The rendered tree's nodes (spec 7; R15 tier 2): what a program walks after ``render``. Model: the standard ``ast``
module. Nodes are read-only objects with ``__match_args__``, read with ``match``; a block's ``walk()`` iterates a
subtree as ``ast.walk`` does (here in written order); every node carries where it came from. Directives and values
are expanded (variables replaced, snippets and extension files spliced in). A directive is built on its directive
expansion's own objects (kno-umh.8): its ``values`` are the low level's expanded values and its ``unreadable`` the
low level's unreadable expansions, the same objects; this layer adds ``name``, ``parent``, ``closest``, the address
and ``error``, and its block (``RenderedBlock``) the walk. It names low-level handles, never the other way round."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import final

from knobly._api import rendered as api
from knobly._api.errors import DiagnosticError
from knobly._api.rendered import AddressStep
from knobly._api.shared import DirectiveOrigin
from knobly._block import BlockBase
from knobly._report import LocatedDiagnostic, check_program_code
from knobly.written import DirectiveExpansion, ExpandedValue, UnreadableExpansion, WrittenDirective


@final
@dataclass(frozen=True, slots=True)
class Address(api.Address):
    steps: tuple[AddressStep, ...] = field()
    """From the top level down to this directive."""

    @property
    def text(self) -> str:
        return json.dumps(
            [[s.name, s.key, s.occurrence] for s in self.steps], ensure_ascii=False, separators=(",", ":")
        )

    @property
    def parent(self) -> Address | None:
        return Address(self.steps[:-1]) if len(self.steps) > 1 else None

    def __str__(self) -> str:
        return " > ".join(
            s.name
            + ("" if s.key is None else " " + json.dumps(s.key, ensure_ascii=False))
            + ("" if s.occurrence == 0 else f" #{s.occurrence}")
            for s in self.steps
        )


@final
class Directive(api.Directive):
    __match_args__ = ("name", "values", "block")
    __slots__ = ("_block", "_name", "_origin", "_parent", "_unreadable", "_values", "_written")

    def __init__(self, expansion: DirectiveExpansion, parent: Directive | None, inner: list[Directive]) -> None:
        """Made by ``render`` only (``rendered_block``), from one directive copy of the graph's expansion. ``inner``
        becomes its block's directives: ``rendered_block`` fills it with them, each with this one as its parent."""
        self._name = expansion.written.name
        self._values = expansion.values
        self._parent = parent
        self._origin = expansion.origin
        self._written = expansion.written
        self._block = None if expansion.block is None else RenderedBlock(inner)
        self._unreadable = expansion.unreadable

    def __repr__(self) -> str:
        return f"Directive({self._name!r}, {[a.text for a in self._values]!r})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def values(self) -> tuple[ExpandedValue, ...]:
        return self._values

    @property
    def block(self) -> RenderedBlock | None:
        return self._block

    @property
    def unreadable(self) -> tuple[UnreadableExpansion, ...]:
        return self._unreadable

    @property
    def parent(self) -> Directive | None:
        return self._parent

    @property
    def origin(self) -> DirectiveOrigin:
        return self._origin

    @property
    def written(self) -> WrittenDirective:
        # The user doc is the schema's, inherited from the generated Protocol (closes kno-uji).
        return self._written

    def closest(self, predicate: Callable[[Directive], bool], /) -> Directive | None:
        directive: Directive | None = self
        while directive is not None and not predicate(directive):
            directive = directive.parent
        return directive

    def error(self, message: str, *, code: str) -> DiagnosticError:
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.place, self._origin.via))


@final
class RenderedBlock(BlockBase[Directive, Directive], api.RenderedBlock):
    __slots__ = ("_items",)

    def __init__(self, items: Sequence[Directive]) -> None:
        """Made by ``render`` only; ``rendered_block`` fills ``items`` before ``render`` returns, and nothing changes
        them after."""
        self._items = items

    def _members(self) -> Sequence[Directive]:
        return self._items

    def _directive(self, item: Directive, /) -> Directive:
        return item

    def _name(self, directive: Directive, /) -> str:
        return directive.name

    def _inner(self, item: Directive, /) -> RenderedBlock | None:
        return item.block


def rendered_block(expansions: Iterable[DirectiveExpansion]) -> RenderedBlock:
    """The rendered top level of an expansion's top-level directives. Each directive is made with its parent and an
    empty list, its block's directives, which the loop fills later. A loop, not a recursion: the tree may be
    MAX_EXPANDED_NESTING deep (spec 2.5)."""
    top: list[Directive] = []
    stack: list[tuple[Iterable[DirectiveExpansion], Directive | None, list[Directive]]] = [(expansions, None, top)]
    while stack:
        items, parent, into = stack.pop()
        for expansion in items:
            inner: list[Directive] = []
            directive = Directive(expansion, parent, inner)
            into.append(directive)
            if expansion.block is not None:
                stack.append((expansion.block, directive, inner))
    return RenderedBlock(top)
