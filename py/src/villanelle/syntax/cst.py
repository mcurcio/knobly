"""The lossless concrete syntax tree: concept nodes over token ranges (design/RECORD.md, "The CST")."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from villanelle.diagnostics import Diagnostic
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax.tokens import Token


class NodeKind(StrEnum):
    DOCUMENT = "document"
    DIRECTIVE = "directive"
    BLOCK = "block"
    LIST = "list"
    SLICE = "slice"
    ERROR = "error"
    """One bad statement, or a run of tokens the parser could not use. Never has children."""


class TokenRange(Protocol):
    """A half-open range [start, end) of token indices."""

    @property
    def start(self) -> int: ...

    @property
    def end(self) -> int: ...


@dataclass(frozen=True, slots=True)
class Node:
    """A CST node: children in source order, non-overlapping, inside [start, end); tokens not covered by a child
    belong to this node directly. A ``slice`` node spans ``name[bounds]`` exactly."""

    kind: NodeKind
    start: int
    end: int
    children: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Syntax:
    """The result of ``parse``: every token, a ``document`` root over [0, len(tokens)), and what went wrong."""

    tokens: tuple[Token, ...]
    root: Node
    diagnostics: tuple[Diagnostic, ...]


ValueRef = int | Node
"""The index of a WORD, STRING or VARIABLE token, or a ``slice`` or ``list`` node: one value as written."""

_ORIGIN = SourcePosition(offset=0, line=0, column=0)


def span_of(syntax: Syntax, rng: TokenRange) -> SourceSpan:
    """The span of a token range. An empty range at index i is a zero-width span at the start of token i, or at the
    end of the text when i == len(tokens). Raises ValueError outside [0, len(tokens)] or when start > end."""
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
    Raises ValueError outside [0, len(tokens)] or when start > end."""
    _check_range(len(syntax.tokens), rng)
    return "".join(token.text for token in syntax.tokens[rng.start : rng.end])


def _check_range(length: int, rng: TokenRange) -> None:
    start, end = rng.start, rng.end
    if start < 0 or end > length or start > end:
        raise ValueError(f"token range [{start}, {end}) is outside [0, {length}]")
