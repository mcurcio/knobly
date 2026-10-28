"""Where files come from: the one port the load reads through, for the root file and for every file an extension
names (round 11 review finding 3). The core does no I/O (R16): ``villanelle.files`` gives a filesystem source;
``memory_source`` serves texts the program already holds (tests, editors)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LoadContext:
    """Where a spec is being resolved from."""

    parent_path: str
    """Resolved path of the file holding the extension directive."""


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


def memory_source(files: Mapping[str, str], /) -> DocumentSource:
    """A source over texts held in memory, keyed by path, with the same resolve rules as TypeScript's ``memorySource``
    (POSIX join to the parent's directory, ``.`` and ``..`` removed, a leading ``/`` taken as is, a glob in the last
    segment). ``read`` of a path that is not a key raises KeyError. Pure: no I/O."""
    raise NotImplementedError("memory_source")
