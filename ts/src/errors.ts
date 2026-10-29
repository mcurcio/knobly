/**
 * The package's error classes (spec/contract.md 4; spec/schema/api.json "error groups"): one base, `VillanelleError`,
 * under which every class the package defines sits, so one `catch (e) { if (e instanceof VillanelleError) ... }`
 * catches them all. Program bugs use the language's own classes and are not under it: `TypeError` for an argument of
 * the wrong type or a bad argument value, `RangeError` for an index out of range. Shared by every layer.
 */

import type { IDiagnostic } from "./diagnostics.js";
import type { ILocatedDiagnostic } from "./report.js";

/** The base of every error class villanelle defines. Never thrown by itself. */
export class VillanelleError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "VillanelleError";
  }
}

/**
 * A problem the config text decides, carrying one located diagnostic: a value reader given the wrong kind of value
 * or spelling, or a program's own `error(...)`.
 */
export class DiagnosticError extends VillanelleError {
  constructor(readonly diagnostic: ILocatedDiagnostic) {
    super(diagnostic.message);
    this.name = "DiagnosticError";
  }
}

/**
 * `load` could not resolve the root path to exactly one file, or could not read it. `paths` is the root path as given
 * to `load`; `cause` is the source's rejection (absent when it resolved no file or several). No diagnostic, no code:
 * a missing root file is not an extension line's failure (E3004 stays an include line's code).
 */
export class ReadError extends VillanelleError {
  constructor(
    message: string,
    readonly paths: readonly string[],
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ReadError";
  }
}

/**
 * The writer rejected. No document's `savedText` changed. `paths` are the resolved paths handed to the writer, in
 * batch order; `cause` is what the writer rejected with.
 */
export class SaveError extends VillanelleError {
  constructor(
    message: string,
    readonly paths: readonly string[],
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "SaveError";
  }
}

/** Base of the refusals of an edit. Nothing changed when one is thrown. */
export class EditError extends VillanelleError {
  constructor(message: string) {
    super(message);
    this.name = "EditError";
  }
}

/**
 * The text given to an edit, or an override's text, is not what it takes: a syntax error, values where statements go
 * (or the other way), or a text-alone rule broken (E5002, E5005, E5009-E5011). `diagnostics` are located in the given
 * text (UTF-16 code units, spec/contract.md 1), with the codes a load gives.
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

/**
 * The handle's tokens were removed by an edit, or its document's whole text was replaced. Not an edit error: reading
 * a property of a detached handle throws it too.
 */
export class DetachedError extends VillanelleError {
  constructor(message: string) {
    super(message);
    this.name = "DetachedError";
  }
}
