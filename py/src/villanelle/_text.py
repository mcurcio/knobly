"""The check that villanelle text was given where villanelle text is taken (spec 6.9; owner, 2026-10-29: "A Keep text
only, make misuse impossible"): the one home of the argument type error and its message
(spec/schema/api.json, "argument type error message"), and ``quote``, which writes a plain string as villanelle text.
Shared (spec/schema/api.json: ``quote`` is in the shared layer, as TypeScript's ``ts/src/text.ts``); ``quote`` is
public through ``villanelle``, ``require_text`` is private to the package."""

from __future__ import annotations

from villanelle._values import canonical_string


def require_text(value: object, *, member: str, parameter: str) -> str:
    """``value`` when it is a str; else TypeError naming ``member`` (as the caller wrote it) and ``parameter``."""
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{member}() argument '{parameter}' must be str, not {type(value).__name__}; "
        "villanelle edits take text: quote() a program string, str() a number"
    )


def quote(text: str, /) -> str:
    """A plain string as a villanelle string, escapes included: ``quote("10.0.60.31")`` is ``'"10.0.60.31"'``, ready
    for an edit (``stmt.set(quote(host))``). The canonical string text of an expanded value. TypeError for a ``text``
    that is not a str."""
    return canonical_string(require_text(text, member="quote", parameter="text"))
