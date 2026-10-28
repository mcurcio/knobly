/**
 * Where a problem about a value or a directive is placed (slices.md §1.2, RV8). Private to the load layer.
 */

import { type DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import { messageOf } from "../syntax/recovery.js";
import type { IOrigin, IPlace, IStep } from "./origin.js";
import type { ProgramCode } from "./report.js";

/**
 * The file place and steps of an origin. A value handed in by the program is written in no file: it is placed on
 * the `$name` that used it (its first step), with the steps after that one.
 */
export function locate(origin: IOrigin): { readonly at: IPlace; readonly via: readonly IStep[] } {
  if (origin.written.kind === "file") return { at: origin.written, via: origin.via };
  const [step, ...rest] = origin.via;
  if (step === undefined) throw new Error(`handed-in value ${origin.written.variable} has no variable step`);
  return { at: step.at, via: rest };
}

const PROGRAM_CODE = /^[^/\s]+\/\S+$/;

/** A program's located error. @throws TypeError when `code` is not `<namespace>/<name>`. */
export function programError(origin: IOrigin, message: string, code: ProgramCode): DiagnosticError {
  checkProgramCode(code);
  return new DiagnosticError({ code, message, ...locate(origin) });
}

/** @throws TypeError when `code` is not `<namespace>/<name>`: villanelle's own codes are not the program's to make. */
export function checkProgramCode(code: string): void {
  if (typeof code !== "string" || !PROGRAM_CODE.test(code)) {
    throw new TypeError(`a program's diagnostic code is <namespace>/<name>: ${JSON.stringify(code)}`);
  }
}

/** villanelle's own located error for a value or directive, with the code's message and an optional detail. */
export function codeError(origin: IOrigin, code: DiagnosticCode, detail?: string): DiagnosticError {
  const message = detail === undefined ? messageOf(code) : `${messageOf(code)}: ${detail}`;
  return new DiagnosticError({ code, message, ...locate(origin) });
}
