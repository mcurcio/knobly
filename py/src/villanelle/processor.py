"""Loading, rendering and change lists (R15 tier 2; round 12 design.md §6). A ``Processor`` is made once with its
document source and extensions (as ``jinja2.Environment`` is made with its loader and extensions); ``load`` reads a
root file and everything it includes into a document graph (the files as written), synchronously; ``render`` builds
the rendered tree from the graph's current texts; ``diff`` compares two renders by address under a key rule."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, TypeAlias, final

from villanelle.diagnostics import DiagnosticError
from villanelle.directives import Address, AddressStep, Argument, Directive, KeyRule, Unreadable
from villanelle.origin import DirectiveOrigin
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.source import DocumentSource
from villanelle.written.model import DocumentGraph


@dataclass(frozen=True, slots=True)
class ExtensionUse:
    """One use of an extension directive, as the extension sees it."""

    args: tuple[Argument, ...]
    """The directive's values, expanded."""
    origin: DirectiveOrigin


class Extension(Protocol):
    """An extension (R20): owns one directive name and turns each use of it into specs of files to splice in its
    place. Pure: the load resolves and reads the specs through its document source, parses each file once, applies
    the use's block of ``set`` lines, and enforces depth, cycles and limits. While registered, the name is reserved at
    a line's start, as ``set``, ``snippet`` and ``use`` are."""

    @property
    def directive(self) -> str: ...

    def specs(self, use: ExtensionUse, /) -> Sequence[str]:
        """The specs for one use, in splice order. Raise DiagnosticError for a located failure; any other exception
        becomes E3006 at the directive."""
        ...


@final
class Rendered:
    """The rendered tree of one graph (PR 3's ``Loaded``, renamed). Problems are diagnostics; the root file owns the
    top level, as a directive its block."""

    __slots__ = ("_body", "_diagnostics", "_graph", "_origin", "_processor", "_unreadable")

    def __init__(
        self,
        processor: Processor,
        body: tuple[Directive, ...],
        unreadable: tuple[Unreadable, ...],
        origin: DirectiveOrigin,
        diagnostics: tuple[LocatedDiagnostic, ...],
        graph: DocumentGraph,
    ) -> None:
        """Made by ``Processor.render`` only."""
        self._processor = processor
        self._body = body
        self._unreadable = unreadable
        self._origin = origin
        self._diagnostics = diagnostics
        self._graph = graph

    @property
    def body(self) -> tuple[Directive, ...]:
        """The top-level readable directives, expanded."""
        return self._body

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """Top-level statements that could not be read (R6: their siblings stay)."""
        return self._unreadable

    @property
    def origin(self) -> DirectiveOrigin:
        """The root file at 0:0, zero width: where a problem with no line of its own is placed."""
        return self._origin

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """PR 3's content and order (D11): every file's syntax diagnostics (documents in order), then the walk's
        problems in walk order."""
        return self._diagnostics

    @property
    def graph(self) -> DocumentGraph:
        """The graph it was rendered from."""
        return self._graph

    def addresses(self, *, key: KeyRule | None = None) -> Mapping[Directive, Address]:
        """Every directive's address under ``key``, in walk order (the mapping's order). The key rule is called once
        per directive, parents before children; what it raises propagates. The one home of the address rule (D4);
        ``Processor.diff`` uses it. Without a key rule, a directive is named by its position among same-name
        siblings."""
        out: dict[Directive, Address] = {}

        def name(container: Sequence[Directive], parent: tuple[AddressStep, ...]) -> None:
            occurrences: dict[tuple[str, str | None], int] = {}
            for directive in container:
                key_text = None if key is None else key(directive)
                slot = (directive.name, key_text)
                occurrence = occurrences.get(slot, 0)
                occurrences[slot] = occurrence + 1
                steps = (*parent, AddressStep(directive.name, key_text, occurrence))
                out[directive] = Address(steps)
                if directive.body is not None:
                    name(directive.body, steps)

        name(self._body, ())
        return MappingProxyType(out)

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error for a problem of the whole file, such as a required top-level directive left out."""
        check_program_code(code)
        return DiagnosticError(LocatedDiagnostic(code, message, self._origin.written, self._origin.via))


@final
@dataclass(frozen=True, slots=True)
class Added:
    address: Address
    after: Directive


@final
@dataclass(frozen=True, slots=True)
class Removed:
    address: Address
    before: Directive


@final
@dataclass(frozen=True, slots=True)
class Changed:
    """Same address; its own values (by text) or whether it has a block differ."""

    address: Address
    before: Directive
    after: Directive


@final
@dataclass(frozen=True, slots=True)
class Unknown:
    """It was in ``before``; in ``after`` its block holds an unreadable statement that may be it."""

    address: Address
    before: Directive


Change: TypeAlias = Added | Removed | Changed | Unknown
"""One difference between two renders. An added, removed or unknown directive is listed alone, never with the directives
inside it (``walk`` it); a changed one's block is compared at its own addresses."""


