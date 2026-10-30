/**
 * Values going in (spec 6.9): every edit takes config text only, its own type (owner, 2026-10-29, "Yes, its own
 * type"), made only by `quote` (a program string written as a knobly string) or `text` (text already written as
 * knobly text). A branded string: the TypeScript handbook's and Zod's `.brand()` pattern, as the browser's Trusted
 * Types accept a sink's string only from a named factory. Shared: the one home of the argument type check and its
 * message (spec/schema/api.json, "argument type error message", generated as `argumentTypeMessage`). The type
 * `ConfigText` is generated (gen/api/shared.ts).
 */

import { argumentTypeMessage } from "./gen/api/errors.js";
import type { ConfigText } from "./gen/api/shared.js";
import { canonicalString } from "./values.js";

/**
 * The argument type check: `value` must be a string, else TypeError naming the member and the parameter as the caller
 * wrote them (`set`, `"text"`; `load`, `overrides["port"]`) and pointing to `quote()` and `text()`. Every member that
 * takes text calls it before changing anything (the brand is erased at run time: only the type checker sees it).
 * @throws TypeError when `value` is not a string
 */
export function requireText(value: unknown, member: string, parameter: string): asserts value is string {
  if (typeof value === "string") return;
  throw new TypeError(argumentTypeMessage(member, parameter, typeNameOf(value)));
}

/** What an argument type error says a value is: `null`, `array`, or its `typeof`. */
export function typeNameOf(value: unknown): string {
  return value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
}

export function quote(text: string): ConfigText {
  requireText(text, "quote", "text");
  return canonicalString(text) as ConfigText;
}

export function text(raw: string): ConfigText {
  requireText(raw, "text", "raw");
  return raw as ConfigText;
}
