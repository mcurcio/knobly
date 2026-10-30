"""The read loop (round 12 slices.md S1; D12, D26, D-S1-3): read the root, then whatever the binding names as unread,
until nothing new is named. It takes the first unread edge in walk order each time, so files are read in the order
PR 3's expansion read them (depth first), each path once (R21), and a rejection is kept, never retried. Private; a
port of ts/src/written/read.ts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from knobly._api.errors import ReadError
from knobly._api.io import DocumentSource, LoadContext
from knobly._api.shared import ConfigText
from knobly._text import port_text, port_texts
from knobly.written import _bind, _graph
from knobly.written._model import DocumentGraph

if TYPE_CHECKING:
    from knobly._api.written import Extension


def load_graph(
    source: DocumentSource, extensions: Mapping[str, Extension], path: str, overrides: Mapping[str, ConfigText]
) -> DocumentGraph:
    """Read the root file at ``path`` (resolved through the source, as an included file's spec is, F1-04) and every
    file its include lines name. Checks the overrides first (``_graph.check_override``); raises ReadError (``paths``:
    the root path) when the source fails, finds no file, finds more than one, or returns anything but a tuple of
    str (``resolve``) or a str (``read``)."""
    graph = DocumentGraph(source, extensions, overrides)

    def fail(reason: object) -> ReadError:
        return ReadError(f"cannot read the root file {path}: {reason}", [path])

    try:
        paths = port_texts(source.resolve(path, LoadContext("")), port="resolve()")
    except Exception as error:
        raise fail(error) from error
    if len(paths) != 1:
        raise fail("no such file" if not paths else f"it names {len(paths)} files")
    try:
        text = port_text(source.read(paths[0]), port="read()")
    except Exception as error:
        raise fail(error) from error
    _graph.record_read(graph, paths[0], text)
    read_unread(graph)
    return graph


def read_unread(graph: DocumentGraph) -> list[str]:
    """Resolve and read what ``graph.unread()`` names through the graph's source, until nothing new is named. Returns
    the paths read, in read order. A source's result that is not a tuple of str (``resolve``) or a str (``read``) is
    its failure, as a raise is: E3004 at the extension line."""
    source = graph._source
    read: list[str] = []
    while True:
        binding = _graph.binding(graph)
        if not binding.unread:
            return read
        need = binding.need_of(binding.unread[0])
        if isinstance(need, _bind.ResolveNeed):
            for spec in need.specs:
                if (need.parent_path, spec) in graph._resolutions:
                    continue
                paths: tuple[str, ...] | Exception
                try:
                    paths = port_texts(source.resolve(spec, LoadContext(need.parent_path)), port="resolve()")
                except Exception as error:
                    paths = error
                _graph.record_resolved(graph, need.parent_path, spec, paths)
                # Expansion stops at the first spec that fails: the later ones are not resolved (PR 3's order).
                if isinstance(paths, Exception) or not paths:
                    break
            continue
        assert need is not None, "an unread edge without a need"
        for path in need.paths:
            if path in graph._documents or path in graph._failed:
                continue
            text: str | Exception
            try:
                text = port_text(source.read(path), port="read()")
            except Exception as error:
                text = error
            _graph.record_read(graph, path, text)
            if isinstance(text, Exception):
                break
            read.append(path)
