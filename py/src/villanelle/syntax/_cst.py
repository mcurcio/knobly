"""The lossless concrete syntax tree: concept nodes over token ranges (design/RECORD.md, "The CST"). ``Token``,
``TokenRange``, ``Node`` and ``Syntax`` are generated records (``villanelle._api.syntax``): a node is a token range
whose children are in source order, non-overlapping, inside [start, end), and a ``slice`` node spans ``name[bounds]``
exactly; ``parse`` returns every token (contiguous, in source order, never empty, their texts concatenated equal to the
input), a ``document`` root over [0, len(tokens)) and what went wrong."""

from __future__ import annotations

from villanelle._api.shared import SourcePosition, SourceSpan
from villanelle._api.syntax import Node, Syntax, TokenRange

ValueRef = int | Node
"""Private to the package (not exported, round 15). The index of a WORD, INTEGER, DIGIT_WORD, STRING or VARIABLE
token, or a ``slice`` or ``list`` node: one value as written."""

_ORIGIN = SourcePosition(offset=0, line=0, column=0)


def span_of(syntax: Syntax, rng: TokenRange) -> SourceSpan:
    """The span of a token range. An empty range at index i is a zero-width span at the start of token i, or at the
    end of the text when i == len(tokens). Raises IndexError outside [0, len(tokens)] or when start > end."""
    tokens = syntax.tokens
    _check_range(len(tokens), rng)

    def at(i: int) -> SourcePosition:
        if i < len(tokens):
            return tokens[i].span.start
        return tokens[-1].span.end if tokens else _ORIGIN

    start = at(rng.start)
    if rng.start == rng.end:
        return SourceSpan(start=start, end=start)
    return SourceSpan(start=start, end=tokens[rng.end - 1].span.end)


def text_of(syntax: Syntax, rng: TokenRange) -> str:
    """The exact source text of a token range; ``text_of(syntax, syntax.root)`` is the whole input.
    Raises IndexError outside [0, len(tokens)] or when start > end."""
    _check_range(len(syntax.tokens), rng)
    return "".join(token.text for token in syntax.tokens[rng.start : rng.end])


def _check_range(length: int, rng: TokenRange) -> None:
    start, end = rng.start, rng.end
    if start < 0 or end > length or start > end:
        raise IndexError(f"token range [{start}, {end}) is outside [0, {length}]")
