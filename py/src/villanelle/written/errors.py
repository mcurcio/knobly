"""The low level's errors (round 12 design.md §6; slices.md S3). An edit that raises an ``EditError`` changed
nothing. The same classes as TypeScript's ``ts/src/written/errors.ts``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from villanelle.diagnostics import Diagnostic, DiagnosticError

if TYPE_CHECKING:
    from villanelle.report import LocatedDiagnostic
    from villanelle.source import FileWrite


class EditError(ValueError):
    """Base of the errors an edit raises. Nothing changed when one is raised."""


class BadTextError(EditError):
    """The text given to an edit, or an override's text, is not what it takes: a syntax error, values where
    statements go (or the other way), or a text-alone rule broken (E5002, E5005, E5009-E5011). ``diagnostics`` are
    located in the given text, with the codes a load gives."""

    def __init__(self, message: str, diagnostics: Sequence[Diagnostic]) -> None:
        super().__init__(message)
        self.diagnostics: tuple[Diagnostic, ...] = tuple(diagnostics)


class DetachedError(EditError):
    """The handle's tokens were removed by an edit, or its document's whole text was replaced."""


class NoSetLineError(EditError):
    """``Variable.set`` or ``Variable.rename`` on a parameter (edit the ``use`` line) or an override (use
    ``DocumentGraph.set_override``)."""


class SaveError(Exception):
    """The writer raised. No document's ``saved_text`` changed. ``__cause__`` is what the writer raised."""

    def __init__(self, message: str, files: Sequence[FileWrite]) -> None:
        super().__init__(message)
        self.files: tuple[FileWrite, ...] = tuple(files)


class ReadError(DiagnosticError):
    """``load`` could not read the root file: E3004 placed at the root path, as before."""

    def __init__(self, diagnostic: LocatedDiagnostic) -> None:
        super().__init__(diagnostic)
