/**
 * People forms (spec/contract.md 2): the text a located thing prints as, the one home of each. The records' own
 * `toString()` (so `String(x)` and template literals) and `formatDiagnostic` both build on these. Lines and columns
 * count from 1; columns in UTF-16 code units, this binding's string unit (spec/contract.md 1).
 */

import type { SourceSpan } from "./gen/api/shared.js";

interface IPlaceLike {
  readonly resolvedPath: string;
  readonly span: SourceSpan;
}

/** `path:line:col`, at the span's start: `sink.conf:4:5`. */
export function placeForm(place: IPlaceLike): string {
  return `${place.resolvedPath}:${String(place.span.start.line + 1)}:${String(place.span.start.column + 1)}`;
}

/** `override <variable>`, without `$`: `override pixels`. */
export function overrideForm(override: { readonly variable: string }): string {
  return `override ${override.variable}`;
}

/** `<kind> <name> at <place>`: `variable pixels at main.conf:7:15`. */
export function stepForm(step: { readonly kind: string; readonly name: string; readonly place: IPlaceLike }): string {
  return `${step.kind} ${step.name} at ${placeForm(step.place)}`;
}

/** `<place>: <code>: <message>`: `main.conf:7:15: E5001: unknown variable: $pixels`. */
export function locatedForm(diagnostic: { readonly code: string; readonly message: string; readonly place: IPlaceLike }): string {
  return `${placeForm(diagnostic.place)}: ${diagnostic.code}: ${diagnostic.message}`;
}

/** `line:col: <code>: <message>`, at the span's start (a syntax diagnostic has no file): `1:3: E2004: ...`. */
export function diagnosticForm(diagnostic: { readonly code: string; readonly message: string; readonly span: SourceSpan }): string {
  const { line, column } = diagnostic.span.start;
  return `${String(line + 1)}:${String(column + 1)}: ${diagnostic.code}: ${diagnostic.message}`;
}
