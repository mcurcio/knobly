/**
 * The lossless concrete syntax tree: concept nodes over token ranges (design/RECORD.md, "The CST").
 */

import type { IDiagnostic } from "../diagnostics.js";
import type { NodeKind } from "../gen/api/kinds.js";
import type { ISourcePosition, ISourceSpan } from "../span.js";
import type { IToken } from "./tokens.js";

/** The node kinds, generated from spec/schema/api.json. An error node is one bad statement, or a run of tokens the
 * parser could not use; it never has children. */
export type { NodeKind };

/** A half-open range [start, end) of token indices. */
export interface ITokenRange {
  readonly start: number;
  readonly end: number;
}

/**
 * A CST node. Invariants:
 * - `children` are in source order, do not overlap, and lie inside [start, end);
 * - tokens of the range not covered by a child belong to this node directly (names, punctuation, spaces);
 * - a `directive` node starts at its name token (a WORD); a `slice` node spans `name[bounds]` exactly.
 */
export interface INode extends ITokenRange {
  readonly kind: NodeKind;
  readonly children: readonly INode[];
}

/** The result of `parse`: every token, the tree over them, and what went wrong. */
export interface ISyntax {
  /** Every token of the input; see IToken for the round-trip invariant. */
  readonly tokens: readonly IToken[];
  /** A `document` node with `start === 0` and `end === tokens.length`. */
  readonly root: INode;
  /** Lexical and syntax diagnostics in source order; empty exactly when the input is in the grammar's language. */
  readonly diagnostics: readonly IDiagnostic[];
}

/**
 * A reference to one value of a directive or list: the index of a WORD, STRING or VARIABLE token, or a `slice` or
 * `list` node. The binding expands it into an expanded value.
 */
export type ValueRef = number | INode;

/**
 * The span of a token range. An empty range at index i is a zero-width span at the start of token i, or at the
 * end of the text when i === tokens.length.
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function spanOf(syntax: ISyntax, range: ITokenRange): ISourceSpan {
  const { tokens } = syntax;
  checkRange(tokens.length, range);
  const at = (i: number): ISourcePosition =>
    tokens[i]?.span.start ?? tokens.at(-1)?.span.end ?? { offset: 0, line: 0, column: 0 };
  const start = at(range.start);
  if (range.start === range.end) return { start, end: start };
  return { start, end: tokens[range.end - 1]?.span.end ?? start };
}

/**
 * The exact source text of a token range. `textOf(syntax, syntax.root)` is the whole input (the round trip).
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function textOf(syntax: ISyntax, range: ITokenRange): string {
  checkRange(syntax.tokens.length, range);
  let text = "";
  for (let i = range.start; i < range.end; i++) text += syntax.tokens[i]?.text ?? "";
  return text;
}

function checkRange(length: number, range: ITokenRange): void {
  const { start, end } = range;
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > length || start > end) {
    throw new RangeError(`token range [${start}, ${end}) is outside [0, ${length}]`);
  }
}
