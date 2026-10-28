"""``villanelle.files``: a document source over the filesystem, the I/O edge the core leaves out (R16), as
TypeScript's ``villanelle/node`` entry."""

from __future__ import annotations

import os
import stat
from collections.abc import Sequence

from villanelle._glob import glob_pattern, has_glob
from villanelle.source import DocumentSource, LoadContext


def file_source() -> DocumentSource:
    """``read`` reads a path as given, as UTF-8; ``resolve`` joins a spec to the directory of ``context.parent_path``;
    a glob (``*`` and ``?`` in the last path segment only) lists that directory and returns every matching file. A
    missing file, a missing directory or a path that is a directory resolves to no paths (E3001); any other
    filesystem error (permissions) raises (E3004), as TypeScript's ``createFileSource`` does (S2-04)."""
    return _FileSource()


class _FileSource:
    __slots__ = ()

    def resolve(self, spec: str, context: LoadContext, /) -> Sequence[str]:
        path = os.path.normpath(os.path.join(os.path.dirname(context.parent_path), spec))
        if not has_glob(path):
            return [path] if _is_file(path) else []
        directory, name = os.path.split(path)
        pattern = glob_pattern(name)
        try:
            entries = os.listdir(directory or ".")
        except (FileNotFoundError, NotADirectoryError):
            return []
        return [
            os.path.join(directory, entry)
            for entry in entries
            if pattern.fullmatch(entry) is not None and _is_file(os.path.join(directory, entry))
        ]

    def read(self, resolved_path: str, /) -> str:
        # newline="" keeps "\r\n" as written: positions count every character of the file.
        with open(resolved_path, encoding="utf-8", newline="") as file:
            return file.read()


def _is_file(path: str) -> bool:
    """Whether ``path`` names a file; False when nothing is there. Other failures (permissions) raise."""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False
