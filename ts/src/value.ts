/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * Typed values: the view over the CST that consumers read instead of re-parsing tokens (vil-9ze).
 * The `Value` union grows one kind at a time; kinds not yet supported throw (see valueOf).
 */

import type { ISourceSpan } from "./span.js";
import type { ISyntax, ValueRef } from "./syntax/cst.js";

export const ValueKind = {
  Word: "word",
  String: "string",
  Slice: "slice",
  Index: "index",
} as const;
export type ValueKind = (typeof ValueKind)[keyof typeof ValueKind];

/** A bare word, such as `listen` or `/*.conf`. */
export interface IWordValue {
  readonly kind: typeof ValueKind.Word;
  /** The word exactly as written. */
  readonly text: string;
  readonly span: ISourceSpan;
}

/** A quoted string literal, decoded. */
export interface IStringValue {
  readonly kind: typeof ValueKind.String;
  /**
   * The text between the quotes with escapes decoded: \\ \n \t \r \" \' (v1 escapes, vil-m8w). Any other
   * backslash escape decodes to the escaped character itself (`\q` gives `q`), as the rasl lexer did.
   */
  readonly value: string;
  readonly span: ISourceSpan;
}

/** `name[start:end]`, `name[start:]` or `name[:end]`. At least one of start and end is present. */
export interface ISliceValue {
  readonly kind: typeof ValueKind.Slice;
  readonly name: string;
  readonly start?: number;
  readonly end?: number;
  /** The whole slice, from the first character of the name to the closing `]`. */
  readonly span: ISourceSpan;
}

/** `name[index]`: one element (vil-9ze.2). */
export interface IIndexValue {
  readonly kind: typeof ValueKind.Index;
  readonly name: string;
  readonly index: number;
  readonly span: ISourceSpan;
}

export type Value = IWordValue | IStringValue | ISliceValue | IIndexValue;

/**
 * The typed value a reference points to.
 *
 * Bounds and indexes are integers (vil-9ze.3): an optional "-" then ASCII digits, within
 * Number.MIN_SAFE_INTEGER..Number.MAX_SAFE_INTEGER. Meaning (inclusive or exclusive end, negative counting) is the
 * consumer's, not villanelle's.
 *
 * @throws DiagnosticError with code E4001 (NonIntegerBound), spanning the bad bound token, for any other bound.
 * @throws Error "unsupported value kind: <kind>" for a value kind the union does not have yet (lists, until vil-9ze).
 * @throws TypeError when `ref` is not a WORD/STRING token index or a slice/list node of `syntax`.
 */
export function valueOf(syntax: ISyntax, ref: ValueRef): Value {
  throw new Error("not implemented");
}
