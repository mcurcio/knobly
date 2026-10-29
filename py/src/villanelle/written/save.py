"""What a save hands to the program's writer (``DocumentGraph.save``), and writing a plain string as villanelle text
(round 12 design.md §6; slices.md S3). The core does no I/O: the writer is the program's (``villanelle.files.fs_writer``
writes files on disk)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from villanelle._text import require_text
from villanelle._values import canonical_string


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


def quote(text: str, /) -> str:
    """A plain string as a villanelle string, escapes included: ``quote("10.0.60.31")`` is ``'"10.0.60.31"'``, ready
    for an edit (``stmt.set(quote(host))``). The canonical string text of an expanded value. TypeError for a ``text``
    that is not a str."""
    return canonical_string(require_text(text, member="quote", parameter="text"))
