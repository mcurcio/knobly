"""The file graph of one load: every file read, each read and parsed once however many places splice it in (R21),
and one edge per place an extension directive spliced files. Read-only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from villanelle.origin import DirectiveOrigin
from villanelle.syntax.cst import Syntax


@dataclass(frozen=True, slots=True)
class DocumentNode:
    """One file read during a load."""

    resolved_path: str
    source: str
    """The text as read."""
    syntax: Syntax
    """Its tier-1 parse: tokens, lossless tree and this file's syntax diagnostics."""


@dataclass(frozen=True, slots=True)
class DocumentEdge:
    """One place an extension directive spliced files in (a file included at two places has two edges)."""

    directive: str
    """The extension's directive name: ``"include"``."""
    origin: DirectiveOrigin
    specs: tuple[str, ...]
    """The specs the extension gave, in its order."""
    targets: tuple[str, ...]
    """Resolved paths in splice order; empty when it failed (a diagnostic says why)."""


@dataclass(frozen=True, slots=True)
class DocumentGraph:
    root: DocumentNode
    nodes: Mapping[str, DocumentNode]
    """Every file read, by resolved path, the root included, in first-read order."""
    edges: tuple[DocumentEdge, ...]
    """Every extension place, in expansion order."""
