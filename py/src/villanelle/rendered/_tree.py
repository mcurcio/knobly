"""The rendered tree's nodes (spec 7; R15 tier 2): what a program walks after ``render``. Model: the standard ``ast``
module. Nodes are read-only objects with ``__match_args__``, read with ``match``; ``walk()`` iterates a subtree as
``ast.walk`` does (here in written order); every node carries where it came from. Directives and values are expanded
(variables replaced, snippets and extension files spliced in). A directive is built on its directive expansion's own
objects (vil-umh.8): its ``values`` are the low level's expanded values and its ``unreadable`` the low level's
unreadable expansions, the same objects; this layer adds ``name``, ``parent``, ``walk``, ``closest``, the address and
``error``. It names low-level handles, never the other way round."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import TypeAlias, final

from villanelle.errors import DiagnosticError
from villanelle.origin import DirectiveOrigin
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.written import DirectiveExpansion, ExpandedValue, UnreadableExpansion, WrittenDirective


@dataclass(frozen=True, slots=True)
class AddressStep:
    name: str
    key: str | None
    """What the key rule returned for this directive; None when it returned nothing or there is no rule."""
    occurrence: int
    """0-based, among earlier siblings with the same name and key."""


@final
@dataclass(frozen=True, slots=True)
class Address:
    """Where a directive lands in the expanded tree: its identity across loads. Hashable; unique within one load. A file
    included at two places, or a snippet used twice, lands at two addresses (R21: "Allowed, per place")."""

    steps: tuple[AddressStep, ...]
    """From the top level down to this directive."""

    @property
    def text(self) -> str:
        """The canonical string, the same bytes as TypeScript: ``json.dumps([[s.name, s.key, s.occurrence] for s in
        steps], ensure_ascii=False, separators=(",", ":"))``."""
        return json.dumps(
            [[s.name, s.key, s.occurrence] for s in self.steps], ensure_ascii=False, separators=(",", ":")
        )

    @property
    def parent(self) -> Address | None:
        """The enclosing directive's address; None at the top level."""
        return Address(self.steps[:-1]) if len(self.steps) > 1 else None

    def __str__(self) -> str:
        """For people: ``graph > node "leds" > max_count`` (slices.md "Address")."""
        return " > ".join(
            s.name
            + ("" if s.key is None else " " + json.dumps(s.key, ensure_ascii=False))
            + ("" if s.occurrence == 0 else f" #{s.occurrence}")
            for s in self.steps
        )


@final
class Directive:
    """One directive after expansion. ``@set``, ``@snippet``, ``@use`` and extension lines never appear: their results
    do, in their place. Match it: ``case vl.Directive("node", [kind, node_id, *rest], block):``. Its address is
    ``rendered.addresses(key=...)[directive]`` (D4)."""

    __match_args__ = ("name", "values", "block")
    __slots__ = ("_block", "_name", "_origin", "_parent", "_unreadable", "_values", "_written")

    def __init__(self, expansion: DirectiveExpansion, parent: Directive | None) -> None:
        """Made by ``render`` only, from one directive copy of the graph's expansion: its block's directives are made
        with it, each with this one as its parent."""
        self._name = expansion.written.name
        self._values = expansion.values
        self._parent = parent
        self._origin = expansion.origin
        self._written = expansion.written
        self._block = None if expansion.block is None else tuple(Directive(child, self) for child in expansion.block)
        self._unreadable = expansion.unreadable

    def __repr__(self) -> str:
        return f"Directive({self._name!r}, {[a.text for a in self._values]!r})"

    @property
    def name(self) -> str:
        return self._name

    @property
    def values(self) -> tuple[ExpandedValue, ...]:
        """Its values, expanded, with their links: its directive expansion's own objects."""
        return self._values

    @property
    def block(self) -> tuple[Directive, ...] | None:
        """The block's readable directives; None when written without a block."""
        return self._block

    @property
    def unreadable(self) -> tuple[UnreadableExpansion, ...]:
        """The block's statements that could not be read (its directive expansion's own objects); empty when there
        is no block or all were read."""
        return self._unreadable

    @property
    def parent(self) -> Directive | None:
        """The enclosing directive; None at the top level."""
        return self._parent

    @property
    def origin(self) -> DirectiveOrigin:
        """Where its name was written, and the uses and includes that brought it here."""
        return self._origin

    @property
    def written(self) -> WrittenDirective:
        """The written directive this is a copy of (closes vil-uji): the same handle for every copy of one line."""
        return self._written

    def walk(self, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]:
        """Every directive in its block, at any depth (not itself), depth-first in written order. ``descend``, when
        given, is asked of each directive yielded; False passes over its block. Stop early with ``break``."""
        return walk_block(self._block or (), descend)

    def closest(self, predicate: Callable[[Directive], bool], /) -> Directive | None:
        """This directive or its nearest enclosing one that matches, as the DOM's ``Element.closest``."""
        directive: Directive | None = self
        while directive is not None and not predicate(directive):
            directive = directive.parent
        return directive

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error placed on this directive's name. Raises ValueError when ``code`` has no "/"."""
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.place, self._origin.via))


KeyRule: TypeAlias = Callable[[Directive], "str | None"]
"""The program's rule for naming a directive among its siblings, so it keeps its address when lines move (D5: it
takes the rendered directive). Called once per directive, parents before children, in walk order, by
``Rendered.addresses`` and ``Rendered.diff``; what it raises propagates. rasl:
``lambda d: d.values[1].text if d.name == "node" and d.parent and d.parent.name == "graph" else None``."""


def walk_block(block: Sequence[Directive], descend: Callable[[Directive], bool] | None) -> Iterator[Directive]:
    """The one home of the walk: every directive under ``block``, depth-first in written order. Private to the
    rendered layer."""
    stack: list[Iterator[Directive]] = [iter(block)]
    while stack:
        directive = next(stack[-1], None)
        if directive is None:
            stack.pop()
            continue
        yield directive
        inner = directive.block
        if inner and (descend is None or descend(directive)):
            stack.append(iter(inner))
