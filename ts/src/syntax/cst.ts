/**
 * The lossless concrete syntax tree: concept nodes over token ranges (design/RECORD.md, "The CST"). The types are
 * generated (gen/api/syntax.ts). A node's `children` are in source order, do not overlap, and lie inside [start, end);
 * tokens of the range not covered by a child belong to the node directly (names, punctuation, spaces); a `directive`
 * node starts at its name token; a `slice` node spans `name[bounds]` exactly. An error node is one bad statement, or a
 * run of tokens the parser could not use; it never has children.
 */

import type { SourcePosition, SourceSpan } from "../gen/api/shared.js";
import type { Node, Syntax, TokenRange } from "../gen/api/syntax.js";

/**
 * A reference to one value of a directive or list: the index of a WORD, STRING or VARIABLE token, or a `slice` or
 * `list` node. The binding expands it into an expanded value. Package-internal.
 */
export type ValueRef = number | Node;

/**
 * The span of a token range. An empty range at index i is a zero-width span at the start of token i, or at the
 * end of the text when i === tokens.length.
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function spanOf(syntax: Syntax, range: TokenRange): SourceSpan {
  const { tokens } = syntax;
  checkRange(tokens.length, range);
  const at = (i: number): SourcePosition =>
    tokens[i]?.span.start ?? tokens.at(-1)?.span.end ?? { offset: 0, line: 0, column: 0 };
  const start = at(range.start);
  if (range.start === range.end) return { start, end: start };
  return { start, end: tokens[range.end - 1]?.span.end ?? start };
}

/**
 * The exact source text of a token range. `textOf(syntax, syntax.root)` is the whole input (the round trip).
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function textOf(syntax: Syntax, range: TokenRange): string {
  checkRange(syntax.tokens.length, range);
  let text = "";
  for (let i = range.start; i < range.end; i++) text += syntax.tokens[i]?.text ?? "";
  return text;
}

function checkRange(length: number, range: TokenRange): void {
  const { start, end } = range;
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > length || start > end) {
    throw new RangeError(`token range [${start}, ${end}) is outside [0, ${length}]`);
  }
}
