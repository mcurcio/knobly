"""The I/O ports (spec/schema/api.json, layer io): where files come from, the one port the load reads through for the
root file and for every file an extension names (round 11 review finding 3), and where a save writes them
(``DocumentWriter``, given ``FileWrite``s by ``DocumentGraph.save``). The core does no I/O (R16):
``villanelle.files`` gives a filesystem source and writer; ``memory_source`` serves texts the program already holds
(tests, editors)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from villanelle._glob import glob_pattern, has_glob


@dataclass(frozen=True, slots=True)
class LoadContext:
    """Where a spec is being resolved from."""

    parent_path: str
    """Resolved path of the file holding the extension directive; empty when the root path itself is resolved."""


class DocumentSource(Protocol):
    """The document source. The load calls ``read`` at most once per resolved path, however many places splice the
    file in (R21: "Obviously the file only needs to be read once")."""

    def resolve(self, spec: str, context: LoadContext, /) -> Sequence[str]:
        """The resolved paths a spec names (a path, or a glob with ``*`` and ``?`` in its last segment), in any order;
        empty means not found (E3001). An exception becomes E3004 at the extension directive."""
        ...

    def read(self, resolved_path: str, /) -> str:
        """The text of one resolved file. An exception becomes E3004 (for the root file, ``load`` raises)."""
        ...


@dataclass(frozen=True, slots=True)
class FileWrite:
    """One file a save hands to the writer."""

    resolved_path: str
    text: str
    """What to write."""
    saved_text: str
    """The document's ``saved_text``: compare it with the disk to find a lost update."""


class DocumentWriter(Protocol):
    """The program's writer."""

    def write(self, files: Sequence[FileWrite], /) -> None:
        """One batch: stage every file, then commit them together. Raising while staging means nothing was committed;
        a writer that can fail part way through committing (the fs writer's renames) leaves the files it committed
        changed on disk while their ``saved_text`` stays the old text, so the next save refuses them as lost updates
        until the program reloads (stated cost, D-F1-10)."""
        ...


def memory_source(files: Mapping[str, str], /) -> DocumentSource:
    """A source over texts held in memory, keyed by path, with the same resolve rules as TypeScript's ``memorySource``
    (POSIX join to the parent's directory, ``.`` and ``..`` removed, a leading ``/`` taken as is, a glob in the last
    segment). ``read`` of a path that is not a key raises KeyError. Pure: no I/O."""
    return _MemorySource(dict(files))


class _MemorySource:
    __slots__ = ("_texts",)

    def __init__(self, texts: dict[str, str]) -> None:
        self._texts = texts

    def resolve(self, spec: str, context: LoadContext, /) -> Sequence[str]:
        path = _normalize(spec if spec.startswith("/") else _directory_of(context.parent_path) + spec)
        if not has_glob(path):
            return [path] if path in self._texts else []
        directory = _directory_of(path)
        pattern = glob_pattern(path[len(directory) :])
        return [
            key
            for key in self._texts
            if _directory_of(key) == directory and pattern.fullmatch(key[len(directory) :]) is not None
        ]

    def read(self, resolved_path: str, /) -> str:
        if resolved_path not in self._texts:
            raise KeyError(f"no such file: {resolved_path}")
        return self._texts[resolved_path]


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
