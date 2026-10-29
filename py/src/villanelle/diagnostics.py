"""The diagnostic shape every layer reports (its Protocol is ``villanelle._api.shared.Diagnostic``).

``DiagnosticCode`` is generated from spec/schema/diagnostics.json (``villanelle._api.codes``); programs import it from
``villanelle``. Codes are stable across languages and releases.
Retired, never reused: E2006, E3002, E3003.
Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and extensions, 4xxx values, 5xxx expansion (variables, snippets,
limits), 6xxx reserved for the deferred sugar (none yet). A program's own codes are namespaced (``"rasl/no-graph"``),
so they never collide with these. Every code is an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from villanelle._api import shared
from villanelle._api.codes import DiagnosticCode
from villanelle._api.shared import SourceSpan


@dataclass(frozen=True, slots=True)
class Diagnostic(shared.Diagnostic):
    """One located problem in one source text. ``message`` is not part of the cross-language contract."""

    code: DiagnosticCode = field()
    message: str = field()
    span: SourceSpan = field()

    def __str__(self) -> str:
        """Its people form (spec/contract.md 2): ``line:col: code: message``, counting from 1 (the span's start)."""
        start = self.span.start
        return f"{start.line + 1}:{start.column + 1}: {self.code}: {self.message}"


__all__ = ["Diagnostic"]
