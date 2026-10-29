"""The processor (spec 6.1; round 12 design.md §6). A ``Processor`` is made once with its document source and
extensions (as ``jinja2.Environment`` is made with its loader and extensions); ``load`` reads a root file and
everything it includes into a document graph (the files as written), synchronously. Loading is its only operation:
every later one is a method on what it returned (``graph.read()``, ``graph.save(writer)``), and the rendered layer
builds on the graph (``villanelle.render(graph)``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import final

from villanelle._api.limits import RESERVED
from villanelle.extension import Extension
from villanelle.source import DocumentSource
from villanelle.written.model import DocumentGraph


@final
class Processor:
    """Made once with the document source and extensions; loads."""

    __slots__ = ("_extensions", "_source")

    def __init__(self, *, source: DocumentSource, extensions: Sequence[Extension] = ()) -> None:
        """Raises ValueError for an extension named ``set``, ``snippet`` or ``use``, or two extensions with one name
        (S2-01: rule 1 reserves those names, and one directive name has one owner)."""
        self._source = source
        self._extensions: dict[str, Extension] = {}
        for extension in extensions:
            name = extension.directive
            if name in RESERVED or name in self._extensions:
                raise ValueError(f"extension directive name taken: {name!r}")
            self._extensions[name] = extension

    def load(self, path: str, *, overrides: Mapping[str, str] | None = None) -> DocumentGraph:
        """Read the root file at ``path`` (resolved through the source, as an included file's spec is, so the root
        has one path in the graph) and every file its include lines name, once each (R21), repeating until nothing
        new is named. Never raises for anything in the text. ``overrides`` are by name without ``$``, each villanelle
        text (``{"host": quote("10.0.60.30"), "port": "8080"}``); an override wins over every ``set`` of its name
        (L3). Each is checked as ``DocumentGraph.set_override`` checks it: TypeError for a text that is not a str,
        ValueError for a name that is not letters, digits and ``_``, BadTextError for a text that is not one or more
        values. Raises ReadError (``paths``: ``[path]``; ``__cause__``: the source's failure) when the source cannot
        resolve the root to exactly one file or read it."""
        from villanelle.written import _read

        return _read.load_graph(self._source, self._extensions, path, overrides or {})
