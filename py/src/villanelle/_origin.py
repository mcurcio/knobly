"""Where text was written, and how it got to where a program reads it (round 11, slices.md "Shared primitives").

Pure data, shared by the low level and the rendered layer: every expanded value, directive and diagnostic carries
one of these. ``Origin`` and ``DirectiveOrigin`` are generated records (``villanelle._api.shared``); ``Place``,
``Override`` and ``Step`` carry a people form, so the generator writes Protocols for them and these dataclasses
subclass those (each field is ``= field()``: without it the Protocol's property would become the field's default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from villanelle._api import shared
from villanelle._api.kinds import PlaceKind, StepKind
from villanelle._api.shared import SourceSpan


@dataclass(frozen=True, slots=True)
class Place(shared.Place):
    """A range of one file's text."""

    resolved_path: str = field()
    """The file's identity, as the document source gave it."""
    span: SourceSpan = field()

    @property
    def kind(self) -> Literal[PlaceKind.FILE]:
        return PlaceKind.FILE

    def __str__(self) -> str:
        """Its people form (spec/contract.md 2): ``path:line:col``, counting from 1, at the span's start. The one home
        of this form: every located thing's people form and ``format_diagnostic`` build on it."""
        start = self.span.start
        return f"{self.resolved_path}:{start.line + 1}:{start.column + 1}"


@dataclass(frozen=True, slots=True)
class Override(shared.Override):
    """A value the program passed in at load or with ``set_override`` (``rasl --set host=10.0.60.30``): written in
    no file."""

    variable: str = field()
    """The variable's name, without ``$``."""

    @property
    def kind(self) -> Literal[PlaceKind.OVERRIDE]:
        return PlaceKind.OVERRIDE

    def __str__(self) -> str:
        """Its people form: ``override <variable>`` (no ``$``)."""
        return f"override {self.variable}"


@dataclass(frozen=True, slots=True)
class Step(shared.Step):
    """One expansion a directive or value went through to reach where it is read: ``variable`` (``$pixels`` replaced
    by its value), ``use`` (a snippet's body spliced) or ``extension`` (files spliced by an extension line)."""

    kind: StepKind = field()
    name: str = field()
    """The variable (without ``$``), snippet or extension directive name."""
    place: Place = field()
    """Where the reference was written: the ``$pixels`` token, the ``@use`` keyword, the ``@include`` token."""

    def __str__(self) -> str:
        """Its people form: ``<kind> <name> at <place>`` (``variable pixels at main.conf:7:15``)."""
        return f"{self.kind} {self.name} at {self.place}"


__all__ = ["Override", "Place", "Step"]
