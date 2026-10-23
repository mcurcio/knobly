/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * The lossless concrete syntax tree: concept nodes over token ranges (design/RECORD.md, "The CST").
 */

import type { IDiagnostic } from "../diagnostics.js";
import type { ISourceSpan } from "../span.js";
import type { IToken } from "./tokens.js";

export const NodeKind = {
  Document: "document",
  Directive: "directive",
  Block: "block",
  List: "list",
  Slice: "slice",
  /** One bad statement, or a run of tokens the parser could not use. Never has children. */
  Error: "error",
} as const;
export type NodeKind = (typeof NodeKind)[keyof typeof NodeKind];

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
 * A reference to one value of a directive or list: the index of a WORD or STRING token, or a `slice` or `list`
 * node. `valueOf` turns it into a typed value.
 */
export type ValueRef = number | INode;

/**
 * The span of a token range. An empty range at index i is a zero-width span at the start of token i, or at the
 * end of the text when i === tokens.length.
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function spanOf(syntax: ISyntax, range: ITokenRange): ISourceSpan {
  throw new Error("not implemented");
}

/**
 * The exact source text of a token range. `textOf(syntax, syntax.root)` is the whole input (the round trip).
 * @throws RangeError when the range is outside [0, tokens.length] or start > end.
 */
export function textOf(syntax: ISyntax, range: ITokenRange): string {
  throw new Error("not implemented");
}
