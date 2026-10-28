/**
 * Diagnostics of the load layer, and the one sink that load, value readers and programs all report into
 * (round 11 review finding 2; R14's report helper). Prior art: PostCSS `Result.messages` / `node.warn(result)`,
 * HCL's `hcl.Diagnostics`.
 */

import { type DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import type { IDocumentGraph } from "./graph.js";
import type { IPlace, IStep } from "./origin.js";

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
  private readonly items: ILocatedDiagnostic[];

  /** Start with these, in order (usually `loaded.diagnostics`). */
  constructor(initial?: Iterable<ILocatedDiagnostic>) {
    this.items = [...(initial ?? [])];
  }

  /** How many problems are recorded. */
  get length(): number {
    return this.items.length;
  }

  /** Record one problem. */
  add(diagnostic: ILocatedDiagnostic): void {
    this.items.push(diagnostic);
  }

  /** Record a program's problem placed on `at`: `problems.report(d, "no such node", "rasl/unknown-node")`. */
  report(at: ILocatable, message: string, code: ProgramCode): void {
    this.add(at.error(message, code).diagnostic);
  }

  /**
   * Run one read. If it throws a DiagnosticError, record its diagnostic and return undefined; otherwise return
   * what it returned. Any other exception passes through.
   */
  collect<T>(read: () => T): T | undefined {
    try {
      return read();
    } catch (error) {
      if (!(error instanceof DiagnosticError)) throw error;
      this.add(error.diagnostic);
      return undefined;
    }
  }

  /** The problems recorded, in order. */
  toArray(): readonly ILocatedDiagnostic[] {
    return [...this.items];
  }

  [Symbol.iterator](): Iterator<ILocatedDiagnostic> {
    return this.items[Symbol.iterator]();
  }
}

/** `path:line:col`, 1-based, for people. */
function where(at: IPlace): string {
  return `${at.resolvedPath}:${String(at.span.start.line + 1)}:${String(at.span.start.column + 1)}`;
}

/**
 * `path:line:col: code: message` (1-based line and column, for people), then the source line and a caret under the
 * span when `graph` holds the file, then one `  via <kind> <name> at path:line:col` line per step (rasl-ynq).
 * Reads text only from `graph`; never does I/O.
 */
export function formatDiagnostic(diagnostic: ILocatedDiagnostic, graph?: IDocumentGraph): string {
  const { at, via } = diagnostic;
  const lines = [`${where(at)}: ${diagnostic.code}: ${diagnostic.message}`];
  const source = graph?.nodes.get(at.resolvedPath)?.source;
  if (source !== undefined) {
    const { start, end } = at.span;
    const lineStart = start.offset - start.column;
    const lineEnd = source.slice(lineStart).search(/\r\n|\n|\r/u);
    const text = lineEnd < 0 ? source.slice(lineStart) : source.slice(lineStart, lineStart + lineEnd);
    const width = end.line === start.line ? end.column - start.column : text.length - start.column;
    // Tabs stay tabs so the caret lines up under the same characters.
    const pad = text.slice(0, start.column).replace(/[^\t]/g, " ");
    lines.push(text, `${pad}${"^".repeat(Math.max(1, width))}`);
  }
  for (const step of via) lines.push(`  via ${step.kind} ${step.name} at ${where(step.at)}`);
  return lines.join("\n");
}
