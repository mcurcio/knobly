/**
 * The value rules of grammar/villanelle.ebnf (NumberText, IntegerText, BooleanText, EscapeText) and the canonical text of a value
 * (slices.md §1.3): the one home of each rule. Package-internal, shared; Python ports it as `_values.py`.
 */

/** IntegerText: `'-'? Digits`, Digits being `0` or a non-zero digit then digits. */
const INTEGER_TEXT = /^-?(?:0|[1-9][0-9]*)$/;

/**
 * The integer a word spells, or undefined when it is not an IntegerText or lies outside plus or minus 2^53-1 (so
 * every binding reads the same number). `-0` is `0` (spec/contract.md 3: zero has one sign).
 */
export function integerOf(word: string): number | undefined {
  if (!INTEGER_TEXT.test(word)) return undefined;
  const value = Number(word);
  if (!Number.isSafeInteger(value)) return undefined;
  return value === 0 ? 0 : value;
}

/** NumberText: a JSON number (RFC 8259 section 6), `'-'? Digits Fraction? Exponent?`. */
const NUMBER_TEXT = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?$/;

/**
 * The number a word spells, rounded to the nearest double; undefined when it is not a NumberText or its value lies
 * beyond the double range (`1e400`). Never negative zero: `-0`, `-0.0` and `-1e-400` read as `0` (spec/contract.md 3).
 */
export function numberOf(word: string): number | undefined {
  if (!NUMBER_TEXT.test(word)) return undefined;
  const value = Number(word);
  if (!Number.isFinite(value)) return undefined;
  return value === 0 ? 0 : value;
}

/** BooleanText: the word `true` or `false`; undefined for any other word. */
export function booleanOf(word: string): boolean | undefined {
  if (word === "true") return true;
  if (word === "false") return false;
  return undefined;
}

/** The six escapes of EscapeText and what each decodes to. */
const ESCAPES: Readonly<Record<string, string>> = { '"': '"', "'": "'", "\\": "\\", n: "\n", t: "\t", r: "\r" };

/** Whether every backslash escape in a STRING token's text is one of the six of EscapeText. */
export function hasOnlyKnownEscapes(token: string): boolean {
  for (const match of token.slice(1, -1).matchAll(/\\(.)/gsu)) {
    if (ESCAPES[match[1] ?? ""] === undefined) return false;
  }
  return true;
}

/** The text between a STRING token's quotes, escapes decoded. Call only after `hasOnlyKnownEscapes`. */
export function decodeString(token: string): string {
  return token.slice(1, -1).replace(/\\(.)/gsu, (_, escaped: string) => ESCAPES[escaped] ?? escaped);
}

/** A decoded string's canonical text: double-quoted, with `\`, `"`, newline, tab and carriage return escaped. */
export function canonicalString(value: string): string {
  const escaped = value.replace(/[\\"\n\t\r]/g, (c) => ({ "\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r" })[c] ?? c);
  return `"${escaped}"`;
}

/** A slice's or an index's canonical text: `name[start:end]` (either side empty when absent) or `name[i]`. */
export function canonicalSlice(name: string, bounds: { start?: number; end?: number } | { index: number }): string {
  if ("index" in bounds) return `${name}[${String(bounds.index)}]`;
  const side = (n: number | undefined): string => (n === undefined ? "" : String(n));
  return `${name}[${side(bounds.start)}:${side(bounds.end)}]`;
}

/** A list's canonical text: its items' texts joined by `, ` in brackets. */
export function canonicalList(items: readonly string[]): string {
  return `[${items.join(", ")}]`;
}
