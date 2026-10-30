"""The value rules of the grammar (NumberText, IntegerText, BooleanText, EscapeText) and the canonical
text of a value (round 11 slices.md §1.3): the one home of each rule. Private; a port of ts/src/values.ts."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from villanelle._api.limits import MAX_SAFE_INTEGER

_INTEGER_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)")
"""IntegerText: ``'-'? Digits``, Digits being ``0`` or a non-zero digit then digits."""

_SAFE_DIGITS = len(str(MAX_SAFE_INTEGER))
"""The most digits a word within ±(2**53 - 1) has. A longer word is never converted with ``int``: CPython refuses
digit strings beyond its conversion limit (4300 digits) with a bare ValueError."""

_NUMBER_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?")
"""NumberText: a JSON number (RFC 8259 section 6)."""


def integer_of(word: str) -> int | None:
    """The integer a word spells, or None when it is not an IntegerText or lies outside ±(2**53 - 1)."""
    if not _INTEGER_TEXT.fullmatch(word) or len(word.lstrip("-")) > _SAFE_DIGITS:
        return None
    value = int(word)
    return value if abs(value) <= MAX_SAFE_INTEGER else None


def number_of(word: str) -> int | float | None:
    """The number a word spells (spec/contract.md 3), or None when it is not a NumberText or its value overflows the
    double range (``1e400``). An int when the word has no fraction or exponent and lies within ±(2**53 - 1), else a
    float rounded to the nearest double; never ``-0.0`` (any zero reads as zero, ``1e-400`` included)."""
    if not _NUMBER_TEXT.fullmatch(word):
        return None
    if not any(c in word for c in ".eE") and len(word.lstrip("-")) <= _SAFE_DIGITS:
        value = int(word)
        if abs(value) <= MAX_SAFE_INTEGER:
            return value
    # Outside ±(2**53 - 1) an int would be exact here and rounded in TypeScript: read it as the same double (F1-09).
    number = float(word)
    if math.isinf(number):
        return None
    return 0.0 if number == 0 else number


def boolean_of(word: str) -> bool | None:
    """BooleanText: ``true`` or ``false``; None for any other word."""
    return {"true": True, "false": False}.get(word)


_ESCAPES = {'"': '"', "'": "'", "\\": "\\", "n": "\n", "t": "\t", "r": "\r"}
"""The six escapes of EscapeText (double-quoted strings only) and what each decodes to."""
_ESCAPE = re.compile(r"\\(.)", re.DOTALL)


def decode_string(token: str) -> str:
    """The text between a STRING token's quotes. A single-quoted token is raw (spec 3.1, TOML's literal strings): its
    text unchanged. A double-quoted one has its escapes decoded; it holds only the six escapes (the grammar's rule:
    any other makes the string a BAD_ESCAPE token, E1005)."""
    inner = token[1:-1]
    return inner if token.startswith("'") else _ESCAPE.sub(lambda m: _ESCAPES[m[1]], inner)


_CANONICAL_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def canonical_string(value: str) -> str:
    """A decoded string's canonical text: double-quoted, with ``\\``, ``"``, newline, tab and carriage return
    escaped."""
    return '"' + re.sub(r'[\\"\n\t\r]', lambda m: _CANONICAL_ESCAPES[m[0]], value) + '"'


def canonical_slice(name: str, start: int | None, end: int | None) -> str:
    """A slice's canonical text: ``name[start~end]``, either side empty when absent."""
    return f"{name}[{'' if start is None else start}~{'' if end is None else end}]"


def canonical_index(name: str, index: int) -> str:
    """An index's canonical text: ``name[i]``."""
    return f"{name}[{index}]"


def canonical_list(items: Iterable[str]) -> str:
    """A list's canonical text: its items' texts joined by ``, `` in brackets."""
    return "[" + ", ".join(items) + "]"
