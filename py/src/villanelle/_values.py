"""The value rules of grammar/villanelle.ebnf (NumberText, IntegerText, BooleanText, EscapeText) and the canonical
text of a value (round 11 slices.md §1.3): the one home of each rule. Private; a port of ts/src/load/values.ts."""

from __future__ import annotations

import re
from collections.abc import Iterable

_INTEGER_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)")
"""IntegerText: ``'-'? Digits``, Digits being ``0`` or a non-zero digit then digits."""

_NUMBER_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?")
"""NumberText: a JSON number (RFC 8259 section 6)."""

MAX_SAFE_INTEGER = 2**53 - 1
"""TypeScript's safe-integer limit; integers outside ±this are refused so both languages read the same number."""


def integer_of(word: str) -> int | None:
    """The integer a word spells, or None when it is not an IntegerText or lies outside ±(2**53 - 1)."""
    if not _INTEGER_TEXT.fullmatch(word):
        return None
    value = int(word)
    return value if abs(value) <= MAX_SAFE_INTEGER else None


def number_of(word: str) -> int | float | None:
    """The number a word spells (int without fraction or exponent and within ±(2**53 - 1), else float), or None when
    not a NumberText."""
    if not _NUMBER_TEXT.fullmatch(word):
        return None
    if any(c in word for c in ".eE"):
        return float(word)
    value = int(word)
    # Outside ±(2**53 - 1) an int would be exact here and rounded in TypeScript: read it as the same float (F1-09).
    return value if abs(value) <= MAX_SAFE_INTEGER else float(word)


def boolean_of(word: str) -> bool | None:
    """BooleanText: ``true`` or ``false``; None for any other word."""
    return {"true": True, "false": False}.get(word)


_ESCAPES = {'"': '"', "'": "'", "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}
"""The six escapes of EscapeText and what each decodes to."""
_ESCAPE = re.compile(r"\\(.)", re.DOTALL)


def has_only_known_escapes(token: str) -> bool:
    """Whether every backslash escape in a STRING token's text is one of the six of EscapeText."""
    return all(m[1] in _ESCAPES for m in _ESCAPE.finditer(token[1:-1]))


def decode_string(token: str) -> str:
    """The text between a STRING token's quotes, escapes decoded. Call only after ``has_only_known_escapes``."""
    return _ESCAPE.sub(lambda m: _ESCAPES[m[1]], token[1:-1])


_CANONICAL_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def canonical_string(value: str) -> str:
    """A decoded string's canonical text: double-quoted, with ``\\``, ``"``, newline, tab and carriage return
    escaped."""
    return '"' + re.sub(r'[\\"\n\t\r]', lambda m: _CANONICAL_ESCAPES[m[0]], value) + '"'


def canonical_slice(name: str, start: int | None, end: int | None) -> str:
    """A slice's canonical text: ``name[start:end]``, either side empty when absent."""
    return f"{name}[{'' if start is None else start}:{'' if end is None else end}]"


def canonical_index(name: str, index: int) -> str:
    """An index's canonical text: ``name[i]``."""
    return f"{name}[{index}]"


def canonical_list(items: Iterable[str]) -> str:
    """A list's canonical text: its items' texts joined by ``, `` in brackets."""
    return "[" + ", ".join(items) + "]"
