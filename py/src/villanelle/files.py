"""``villanelle.files``: a document source over the filesystem, the I/O edge the core leaves out (R16), as
TypeScript's ``villanelle/node`` entry."""

from __future__ import annotations

import os
from collections.abc import Sequence

from villanelle._glob import glob_pattern, has_glob
from villanelle.source import DocumentSource, LoadContext


def file_source() -> DocumentSource:
    """``read`` reads a path as given, as UTF-8; ``resolve`` joins a spec to the directory of ``context.parent_path``;
    a glob (``*`` and ``?`` in the last path segment only) lists that directory and returns every matching file. A
    missing file resolves to no paths (E3001)."""
    return _FileSource()


class _FileSource:
    __slots__ = ()

    def resolve(self, spec: str, context: LoadContext, /) -> Sequence[str]:
        path = os.path.normpath(os.path.join(os.path.dirname(context.parent_path), spec))
        if not has_glob(path):
            return [path] if os.path.isfile(path) else []
        directory, name = os.path.split(path)
        pattern = glob_pattern(name)
        try:
            entries = os.listdir(directory or ".")
        except FileNotFoundError:
            return []
        return [
            os.path.join(directory, entry)
            for entry in entries
            if pattern.fullmatch(entry) is not None and os.path.isfile(os.path.join(directory, entry))
        ]

    def read(self, resolved_path: str, /) -> str:
        # newline="" keeps "\r\n" as written: positions count every character of the file.
        with open(resolved_path, encoding="utf-8", newline="") as file:
            return file.read()
