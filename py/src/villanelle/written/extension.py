"""Extensions (spec 5), owned by the low level (vil-umh.8): an extension owns one directive name and turns each use of
it into specs of files to splice in its place. Pure, like the rest of the expansion: the load resolves and reads the
specs through its document source. An extension use holds the low level's expanded values and names no rendered
type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from villanelle.origin import DirectiveOrigin
from villanelle.written.value import ExpandedValue


@dataclass(frozen=True, slots=True)
class ExtensionUse:
    """One use of an extension directive, as the extension sees it."""

    values: tuple[ExpandedValue, ...]
    """The directive's values, expanded, with their links."""
    origin: DirectiveOrigin


class Extension(Protocol):
    """An extension (R20): owns one directive name and turns each use of it into specs of files to splice in its
    place. Pure: the load resolves and reads the specs through its document source, parses each file once, applies
    the use's block of ``set`` lines, and enforces depth, cycles and limits. While registered, the name is reserved at
    a line's start, as ``set``, ``snippet`` and ``use`` are."""

    @property
    def directive(self) -> str: ...

    def specs(self, use: ExtensionUse, /) -> tuple[str, ...]:
        """The specs for one use, in splice order. Raise DiagnosticError for a located failure; any other exception,
        or a result that is not a sequence of str (a bare ``str`` included, checked at run time), becomes E3006 at the
        directive."""
        ...


__all__ = ["Extension", "ExtensionUse"]
