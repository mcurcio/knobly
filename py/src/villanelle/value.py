"""Values after expansion, shared by the low level and the rendered layer (spec 2.9): the value kinds, the values of
a slice and an index, and ``ExpandedValue`` with its readers. An extension use holds expanded values; the rendered
layer's ``Argument`` builds on one. The rules each reader applies live in ``villanelle._values``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeAlias

from villanelle import _values
from villanelle._api.codes import MESSAGES
from villanelle._api.kinds import ValueKind
from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.origin import Origin, Place
from villanelle.report import LocatedDiagnostic, check_program_code


@dataclass(frozen=True, slots=True)
class SliceValue:
    """``name[start:end]``, ``name[start:]`` or ``name[:end]``; the absent side is None. A value's origin says where
    it was written."""

    kind: ClassVar[ValueKind] = ValueKind.SLICE
    name: str
    start: int | None
    end: int | None


@dataclass(frozen=True, slots=True)
class IndexValue:
    """``name[index]``: one element (vil-9ze.2)."""

    kind: ClassVar[ValueKind] = ValueKind.INDEX
    name: str
    index: int


PlainValue: TypeAlias = "int | float | bool | str | SliceValue | IndexValue | tuple[PlainValue, ...]"
"""A value by villanelle's one rule. Quoting means text: ``"8080"`` and ``"true"`` are str; only a bare word is read
as a number (NumberText) or as true/false (BooleanText)."""

Held: TypeAlias = "str | tuple[ExpandedValue, ...] | SliceValue | IndexValue"
"""What an expanded value holds, by kind: a word's text, a string's decoded text, a list's items, a slice or an
index. Private to the package."""


class ExpandedValue:
    """One value after expansion: a ``$name`` has already become its value(s). Plain data; it holds no low-level
    handle. Its ``kind`` is never ``ValueKind.REFERENCE``. Invariants checked at load, so readers never meet them: a
    string's escapes are the six of EscapeText; a slice bound is an IntegerText. Match it:
    ``case vl.ExpandedValue("word", "true"):``."""

    __match_args__ = ("kind", "text")
    __slots__ = ("_kind", "_origin", "_text", "_value")

    def __init__(self, kind: ValueKind, value: Held, origin: Origin) -> None:
        """Made by the binding and the rendered layer only."""
        self._kind = kind
        self._value = value
        self._origin = origin
        self._text = _canonical_text(kind, value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._kind.value!r}, {self._text!r})"

    @property
    def kind(self) -> ValueKind:
        return self._kind

    @property
    def text(self) -> str:
        """The canonical text, the same in every binding (spec 2.9). Comments and line breaks are never part of it.
        Two values are the same exactly when their texts are equal."""
        return self._text

    @property
    def origin(self) -> Origin:
        return self._origin

    def as_word(self) -> str:
        """A bare word. Raises DiagnosticError E4002 for any other kind."""
        return self._word("a word")

    def as_str(self) -> str:
        """A word or a string, decoded. Raises DiagnosticError E4002 for a list, slice or index."""
        if isinstance(self._value, str):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a word or a string, not a {self._kind}")

    def as_number(self) -> int | float:
        """A word spelling a NumberText: int without fraction or exponent, else float. E4002, E4004."""
        number = _values.number_of(self._word("a number"))
        if number is None:
            raise self._problem(DiagnosticCode.NOT_A_NUMBER, self._text)
        return number

    def as_int(self) -> int:
        """A word spelling an IntegerText. E4002, E4005."""
        integer = _values.integer_of(self._word("an integer"))
        if integer is None:
            raise self._problem(DiagnosticCode.NOT_AN_INTEGER, self._text)
        return integer

    def as_bool(self) -> bool:
        """The word ``true`` or ``false``. E4002, E4006."""
        boolean = _values.boolean_of(self._word("true or false"))
        if boolean is None:
            raise self._problem(DiagnosticCode.NOT_A_BOOLEAN, self._text)
        return boolean

    def as_list(self) -> tuple[ExpandedValue, ...]:
        """A list's items, each with its own origin. E4002 for any other kind."""
        if isinstance(self._value, tuple):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a list, not a {self._kind}")

    def as_slice(self) -> SliceValue | IndexValue:
        """A slice or an index. E4002 for any other kind."""
        if isinstance(self._value, SliceValue | IndexValue):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a slice or an index, not a {self._kind}")

    def plain(self) -> PlainValue:
        """Any value by the one rule: a string is its str; a word is a number if it spells a NumberText, a bool if
        ``true``/``false``, else its str; a list is a tuple of its items read the same way; a slice or an index is its
        value. Never raises."""
        value = self._value
        if isinstance(value, tuple):
            return tuple(item.plain() for item in value)
        if self._kind is ValueKind.WORD and isinstance(value, str):
            number = _values.number_of(value)
            if number is not None:
                return number
            boolean = _values.boolean_of(value)
            return value if boolean is None else boolean
        return value

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report, placed on this value (for an override's value: on the ``$name`` that
        used it). Raises ValueError at once when ``code`` has no "/" (villanelle's codes are its own)."""
        check_program_code(code)
        return value_error(self, code, message)

    def _word(self, wanted: str) -> str:
        if self._kind is ValueKind.WORD and isinstance(self._value, str):
            return self._value
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected {wanted}, not a {self._kind}")

    def _problem(self, code: DiagnosticCode, detail: str) -> DiagnosticError:
        return value_error(self, code, f"{MESSAGES[code]}: {detail}")


def value_error(value: ExpandedValue, code: DiagnosticCode | str, message: str) -> DiagnosticError:
    """A located error placed on a value. An override is written in no file: the problem is placed on the ``$name``
    that used it (``via[0]``) and the message names the variable. Private to the package."""
    place, via = value.origin.place, value.origin.via
    if isinstance(place, Place):
        return DiagnosticError(LocatedDiagnostic(code, message, place, via))
    return DiagnosticError(LocatedDiagnostic(code, f"{message} (override ${place.variable})", via[0].place, via[1:]))


def _canonical_text(kind: ValueKind, value: Held) -> str:
    """The canonical text of a value (spec 2.9)."""
    if isinstance(value, tuple):
        return _values.canonical_list(item.text for item in value)
    if isinstance(value, SliceValue):
        return _values.canonical_slice(value.name, value.start, value.end)
    if isinstance(value, IndexValue):
        return _values.canonical_index(value.name, value.index)
    return _values.canonical_string(value) if kind is ValueKind.STRING else value


__all__ = ["ExpandedValue", "IndexValue", "PlainValue", "SliceValue", "ValueKind"]
