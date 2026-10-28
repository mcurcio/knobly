"""Value kinds, and the values of a slice and an index. Programs read values through the load layer's ``Argument``
(``villanelle.directives``); the rules each reader applies live in ``villanelle._values``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class ValueKind(StrEnum):
    WORD = "word"
    STRING = "string"
    LIST = "list"
    """``[0.04, 1, 0.5]``: read through ``Argument.as_list()``."""
    SLICE = "slice"
    INDEX = "index"


@dataclass(frozen=True, slots=True)
class SliceValue:
    """``name[start:end]``, ``name[start:]`` or ``name[:end]``; the absent side is None. An argument's origin says
    where it was written."""

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
