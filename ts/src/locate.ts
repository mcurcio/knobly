/**
 * Where a problem about a value or a directive is placed (spec 2.2). Package-internal, shared.
 */

import { PROGRAM_CODE } from "./gen/api/limits.js";
import { makeLocated } from "./report.js";
import type { Origin, Place, ProgramCode, Step } from "./gen/api/shared.js";
import { type DiagnosticCode, describe } from "./gen/api/codes.js";
import { DiagnosticError, MisuseError } from "./gen/api/errors.js";
import { PlaceKind } from "./gen/api/kinds.js";

/**
 * The file place and steps of an origin. An override is written in no file: it is placed on the `$name` that used
 * it (its first step), with the steps after that one.
 */
export function locate(origin: Origin): { readonly place: Place; readonly via: readonly Step[] } {
  if (origin.place.kind === PlaceKind.File) return { place: origin.place, via: origin.via };
  const [step, ...rest] = origin.via;
  if (step === undefined) throw new Error(`override ${origin.place.variable} has no variable step`);
  return { place: step.place, via: rest };
}

/** A program's located error. @throws MisuseError when `code` is not `<namespace>/<name>`. */
export function programError(origin: Origin, message: string, code: ProgramCode): DiagnosticError {
  checkProgramCode(code);
  const { place, via } = locate(origin);
  return new DiagnosticError(makeLocated(code, message, place, via));
}

/** @throws MisuseError when `code` is not `<namespace>/<name>`: knobly's own codes are not the program's to make. */
export function checkProgramCode(code: string): void {
  if (typeof code !== "string" || !PROGRAM_CODE.test(code)) {
    throw new MisuseError(`a program's diagnostic code is <namespace>/<name>: ${JSON.stringify(code)}`);
  }
}

/** knobly's own located error for a value or directive, with the code's message and an optional detail. */
export function codeError(origin: Origin, code: DiagnosticCode, detail?: string): DiagnosticError {
  const { message } = describe(code, detail);
  const { place, via } = locate(origin);
  return new DiagnosticError(makeLocated(code, message, place, via));
}
