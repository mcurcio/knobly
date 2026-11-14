/**
 * The "knobly/highlight" entry: syntax highlighting for an editor, with no antlr4 (design/releases-and-highlighting.md
 * section 3). It scans with the lexer DFA that tools/highlight/gen.py builds from grammar/Knobly.g4, the same
 * longest-match DFA every knobly lexer is, so each span is exactly one of the tokens `parse` returns, and classes
 * each token by grammar/highlight.json. It uses no Node API, so a browser bundle can take it.
 *
 * Proposal (pending the owner, design note section 5 question 4): these declarations are hand-written until the
 * highlighter's place in spec/schema/api.json is decided.
 */

import type { TokenKind } from "./gen/api/kinds.js";
import { ACCEPT, CLASS, CLASSES, HEAD, KINDS, MOVES, ROLE } from "./gen/highlight.js";

/** The highlight classes (grammar/highlight.json): one per span, stable strings an editor can style. */
export const HighlightClass = {
  /** A statement's name: its first word. */
  Directive: "directive",
  /** An `@` word: `@set`, `@snippet`, `@use`, an extension's `@include`. */
  Keyword: "keyword",
  /** A bare word that is a value. */
  Word: "word",
  /** A `$name`. */
  Variable: "variable",
  /** A word that starts with a digit or `-`. */
  Number: "number",
  /** A quoted string, double or single. */
  String: "string",
  /** A `#` comment. */
  Comment: "comment",
  /** `{ } [ ] ; , ~` */
  Punctuation: "punctuation",
  /** Spaces, tabs, line breaks and a byte order mark. */
  Space: "space",
  /** Text that does not lex: an unterminated string, a bad escape, a lone `$`, a character no token starts with. */
  Error: "error",
} as const;
export type HighlightClass = (typeof HighlightClass)[keyof typeof HighlightClass];

/** One token of the text, classed. */
export interface HighlightSpan {
  /** Where the span starts: a UTF-16 offset into the text, as every TypeScript position. */
  readonly start: number;
  /** Where it ends (exclusive); never equal to `start`. */
  readonly end: number;
  readonly class: HighlightClass;
  /** The token's kind, for finer styling: the kind `parse` gives the same token. */
  readonly kind: TokenKind;
}

const classes: readonly HighlightClass[] = CLASSES;

/**
 * The text's tokens, each classed for highlighting. The spans are contiguous, start at 0, end at `text.length`, are
 * never empty and are exactly `parse(text).tokens`. A `WORD` that is a statement's first token (after the text's
 * start, a `;`, a `{` or a `}`, with only spaces, line breaks and comments between) is a `directive`. Never throws:
 * what does not lex is an `error` span.
 */
export function highlight(text: string): HighlightSpan[] {
  const spans: HighlightSpan[] = [];
  let at = 0;
  let head = true;
  while (at < text.length) {
    // The longest match: every state but the start accepts, so run until no move applies.
    let state = 0;
    let i = at;
    for (;;) {
      if (i >= text.length) break;
      const cp = text.codePointAt(i) as number;
      const next = move(MOVES[state] as readonly number[], cp);
      if (next < 0) break;
      state = next;
      i += cp > 0xffff ? 2 : 1;
    }
    // The start state takes every code point (tools/highlight/gen.py checks it), so `i > at` here.
    const token = ACCEPT[state] as number;
    const headClass = HEAD[token] as number;
    const cls = head && headClass >= 0 ? headClass : (CLASS[token] as number);
    spans.push({ start: at, end: i, class: classes[cls] as HighlightClass, kind: KINDS[token] as TokenKind });
    const role = ROLE[token] as number;
    head = role === 1 || (head && role === 2);
    at = i;
  }
  return spans;
}

/** The target of the state's move on `cp`, or -1: a binary search of its sorted (lo, hi, target) triples. */
function move(row: readonly number[], cp: number): number {
  let lo = 0;
  let hi = row.length / 3 - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const base = mid * 3;
    if (cp < (row[base] as number)) hi = mid - 1;
    else if (cp > (row[base + 1] as number)) lo = mid + 1;
    else return row[base + 2] as number;
  }
  return -1;
}
