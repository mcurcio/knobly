"""The check that villanelle text was given where villanelle text is taken (spec 6.9; owner, 2026-10-29: "A Keep text
only, make misuse impossible"): the one home of the argument type error and its message
(spec/schema/api.json, "argument type error message"), and ``quote``, which writes a plain string as villanelle text.
Shared (spec/schema/api.json: ``quote`` is in the shared layer, as TypeScript's ``ts/src/text.ts``); ``quote`` is
public through ``villanelle``, ``require_text`` is private to the package."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle._values import canonical_string


def require_text(value: object, *, member: str, parameter: str) -> str:
    """``value`` when it is a str; else TypeError naming ``member`` (as the caller wrote it) and ``parameter``."""
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{member}() argument '{parameter}' must be str, not {type(value).__name__}; "
        "villanelle edits take text: quote() a program string, str() a number"
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


def quote(text: str, /) -> str:
    """A plain string as a villanelle string, escapes included: ``quote("10.0.60.31")`` is ``'"10.0.60.31"'``, ready
    for an edit (``stmt.set(quote(host))``). The canonical string text of an expanded value. TypeError for a ``text``
    that is not a str."""
    return canonical_string(require_text(text, member="quote", parameter="text"))
