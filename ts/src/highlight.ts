/**
 * The "knobly/highlight" entry: syntax highlighting for an editor, with no antlr4 (spec 3.4: a MAY capability,
 * TypeScript only today). It scans with the lexer DFA that tools/highlight/gen.py builds from grammar/Knobly.g4, the
 * same longest-match DFA every knobly lexer is, so each span is exactly one of the tokens `parse` returns, and classes
 * each token by grammar/highlight.json. It uses no Node API, so a browser bundle can take it. Its types are generated
 * (gen/api/syntax.ts, gen/api/kinds.ts).
 */

import { HighlightClass } from "./gen/api/kinds.js";
import type { TokenKind } from "./gen/api/kinds.js";
import type { HighlightFunctions, HighlightSpan } from "./gen/api/syntax.js";
import { ACCEPT, CLASS, CLASSES, HEAD, KINDS, MOVES, ROLE } from "./gen/highlight.js";

export { HighlightClass };
export type { HighlightSpan };

const classes: readonly HighlightClass[] = CLASSES;

export const highlight: HighlightFunctions["highlight"] = (text) => {
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
};

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
