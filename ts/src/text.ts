/**
 * Values going in (spec 6.9): every edit takes villanelle text only, and `quote` writes a plain string as villanelle
 * text. Shared: the one home of the argument type check and its message (spec/schema/api.json, "argument type error
 * message").
 */

import { canonicalString } from "./values.js";

/**
 * The argument type check: `value` must be a string, else TypeError naming the member and the parameter as the caller
 * wrote them (`set`, `"text"`; `load`, `overrides["port"]`) and pointing to `quote()`. Every member that takes text
 * calls it before changing anything.
 * @throws TypeError when `value` is not a string
 */
export function requireText(value: unknown, member: string, parameter: string): asserts value is string {
  if (typeof value === "string") return;
  const got = value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
  throw new TypeError(
    `${member}(): argument "${parameter}" must be a string, not ${got}; villanelle edits take text: quote() a program string, String() a number`,
  );
}

/**
 * A plain string as a villanelle string, escapes included: `quote("10.0.60.31")` is `"10.0.60.31"`. The same
 * canonical string text a rendered value has (backslash, quote, newline, tab and carriage return escaped).
 * @throws TypeError when `text` is not a string
 */
export function quote(text: string): string {
  requireText(text, "quote", "text");
  return canonicalString(text);
}
