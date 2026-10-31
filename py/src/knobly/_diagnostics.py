"""The diagnostic shape every layer reports (its Protocol is ``knobly._api.shared.Diagnostic``).

``DiagnosticCode`` is generated from spec/schema/diagnostics.json (``knobly._api.codes``); programs import it from
``knobly``. Codes are stable across languages and releases.
Retired, never reused: E2006, E3002, E3003.
Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and extensions, 4xxx values, 5xxx expansion (variables, snippets,
limits), 6xxx reserved for the deferred sugar (none yet). A program's own codes are namespaced (``"rasl/no-graph"``),
so they never collide with these. A code's letter is its severity (spec 2.3): E an error, W a warning; a program's
code is an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knobly._api import shared
from knobly._api.codes import CODE_FACTS, DiagnosticCode
from knobly._api.kinds import Severity
from knobly._api.shared import SourceSpan


def severity_of(code: DiagnosticCode | str) -> Severity:
    """A code's severity (spec 2.3): a knobly code's is the registry's (its letter's); a program's code is an error."""
    return CODE_FACTS[code].severity if isinstance(code, DiagnosticCode) else Severity.ERROR


@dataclass(frozen=True, slots=True)
class Diagnostic(shared.Diagnostic):
    code: DiagnosticCode = field()
    severity: Severity = field(init=False)
    message: str = field()
    span: SourceSpan = field()

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", severity_of(self.code))

    def __str__(self) -> str:
        start = self.span.start
        return f"{start.line + 1}:{start.column + 1}: {self.code}: {self.message}"


__all__ = ["Diagnostic", "severity_of"]
