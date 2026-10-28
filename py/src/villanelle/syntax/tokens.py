"""Our token vocabulary. Values are the token names of grammar/Villanelle.g4; ANTLR types never leave the adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from villanelle.span import SourceSpan


class TokenKind(StrEnum):
    BOM = "BOM"
    SPACE = "SPACE"
    NEWLINE = "NEWLINE"
    COMMENT = "COMMENT"
    VARIABLE = "VARIABLE"
    """``$name``: a variable reference (letters, digits and ``_`` after the ``$``)."""
    WORD = "WORD"
    STRING = "STRING"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACK = "LBRACK"
    RBRACK = "RBRACK"
    SEMI = "SEMI"
    COMMA = "COMMA"
    COLON = "COLON"
    UNTERMINATED_STRING = "UNTERMINATED_STRING"
    """Error token: a string literal without its closing quote. Never used by the syntax rules."""
    LONE_DOLLAR = "LONE_DOLLAR"
    """Error token: a ``$`` with no variable name after it. Never used by the syntax rules."""
    BAD_CHAR = "BAD_CHAR"
    """Error token: one character no other token may start with. Never used by the syntax rules."""


@dataclass(frozen=True, slots=True)
class Token:
    """One token. The tokens ``parse`` returns are contiguous, in source order, never empty, and their texts
    concatenated equal the input exactly (there is no end-of-file token)."""

    kind: TokenKind
    text: str
    span: SourceSpan
