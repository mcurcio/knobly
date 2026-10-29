"""Located diagnostics (shared by the low level and the rendered layer), and the one sink that load, value readers
and programs all report into (round 11 review finding 2; R14's report helper). Prior art: HCL's
``hcl.Diagnostics``, PostCSS ``Result.messages``."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Protocol

from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.origin import Place, Step

if TYPE_CHECKING:
    from villanelle.written.model import DocumentGraph


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


def format_diagnostic(diagnostic: LocatedDiagnostic, graph: DocumentGraph | None = None) -> str:
    """``path:line:col: code: message`` (1-based line and column, for people), then the source line and a caret under
    the span when ``graph`` holds the file (its current text), then one ``  via <kind> <name> at path:line:col`` line
    per step. Reads text only from ``graph``; never does I/O."""
    lines = [f"{_place(diagnostic.place)}: {diagnostic.code}: {diagnostic.message}"]
    document = None if graph is None else graph.documents.get(diagnostic.place.resolved_path)
    if document is not None:
        start, end = diagnostic.place.span.start, diagnostic.place.span.end
        source_lines = document.text.split("\n")
        if start.line < len(source_lines):
            line = source_lines[start.line].removesuffix("\r")
            # Columns count UTF-16 code units, as TypeScript's strings do: a character above U+FFFF counts two.
            units = [2 if ord(c) > 0xFFFF else 1 for c in line]
            width = end.column - start.column if end.line == start.line else sum(units) - start.column
            # Tabs stay tabs so the caret lines up under the same characters; every other unit becomes a space.
            pad: list[str] = []
            column = 0
            for char, size in zip(line, units, strict=True):
                if column >= start.column:
                    break
                pad.append("\t" if char == "\t" else " " * size)
                column += size
            lines.append(line)
            lines.append("".join(pad) + "^" * max(1, width))
    lines.extend(f"  via {step.kind} {step.name} at {_place(step.place)}" for step in diagnostic.via)
    return "\n".join(lines)


def _place(place: Place) -> str:
    """``path:line:col``, 1-based, for people."""
    position = place.span.start
    return f"{place.resolved_path}:{position.line + 1}:{position.column + 1}"


_CODES = frozenset(code.value for code in DiagnosticCode)


_PROGRAM_CODE = re.compile(r"[^/\s]+/\S+")
"""``<namespace>/<name>``: both parts non-empty, no whitespace (S2-08, the same pattern as TypeScript's)."""


def check_program_code(code: str) -> None:
    """Raise ValueError unless ``code`` is ``<namespace>/<name>`` (a program's own code; villanelle's are its own)."""
    if not isinstance(code, str) or _PROGRAM_CODE.fullmatch(code) is None:
        raise ValueError(f'a program\'s code is "<namespace>/<name>", such as "rasl/unknown-node": {code!r}')
