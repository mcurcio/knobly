"""Diagnostics of the load layer, and the one sink that load, value readers and programs all report into (round 11
review finding 2; R14's report helper). Prior art: HCL's ``hcl.Diagnostics``, PostCSS ``Result.messages``."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.graph import DocumentGraph
from villanelle.origin import Place, Step


@dataclass(frozen=True, slots=True)
class LocatedDiagnostic:
    """One located problem of a load: villanelle's or a program's. Always at a place in a file (design rule 3).

    ``code`` is a DiagnosticCode, or a program's own ``"<namespace>/<name>"`` (``"rasl/unknown-node"``). For a value
    handed in by the program, ``at`` is the ``$name`` that used it and the message names the variable."""

    code: DiagnosticCode | str
    message: str
    """For people; not part of the cross-language contract."""
    at: Place
    via: tuple[Step, ...]
    """The variables, uses and extension directives that brought the text to ``at``'s reader; innermost first."""

    def __post_init__(self) -> None:
        """Raise ValueError when ``code`` is neither a DiagnosticCode value nor a namespaced program code."""
        raise NotImplementedError("LocatedDiagnostic.__post_init__")


class Locatable(Protocol):
    """Anything a program can place a problem on: a directive, a value, or the whole load (its root file)."""

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report. Raises ValueError when ``code`` has no "/"."""
        ...


class Collecting:
    """``with problems.collecting(): ...``: a DiagnosticError raised inside is recorded and the block ends; any other
    exception passes through. A class (not ``@contextmanager``) so type checkers know the block can end early."""

    def __enter__(self) -> None:
        raise NotImplementedError("Collecting.__enter__")

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
        /,
    ) -> bool:
        """True (swallow) for a DiagnosticError only."""
        raise NotImplementedError("Collecting.__exit__")


class Diagnostics:
    """The one place problems collect. A program starts it with ``loaded.diagnostics``, reports its own problems into
    it, and runs reads under ``collecting()`` so a reader's DiagnosticError is recorded instead of ending it."""

    def __init__(self, initial: Iterable[LocatedDiagnostic] = (), /) -> None:
        raise NotImplementedError("Diagnostics")

    def __len__(self) -> int:
        raise NotImplementedError("Diagnostics.__len__")

    def __iter__(self) -> Iterator[LocatedDiagnostic]:
        raise NotImplementedError("Diagnostics.__iter__")

    def add(self, diagnostic: LocatedDiagnostic, /) -> None:
        """Record one problem."""
        raise NotImplementedError("Diagnostics.add")

    def report(self, at: Locatable, message: str, *, code: str) -> None:
        """Record a program's problem placed on ``at``. Raises ValueError when ``code`` has no "/"."""
        raise NotImplementedError("Diagnostics.report")

    def collecting(self) -> Collecting:
        """A context manager that records a DiagnosticError raised inside it into this sink."""
        raise NotImplementedError("Diagnostics.collecting")


def format_diagnostic(diagnostic: LocatedDiagnostic, graph: DocumentGraph | None = None) -> str:
    """``path:line:col: code: message`` (1-based line and column, for people), then the source line and a caret under
    the span when ``graph`` holds the file, then one ``  via <kind> <name> at path:line:col`` line per step.
    Reads text only from ``graph``; never does I/O."""
    raise NotImplementedError("format_diagnostic")
