"""The check that villanelle text was given where villanelle text is taken (spec 6.9; owner, 2026-10-29: "A Keep text
only, make misuse impossible"): the one home of the argument type error and its message
(spec/schema/api.json, "argument type error message"). Private to the package."""

from __future__ import annotations


def require_text(value: object, *, member: str, parameter: str) -> str:
    """``value`` when it is a str; else TypeError naming ``member`` (as the caller wrote it) and ``parameter``."""
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{member}() argument '{parameter}' must be str, not {type(value).__name__}; "
        "villanelle edits take text: quote() a program string, str() a number"
    )
