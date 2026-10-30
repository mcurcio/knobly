"""The processor (spec 6.1; round 12 design.md §6). A ``Processor`` is made once with its document source and
extensions (as ``jinja2.Environment`` is made with its loader and extensions); ``load`` reads a root file and
everything it includes into a document graph (the files as written), synchronously. Loading is its only operation:
every later one is a method on what it returned (``graph.read()``, ``graph.save(writer)``), and the rendered layer
builds on the graph (``knobly.rendered.render(graph)``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import final

from knobly._api import written as api
from knobly._api.io import DocumentSource
from knobly._api.limits import RESERVED
from knobly._api.shared import ConfigText
from knobly._api.written import Extension
from knobly._text import require_text
from knobly.written import _names
from knobly.written._model import DocumentGraph


@final
class Processor(api.Processor):
    __slots__ = ("_extensions", "_source")

    def __init__(self, *, source: DocumentSource, extensions: Sequence[Extension] | None = None) -> None:
        self._source = source
        self._extensions: dict[str, Extension] = {}
        for extension in extensions or ():
            given = require_text(extension.directive, member="Processor", parameter="directive")
            name = _names.directive_name(given, member="Processor")
            if name in RESERVED or name in self._extensions:
                raise ValueError(f"extension directive name taken: {name!r}")
            self._extensions[name] = extension

    def load(self, path: str, *, overrides: Mapping[str, ConfigText] | None = None) -> DocumentGraph:
        from knobly.written import _read

        return _read.load_graph(self._source, self._extensions, path, overrides or {})
