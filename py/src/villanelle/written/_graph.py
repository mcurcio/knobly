"""The document graph's state (round 12 slices.md 2.7, 2.8): the files, the handed-in values and the read ledger.
Everything else (copies, edges, variables, resolutions, diagnostics) is derived from them by ``_bind.bind``, cached
per graph version; every edit, ``set_handed`` and read bumps the version, and everything holds with the cache empty.
Private; a port of ts/src/written/graph.ts (and S2's ``setHanded``)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from villanelle.report import LocatedDiagnostic
from villanelle.written import _bind, _document
from villanelle.written.errors import BadTextError
from villanelle.written.model import Document, DocumentGraph, Variable

if TYPE_CHECKING:
    from villanelle.processor import Extension

_RENDER_CODES = frozenset({"E5001", "E5003", "E5004", "E5008"})
"""The codes ``render`` owns besides E4xxx: ``diagnostics()`` leaves them out (D11)."""


def init(graph: DocumentGraph, extensions: Mapping[str, Extension], handed: Mapping[str, str], owner: object) -> None:
    graph._extensions = extensions
    graph._extension_names = frozenset(extensions)
    graph._documents = {}
    graph._root = None
    graph._handed_texts = {}
    graph._handed_values = {}
    graph._handed_variables = {}
    graph._resolutions = {}
    graph._failed = {}
    graph._version = 0
    graph._cache = None
    graph._owner = owner
    for name, text in handed.items():
        graph._handed_values[name] = _bind.read_handed(name, text)
        graph._handed_texts[name] = text
        graph._handed_variables[name] = Variable("handed", name=name, graph=graph)


class _Ledger:
    """The graph's read ledger, as the binding asks it."""

    __slots__ = ("_graph",)

    def __init__(self, graph: DocumentGraph) -> None:
        self._graph = graph

    def resolved(self, parent_path: str, spec: str, /) -> tuple[str, ...] | Exception | None:
        return self._graph._resolutions.get((parent_path, spec))

    def read(self, resolved_path: str, /) -> Document | Exception | None:
        return self._graph._documents.get(resolved_path) or self._graph._failed.get(resolved_path)


def binding(graph: DocumentGraph) -> _bind.Binding:
    """The current derivation, made again after any change."""
    cache = graph._cache
    if cache is not None and cache[0] == graph._version:
        return cache[1]
    handed = {
        name: _bind.HandedInput(graph._handed_variables[name], graph._handed_values[name])
        for name in graph._handed_texts
    }
    made = _bind.bind(graph.root, graph._extensions, handed, _Ledger(graph))
    graph._cache = (graph._version, made)
    return made


def changed(graph: DocumentGraph) -> None:
    graph._version += 1


def syntax_diagnostics(graph: DocumentGraph) -> list[LocatedDiagnostic]:
    """Each document's syntax diagnostics, documents in order, located."""
    return [
        LocatedDiagnostic(d.code, d.message, _document.place_of_span(doc, d.span), ())
        for doc in graph._documents.values()
        for d in doc._syntax.diagnostics
    ]


def diagnostics(graph: DocumentGraph) -> tuple[LocatedDiagnostic, ...]:
    found = [
        d for d in binding(graph).diagnostics if not str(d.code).startswith("E4") and str(d.code) not in _RENDER_CODES
    ]
    return (*syntax_diagnostics(graph), *found)


def record_resolved(graph: DocumentGraph, parent_path: str, spec: str, paths: tuple[str, ...] | Exception) -> None:
    graph._resolutions[(parent_path, spec)] = paths
    changed(graph)


def record_read(graph: DocumentGraph, resolved_path: str, text: str | Exception) -> Document | None:
    """Record one read: the document made from its text (the root first), or the failure."""
    changed(graph)
    if isinstance(text, Exception):
        graph._failed[resolved_path] = text
        return None
    doc = Document(graph, resolved_path, text)
    graph._documents[resolved_path] = doc
    if graph._root is None:
        graph._root = doc
    return doc


def set_handed(graph: DocumentGraph, name: str, text: str | None) -> None:
    """Add, change or remove one handed-in value (D28: one Variable per name for the graph's life). The text is
    checked as a values text (2.3), then read as a load reads it; whatever that refuses is a BadTextError located in
    the given text."""
    if not _bind.VARIABLE_NAME.fullmatch(name):
        raise ValueError(f"handed-in variable name must be letters, digits and _: {name!r}")
    if text is None:
        if name in graph._handed_texts:
            del graph._handed_texts[name]
            del graph._handed_values[name]
            changed(graph)
        return
    problems = _document.handed_text_problems(text)
    if not problems:
        fault = _bind.handed_value_problem(text)
        if fault is not None:
            problems = (_document.wrapped_diagnostic(text, "x ", fault),)
    if problems:
        raise BadTextError(f"not a handed-in value: {', '.join(d.code for d in problems)}", problems)
    values = _bind.read_handed(name, text)
    graph._handed_texts[name] = text
    graph._handed_values[name] = values
    if name not in graph._handed_variables:
        graph._handed_variables[name] = Variable("handed", name=name, graph=graph)
    changed(graph)
