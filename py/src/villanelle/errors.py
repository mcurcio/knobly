"""Every error class the package defines (spec 2.8, spec/contract.md 4), on the spec's two sorts. An **expected
outcome** (the input or the outside world decides it) is under the one base class ``VillanelleError``, so one
``except VillanelleError`` clause catches every outcome and no bug. A **program bug** (the program could have checked
first) is outside it: ``DetachedError`` (a ``ReferenceError``), and the language's own ``TypeError`` (an argument of
the wrong type), ``ValueError`` (misuse: every bad name among them) and ``IndexError`` (an index out of range). Prior
art: Midori's "bugs are not recoverable errors" (Joe Duffy), Rust's panic against ``Result``. The same tree as
TypeScript's ``ts/src/errors.ts``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from villanelle.diagnostics import Diagnostic
    from villanelle.report import LocatedDiagnostic


class VillanelleError(Exception):
    """The base of every expected-outcome class villanelle defines, and of nothing else. Never raised by itself."""


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


class BadTextError(VillanelleError):
    """The text given to an edit, or an override's text, is not what it takes: its entry rule's first error (spec
    2.8), values where statements go (or the other way), or a text-alone rule broken (E5002, E5005, E5009-E5011).
    Nothing changed. ``diagnostics`` are located in the given text, in code points, with the codes a load gives; the
    message is built from them: ``bad text: 1:2: E2001: unexpected token: ";"`` (each diagnostic's people form,
    joined by ``; ``). Not a ``ValueError``: that is misuse, a program bug."""

    def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
        self.diagnostics: tuple[Diagnostic, ...] = tuple(diagnostics)
        super().__init__("bad text: " + "; ".join(str(d) for d in self.diagnostics))


class SaveError(VillanelleError):
    """The writer failed. No document's ``saved_text`` changed. ``paths`` are the resolved paths handed to the writer,
    in batch order; ``__cause__`` is what the writer raised."""

    def __init__(self, message: str, paths: Sequence[str]) -> None:
        super().__init__(message)
        self.paths: tuple[str, ...] = tuple(paths)


class LostUpdateError(SaveError):
    """A file the save would write changed since it was read or last saved (spec 4.2): its text in the medium now
    differs from its ``saved_text``. ``paths`` are only the conflicting files, in batch order; no cause. Raised by
    ``check_lost_updates`` inside every writer, before it writes anything; ``save`` raises it as it is."""

    def __init__(self, paths: Sequence[str]) -> None:
        super().__init__(f"lost update: changed since read: {', '.join(paths)}", paths)


class DetachedError(ReferenceError):
    """A program bug, outside ``VillanelleError``: the handle's tokens were removed by an edit, or its document's
    whole text was replaced, and a member but ``kind`` was used. A ``ReferenceError``, the error a dead ``weakref``
    proxy raises: a reference that no longer leads anywhere."""


__all__ = [
    "BadTextError",
    "DetachedError",
    "DiagnosticError",
    "LostUpdateError",
    "ReadError",
    "SaveError",
    "VillanelleError",
]
