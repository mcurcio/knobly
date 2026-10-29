"""Values after expansion, shared by the low level and the rendered layer (spec 2.9): one class per value kind
(``ExpandedWord``, ``ExpandedString``, ``ExpandedList``, ``ExpandedSlice``, ``ExpandedIndex``; the union
``ExpandedValue``), each with the readers, and the plain values of a slice and an index. An extension use holds
expanded values; the rendered layer's arguments build on them. The rules each reader applies live in
``villanelle._values``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal, TypeAlias

from villanelle import _values
from villanelle._api.codes import MESSAGES
from villanelle._api.kinds import ValueKind
from villanelle.diagnostics import DiagnosticCode
from villanelle.errors import DiagnosticError
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


class _Expanded:
    """What every expanded value has: ``kind``, ``text``, ``origin``, the readers and ``error``. Private: the public
    type is the union ``ExpandedValue``. Invariants checked at load, so readers never meet them: a string's escapes are
    the six of EscapeText; a slice bound is an IntegerText. (The readers ``list`` and ``slice`` shadow the builtins in
    this class body: no annotation below names them.)"""

    __slots__ = ("_origin", "_text")

    _origin: Origin
    _text: str

    def __init__(self, text: str, origin: Origin) -> None:
        self._text = text
        self._origin = origin

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._text!r})"

    @property
    def kind(self) -> ValueKind:
        raise NotImplementedError

    @property
    def text(self) -> str:
        """The canonical text, the same in every binding (spec 2.9). Comments and line breaks are never part of it.
        Two values are the same exactly when their texts are equal."""
        return self._text

    @property
    def origin(self) -> Origin:
        return self._origin

    def word(self) -> str:
        """A bare word. Raises DiagnosticError E4002 for any other kind."""
        return self._word("a word")

    def string(self) -> str:
        """A word or a string, decoded. Raises DiagnosticError E4002 for a list, slice or index."""
        if isinstance(self, ExpandedString):
            return self._value
        if isinstance(self, ExpandedWord):
            return self._text
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a word or a string, not a {self.kind}")

    def number(self) -> int | float:
        """A word spelling a NumberText (spec/contract.md 3): an int without fraction or exponent within
        ±(2**53 - 1), else a float, never ``-0.0``. E4002; E4004, also for a value beyond the double range
        (``1e400``)."""
        number = _values.number_of(self._word("a number"))
        if number is None:
            raise self._problem(DiagnosticCode.NOT_A_NUMBER, self._text)
        return number

    def integer(self) -> int:
        """A word spelling an IntegerText within ±(2**53 - 1). E4002, E4005."""
        integer = _values.integer_of(self._word("an integer"))
        if integer is None:
            raise self._problem(DiagnosticCode.NOT_AN_INTEGER, self._text)
        return integer

    def boolean(self) -> bool:
        """The word ``true`` or ``false``. E4002, E4006."""
        boolean = _values.boolean_of(self._word("true or false"))
        if boolean is None:
            raise self._problem(DiagnosticCode.NOT_A_BOOLEAN, self._text)
        return boolean

    def list(self) -> tuple[ExpandedValue, ...]:
        """A list's items (its ``items``), each with its own origin. E4002 for any other kind."""
        if isinstance(self, ExpandedList):
            return self._items
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a list, not a {self.kind}")

    def slice(self) -> SliceValue | IndexValue:
        """A slice or an index. E4002 for any other kind."""
        if isinstance(self, ExpandedSlice):
            return SliceValue(self._name, self._start, self._end)
        if isinstance(self, ExpandedIndex):
            return IndexValue(self._name, self._index)
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected a slice or an index, not a {self.kind}")

    def plain(self) -> PlainValue:
        """Any value by the one rule: a string is its str; a word is a number when ``number()`` would accept it, a
        bool when ``true``/``false``, else its str (``1e400`` stays text); a list is a tuple of its items read the same
        way; a slice or an index is its value. Never raises."""
        if isinstance(self, ExpandedList):
            return tuple(item.plain() for item in self._items)
        if isinstance(self, ExpandedWord):
            number = _values.number_of(self._text)
            if number is not None:
                return number
            boolean = _values.boolean_of(self._text)
            return self._text if boolean is None else boolean
        if isinstance(self, ExpandedString):
            return self._value
        return self.slice()

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report, placed on this value (for an override's value: on the ``$name`` that
        used it). Raises ValueError at once when ``code`` has no "/" (villanelle's codes are its own)."""
        check_program_code(code)
        return value_error(self, code, message)

    def _word(self, wanted: str) -> str:
        if isinstance(self, ExpandedWord):
            return self._text
        raise self._problem(DiagnosticCode.WRONG_VALUE_KIND, f"expected {wanted}, not a {self.kind}")

    def _problem(self, code: DiagnosticCode, detail: str) -> DiagnosticError:
        return value_error(self, code, f"{MESSAGES[code]}: {detail}")


class ExpandedWord(_Expanded):
    """A bare word. Match it: ``case ExpandedWord("true"):``."""

    __match_args__ = ("text",)
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.WORD]:
        return ValueKind.WORD


