"""Located diagnostics (shared by the low level and the rendered layer), and the one sink that load, value readers
and programs all report into (round 11 review finding 2; R14's report helper). Prior art: HCL's
``hcl.Diagnostics``, PostCSS ``Result.messages``."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from villanelle.diagnostics import DiagnosticCode
from villanelle.errors import DiagnosticError
from villanelle.origin import Place, Step


@dataclass(frozen=True, slots=True)
class LocatedDiagnostic:
    """One located problem of a load: villanelle's or a program's. Always at a place in a file (design rule 3).

    ``code`` is a DiagnosticCode, or a program's own ``"<namespace>/<name>"`` (``"rasl/unknown-node"``). For an
    override's value, ``place`` is the ``$name`` that used it and the message names the variable."""

    code: DiagnosticCode | str
    message: str
    """For people; not part of the cross-language contract."""
    place: Place
    via: tuple[Step, ...]
    """The variables, uses and extension directives that brought the text to ``place``'s reader; innermost first."""

    def __post_init__(self) -> None:
        """Raise ValueError when ``code`` is neither a DiagnosticCode value nor a namespaced program code."""
        if isinstance(self.code, DiagnosticCode):
            return
        if self.code in _CODES:
            object.__setattr__(self, "code", DiagnosticCode(self.code))
            return
        check_program_code(self.code)

    def __str__(self) -> str:
        """Its people form (spec/contract.md 2): ``<place>: <code>: <message>``, the first line of
        ``format_diagnostic``."""
        return f"{self.place}: {self.code}: {self.message}"


class Locatable(Protocol):
    """Anything a program can place a problem on: a directive, a value, or the whole load (its root file)."""

    def error(self, message: str, *, code: str) -> DiagnosticError:
        """A located error to raise or report. Raises ValueError when ``code`` has no "/"."""
        ...


class Collecting:
    """``with problems.collecting(): ...``: a DiagnosticError raised inside is recorded and the block ends; any other
    exception passes through. A class (not ``@contextmanager``) so type checkers know the block can end early."""

    __slots__ = ("_into",)

    def __init__(self, into: Diagnostics, /) -> None:
        self._into = into

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
        /,
    ) -> bool:
        """True (swallow) for a DiagnosticError only."""
        if isinstance(error, DiagnosticError):
            self._into.add(error.diagnostic)
            return True
        return False


class Diagnostics:
    """The one place problems collect. A program starts it with ``rendered.diagnostics``, reports its own problems into
    it, and runs reads under ``collecting()`` so a reader's DiagnosticError is recorded instead of ending it."""

    __slots__ = ("_items",)

    def __init__(self, initial: Iterable[LocatedDiagnostic] = (), /) -> None:
        self._items: list[LocatedDiagnostic] = list(initial)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[LocatedDiagnostic]:
        return iter(tuple(self._items))

    def add(self, diagnostic: LocatedDiagnostic, /) -> None:
        """Record one problem."""
        self._items.append(diagnostic)

    def report(self, at: Locatable, message: str, *, code: str) -> None:
        """Record a program's problem placed on ``at``. Raises ValueError when ``code`` has no "/"."""
        self.add(at.error(message, code=code).diagnostic)

    def collecting(self) -> Collecting:
        """A context manager that records a DiagnosticError raised inside it into this sink."""
        return Collecting(self)


_CODES = frozenset(code.value for code in DiagnosticCode)


_PROGRAM_CODE = re.compile(r"[^/\s]+/\S+")
"""``<namespace>/<name>``: both parts non-empty, no whitespace (S2-08, the same pattern as TypeScript's)."""


def check_program_code(code: str) -> None:
    """Raise ValueError unless ``code`` is ``<namespace>/<name>`` (a program's own code; villanelle's are its own)."""
    if not isinstance(code, str) or _PROGRAM_CODE.fullmatch(code) is None:
        raise ValueError(f'a program\'s code is "<namespace>/<name>", such as "rasl/unknown-node": {code!r}')
