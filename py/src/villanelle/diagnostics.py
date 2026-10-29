"""Stable diagnostic codes and the diagnostic shape every layer reports.

``DiagnosticCode`` is generated from spec/schema/diagnostics.json (``villanelle._api.codes``) and re-exported here,
where programs import it. Codes are stable across languages and releases.
Retired, never reused: E2006, E3002, E3003.
Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and extensions, 4xxx values, 5xxx expansion (variables, snippets,
limits), 6xxx reserved for the deferred sugar (none yet). A program's own codes are namespaced (``"rasl/no-graph"``),
so they never collide with these. Every code is an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from villanelle._api.codes import DiagnosticCode
from villanelle.span import SourceSpan

if TYPE_CHECKING:
    from villanelle.report import LocatedDiagnostic


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One located problem in one source text. ``message`` is not part of the cross-language contract."""

    code: DiagnosticCode
    message: str
    span: SourceSpan


class DiagnosticError(Exception):
    """Raised by operations whose contract a user's input breaks (a value reader, a program's own check, a root file
    the source cannot read), carrying the located diagnostic of the load layer."""

    diagnostic: LocatedDiagnostic

    def __init__(self, diagnostic: LocatedDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


__all__ = ["Diagnostic", "DiagnosticCode", "DiagnosticError"]