class ExpandedString(_Expanded):
    """A quoted string: ``text`` is its canonical quoted text, ``string()`` the decoded text."""

    __match_args__ = ("text",)
    __slots__ = ("_value",)

    _value: str

    def __init__(self, value: str, origin: Origin) -> None:
        """``value`` is the decoded text."""
        super().__init__(_values.canonical_string(value), origin)
        self._value = value

    @property
    def kind(self) -> Literal[ValueKind.STRING]:
        return ValueKind.STRING


class ExpandedList(_Expanded):
    """A list: ``items`` are its values, each with its own origin."""

    __match_args__ = ("items",)
    __slots__ = ("_items",)

    _items: tuple[ExpandedValue, ...]

    def __init__(self, items: tuple[ExpandedValue, ...], origin: Origin) -> None:
        super().__init__(_values.canonical_list(item.text for item in items), origin)
        self._items = items

    @property
    def kind(self) -> Literal[ValueKind.LIST]:
        return ValueKind.LIST

    @property
    def items(self) -> tuple[ExpandedValue, ...]:
        return self._items


class ExpandedSlice(_Expanded):
    """``name[start:end]``; an absent side is None."""

    __match_args__ = ("name", "start", "end")
    __slots__ = ("_end", "_name", "_start")

    _name: str
    _start: int | None
    _end: int | None

    def __init__(self, name: str, start: int | None, end: int | None, origin: Origin) -> None:
        super().__init__(_values.canonical_slice(name, start, end), origin)
        self._name = name
        self._start = start
        self._end = end

    @property
    def kind(self) -> Literal[ValueKind.SLICE]:
        return ValueKind.SLICE

    @property
    def name(self) -> str:
        return self._name

    @property
    def start(self) -> int | None:
        return self._start

    @property
    def end(self) -> int | None:
        return self._end


class ExpandedIndex(_Expanded):
    """``name[index]``: one element."""

    __match_args__ = ("name", "index")
    __slots__ = ("_index", "_name")

    _name: str
    _index: int

    def __init__(self, name: str, index: int, origin: Origin) -> None:
        super().__init__(_values.canonical_index(name, index), origin)
        self._name = name
        self._index = index

    @property
    def kind(self) -> Literal[ValueKind.INDEX]:
        return ValueKind.INDEX

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._index


ExpandedValue: TypeAlias = ExpandedWord | ExpandedString | ExpandedList | ExpandedSlice | ExpandedIndex
"""One value after expansion: a ``$name`` has already become its value(s). Plain data; it holds no low-level handle.
Its kind is never ``reference``. Match it by class: ``case ExpandedWord("true"):``."""


def value_error(value: _Expanded, code: DiagnosticCode | str, message: str) -> DiagnosticError:
    """A located error placed on a value. An override is written in no file: the problem is placed on the ``$name``
    that used it (``via[0]``) and the message names the variable. Private to the package."""
    place, via = value.origin.place, value.origin.via
    if isinstance(place, Place):
        return DiagnosticError(LocatedDiagnostic(code, message, place, via))
    return DiagnosticError(LocatedDiagnostic(code, f"{message} (override ${place.variable})", via[0].place, via[1:]))


__all__ = [
    "ExpandedIndex",
    "ExpandedList",
    "ExpandedSlice",
    "ExpandedString",
    "ExpandedValue",
    "ExpandedWord",
    "IndexValue",
    "PlainValue",
    "SliceValue",
    "ValueKind",
]
