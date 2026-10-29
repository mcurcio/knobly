"""Source positions and spans, shared by tokens, values and diagnostics (spec/contract.md 1).

- ``offset`` and ``column`` count code points, Python's own string unit: ``text[start.offset:end.offset]`` is the
  text of the span. (TypeScript counts UTF-16 code units; the conformance corpus stays in UTF-16 and the shared
  driver converts.)
- ``line`` and ``column`` are 0-based. A line ends after each "\\n" (so "\\r\\n" ends one line); a lone "\\r" does not.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourcePosition:
    """A point between two code points of the source text."""

    offset: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """The half-open range [start, end) of source text. ``start.offset <= end.offset`` always."""

    start: SourcePosition
    end: SourcePosition
