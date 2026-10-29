/**
 * The package's error classes on the spec's two sorts (spec 2.8; spec/contract.md 4; spec/schema/api.json "error
 * groups"). An expected outcome, which only the input or the outside world decides, is a `VillanelleError`, and
 * nothing else is: one `catch (e) { if (e instanceof VillanelleError) ... }` catches every outcome and no bug. A
 * program bug, which the program could have checked first, is outside it: `DetachedError` (a `ReferenceError`),
 * `MisuseError`, the native `TypeError` (an argument of the wrong type) and `RangeError` (an index out of range).
 * Prior art: Joe Duffy's "bugs are not recoverable errors" (Midori); Rust's panic against `Result`. Shared by every
 * layer.
 */

import type { IDiagnostic } from "./diagnostics.js";
import type { ILocatedDiagnostic } from "./report.js";

/** The base of every expected-outcome class villanelle defines. Never thrown by itself. */
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
 * to `load`; `cause` is the source's rejection (absent when it resolved no file or several). No diagnostic, no code.
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
 * The text given to an edit, or an override's text, is not what it takes: its entry rule refuses it (spec 2.8), or a
 * text-alone rule is broken (E5002, E5005, E5009-E5011). Nothing changed. `diagnostics` are located in the given text
 * (UTF-16 code units, spec/contract.md 1); the message is built from them: `bad text: 1:2: E2001: unexpected token: ";"`.
 */
export class BadTextError extends VillanelleError {
  constructor(readonly diagnostics: readonly IDiagnostic[]) {
    super(`bad text: ${diagnostics.map(String).join("; ")}`);
    this.name = "BadTextError";
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

/**
 * A file the save would write changed since it was read or last saved (spec 4.2): its text in the medium now differs
 * from its `savedText`. `paths` are only the conflicting files, in batch order; no cause. Raised by
 * `checkLostUpdates` inside every writer; `save` raises it as it is.
 */
export class LostUpdateError extends SaveError {
  constructor(paths: readonly string[]) {
    super(`lost update: changed since read: ${paths.join(", ")}`, paths);
    this.name = "LostUpdateError";
  }
}

/**
 * A program bug: a member of a detached handle was used (its tokens were removed by an edit, or its document's whole
 * text was replaced). A reference that no longer leads anywhere, so a `ReferenceError`, outside `VillanelleError`.
 */
export class DetachedError extends ReferenceError {
  constructor(message: string) {
    super(message);
    this.name = "DetachedError";
  }
}

/**
 * A program bug: a bad argument value the program could have checked (spec 2.8): every bad name, a program code
 * without "/", a reserved or repeated extension name. Outside `VillanelleError`, and not a `TypeError`, so a misuse
 * and an argument of the wrong type are told apart.
 */
export class MisuseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MisuseError";
  }
}
