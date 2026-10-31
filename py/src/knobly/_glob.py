"""The glob rule of include specs (spec 4.1), shared by the core's bind (W3005 or E3001 for an empty result),
``memory_source`` and ``file_source``: ``*`` matches any run of characters and ``?`` one character, in the last
path segment only. Private; a port of ts/src/graph/glob.ts."""

from __future__ import annotations

import re


def has_glob(spec: str) -> bool:
    """Whether a spec is a glob: it holds ``*`` or ``?``."""
    return "*" in spec or "?" in spec


def glob_pattern(pattern: str) -> re.Pattern[str]:
    """A file-name pattern for ``fullmatch``: ``*`` any run of characters, ``?`` one, everything else itself."""
    escaped = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.compile(escaped, re.DOTALL)
