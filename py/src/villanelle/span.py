"""Source positions and spans, shared by tokens, values and diagnostics.

Units (the cross-language contract, also used by the conformance corpus):

- ``offset`` and ``column`` count UTF-16 code units, as in the TypeScript package. Python ``str`` indexes count code
  points, so an offset is not a ``str`` index once an astral character precedes it.
- ``line`` and ``column`` are 0-based. A line ends after each "\\n" (so "\\r\\n" ends one line); a lone "\\r" does not.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourcePosition:
    """A point between two UTF-16 code units of the source text."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """The half-open range [start, end) of source text. ``start.offset <= end.offset`` always."""

    start: SourcePosition
    end: SourcePosition
