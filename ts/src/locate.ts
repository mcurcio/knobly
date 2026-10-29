/**
 * Where a problem about a value or a directive is placed (spec 2.2). Package-internal, shared.
 */

import { type DiagnosticCode, messageOf } from "./diagnostics.js";
import { DiagnosticError, MisuseError } from "./errors.js";
import type { IOrigin, IPlace, IStep } from "./origin.js";
import { PROGRAM_CODE } from "./gen/api/limits.js";
import { makeLocated, type ProgramCode } from "./report.js";

/**
 * The file place and steps of an origin. An override is written in no file: it is placed on the `$name` that used
 * it (its first step), with the steps after that one.
 */
export function locate(origin: IOrigin): { readonly place: IPlace; readonly via: readonly IStep[] } {
  if (origin.place.kind === "file") return { place: origin.place, via: origin.via };
  const [step, ...rest] = origin.via;
  if (step === undefined) throw new Error(`override ${origin.place.variable} has no variable step`);
  return { place: step.place, via: rest };
}

/** A program's located error. @throws MisuseError when `code` is not `<namespace>/<name>`. */
export function programError(origin: IOrigin, message: string, code: ProgramCode): DiagnosticError {
  checkProgramCode(code);
  const { place, via } = locate(origin);
  return new DiagnosticError(makeLocated(code, message, place, via));
}

/** @throws MisuseError when `code` is not `<namespace>/<name>`: villanelle's own codes are not the program's to make. */
export function checkProgramCode(code: string): void {
  if (typeof code !== "string" || !PROGRAM_CODE.test(code)) {
    throw new MisuseError(`a program's diagnostic code is <namespace>/<name>: ${JSON.stringify(code)}`);
  }
}

/** villanelle's own located error for a value or directive, with the code's message and an optional detail. */
export function codeError(origin: IOrigin, code: DiagnosticCode, detail?: string): DiagnosticError {
  const message = detail === undefined ? messageOf(code) : `${messageOf(code)}: ${detail}`;
  const { place, via } = locate(origin);
  return new DiagnosticError(makeLocated(code, message, place, via));
}
