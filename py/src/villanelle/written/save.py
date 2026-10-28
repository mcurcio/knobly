"""Saving the edited files, and writing a plain string as villanelle text (round 12 design.md §6; slices.md S3).
The core does no I/O: the writer is the program's (``villanelle.files.fs_writer`` writes files on disk)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from villanelle._values import canonical_string
from villanelle.written.errors import SaveError

if TYPE_CHECKING:
    from villanelle.written.model import DocumentGraph


@dataclass(frozen=True, slots=True)
class FileWrite:
    """One file a save hands to the writer."""

    resolved_path: str
    text: str
    """What to write."""
    source: str
    """The document's ``source``: compare it with the disk to find a lost update."""


class DocumentWriter(Protocol):
    """The program's writer."""

    def write(self, files: Sequence[FileWrite], /) -> None:
        """One batch: stage every file, then commit them together. Raising while staging means nothing was committed;
        a writer that can fail part way through committing (the fs writer's renames) leaves the files it committed
        changed on disk while their ``source`` stays the old text, so the next save refuses them as lost updates until
        the program reloads (stated cost, D-F1-10)."""
        ...


def save(graph: DocumentGraph, writer: DocumentWriter, /) -> list[str]:
    """Hand every document whose ``text`` differs from its ``source`` to the writer in one batch, in ``documents``
    order; with none, the writer is not called. When the writer returns, each written document's ``source`` becomes
    the text handed over; when it raises, no ``source`` changes and ``SaveError`` is raised from it. Returns the
    resolved paths handed over."""
    batch = [
        FileWrite(doc.resolved_path, doc.text, doc.source) for doc in graph.documents.values() if doc.text != doc.source
    ]
    if not batch:
        return []
    try:
        writer.write(tuple(batch))
    except Exception as error:
        raise SaveError(f"the writer raised: {error}", batch) from error
    for file in batch:
        graph.documents[file.resolved_path]._mark_saved(file.text)
    return [file.resolved_path for file in batch]


def quote(text: str, /) -> str:
    """A plain string as a villanelle string, escapes included: ``quote("10.0.60.31")`` is ``'"10.0.60.31"'``. The
    canonical string text of a rendered value (``_values.canonical_string``)."""
    return canonical_string(text)
