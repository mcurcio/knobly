"""The document graph's state (round 12 slices.md 2.7, 2.8): the files, the overrides and the read ledger.
Everything else (copies, edges, variables, resolutions, diagnostics) is derived from them by ``_bind.bind``, cached
per graph version; every edit, ``set_override`` and read bumps the version, and everything holds with the cache empty.
Also the one check of an override (spec 6.3), used by ``load`` and ``set_override`` alike, and the graph's one
diagnostics list. Private; a port of ts/src/written/graph.ts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from knobly._api.errors import BadTextError
from knobly._api.shared import ConfigText
from knobly._report import LocatedDiagnostic
from knobly._text import require_text
from knobly.written import _bind, _document, _names
from knobly.written._model import Document, DocumentGraph, OverrideVariable

if TYPE_CHECKING:
    from knobly._api.io import DocumentSource
    from knobly._api.written import Extension


def init(
    graph: DocumentGraph,
    source: DocumentSource,
    extensions: Mapping[str, Extension],
    overrides: Mapping[str, ConfigText],
) -> None:
    graph._source = source
    graph._extensions = extensions
    graph._extension_names = frozenset(extensions)
    graph._documents = {}
    graph._root = None
    graph._override_texts = {}
    graph._override_values = {}
    graph._override_variables = {}
    graph._resolutions = {}
    graph._failed = {}
    graph._version = 0
    graph._cache = None
    for name, text in overrides.items():
        values = check_override(name, text, member="load", parameter=f'overrides["{name}"]')
        graph._override_values[name] = values
        graph._override_texts[name] = text
        graph._override_variables[name] = OverrideVariable(name, graph)


def check_override(name: object, text: object, *, member: str, parameter: str) -> _bind.OverrideValues:
    """The one check of an override (spec 6.3; ``load`` and ``set_override`` both call it): the name (the one
    variable-name check: TypeError when not a str, ValueError when not letters, digits and ``_``), the text's type
    (TypeError naming ``parameter``), then the text with the ``valuesText`` entry rule: a BadTextError located in the
    text for its first error, E2001 at a ``$name``, or at 0:0 for no value. Returns its values."""
    name = _names.variable_name(name, member=member)
    given = require_text(text, member=member, parameter=parameter)
    problems = _document.override_text_problems(given)
    if problems:
        raise BadTextError(problems)
    return _bind.override_values(name, given)


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
    overrides = {
        name: _bind.OverrideInput(graph._override_variables[name], graph._override_values[name])
        for name in graph._override_texts
    }
    made = _bind.bind(graph.root, graph._extensions, overrides, _Ledger(graph))
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
    """The one list (spec 6.3): each document's syntax diagnostics, then everything the binding found, in walk
    order. The expansion and the render show it unchanged."""
    return (*syntax_diagnostics(graph), *binding(graph).diagnostics)


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


def set_override(graph: DocumentGraph, name: str, text: ConfigText | None) -> None:
    """Add, change or remove one override (D28: one OverrideVariable per name for the graph's life), after the one
    check."""
    if text is None:
        _names.variable_name(name, member="set_override")
        if name in graph._override_texts:
            del graph._override_texts[name]
            del graph._override_values[name]
            changed(graph)
        return
    values = check_override(name, text, member="set_override", parameter="text")
    graph._override_texts[name] = text
    graph._override_values[name] = values
    if name not in graph._override_variables:
        graph._override_variables[name] = OverrideVariable(name, graph)
    changed(graph)
