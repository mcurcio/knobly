"""Every error class the package defines (spec/contract.md 4), shared by all layers, under one base class,
``VillanelleError``, so one ``except`` clause catches them all. The program-bug groups raise the language's own
classes instead (``TypeError`` for an argument of the wrong type, ``ValueError`` for misuse, ``IndexError`` for an
index out of range), which are not under it. The same tree as TypeScript's ``ts/src/errors.ts``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from villanelle.diagnostics import Diagnostic
    from villanelle.report import LocatedDiagnostic


class VillanelleError(Exception):
    """The base of every error class villanelle defines. Never raised by itself."""


class DiagnosticError(VillanelleError):
    """A problem the config text decides, raised by a reader given a value of the wrong kind or spelling, or a
    program's own ``error(...)``: carries one located diagnostic."""

    diagnostic: LocatedDiagnostic

    def __init__(self, diagnostic: LocatedDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class ReadError(VillanelleError):
    """``load`` could not resolve the root path to exactly one file, or could not read it. ``paths`` is the root path
    as given to ``load``; ``__cause__`` is the source's failure (None when it resolved no file or several). No
    diagnostic and no code: a missing root file is not an extension line's failure."""

    def __init__(self, message: str, paths: Sequence[str]) -> None:
        super().__init__(message)
        self.paths: tuple[str, ...] = tuple(paths)


class SaveError(VillanelleError):
    """The writer failed. No document's ``saved_text`` changed. ``paths`` are the resolved paths handed to the writer,
    in batch order; ``__cause__`` is what the writer raised."""

    def __init__(self, message: str, paths: Sequence[str]) -> None:
        super().__init__(message)
        self.paths: tuple[str, ...] = tuple(paths)


class EditError(VillanelleError, ValueError):
    """Base of the refusals of an edit; nothing changed when one is raised. Also a ``ValueError``: a refused text is a
    bad value."""


class BadTextError(EditError):
    """The text given to an edit, or an override's text, is not what it takes: a syntax error, values where
    statements go (or the other way), a line break that would end the statement, or a text-alone rule broken
    (E5002, E5005, E5009-E5011). ``diagnostics`` are located in the given text, in code points, with the codes a
    load gives."""

    def __init__(self, message: str, diagnostics: Sequence[Diagnostic]) -> None:
        super().__init__(message)
        self.diagnostics: tuple[Diagnostic, ...] = tuple(diagnostics)


class DetachedError(VillanelleError, ReferenceError):
    """The handle's tokens were removed by an edit, or its document's whole text was replaced. Raised by every member
    but ``kind``. Also a ``ReferenceError``, the error a dead ``weakref`` proxy raises; not an edit error."""


__all__ = [
    "BadTextError",
    "DetachedError",
    "DiagnosticError",
    "EditError",
    "ReadError",
    "SaveError",
    "VillanelleError",
]
