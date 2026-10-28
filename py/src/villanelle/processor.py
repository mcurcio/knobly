"""Loading and change lists (R15 tier 2). A ``Processor`` is made once with its document source, extensions and key
rule (as ``jinja2.Environment`` is made with its loader and extensions); ``load`` reads a root file and everything it
splices in, synchronously; ``diff`` compares two loads of the same processor by address."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, TypeAlias, final

from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.directives import Address, Argument, Directive, KeyRule, Unreadable
from villanelle.graph import DocumentGraph, DocumentNode
from villanelle.origin import DirectiveOrigin, Place
from villanelle.report import LocatedDiagnostic, check_program_code
from villanelle.source import DocumentSource, LoadContext
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax._recovery import message_of
from villanelle.syntax.parse import parse


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
class Loaded:
    """What one load produced. Problems are diagnostics; the root file owns the top level, as a directive its block."""

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
        """Made by ``Processor.load`` only."""
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
        """Every file's syntax diagnostics (files in first-read order), then expansion problems in expansion order."""
        return self._diagnostics

    @property
    def graph(self) -> DocumentGraph:
        return self._graph

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
"""One difference between two loads. An added, removed or unknown directive is listed alone, never with the directives
inside it (``walk`` it); a changed one's block is compared at its own addresses."""


@final
class Processor:
    """Made once with the document source, extensions and key rule; loads and compares."""

    def __init__(
        self,
        *,
        source: DocumentSource,
        extensions: Sequence[Extension] = (),
        key: KeyRule | None = None,
    ) -> None:
        """Raises ValueError for an extension named ``set``, ``snippet`` or ``use``, or two extensions with one name
        (S2-01: rule 1 reserves those names, and one directive name has one owner)."""
        self._source = source
        self._extensions: dict[str, Extension] = {}
        for extension in extensions:
            name = extension.directive
            if name in _RESERVED or name in self._extensions:
                raise ValueError(f"extension directive name taken: {name!r}")
            self._extensions[name] = extension
        self._key = key

    def load(self, path: str, *, variables: Mapping[str, str] | None = None) -> Loaded:
        """Read the root file at ``path`` (as the source names it) and everything it splices in. ``path`` is resolved
        through the source first, as an included file's spec is, so the root has one path in the graph. Never raises
        for anything in the text. Raises DiagnosticError E3004 placed at the root file when the source cannot read it;
        ValueError for a handed-in variable whose name is not letters, digits and ``_`` or whose text is not one or more
        values; whatever the key rule raises. A handed-in variable wins over every ``set`` of its name (L3)."""
        # Imported here: the expander builds ExtensionUse values, so it imports this module.
        from villanelle._expand import At, Container, Expander, Scope, Stopped, Text, read_handed

        handed = read_handed(variables or {})
        path, source = self._read_root(path)
        start = SourceSpan(_START, _START)
        root = DocumentNode(path, source, parse(source))
        expander = Expander(
            source=self._source, extensions=self._extensions, handed=handed, key=self._key, nodes={path: root}
        )
        top = Container([], [], None)
        with contextlib.suppress(Stopped):  # E5008 is recorded; what was read so far stays.
            expander.statements(At(Text(root.syntax, path), Scope(None), (), (path,)), root.syntax.root, top)
        for directive in expander.directives:
            directive._freeze()
        syntax = [
            LocatedDiagnostic(d.code, d.message, Place(node.resolved_path, d.span), ())
            for node in expander.nodes.values()
            for d in node.syntax.diagnostics
        ]
        graph = DocumentGraph(root, MappingProxyType(dict(expander.nodes)), tuple(expander.edges))
        return Loaded(
            self,
            tuple(top.body),
            tuple(top.unreadable),
            DirectiveOrigin(Place(path, start), ()),
            (*syntax, *expander.diagnostics),
            graph,
        )

    def _read_root(self, path: str) -> tuple[str, str]:
        """The root file's resolved path and text. The root is resolved through the source as an included file is
        (F1-04), so one file has one path in the graph however the caller spells it. Raises DiagnosticError E3004
        at ``path`` when the source fails, finds no file, or finds more than one."""
        code = DiagnosticCode.INCLUDE_RESOLVER_FAILED

        def fail(reason: object) -> DiagnosticError:
            message = f"{message_of(code)}: {path}: {reason}"
            return DiagnosticError(LocatedDiagnostic(code, message, Place(path, SourceSpan(_START, _START)), ()))

        try:
            paths = self._source.resolve(path, LoadContext(""))
        except Exception as error:
            raise fail(error) from error
        if len(paths) != 1:
            raise fail("no such file" if not paths else f"names {len(paths)} files")
        try:
            return paths[0], self._source.read(paths[0])
        except Exception as error:
            raise fail(error) from error

    def diff(self, before: Loaded, after: Loaded, /) -> list[Change]:
        """What differs, by address: removed and unknown in ``before``'s walk order, then added and changed in
        ``after``'s. A directive missing from ``after`` is Unknown, not Removed, when its block in ``after`` (or the top
        level) holds an unreadable statement. Raises ValueError when either load came from another processor."""
        if before._processor is not self or after._processor is not self:
            raise ValueError("diff compares two loads of this processor")
        gone: list[Change] = []
        came: list[Change] = []
        _compare_before(before.body, after.body, bool(after.unreadable), gone)
        _compare_after(after.body, before.body, came)
        return gone + came


_START = SourcePosition(0, 0, 0)
_RESERVED = frozenset({"set", "snippet", "use"})
"""The names reserved at a statement's start besides each registered extension's (rule 1)."""


def _compare_before(
    before: Sequence[Directive], after: Sequence[Directive], incomplete: bool, into: list[Change]
) -> None:
    """Removed and unknown, in ``before``'s walk order. ``incomplete``: ``after``'s container holds an unreadable."""
    by_address = {d.address: d for d in after}
    for directive in before:
        match = by_address.get(directive.address)
        if match is None:
            into.append(Unknown(directive.address, directive) if incomplete else Removed(directive.address, directive))
        else:
            _compare_before(directive.body or (), match.body or (), bool(match.unreadable), into)


def _compare_after(after: Sequence[Directive], before: Sequence[Directive], into: list[Change]) -> None:
    """Added and changed, in ``after``'s walk order."""
    by_address = {d.address: d for d in before}
    for directive in after:
        match = by_address.get(directive.address)
        if match is None:
            into.append(Added(directive.address, directive))
            continue
        if _changed(match, directive):
            into.append(Changed(directive.address, match, directive))
        _compare_after(directive.body or (), match.body or (), into)


def _changed(before: Directive, after: Directive) -> bool:
    """Its own values' canonical texts, or whether it has a block, differ (slices.md §1.5)."""
    texts = [a.text for a in before.args] != [a.text for a in after.args]
    return texts or (before.body is None) != (after.body is None)
