/**
 * The diagnostic every layer reports (spec 2.4): a code, its message, and a span in one text. The codes, their
 * messages and reasons are generated from spec/schema/diagnostics.json (gen/api/codes.ts, `describe`), the one
 * registry every binding reads; the type is generated too (gen/api/shared.ts). The error a reader throws is
 * DiagnosticError.
 */

import type * as api from "./gen/api/shared.js";
import { diagnosticForm } from "./people.js";
import { CODE_FACTS, type DiagnosticCode } from "./gen/api/codes.js";
import { Severity } from "./gen/api/kinds.js";

/** A code's severity (spec 2.3): a knobly code's is the registry's, from its letter; a program's code is an error. */
export function severityOf(code: DiagnosticCode | api.ProgramCode): Severity {
  return Object.hasOwn(CODE_FACTS, code) ? CODE_FACTS[code as DiagnosticCode].severity : Severity.Error;
}

class Diagnostic implements api.Diagnostic {
  readonly severity: Severity;

  constructor(
    readonly code: DiagnosticCode,
    readonly message: string,
    readonly span: api.SourceSpan,
  ) {
    this.severity = severityOf(code);
  }

  toString(): string {
    return diagnosticForm(this);
  }
}

/** One diagnostic of a text. Package-internal. */
export function makeDiagnostic(code: DiagnosticCode, message: string, span: api.SourceSpan): api.Diagnostic {
  return new Diagnostic(code, message, span);
}
