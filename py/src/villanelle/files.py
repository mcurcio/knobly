"""``villanelle.files``: a document source and a writer over the filesystem, the I/O edges the core leaves out (R16),
as TypeScript's ``villanelle/node`` entry."""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from collections.abc import Sequence

from villanelle._glob import glob_pattern, has_glob
from villanelle.source import DocumentSource, LoadContext
from villanelle.written.save import DocumentWriter, FileWrite


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


def fs_writer() -> DocumentWriter:
    """A writer for one batch (slices.md S3; D18): it raises, writing nothing, when any file on disk no longer holds
    its ``source`` (a lost update; the error names the paths); otherwise it writes each text to a temporary file
    beside its target (``<name>.<random>.tmp``), then renames each over its target, as UTF-8 with line breaks as
    written. A failure while staging removes the temporaries and raises with nothing replaced; a failure while
    renaming can leave earlier files replaced (the stated cost)."""
    return _FsWriter()


class _FsWriter:
    __slots__ = ()

    def write(self, files: Sequence[FileWrite], /) -> None:
        lost = [file.resolved_path for file in files if _read_or_none(file.resolved_path) != file.source]
        if lost:
            raise OSError(f"changed on disk since it was read (a lost update): {', '.join(lost)}")
        staged: list[tuple[str, str]] = []
        try:
            for file in files:
                directory, name = os.path.split(file.resolved_path)
                handle, temporary = tempfile.mkstemp(prefix=f"{name}.", suffix=".tmp", dir=directory or ".")
                staged.append((temporary, file.resolved_path))
                with os.fdopen(handle, "w", encoding="utf-8", newline="") as out:
                    out.write(file.text)
        except BaseException:
            for temporary, _ in staged:
                with contextlib.suppress(OSError):
                    os.remove(temporary)
            raise
        for temporary, target in staged:
            os.replace(temporary, target)


def _read_or_none(path: str) -> str | None:
    """The file's text as written, or None when it is missing."""
    try:
        with open(path, encoding="utf-8", newline="") as file:
            return file.read()
    except FileNotFoundError:
        return None


def _is_file(path: str) -> bool:
    """Whether ``path`` names a file; False when nothing is there. Other failures (permissions) raise."""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False
