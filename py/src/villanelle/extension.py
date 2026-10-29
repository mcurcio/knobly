"""Extensions (spec 5), shared by the low level and the rendered layer: an extension owns one directive name and
turns each use of it into specs of files to splice in its place. An extension use names no rendered type: its values
are shared ``ExpandedValue``s."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from villanelle.origin import DirectiveOrigin
from villanelle.value import ExpandedValue


@dataclass(frozen=True, slots=True)
class ExtensionUse:
    """One use of an extension directive, as the extension sees it."""

    values: tuple[ExpandedValue, ...]
    """The directive's values, expanded."""
    origin: DirectiveOrigin


class Extension(Protocol):
    """An extension (R20): owns one directive name and turns each use of it into specs of files to splice in its
    place. Pure: the load resolves and reads the specs through its document source, parses each file once, applies
    the use's block of ``set`` lines, and enforces depth, cycles and limits. While registered, the name is reserved at
    a line's start, as ``set``, ``snippet`` and ``use`` are."""

    @property
    def directive(self) -> str: ...

    def specs(self, use: ExtensionUse, /) -> Sequence[str]:
        """The specs for one use, in splice order. Raise DiagnosticError for a located failure; any other exception
        becomes E3006 at the directive."""
        ...


__all__ = ["Extension", "ExtensionUse"]