@final
class Processor:
    """Made once with the document source and extensions; loads, reads, renders and compares."""

    def __init__(self, *, source: DocumentSource, extensions: Sequence[Extension] = ()) -> None:
        """Raises ValueError for an extension named ``set``, ``snippet`` or ``use``, or two extensions with one name
        (S2-01: rule 1 reserves those names, and one directive name has one owner)."""
        from villanelle.written import _bind

        self._source = source
        self._extensions: dict[str, Extension] = {}
        for extension in extensions:
            name = extension.directive
            if name in _bind.RESERVED or name in self._extensions:
                raise ValueError(f"extension directive name taken: {name!r}")
            self._extensions[name] = extension

    def load(self, path: str, *, variables: Mapping[str, str] | None = None) -> DocumentGraph:
        """Read the root file at ``path`` (resolved through the source, as an included file's spec is, so the root
        has one path in the graph) and every file its include lines name, once each (R21), repeating until nothing
        new is named. Never raises for anything in the text. Raises ReadError (a DiagnosticError, E3004 placed at
        the root path) when the source cannot resolve or read the root; ValueError for a handed-in variable whose
        name is not letters, digits and ``_`` or whose text is not one or more values. A handed-in variable wins
        over every ``set`` of its name (L3)."""
        from villanelle.written import _read

        return _read.load_graph(self._source, self._extensions, path, variables or {}, self)

    def read(self, graph: DocumentGraph, /) -> list[str]:
        """Resolve and read what ``graph.unread()`` names, repeating until nothing new is named; keeps every text
        and every kept rejection (D12). Returns the resolved paths read, in read order. Raises ValueError for a
        graph another processor loaded."""
        from villanelle.written import _read

        self._check(graph)
        return _read.read_unread(graph, self._source)

    def render(self, graph: DocumentGraph, /) -> Rendered:
        """The rendered tree of the graph's current texts and handed-in values. Pure: reads no file; an unread
        include copy renders as nothing (its edge is in ``graph.unread()``). Raises ValueError for a graph another
        processor loaded."""
        from villanelle import _render

        self._check(graph)
        return _render.render(graph, self)

    def diff(self, before: Rendered, after: Rendered, /, *, key: KeyRule | None = None) -> list[Change]:
        """What differs between two renders of this processor's graphs, by address under ``key`` (D4): removed and
        unknown in ``before``'s walk order, then added and changed in ``after``'s. A directive missing from ``after``
        is Unknown, not Removed, when its block in ``after`` (or the top level) holds an unreadable statement.
        Raises ValueError when either render came from another processor; whatever the key rule raises."""
        if before._processor is not self or after._processor is not self:
            raise ValueError("diff compares two renders of this processor")
        old = before.addresses(key=key)
        new = after.addresses(key=key)
        gone: list[Change] = []
        came: list[Change] = []
        _compare_before(before.body, after.body, bool(after.unreadable), old, new, gone)
        _compare_after(after.body, before.body, new, old, came)
        return gone + came

    def _check(self, graph: DocumentGraph) -> None:
        if not isinstance(graph, DocumentGraph) or graph._owner is not self:
            raise ValueError("this processor takes only graphs it loaded")


_Addresses: TypeAlias = Mapping[Directive, Address]


def _compare_before(
    before: Sequence[Directive],
    after: Sequence[Directive],
    incomplete: bool,
    old: _Addresses,
    new: _Addresses,
    into: list[Change],
) -> None:
    """Removed and unknown, in ``before``'s walk order. ``incomplete``: ``after``'s container holds an unreadable."""
    by_address = {new[d]: d for d in after}
    for directive in before:
        address = old[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Unknown(address, directive) if incomplete else Removed(address, directive))
        else:
            _compare_before(directive.body or (), match.body or (), bool(match.unreadable), old, new, into)


def _compare_after(
    after: Sequence[Directive], before: Sequence[Directive], new: _Addresses, old: _Addresses, into: list[Change]
) -> None:
    """Added and changed, in ``after``'s walk order."""
    by_address = {old[d]: d for d in before}
    for directive in after:
        address = new[directive]
        match = by_address.get(address)
        if match is None:
            into.append(Added(address, directive))
            continue
        if _changed(match, directive):
            into.append(Changed(address, match, directive))
        _compare_after(directive.body or (), match.body or (), new, old, into)


def _changed(before: Directive, after: Directive) -> bool:
    """Its own values' canonical texts, or whether it has a block, differ (slices.md §1.5)."""
    texts = [a.text for a in before.args] != [a.text for a in after.args]
    return texts or (before.body is None) != (after.body is None)
