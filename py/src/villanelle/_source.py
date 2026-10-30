"""The I/O ports (spec/schema/api.json, layer io): where files come from, the one port the load reads through for the
root file and for every file an extension names (round 11 review finding 3), and where a save writes them
(``DocumentWriter``, given ``FileWrite``s by ``DocumentGraph.save``). The core does no I/O (R16):
``villanelle.files`` gives a filesystem source and writer (``file_source``, ``file_writer``); ``memory_source`` and
``memory_writer`` serve and keep texts the program holds in one map (tests, editors). Each adapter is named after its
medium and the port it fills (spec/contract.md 5). The ports and their records are generated
(``villanelle._api.io``): a source raises from ``resolve`` for a failure (E3004 at the extension line, ``ReadError``
for the root) and returns no path for a missing file (E3001); ``load`` reads each resolved path at most once (R21);
a writer calls ``check_lost_updates`` first, then stages and commits the batch together."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence

from villanelle._api.errors import LostUpdateError
from villanelle._api.io import DocumentSource, DocumentWriter, FileWrite, LoadContext
from villanelle._glob import glob_pattern, has_glob


def check_lost_updates(files: Sequence[FileWrite], current: Sequence[str | None], /) -> None:
    if len(current) != len(files):
        raise ValueError(f"check_lost_updates: {len(files)} files but {len(current)} current texts")
    lost = [file.resolved_path for file, now in zip(files, current, strict=True) if (now or "") != file.saved_text]
    if lost:
        raise LostUpdateError(lost)


def memory_source(files: Mapping[str, str], /) -> DocumentSource:
    return _MemorySource(files)


class _MemorySource:
    __slots__ = ("_texts",)

    def __init__(self, texts: Mapping[str, str]) -> None:
        self._texts = texts

    def resolve(self, spec: str, context: LoadContext, /) -> tuple[str, ...]:
        path = _normalize(spec if spec.startswith("/") else _directory_of(context.parent_path) + spec)
        if not has_glob(path):
            return (path,) if path in self._texts else ()
        directory = _directory_of(path)
        pattern = glob_pattern(path[len(directory) :])
        return tuple(
            key
            for key in self._texts
            if _directory_of(key) == directory and pattern.fullmatch(key[len(directory) :]) is not None
        )

    def read(self, resolved_path: str, /) -> str:
        if resolved_path not in self._texts:
            raise KeyError(f"no such file: {resolved_path}")
        return self._texts[resolved_path]


def memory_writer(files: MutableMapping[str, str], /) -> DocumentWriter:
    return _MemoryWriter(files)


class _MemoryWriter:
    __slots__ = ("_texts",)

    def __init__(self, texts: MutableMapping[str, str]) -> None:
        self._texts = texts

    def write(self, files: Sequence[FileWrite], /) -> None:
        check_lost_updates(files, [self._texts.get(file.resolved_path) for file in files])
        for file in files:
            self._texts[file.resolved_path] = file.text


def _directory_of(path: str) -> str:
    """Everything up to and including the last ``/``; empty for a bare name."""
    return path[: path.rfind("/") + 1]


def _normalize(path: str) -> str:
    """POSIX rules: ``.`` and empty segments dropped; each ``..`` removes the segment before it when there is one."""
    out: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == ".." and out and out[-1] != "..":
            out.pop()
        else:
            out.append(segment)
    return ("/" if path.startswith("/") else "") + "/".join(out)
