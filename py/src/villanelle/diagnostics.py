"""Stable diagnostic codes and the diagnostic shape every layer reports.

This mirrors the TypeScript package's registry value for value. Codes are stable across languages and releases.
Ranges: 1xxx lexical, 2xxx syntax, 3xxx include graph, 4xxx typed values. Every code is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from villanelle.span import SourceSpan


class DiagnosticCode(StrEnum):
    UNTERMINATED_STRING = "E1001"
    """A string literal reaches the end of its line or of the text without its closing quote."""
    UNEXPECTED_CHARACTER = "E1003"
    """A character no token may start with, or a byte-order mark after the first character."""
    UNEXPECTED_TOKEN = "E2001"
    """A token the grammar does not allow here, when no more specific code applies."""
    EXPECTED_CLOSING_BRACE = "E2003"
    EXPECTED_CLOSING_BRACKET = "E2004"
    EXPECTED_STRING_LITERAL = "E2006"
    BAD_SLICE = "E2007"
    BRACE_ON_OWN_LINE = "E2008"
    VALUES_TOUCH = "E2009"
    NESTING_TOO_DEEP = "E2010"
    INCLUDE_NOT_FOUND = "E3001"
    INCLUDE_CYCLE = "E3002"
    INCLUDE_DEPTH_EXCEEDED = "E3003"
    INCLUDE_RESOLVER_FAILED = "E3004"
    NON_INTEGER_BOUND = "E4001"
    """A slice or index bound that is not an integer, such as ``a[x:2]`` or ``a[1.5]`` (vil-9ze.3)."""


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One located problem in one source text. ``message`` is not part of the cross-language contract."""

    code: DiagnosticCode
    message: str
    span: SourceSpan


class DiagnosticError(Exception):
    """Raised by operations whose contract a user's input breaks, carrying the located diagnostic."""

    diagnostic: Diagnostic

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
