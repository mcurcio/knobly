"""``villanelle.files``: a document source over the filesystem, the I/O edge the core leaves out (R16), as
TypeScript's ``villanelle/node`` entry."""

from __future__ import annotations

from villanelle.source import DocumentSource


def file_source() -> DocumentSource:
    """``read`` reads a path as given, as UTF-8; ``resolve`` joins a spec to the directory of ``context.parent_path``;
    a glob (``*`` and ``?`` in the last path segment only) lists that directory and returns every matching file. A
    missing file resolves to no paths (E3001)."""
    raise NotImplementedError("file_source")
