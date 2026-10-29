/**
 * Stable diagnostic codes and the diagnostic shape every layer reports.
 *
 * The codes and their messages are generated from spec/schema/diagnostics.json (tools/gen-api.py), the one registry
 * every binding reads. Codes are stable across languages and releases: a code is never reused for a different
 * meaning. A program's own codes are namespaced ("rasl/no-graph"), so they can never collide with these
 * (ProgramCode, report.ts). Every code is an error; there are no warning codes.
 */

import { type DiagnosticCode, MESSAGES } from "./gen/api/codes.js";
import type { ILocatedDiagnostic } from "./report.js";
import type { ISourceSpan } from "./span.js";

export { DiagnosticCode } from "./gen/api/codes.js";

/** The message for a code; for people, not part of the cross-language contract. */
export function messageOf(code: DiagnosticCode): string {
  return MESSAGES[code];
}

/** One located problem in one source text. */
export interface IDiagnostic {
  readonly code: DiagnosticCode;
  /** Human-readable explanation. Not part of the cross-language contract; only `code` and `span` are. */
  readonly message: string;
  /** Where the problem is; a zero-width span at the end of the text for "unexpected end of input". */
  readonly span: ISourceSpan;
}

/**
 * Thrown by operations whose contract a user's input breaks (STYLE 11.6), carrying the located diagnostic: a value
 * reader given the wrong kind of value, `error()` on a directive or value, or a load whose root file cannot be read.
 */
export class DiagnosticError extends Error {
  readonly diagnostic: ILocatedDiagnostic;

  constructor(diagnostic: ILocatedDiagnostic) {
    super(diagnostic.message);
    this.name = "DiagnosticError";
    this.diagnostic = diagnostic;
  }
}
