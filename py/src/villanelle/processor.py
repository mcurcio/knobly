"""Loading and change lists (R15 tier 2). A ``Processor`` is made once with its document source, extensions and key
rule (as ``jinja2.Environment`` is made with its loader and extensions); ``load`` reads a root file and everything it
splices in, synchronously; ``diff`` compares two loads of the same processor by address."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias, final

from villanelle.diagnostics import DiagnosticError
from villanelle.directives import Address, Argument, Directive, KeyRule, Unreadable
from villanelle.graph import DocumentGraph
from villanelle.origin import DirectiveOrigin
from villanelle.report import LocatedDiagnostic
from villanelle.source import DocumentSource


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

    @property
    def body(self) -> tuple[Directive, ...]:
        """The top-level readable directives, expanded."""
        raise NotImplementedError("Loaded.body")

    @property
    def unreadable(self) -> tuple[Unreadable, ...]:
        """Top-level statements that could not be read (R6: their siblings stay)."""
        raise NotImplementedError("Loaded.unreadable")

    @property
    def origin(self) -> DirectiveOrigin:
        """The root file at 0:0, zero width: where a problem with no line of its own is placed."""
        raise NotImplementedError("Loaded.origin")

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """Every file's syntax diagnostics (files in first-read order), then expansion problems in expansion order."""
        raise NotImplementedError("Loaded.diagnostics")

    @property
    def graph(self) -> DocumentGraph:
        raise NotImplementedError("Loaded.graph")

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error for a problem of the whole file, such as a required top-level directive left out."""
        raise NotImplementedError("Loaded.error")


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
        raise NotImplementedError("Processor")

    def load(self, path: str, *, variables: Mapping[str, str] | None = None) -> Loaded:
        """Read the root file at ``path`` (as the source names it) and everything it splices in. Never raises for
        anything in the text. Raises DiagnosticError E3004 placed at the root file when the source cannot read it;
        ValueError for a handed-in variable whose name is not letters, digits and ``_`` or whose text is not one or more
        values; whatever the key rule raises. A handed-in variable wins over every ``set`` of its name (L3)."""
        raise NotImplementedError("Processor.load")

    def diff(self, before: Loaded, after: Loaded, /) -> list[Change]:
        """What differs, by address: removed and unknown in ``before``'s walk order, then added and changed in
        ``after``'s. A directive missing from ``after`` is Unknown, not Removed, when its block in ``after`` (or the top
        level) holds an unreadable statement. Raises ValueError when either load came from another processor."""
        raise NotImplementedError("Processor.diff")
