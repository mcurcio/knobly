/**
 * The low level's errors (round 12 design.md §5; slices.md S1). An edit that throws one of the EditErrors changed
 * nothing.
 */

import { DiagnosticError, type IDiagnostic } from "../diagnostics.js";
import type { ILocatedDiagnostic } from "../load/report.js";
import type { IFileWrite } from "./model.js";

/** Base of the errors an edit throws. Nothing changed when one is thrown. */
export class EditError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EditError";
  }
}

/**
 * The text given to an edit is not what that edit takes: a syntax error, values where statements go (or the other
 * way), or a text-alone rule broken (E5002, E5005, E5009-E5011). `diagnostics` are located in the given text, with
 * the codes a load gives.
 */
export class BadTextError extends EditError {
  constructor(
    message: string,
    readonly diagnostics: readonly IDiagnostic[],
  ) {
    super(message);
    this.name = "BadTextError";
  }
}

/** The handle's tokens were removed by an edit, or its document's whole text was replaced. */
export class DetachedError extends EditError {
  constructor(message: string) {
    super(message);
    this.name = "DetachedError";
  }
}

/** `IVariable.setValues` on a parameter (edit the `use` line) or a handed-in value (use `setHanded`). */
export class NoSetLineError extends EditError {
  constructor(message: string) {
    super(message);
    this.name = "NoSetLineError";
  }
}

/** The writer rejected. No document's `source` changed. `cause` (Error's own) is what the writer rejected with. */
export class SaveError extends Error {
  constructor(
    message: string,
    readonly files: readonly IFileWrite[],
    cause: unknown,
  ) {
    super(message, { cause });
    this.name = "SaveError";
  }
}

/** `load` could not read the root file: E3004 placed at the root path, as before. */
export class ReadError extends DiagnosticError {
  constructor(diagnostic: ILocatedDiagnostic) {
    super(diagnostic);
    this.name = "ReadError";
  }
}
