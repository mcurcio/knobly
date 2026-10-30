"""The one check per kind of name (spec 2.8, kno-umh.7): every bad name a program passes is a misuse error
(``ValueError``, a program bug), the same from every member that takes one. A variable's or override's name matches
the ``variable name`` pattern (``load``'s overrides, ``set_override``, a variable's ``rename``); a directive's name, and
an extension's at make processor, is what the grammar's ``nameText`` entry rule takes (one WORD, so never starting
with ``@``). No directive name is reserved (spec 2.5, milestone 5). Private."""

from __future__ import annotations

from knobly._api.limits import VARIABLE_NAME
from knobly._text import require_text
from knobly.syntax._parse import parse_entry


def variable_name(name: object, *, member: str) -> str:
    """``name`` when it is a variable name (without ``$``): TypeError when not a str, ValueError when not letters,
    digits and ``_``."""
    given = require_text(name, member=member, parameter="name")
    if not VARIABLE_NAME.match(given):
        raise ValueError(f"{member}(): a variable's name is letters, digits and _: {given!r}")
    return given


def directive_name(name: str, *, member: str) -> str:
    """``name`` when a directive may be named it: ValueError when the ``nameText`` entry rule refuses it (not one
    word, or starting with a digit, ``-`` or ``@``)."""
    problems = parse_entry(name, "nameText").diagnostics
    if problems:
        raise ValueError(f"{member}(): not a directive name: {name!r} ({problems[0]})")
    return name
