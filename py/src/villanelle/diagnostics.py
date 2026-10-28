"""Stable diagnostic codes and the diagnostic shape every layer reports.

This mirrors the TypeScript package's registry value for value. Codes are stable across languages and releases.
Retired, never reused: E2006, E3002, E3003.
Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and extensions, 4xxx values, 5xxx expansion (variables, snippets,
limits), 6xxx reserved for the deferred sugar (none yet). A program's own codes are namespaced (``"rasl/no-graph"``),
so they never collide with these. Every code is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from villanelle.span import SourceSpan

if TYPE_CHECKING:
    from villanelle.report import LocatedDiagnostic


class DiagnosticCode(StrEnum):
    UNTERMINATED_STRING = "E1001"
    """A string literal reaches the end of its line or of the text without its closing quote."""
    UNEXPECTED_CHARACTER = "E1003"
    """A character no token may start with, or a byte-order mark after the first character."""
    LONE_DOLLAR = "E1004"
    """A ``$`` not followed by a variable name (letters, digits, ``_``)."""
    UNEXPECTED_TOKEN = "E2001"
    """A token the grammar does not allow here, when no more specific code applies."""
    EXPECTED_CLOSING_BRACE = "E2003"
    EXPECTED_CLOSING_BRACKET = "E2004"
    BAD_SLICE = "E2007"
    BRACE_ON_OWN_LINE = "E2008"
    VALUES_TOUCH = "E2009"
    NESTING_TOO_DEEP = "E2010"
    INCLUDE_NOT_FOUND = "E3001"
    INCLUDE_RESOLVER_FAILED = "E3004"
    INCLUDE_BAD_PATH = "E3005"
    """An ``include`` whose values are not exactly one quoted path."""
    EXTENSION_FAILED = "E3006"
    """An extension raised something other than a DiagnosticError while giving its specs."""
    NON_INTEGER_BOUND = "E4001"
    """A slice or index bound that is not an integer, such as ``a[x:2]`` or ``a[1.5]`` (vil-9ze.3)."""
    WRONG_VALUE_KIND = "E4002"
    """A reader asked for a kind of value the argument is not (``as_int()`` on a list)."""
    BAD_ESCAPE = "E4003"
    """A backslash escape other than the six of EscapeText."""
    NOT_A_NUMBER = "E4004"
    NOT_AN_INTEGER = "E4005"
    NOT_A_BOOLEAN = "E4006"
    UNKNOWN_VARIABLE = "E5001"
    """A ``$name`` with no ``set`` visible at that place and no value handed in by the program."""
    VARIABLE_SET_TWICE = "E5002"
    UNKNOWN_SNIPPET = "E5003"
    SNIPPET_ARITY = "E5004"
    SNIPPET_DEFINED_TWICE = "E5005"
    EXPANSION_CYCLE = "E5006"
    """A ``use`` or an extension directive that reaches itself again."""
    EXPANSION_TOO_DEEP = "E5007"
    """``use`` and extension directives nested deeper than 16 places."""
    TOO_MANY_DIRECTIVES = "E5008"
    """More than 100,000 directives after expansion."""
    BAD_SET = "E5009"
    BAD_SNIPPET = "E5010"
    BAD_USE = "E5011"
    EXTENSION_BLOCK_NOT_SET = "E5012"
    """An extension directive whose block holds a line other than ``set``."""


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One located problem in one source text. ``message`` is not part of the cross-language contract."""

    code: DiagnosticCode
    message: str
    span: SourceSpan


class DiagnosticError(Exception):
    """Raised by operations whose contract a user's input breaks (a value reader, a program's own check, a root file
    the source cannot read), carrying the located diagnostic of the load layer."""

    diagnostic: LocatedDiagnostic

    def __init__(self, diagnostic: LocatedDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic
