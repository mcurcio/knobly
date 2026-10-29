"""``villanelle.files``: a document source and a writer over the filesystem, the I/O edges the core leaves out (R16),
as TypeScript's ``villanelle/node`` entry (``fileSource``, ``fileWriter``)."""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from collections.abc import Sequence

from villanelle._api.io import DocumentSource, DocumentWriter, FileWrite, LoadContext
from villanelle._glob import glob_pattern, has_glob
from villanelle.source import check_lost_updates


def file_source() -> DocumentSource:
    """``read`` reads a path as given, as UTF-8; ``resolve`` joins a spec to the directory of ``context.parent_path``;
    a glob (``*`` and ``?`` in the last path segment only) lists that directory and returns every matching file. A
    missing file, a missing directory or a path that is a directory resolves to no paths (E3001); any other
    filesystem error (permissions) raises (E3004), as TypeScript's ``fileSource`` does (S2-04)."""
    return _FileSource()


class _FileSource:
    __slots__ = ()

    def resolve(self, spec: str, context: LoadContext, /) -> tuple[str, ...]:
        path = os.path.normpath(os.path.join(os.path.dirname(context.parent_path), spec))
        if not has_glob(path):
            return (path,) if _is_file(path) else ()
        directory, name = os.path.split(path)
        pattern = glob_pattern(name)
        try:
            entries = os.listdir(directory or ".")
        except (FileNotFoundError, NotADirectoryError):
            return ()
        return tuple(
            os.path.join(directory, entry)
            for entry in entries
            if pattern.fullmatch(entry) is not None and _is_file(os.path.join(directory, entry))
        )

    def read(self, resolved_path: str, /) -> str:
        # newline="" keeps "\r\n" as written: positions count every character of the file.
        with open(resolved_path, encoding="utf-8", newline="") as file:
            return file.read()


def file_writer() -> DocumentWriter:
    """A writer for one batch (slices.md S3; D18): ``check_lost_updates`` with each file's text on disk first, so it
    raises ``LostUpdateError``, writing nothing, when any file on disk no longer holds its ``saved_text``; otherwise
    it writes each text to a temporary file beside its target (``<name>.<random>.tmp``), then renames each over its
    target, as UTF-8 with line breaks as written. A missing target holds "" (a new file has ``saved_text`` "",
    D-S2-5). A failure while staging removes the temporaries and raises with nothing replaced; a failure while
    renaming can leave earlier files replaced (the stated cost) and removes the temporaries not yet renamed."""
    return _FileWriter()


class _FileWriter:
    __slots__ = ()

    def write(self, files: Sequence[FileWrite], /) -> None:
        check_lost_updates(files, [_read_or_none(file.resolved_path) for file in files])
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
        for i, (temporary, target) in enumerate(staged):
            try:
                os.replace(temporary, target)
            except BaseException:
                for left, _ in staged[i:]:
                    with contextlib.suppress(OSError):
                        os.remove(left)
                raise


def _read_or_none(path: str) -> str | None:
    """The file's text as written, or None when nothing is there."""
    try:
        with open(path, encoding="utf-8", newline="") as file:
            return file.read()
    except (FileNotFoundError, NotADirectoryError):
        return None


def _is_file(path: str) -> bool:
    """Whether ``path`` names a file; False when nothing is there. Other failures (permissions) raise."""
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False


__all__ = ["file_source", "file_writer"]
