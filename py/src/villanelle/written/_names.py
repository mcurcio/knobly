"""The one check per kind of name (spec 2.8, vil-umh.7): every bad name a program passes is a misuse error
(``ValueError``, a program bug), the same from every member that takes one. A variable's or override's name matches
the ``variable name`` pattern (``load``'s overrides, ``set_override``, a variable's ``rename``); a directive's name is
what the grammar's ``nameText`` entry rule takes, and neither reserved nor a registered extension's (a directive's
``rename``). Private."""

from __future__ import annotations

from villanelle._api.limits import RESERVED, VARIABLE_NAME
from villanelle._text import require_text
from villanelle.syntax.parse import parse_entry


def variable_name(name: object, *, member: str) -> str:
    """``name`` when it is a variable name (without ``$``): TypeError when not a str, ValueError when not letters,
    digits and ``_``."""
    given = require_text(name, member=member, parameter="name")
    if not VARIABLE_NAME.match(given):
        raise ValueError(f"{member}(): a variable's name is letters, digits and _: {given!r}")
    return given


def directive_name(name: str, extensions: frozenset[str], *, member: str) -> str:
    """``name`` when a directive may be named it: ValueError when the ``nameText`` entry rule refuses it (not one
    word, or starting with a digit or ``-``), or it is reserved or a registered extension's name (it would change the
    statement's kind)."""
    problems = parse_entry(name, "nameText").diagnostics
    if problems:
        raise ValueError(f"{member}(): not a directive name: {name!r} ({problems[0]})")
    if name in RESERVED or name in extensions:
        raise ValueError(f"{member}(): {name!r} is reserved at a line's start")
    return name
