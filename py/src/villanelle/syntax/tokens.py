"""Our token vocabulary. ``TokenKind`` is generated from grammar/Villanelle.g4 (its lexer rule names, the one home of
the list; ``villanelle._api.kinds``); ANTLR types never leave the adapter."""

from __future__ import annotations

from dataclasses import dataclass

from villanelle._api.kinds import TokenKind as TokenKind
from villanelle.span import SourceSpan


@dataclass(frozen=True, slots=True)
class Token:
    """One token. The tokens ``parse`` returns are contiguous, in source order, never empty, and their texts
    concatenated equal the input exactly (there is no end-of-file token)."""

    kind: TokenKind
    text: str
    span: SourceSpan
