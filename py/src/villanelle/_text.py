"""Config text (spec 6.9; owner, 2026-10-29, vil-umh.6: "Yes, its own type"): ``ConfigText``, villanelle text a
program hands to an edit or an override, made only by ``quote`` (a program string written as a villanelle string) or
``text`` (a text already written as villanelle text). A ``typing.NewType`` (PEP 484): a str at run time, so a type
checker refuses a plain str where an edit takes config text, and the run-time check stays ``require_text``. Also the
one raise site of the argument type error (its message is generated: ``argument_type_message``). ``ConfigText`` itself
is generated (``villanelle._api.shared``). Shared
(spec/schema/api.json: ``quote`` and ``text`` are in the shared layer, as TypeScript's ``ts/src/text.ts``);
``ConfigText``, ``quote`` and ``text`` are public through ``villanelle``, the checks are private to the package."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle._api.errors import argument_type_message
from villanelle._api.shared import ConfigText
from villanelle._values import canonical_string


def require_text(value: object, *, member: str, parameter: str) -> str:
    """``value`` when it is a str; else TypeError naming ``member`` (as the caller wrote it) and ``parameter``."""
    if isinstance(value, str):
        return value
    raise TypeError(argument_type_message(member, parameter, type(value).__name__))


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
    return ConfigText(canonical_string(require_text(text, member="quote", parameter="text")))


def text(raw: str, /) -> ConfigText:
    return ConfigText(require_text(raw, member="text", parameter="raw"))
