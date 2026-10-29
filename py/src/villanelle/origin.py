"""Where text was written, and how it got to where a program reads it (round 11, slices.md "Shared primitives").

Pure data, shared by the low level and the rendered layer: every expanded value, directive and diagnostic carries
one of these.
"""

from __future__ import annotations

from dataclasses import dataclass

from villanelle._api.kinds import StepKind
from villanelle.span import SourceSpan


@dataclass(frozen=True, slots=True)
class Place:
    """A range of one file's text."""

    resolved_path: str
    """The file's identity, as the document source gave it."""
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class Override:
    """A value the program passed in at load or with ``set_override`` (``rasl --set host=10.0.60.30``): written in
    no file."""

    variable: str
    """The variable's name, without ``$``."""


@dataclass(frozen=True, slots=True)
class Step:
    """One expansion a directive or value went through to reach where it is read: ``variable`` (``$pixels`` replaced
    by its value), ``use`` (a snippet's body spliced) or ``extension`` (files spliced by an extension line)."""

    kind: StepKind
    name: str
    """The variable (without ``$``), snippet or extension directive name."""
    place: Place
    """Where the reference was written: the ``$pixels`` token, the ``use`` line's name, the ``include`` line's name."""


@dataclass(frozen=True, slots=True)
class Origin:
    """Where a value was written, and how it got here. For a value from a variable, ``place`` is the value's text in
    its ``set`` (the definition) or the override, and ``via[0]`` is the ``$name`` (the use site)."""

    place: Place | Override
    via: tuple[Step, ...]
    """Innermost first. Empty when the text is read where it was written."""


@dataclass(frozen=True, slots=True)
class DirectiveOrigin:
    """A directive's origin: its name is always written in a file, never an override."""

    place: Place
    via: tuple[Step, ...]


__all__ = ["DirectiveOrigin", "Origin", "Override", "Place", "Step", "StepKind"]
