"""Positions: a binding's own string unit to the corpus's UTF-16 units (spec/contract.md 1), in one place.

An adapter reports every position as ``[line, column, offset]`` in its binding's unit (its ``hello`` names the unit).
The driver converts each one with the text it counts in: the document's text, or the text an edit was given.
Lines do not depend on the unit, so only the column and the offset change.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

UNITS = ("utf-16", "code point", "byte")


def utf16_length(text: str) -> int:
    """How many UTF-16 code units ``text`` is: a character above U+FFFF counts two, a lone surrogate one."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def native_length(text: str, unit: str) -> int:
    """How long ``text`` is in ``unit``."""
    if unit == "utf-16":
        return utf16_length(text)
    if unit == "code point":
        return len(text)
    if unit == "byte":
        return len(text.encode("utf-8", "surrogatepass"))
    raise ValueError(f"unknown unit {unit!r}")


class Converter:
    """Native offsets of one text to UTF-16 offsets. Built once per (text, unit); an offset inside a character fails."""

    def __init__(self, text: str, unit: str) -> None:
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit!r}")
        self.unit = unit
        self.native_end = native_length(text, unit)
        self._map: Dict[int, int] | None = None
        if unit != "utf-16":
            mapping: Dict[int, int] = {0: 0}
            native = utf16 = 0
            for ch in text:
                native += 1 if unit == "code point" else len(ch.encode("utf-8", "surrogatepass"))
                utf16 += 1 if ord(ch) <= 0xFFFF else 2
                mapping[native] = utf16
            self._map = mapping

    def offset(self, native: int) -> int:
        if not 0 <= native <= self.native_end:
            raise ValueError(f"offset {native} outside the text (0 to {self.native_end} {self.unit} units)")
        if self._map is None:
            return native
        if native not in self._map:
            raise ValueError(f"offset {native} is inside a character ({self.unit} units)")
        return self._map[native]

    def position(self, pos: Sequence[int]) -> Tuple[int, int, int]:
        """``[line, column, offset]`` in the native unit to ``(line, column, offset)`` in UTF-16 units."""
        line, column, offset = pos
        end = self.offset(offset)
        return line, end - self.offset(offset - column), end


class Converters:
    """A small cache of converters by text, for one binding's unit."""

    def __init__(self, unit: str) -> None:
        self.unit = unit
        self._cache: Dict[str, Converter] = {}

    def __call__(self, text: str) -> Converter:
        found = self._cache.get(text)
        if found is None:
            if len(self._cache) > 64:
                self._cache.clear()
            found = self._cache[text] = Converter(text, self.unit)
        return found


def line_column(conv: Converter, pos: Sequence[int]) -> List[int]:
    """``[line, column]`` of a native position, the column in UTF-16 units."""
    line, column, _ = conv.position(pos)
    return [line, column]
