"""Values after expansion (spec 2.9), owned by the low level (vil-umh.8): one class per value kind
(``ExpandedWord``, ``ExpandedString``, ``ExpandedList``, ``ExpandedSlice``, ``ExpandedIndex``; the union
``ExpandedValue``), each with the readers and three links to the lines it came through (``written``, ``definition``,
``chain``); the values a slice's and an index's reader returns are generated records (``SliceValue``,
``IndexValue``). An extension use holds them, a directive expansion's ``values`` are them, and a rendered directive's
``values`` are the same objects: one family, one home of the readers. Each class implements its generated Protocol.
Two expanded values are equal exactly when their canonical texts are (``==`` and ``hash``). The rules each reader
applies live in ``villanelle._values``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeAlias

from villanelle import _values
from villanelle._api import written as api
from villanelle._api.codes import DiagnosticCode, describe
from villanelle._api.errors import DiagnosticError
from villanelle._api.kinds import ValueKind
from villanelle._api.shared import Origin
from villanelle._api.written import IndexValue, SliceValue
from villanelle._origin import Override, Step
from villanelle._report import LocatedDiagnostic, check_program_code

if TYPE_CHECKING:
    from villanelle._api.written import ReferenceResolution
    from villanelle.written._model import WrittenValue


class _Expanded:
    """What every expanded value has: ``kind``, ``text``, ``origin``, the links, the readers and ``error``. Private:
    the public type is the union ``ExpandedValue``. Made by the low level's expansion only. Invariants the grammar
    checks, so readers never meet them: a string's escapes are the six of EscapeText (E1005 otherwise); a literal
    slice bound is an INTEGER (E2007 otherwise). (The readers ``list`` and ``slice`` shadow the builtins in this
    class body: no annotation below names them.)"""

    __slots__ = ("_chain", "_definition", "_origin", "_text")

    _origin: Origin
    _text: str
    _definition: WrittenValue | None
    _chain: tuple[ReferenceResolution, ...]

    def __init__(
        self,
        text: str,
        origin: Origin,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        self._text = text
        self._origin = origin
        self._definition = definition
        self._chain = chain

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._text!r})"

    def __eq__(self, other: object) -> bool:
        """Two expanded values are the same exactly when their canonical texts are equal (spec 2.9), whatever their
        origins and links."""
        if not isinstance(other, _Expanded):
            return NotImplemented
        return self._text == other._text

    def __hash__(self) -> int:
        return hash(self._text)

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

    @property
    def written(self) -> WrittenValue:
        """The written value on the same line: for a value that came through a variable, the ``$name`` there
        (``chain[0].reference``; a list item shares its list's); otherwise the value itself, also its ``definition``.
        Never None. Editing it edits that one written line, which every copy of the line shares: a file included
        twice has one line read in both copies (``written.statement.copies()``), so the edit shows in both. To change
        one copy only, edit what that copy is given instead (its include block's ``set``, at the include step of
        ``chain``). A live handle: the value itself is a snapshot of one expansion."""
        written = self._chain[0].reference if self._chain else self._definition
        assert written is not None, "an expanded value a program reads always has a line"
        return written

    @property
    def definition(self) -> WrittenValue | None:
        """The written value at the end of its chain (for ``$pixels``, the ``2284`` of its ``set``); None for an
        override. Editing it changes every use."""
        return self._definition

    @property
    def chain(self) -> tuple[ReferenceResolution, ...]:
        """One per variable step of ``origin.via``, from this value's own line toward where it is written:
        ``[0]`` is the ``$name`` written on the directive's line. Empty for a value read where it is written."""
        return self._chain

    def _moved(self, drop: int, append: tuple[Step, ...], resolution: ReferenceResolution | None) -> ExpandedValue:
        """The same value having travelled further (private to the low level's expansion): the last ``drop`` steps of
        its origin (and of each list item's) are replaced by ``append``, and ``resolution`` (a ``$name`` read) goes
        first in the chain."""
        via = self._origin.via
        origin = Origin(self._origin.place, via[: len(via) - drop] + append)
        chain = self._chain if resolution is None else (resolution, *self._chain)
        return self._remade(origin, chain, drop, append, resolution)

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        raise NotImplementedError

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
        described = describe(code, detail)
        return value_error(self, described.code, described.message)


class ExpandedWord(_Expanded, api.ExpandedWord):
    """A bare word. Match it: ``case ExpandedWord("true"):``."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.WORD]:
        return ValueKind.WORD

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        return ExpandedWord(self._text, origin, self._definition, chain)


class ExpandedString(_Expanded, api.ExpandedString):
    """A quoted string: ``text`` is its canonical quoted text, ``string()`` the decoded text."""

    __slots__ = ("_value",)

    _value: str

    def __init__(
        self,
        value: str,
        origin: Origin,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        """``value`` is the decoded text."""
        super().__init__(_values.canonical_string(value), origin, definition, chain)
        self._value = value

    @property
    def kind(self) -> Literal[ValueKind.STRING]:
        return ValueKind.STRING

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        return ExpandedString(self._value, origin, self._definition, chain)


class ExpandedList(_Expanded, api.ExpandedList):
    """A list: ``items`` are its values, each with its own origin and links."""

    __slots__ = ("_items",)

    _items: tuple[ExpandedValue, ...]

    def __init__(
        self,
        items: tuple[ExpandedValue, ...],
        origin: Origin,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        super().__init__(_values.canonical_list(item.text for item in items), origin, definition, chain)
        self._items = items

    @property
    def kind(self) -> Literal[ValueKind.LIST]:
        return ValueKind.LIST

    @property
    def items(self) -> tuple[ExpandedValue, ...]:
        return self._items

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        items = tuple(item._moved(drop, append, resolution) for item in self._items)
        return ExpandedList(items, origin, self._definition, chain)


class ExpandedSlice(_Expanded, api.ExpandedSlice):
    """``name[start~end]``; an absent side is None. ``name`` is the word it slices (a ``$name`` written as the slice
    name is expanded to the one word it holds)."""

    __slots__ = ("_end", "_name", "_start")

    _name: str
    _start: int | None
    _end: int | None

    def __init__(
        self,
        name: str,
        start: int | None,
        end: int | None,
        origin: Origin,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        super().__init__(_values.canonical_slice(name, start, end), origin, definition, chain)
        self._name = name
        self._start = start
        self._end = end

    @property
    def kind(self) -> Literal[ValueKind.SLICE]:
        return ValueKind.SLICE

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        return ExpandedSlice(self._name, self._start, self._end, origin, self._definition, chain)

    @property
    def name(self) -> str:
        return self._name

    @property
    def start(self) -> int | None:
        return self._start

    @property
    def end(self) -> int | None:
        return self._end


class ExpandedIndex(_Expanded, api.ExpandedIndex):
    """``name[index]``: one element."""

    __slots__ = ("_index", "_name")

    _name: str
    _index: int

    def __init__(
        self,
        name: str,
        index: int,
        origin: Origin,
        definition: WrittenValue | None,
        chain: tuple[ReferenceResolution, ...],
    ) -> None:
        super().__init__(_values.canonical_index(name, index), origin, definition, chain)
        self._name = name
        self._index = index

    @property
    def kind(self) -> Literal[ValueKind.INDEX]:
        return ValueKind.INDEX

    def _remade(
        self,
        origin: Origin,
        chain: tuple[ReferenceResolution, ...],
        drop: int,
        append: tuple[Step, ...],
        resolution: ReferenceResolution | None,
    ) -> ExpandedValue:
        return ExpandedIndex(self._name, self._index, origin, self._definition, chain)

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._index


ExpandedValue: TypeAlias = ExpandedWord | ExpandedString | ExpandedList | ExpandedSlice | ExpandedIndex
"""One value after expansion: a ``$name`` has already become its value(s), with its links to the written lines it
came through. A snapshot that holds live handles. Its kind is never ``reference``. Match it by class:
``case ExpandedWord("true"):``."""


def value_error(value: _Expanded, code: DiagnosticCode | str, message: str) -> DiagnosticError:
    """A located error placed on a value. An override is written in no file: the problem is placed on the ``$name``
    that used it (``via[0]``) and the message names the variable. Private to the package (the include extension
    places E3005 with it)."""
    place, via = value.origin.place, value.origin.via
    if not isinstance(place, Override):
        return DiagnosticError(LocatedDiagnostic(code, message, place, via))
    return DiagnosticError(LocatedDiagnostic(code, f"{message} (override ${place.variable})", via[0].place, via[1:]))
