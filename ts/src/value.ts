/**
 * Typed values: the view over the CST that consumers read instead of re-parsing tokens (vil-9ze).
 * The `Value` union grows one kind at a time; kinds not yet supported throw (see valueOf).
 */

import { DiagnosticCode, DiagnosticError } from "./diagnostics.js";
import type { ISourceSpan } from "./span.js";
import { type INode, type ISyntax, NodeKind, spanOf, type ValueRef } from "./syntax/cst.js";
import { type IToken, TokenKind } from "./syntax/tokens.js";

export const ValueKind = {
  Word: "word",
  String: "string",
  /** `[0.04, 1, 0.5]`: read through the load layer's `IArgument.items()` (round 11). */
  List: "list",
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
  if (typeof ref === "number") return tokenValue(syntax, ref);
  switch (ref.kind) {
    case NodeKind.Slice:
      return sliceValue(syntax, ref);
    case NodeKind.List:
      throw new Error("unsupported value kind: list");
    default:
      throw new TypeError(`not a value: a ${ref.kind} node`);
  }
}

function tokenValue(syntax: ISyntax, index: number): Value {
  const token = syntax.tokens[index];
  if (!Number.isInteger(index) || token === undefined) throw new TypeError(`not a token index: ${index}`);
  switch (token.kind) {
    case TokenKind.Word:
      return { kind: ValueKind.Word, text: token.text, span: token.span };
    case TokenKind.String:
      return { kind: ValueKind.String, value: decodeString(token.text), span: token.span };
    default:
      throw new TypeError(`not a value: a ${token.kind} token`);
  }
}

/** Backslash escapes with their own meaning; any other `\x` (`\\`, `\"`, `\'` among them) decodes to `x`. */
const ESCAPES: Readonly<Record<string, string>> = { n: "\n", t: "\t", r: "\r" };

/** The text between a STRING token's quotes, escapes decoded (see IStringValue). One escape is one code point. */
function decodeString(text: string): string {
  return text.slice(1, -1).replace(/\\(.)/gsu, (_, escaped: string) => ESCAPES[escaped] ?? escaped);
}

/** A slice node holds exactly `WORD [ bounds ]`, bounds being `W`, `W:W`, `W:` or `:W` (grammar rule bounds). */
function sliceValue(syntax: ISyntax, node: INode): ISliceValue | IIndexValue {
  const tokens = syntax.tokens.slice(node.start, node.end);
  const [name, open] = tokens;
  const close = tokens.at(-1);
  const bounds = tokens.slice(2, -1);
  if (
    name?.kind !== TokenKind.Word ||
    open?.kind !== TokenKind.LBrack ||
    close?.kind !== TokenKind.RBrack ||
    !isBoundsShape(bounds.map((t) => t.kind))
  ) {
    throw new TypeError(`not a well-formed slice: [${node.start}, ${node.end})`);
  }
  const span = spanOf(syntax, node);
  const [first, second, third] = bounds;
  if (bounds.length === 1 && first !== undefined) {
    return { kind: ValueKind.Index, name: name.text, index: integerBound(first), span };
  }
  const start = first?.kind === TokenKind.Word ? integerBound(first) : undefined;
  const endToken = first?.kind === TokenKind.Colon ? second : third;
  const end = endToken === undefined ? undefined : integerBound(endToken);
  return {
    kind: ValueKind.Slice,
    name: name.text,
    ...(start === undefined ? {} : { start }),
    ...(end === undefined ? {} : { end }),
    span,
  };
}

function isBoundsShape(kinds: readonly string[]): boolean {
  const W = TokenKind.Word;
  const C = TokenKind.Colon;
  return [[W], [W, C, W], [W, C], [C, W]].some(
    (shape) => shape.length === kinds.length && shape.every((kind, i) => kind === kinds[i]),
  );
}

const INTEGER = /^-?[0-9]+$/;

/** The integer a bound token spells (vil-9ze.3), or a located E4001. */
function integerBound(token: IToken): number {
  const value = Number(token.text);
  if (INTEGER.test(token.text) && Number.isSafeInteger(value)) return value;
  throw new DiagnosticError({
    code: DiagnosticCode.NonIntegerBound,
    message: `slice bound "${token.text}" is not an integer`,
    span: token.span,
  });
}
