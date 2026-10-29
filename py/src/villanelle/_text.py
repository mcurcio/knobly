"""Config text (spec 6.9; owner, 2026-10-29, vil-umh.6: "Yes, its own type"): ``ConfigText``, villanelle text a
program hands to an edit or an override, made only by ``quote`` (a program string written as a villanelle string) or
``text`` (a text already written as villanelle text). A ``typing.NewType`` (PEP 484): a str at run time, so a type
checker refuses a plain str where an edit takes config text, and the run-time check stays ``require_text``. Also the
one home of the argument type error and its message (spec/schema/api.json, "argument type error message"). Shared
(spec/schema/api.json: ``quote`` and ``text`` are in the shared layer, as TypeScript's ``ts/src/text.ts``);
``ConfigText``, ``quote`` and ``text`` are public through ``villanelle``, the checks are private to the package."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NewType

from villanelle._values import canonical_string

ConfigText = NewType("ConfigText", str)
"""Villanelle text for an edit or an override: made only by ``quote`` or ``text``. A str at run time."""


def require_text(value: object, *, member: str, parameter: str) -> str:
    """``value`` when it is a str; else TypeError naming ``member`` (as the caller wrote it) and ``parameter``."""
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{member}() argument '{parameter}' must be str, not {type(value).__name__}; "
        "villanelle edits take config text: quote() a program string, text() one already written as villanelle text, "
        "str() a number first"
    )


def port_texts(result: object, *, port: str) -> tuple[str, ...]:
    """A port's list of texts (``Extension.specs``, ``DocumentSource.resolve``), checked at run time (spec 4.1, 5;
    vil-umh.12): a sequence of str. Anything else, a bare ``str`` included (a ``str`` is a sequence of one-letter
    strings, so a type checker alone does not catch it), raises TypeError naming the port and the type it got; the
    caller turns that into the port's failure (E3006, E3004, or a ``ReadError`` for the root)."""
    if isinstance(result, Sequence) and not isinstance(result, str) and all(isinstance(x, str) for x in result):
        return tuple(result)
    got = type(result).__name__ if isinstance(result, str) or not isinstance(result, Sequence) else "a non-str item"
    raise TypeError(f"{port} must return a tuple of str, not {got}")


def port_text(result: object, *, port: str) -> str:
    """A port's text (``DocumentSource.read``), checked at run time: TypeError naming the port and the type got."""
    if isinstance(result, str):
        return result
    raise TypeError(f"{port} must return a str, not {type(result).__name__}")


def quote(text: str, /) -> ConfigText:
    """A plain string as a villanelle string, escapes included: ``quote("10.0.60.31")`` is ``'"10.0.60.31"'``, ready
    for an edit (``stmt.set(quote(host))``). The canonical string text of an expanded value. TypeError for a ``text``
    that is not a str."""
    return ConfigText(canonical_string(require_text(text, member="quote", parameter="text")))


def text(raw: str, /) -> ConfigText:
    """``raw`` as config text, unchanged and unchecked: the program's statement that ``raw`` is already written as
    villanelle text (``stmt.set(text("8080"))``, ``value.set(text("[1, 2]"))``); the edit it is given checks it.
    TypeError for a ``raw`` that is not a str."""
    return ConfigText(require_text(raw, member="text", parameter="raw"))
