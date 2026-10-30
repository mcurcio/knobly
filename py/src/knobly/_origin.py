"""Where text was written, and how it got to where a program reads it (round 11, slices.md "Shared primitives").

Pure data, shared by the low level and the rendered layer: every expanded value, directive and diagnostic carries
one of these. ``Origin`` and ``DirectiveOrigin`` are generated records (``knobly._api.shared``); ``Place``,
``Override`` and ``Step`` carry a people form, so the generator writes Protocols for them and these dataclasses
subclass those (each field is ``= field()``: without it the Protocol's property would become the field's default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from knobly._api import shared
from knobly._api.kinds import PlaceKind, StepKind
from knobly._api.shared import SourceSpan


@dataclass(frozen=True, slots=True)
class Place(shared.Place):
    resolved_path: str = field()
    """The file's identity, as the document source gave it."""
    span: SourceSpan = field()

    @property
    def kind(self) -> Literal[PlaceKind.FILE]:
        return PlaceKind.FILE

    def __str__(self) -> str:
        start = self.span.start
        return f"{self.resolved_path}:{start.line + 1}:{start.column + 1}"


@dataclass(frozen=True, slots=True)
class Override(shared.Override):
    variable: str = field()
    """The variable's name, without ``$``."""

    @property
    def kind(self) -> Literal[PlaceKind.OVERRIDE]:
        return PlaceKind.OVERRIDE

    def __str__(self) -> str:
        return f"override {self.variable}"


@dataclass(frozen=True, slots=True)
class Step(shared.Step):
    kind: StepKind = field()
    name: str = field()
    """The variable (without ``$``), snippet or extension directive name."""
    place: Place = field()
    """Where the reference was written: the ``$pixels`` token, the ``@use`` keyword, the ``@include`` token."""

    def __str__(self) -> str:
        return f"{self.kind} {self.name} at {self.place}"


__all__ = ["Override", "Place", "Step"]
