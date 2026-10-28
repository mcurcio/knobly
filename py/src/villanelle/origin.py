"""Where text was written, and how it got to where a program reads it (round 11, slices.md "Shared primitives").

Pure data: every directive, value and diagnostic of the load layer carries one of these.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from villanelle.span import SourceSpan


@dataclass(frozen=True, slots=True)
class Place:
    """A range of one file's text."""

    resolved_path: str
    """The file's identity, as the document source gave it."""
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Handed:
    """A value the program handed in at load (``rasl --set host=10.0.60.30``): written in no file."""

    variable: str
    """The variable's name, without ``$``."""


class StepKind(StrEnum):
    VARIABLE = "variable"
    """``$pixels`` was replaced by its value."""
    USE = "use"
    """``use twinkle rgb_150;`` spliced a snippet's body."""
    EXTENSION = "extension"
    """An extension directive (``include "palettes.conf";``) spliced files."""


@dataclass(frozen=True, slots=True)
class Step:
    """One expansion a directive or value went through to reach where it is read."""

    kind: StepKind
    name: str
    """The variable (without ``$``), snippet or extension directive name."""
    at: Place
    """Where the reference was written: the ``$pixels`` token, the ``use`` line's name, the ``include`` line's name."""


@dataclass(frozen=True, slots=True)
class Origin:
    """Where a value was written, and how it got here. For a value from a variable, ``written`` is the value's text in
    its ``set`` (the definition) or the handed-in variable, and ``via[0]`` is the ``$name`` (the use site)."""

    written: Place | Handed
    via: tuple[Step, ...]
    """Innermost first. Empty when the text is read where it was written."""


@dataclass(frozen=True, slots=True)
class DirectiveOrigin:
    """A directive's origin: its name is always written in a file, never handed in."""

    written: Place
    via: tuple[Step, ...]
