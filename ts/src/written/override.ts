/**
 * The check of an override (spec 6.3): one check, one home. `load` (for each of its `overrides`, in order) and
 * `set override` both call it, so both refuse the same texts with the same errors (round 13 root cause 2: before
 * milestone 1 they checked two ways and disagreed about "1;").
 */

import { DiagnosticCode, type IDiagnostic, makeDiagnostic, messageOf } from "../diagnostics.js";
import { BadTextError } from "../errors.js";
import { VARIABLE_NAME } from "../gen/api/limits.js";
import { parse } from "../syntax/parse.js";
import { requireText } from "../text.js";
import { readOverride } from "./bind.js";
import { positionIn, valuesTextProblems } from "./document.js";
import type { Bound } from "./expanded.js";

/** How the caller named what it was given, for the argument type error: `setOverride` / `text`, `load` / `overrides["port"]`. */
export interface IOverrideCaller {
  readonly member: string;
  readonly textParameter: string;
}

/** The check of an override's name alone (`setOverride(name, undefined)`). @throws TypeError unless letters, digits and `_` */
export function checkOverrideName(name: unknown, member: string): asserts name is string {
  requireText(name, member, "name");
  if (!VARIABLE_NAME.test(name)) throw new TypeError(`override name must be letters, digits and _: ${JSON.stringify(name)}`);
}

/**
 * Check one override and read its values: the name (a misuse error, TypeError, unless letters, digits and `_`), the
 * text's type (the argument type error), then the text as the values of a line `x <text>` by the check of a values
 * text (its syntax diagnostics, or E2001 at the first token that is more than values, a line break outside a list
 * included); else E2001 at a `$name`, or at 0:0 when it holds no value; else E4003
 * or E4001 at the first value the reader refuses. Every diagnostic is located in `text`.
 * @throws TypeError for a bad name or a text that is not a string; BadTextError for text the check refuses
 */
export function checkOverride(name: unknown, text: unknown, caller: IOverrideCaller): readonly Bound[] {
  checkOverrideName(name, caller.member);
  requireText(text, caller.member, caller.textParameter);
  const refuse = (diagnostics: readonly IDiagnostic[]): BadTextError =>
    new BadTextError(`not override text for $${name}: ${JSON.stringify(text)}`, diagnostics);
  const fault = (offset: number, code: DiagnosticCode): BadTextError => {
    const at = positionIn(text, offset);
    return refuse([makeDiagnostic(code, messageOf(code), { start: at, end: at })]);
  };
  const given = text.trim() === "" ? [] : valuesTextProblems(text, false);
  if (given.length > 0) throw refuse(given);
  const tokens = parse(`x ${text};`).tokens.filter((t) => t.span.start.offset >= 2 && t.span.start.offset < 2 + text.length);
  const first = tokens.find((t) => t.kind !== "SPACE" && t.kind !== "NEWLINE" && t.kind !== "COMMENT");
  if (first === undefined) throw fault(0, DiagnosticCode.UnexpectedToken);
  const variable = tokens.find((t) => t.kind === "VARIABLE");
  if (variable !== undefined) throw fault(variable.span.start.offset - 2, DiagnosticCode.UnexpectedToken);
  const read = readOverride(name, text);
  if ("problem" in read) throw fault(read.problem.span.start.offset - 2, read.problem.code);
  return read.values;
}
