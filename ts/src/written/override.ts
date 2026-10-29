/**
 * The check of an override (spec 6.3): one check, one home. `load` (for each of its `overrides`, in order) and
 * `set override` both call it, so both refuse the same texts with the same errors (round 13 root cause 2: before
 * milestone 1 they checked two ways and disagreed about "1;").
 */

import { makeDiagnostic } from "../diagnostics.js";
import { parseEntry } from "../syntax/parse.js";
import { requireText } from "../text.js";
import { type IOverrideValues, readOverride } from "./bind.js";
import { checkVariableName } from "./names.js";
import { DiagnosticCode, describe } from "../gen/api/codes.js";
import { BadTextError } from "../gen/api/errors.js";
import { TokenKind } from "../gen/api/kinds.js";

/** How the caller named what it was given, for the argument type error: `setOverride` / `text`, `load` / `overrides["port"]`. */
export interface IOverrideCaller {
  readonly member: string;
  readonly textParameter: string;
}

/** The check of an override's name alone (`setOverride(name, undefined)`). @throws MisuseError for a bad name */
export function checkOverrideName(name: unknown, member: string): asserts name is string {
  requireText(name, member, "name");
  checkVariableName(name);
}

/**
 * Check one override and read its values: the name (a misuse error unless it is a variable name), the text's type
 * (the argument type error), then the text with the grammar's `valuesText` entry rule (its diagnostic); else E2001 at
 * a `$name`, or at 0:0 when it holds no value. Every diagnostic is located in `text`.
 * @throws MisuseError for a bad name; TypeError for a text that is not a string; BadTextError for text the check refuses
 */
export function checkOverride(name: unknown, text: unknown, caller: IOverrideCaller): IOverrideValues {
  checkOverrideName(name, caller.member);
  requireText(text, caller.member, caller.textParameter);
  const syntax = parseEntry(text, "valuesText");
  if (syntax.diagnostics.length > 0) throw new BadTextError(syntax.diagnostics);
  const values = syntax.tokens.filter((t) => t.kind !== TokenKind.SPACE && t.kind !== TokenKind.NEWLINE && t.kind !== TokenKind.COMMENT);
  const at = values.length === 0 ? undefined : values.find((t) => t.kind === TokenKind.VARIABLE);
  if (values.length === 0 || at !== undefined) {
    const code = DiagnosticCode.UnexpectedToken;
    const position = at?.span.start ?? { offset: 0, line: 0, column: 0 };
    throw new BadTextError([makeDiagnostic(code, describe(code).message, { start: position, end: position })]);
  }
  return readOverride(name, syntax);
}
