/**
 * The diagnostic every layer reports (spec 2.4): a code, its message, and a span in one text. The codes, their
 * messages and reasons are generated from spec/schema/diagnostics.json (gen/api/codes.ts, `describe`), the one
 * registry every binding reads; the type is generated too (gen/api/shared.ts). The error a reader throws is
 * DiagnosticError.
 */

import type * as api from "./gen/api/shared.js";
import { diagnosticForm } from "./people.js";
import type { DiagnosticCode } from "./gen/api/codes.js";

class Diagnostic implements api.Diagnostic {
  constructor(
    readonly code: DiagnosticCode,
    readonly message: string,
    readonly span: api.SourceSpan,
  ) {}

  toString(): string {
    return diagnosticForm(this);
  }
}

/** One diagnostic of a text. Package-internal. */
export function makeDiagnostic(code: DiagnosticCode, message: string, span: api.SourceSpan): api.Diagnostic {
  return new Diagnostic(code, message, span);
}
