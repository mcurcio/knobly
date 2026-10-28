/**
 * Diagnostics of the load layer, and the one sink that load, value readers and programs all report into
 * (round 11 review finding 2; R14's report helper). Prior art: PostCSS `Result.messages` / `node.warn(result)`,
 * HCL's `hcl.Diagnostics`.
 */

import type { DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import type { IDocumentGraph } from "./graph.js";
import type { IPlace, IStep } from "./origin.js";
import { notImplemented } from "./todo.js";

/**
 * A program's own code: `<namespace>/<name>`, such as "rasl/unknown-node". Never collides with villanelle's codes
 * (which start with "E"). Checked when made: `error()` and `report()` throw TypeError for a code without "/".
 */
export type ProgramCode = `${string}/${string}`;

/** One located problem of a load: villanelle's or a program's. Always at a place in a file (design rule 3). */
export interface ILocatedDiagnostic {
  readonly code: DiagnosticCode | ProgramCode;
  /** For people; not part of the cross-language contract. */
  readonly message: string;
  /**
   * Where the problem is. For a value handed in by the program (written in no file) this is the `$name` that used
   * it, and the message names the handed-in variable.
   */
  readonly at: IPlace;
  /** The variables, uses and extension directives that brought the text to `at`'s reader; innermost first. */
  readonly via: readonly IStep[];
}

/** Anything a program can place a problem on: a directive, a value, or the whole load (its root file). */
export interface ILocatable {
  /** A located error for the program to throw or report. @throws TypeError when `code` has no "/". */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/**
 * The one place problems collect. A program starts it with `loaded.diagnostics`, reports its own problems into
 * it, and runs reads through `collect` so a reader's DiagnosticError is recorded instead of ending the program.
 */
export class Diagnostics implements Iterable<ILocatedDiagnostic> {
  /** Start with these, in order (usually `loaded.diagnostics`). */
  constructor(initial?: Iterable<ILocatedDiagnostic>) {
    throw notImplemented("Diagnostics", initial);
  }

  /** How many problems are recorded. */
  get length(): number {
    throw notImplemented("Diagnostics.length");
  }

  /** Record one problem. */
  add(diagnostic: ILocatedDiagnostic): void {
    throw notImplemented("Diagnostics.add", diagnostic);
  }

  /** Record a program's problem placed on `at`: `problems.report(d, "no such node", "rasl/unknown-node")`. */
  report(at: ILocatable, message: string, code: ProgramCode): void {
    throw notImplemented("Diagnostics.report", at, message, code);
  }

  /**
   * Run one read. If it throws a DiagnosticError, record its diagnostic and return undefined; otherwise return
   * what it returned. Any other exception passes through.
   */
  collect<T>(read: () => T): T | undefined {
    throw notImplemented("Diagnostics.collect", read);
  }

  /** The problems recorded, in order. */
  toArray(): readonly ILocatedDiagnostic[] {
    throw notImplemented("Diagnostics.toArray");
  }

  [Symbol.iterator](): Iterator<ILocatedDiagnostic> {
    throw notImplemented("Diagnostics[Symbol.iterator]");
  }
}

/**
 * `path:line:col: code: message` (1-based line and column, for people), then the source line and a caret under the
 * span when `graph` holds the file, then one `  via <kind> <name> at path:line:col` line per step (rasl-ynq).
 * Reads text only from `graph`; never does I/O.
 */
export function formatDiagnostic(diagnostic: ILocatedDiagnostic, graph?: IDocumentGraph): string {
  throw notImplemented("formatDiagnostic", diagnostic, graph);
}
