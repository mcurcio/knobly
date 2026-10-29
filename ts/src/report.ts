/**
 * Located diagnostics, and the one sink that load, value readers and programs all report into
 * (round 11 review finding 2; R14's report helper). Prior art: PostCSS `Result.messages` / `node.warn(result)`,
 * HCL's `hcl.Diagnostics`. The types are generated (gen/api/shared.ts).
 */

import type * as api from "./gen/api/shared.js";
import { locatedForm } from "./people.js";
import type { DiagnosticCode } from "./gen/api/codes.js";
import { DiagnosticError } from "./gen/api/errors.js";

class LocatedDiagnostic implements api.LocatedDiagnostic {
  constructor(
    readonly code: DiagnosticCode | api.ProgramCode,
    readonly message: string,
    readonly place: api.Place,
    readonly via: readonly api.Step[],
  ) {}

  toString(): string {
    return locatedForm(this);
  }
}

/** One located diagnostic. Package-internal. */
export function makeLocated(code: DiagnosticCode | api.ProgramCode, message: string, place: api.Place, via: readonly api.Step[]): api.LocatedDiagnostic {
  return new LocatedDiagnostic(code, message, place, via);
}

/**
 * The one place problems collect. A program starts it with `rendered.diagnostics`, reports its own problems into
 * it, and runs reads through `collect` so a reader's DiagnosticError is recorded instead of ending the program.
 */
export class Diagnostics implements api.Diagnostics {
  private readonly items: api.LocatedDiagnostic[];

  /** Start with these, in order (usually `rendered.diagnostics`). */
  constructor(initial?: Iterable<api.LocatedDiagnostic>) {
    this.items = [...(initial ?? [])];
  }

  /** How many problems are recorded. */
  get length(): number {
    return this.items.length;
  }

  /** Record one problem. */
  add(diagnostic: api.LocatedDiagnostic): void {
    this.items.push(diagnostic);
  }

  /** Record a program's problem placed on `at`: `problems.report(d, "no such node", "rasl/unknown-node")`. */
  report(at: api.Locatable, message: string, code: api.ProgramCode): void {
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
  toArray(): readonly api.LocatedDiagnostic[] {
    return [...this.items];
  }

  [Symbol.iterator](): Iterator<api.LocatedDiagnostic> {
    return this.items[Symbol.iterator]();
  }
}
