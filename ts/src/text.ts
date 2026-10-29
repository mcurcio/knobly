/**
 * Values going in (spec 6.9): every edit takes config text only, its own type (owner, 2026-10-29, "Yes, its own
 * type"), made only by `quote` (a program string written as a villanelle string) or `text` (text already written as
 * villanelle text). A branded string: the TypeScript handbook's and Zod's `.brand()` pattern, as the browser's Trusted
 * Types accept a sink's string only from a named factory. Shared: the one home of the argument type check and its
 * message (spec/schema/api.json, "argument type error message").
 */

import { canonicalString } from "./values.js";

declare const configTextBrand: unique symbol;

/**
 * Villanelle text an edit or an override takes: a string branded so that a plain string is a type error. Made only by
 * `quote()` or `text()`; reading members (a value's or statement's `text`) return plain strings.
 */
export type ConfigText = string & { readonly [configTextBrand]: true };

/**
 * The argument type check: `value` must be a string, else TypeError naming the member and the parameter as the caller
 * wrote them (`set`, `"text"`; `load`, `overrides["port"]`) and pointing to `quote()` and `text()`. Every member that
 * takes text calls it before changing anything (the brand is erased at run time: only the type checker sees it).
 * @throws TypeError when `value` is not a string
 */
export function requireText(value: unknown, member: string, parameter: string): asserts value is string {
  if (typeof value === "string") return;
  throw new TypeError(
    `${member}(): argument "${parameter}" must be a string, not ${typeNameOf(value)}; villanelle edits take config text: quote() a program string, text() one already written as villanelle text, String() a number first`,
  );
}

/** What an argument type error says a value is: `null`, `array`, or its `typeof`. */
export function typeNameOf(value: unknown): string {
  return value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
}

/**
 * A plain string as a villanelle string, escapes included: `quote("10.0.60.31")` is `"10.0.60.31"`. The same
 * canonical string text a rendered value has (backslash, quote, newline, tab and carriage return escaped).
 * @throws TypeError when `text` is not a string
 */
export function quote(text: string): ConfigText {
  requireText(text, "quote", "text");
  return canonicalString(text) as ConfigText;
}

/**
 * Text already written as villanelle text, as config text, unchanged and unchecked (the edit it is given to checks
 * it): `statement.set(text("8080"))`, `value.set(text("[1, 2]"))`.
 * @throws TypeError when `raw` is not a string
 */
export function text(raw: string): ConfigText {
  requireText(raw, "text", "raw");
  return raw as ConfigText;
}
