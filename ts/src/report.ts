/**
 * Located diagnostics, and the one sink that load, value readers and programs all report into
 * (round 11 review finding 2; R14's report helper). Prior art: PostCSS `Result.messages` / `node.warn(result)`,
 * HCL's `hcl.Diagnostics`. The types are generated (gen/api/shared.ts).
 */

import type * as api from "./gen/api/shared.js";
import { locatedForm } from "./people.js";
import type { DiagnosticCode } from "./gen/api/codes.js";
import { DiagnosticError } from "./gen/api/errors.js";
import type { Severity } from "./gen/api/kinds.js";
import { severityOf } from "./diagnostics.js";

class LocatedDiagnostic implements api.LocatedDiagnostic {
  readonly severity: Severity;

  constructor(
    readonly code: DiagnosticCode | api.ProgramCode,
    readonly message: string,
    readonly place: api.Place,
    readonly via: readonly api.Step[],
  ) {
    this.severity = severityOf(code);
  }

  toString(): string {
    return locatedForm(this);
  }
}

/** One located diagnostic. Package-internal. */
export function makeLocated(code: DiagnosticCode | api.ProgramCode, message: string, place: api.Place, via: readonly api.Step[]): api.LocatedDiagnostic {
  return new LocatedDiagnostic(code, message, place, via);
}

export class Diagnostics implements api.Diagnostics {
  private readonly items: api.LocatedDiagnostic[];

  constructor(initial?: Iterable<api.LocatedDiagnostic>) {
    this.items = [...(initial ?? [])];
  }

  get length(): number {
    return this.items.length;
  }

  add(diagnostic: api.LocatedDiagnostic): void {
    this.items.push(diagnostic);
  }

  report(at: api.Locatable, message: string, code: api.ProgramCode): void {
    this.add(at.error(message, code).diagnostic);
  }

  collect<T>(read: () => T): T | undefined {
    try {
      return read();
    } catch (error) {
      if (!(error instanceof DiagnosticError)) throw error;
      this.add(error.diagnostic);
      return undefined;
    }
  }

  [Symbol.iterator](): Iterator<api.LocatedDiagnostic> {
    return this.items[Symbol.iterator]();
  }
}
