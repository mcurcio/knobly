/**
 * Our token vocabulary. The values are the token names of grammar/Villanelle.g4, so the grammar is the one
 * source of the names; ANTLR's types never cross the adapter in syntax/parse.ts.
 */

import type { ISourceSpan } from "../span.js";

export const TokenKind = {
  Bom: "BOM",
  Space: "SPACE",
  Newline: "NEWLINE",
  Comment: "COMMENT",
  Word: "WORD",
  String: "STRING",
  LBrace: "LBRACE",
  RBrace: "RBRACE",
  LBrack: "LBRACK",
  RBrack: "RBRACK",
  Semi: "SEMI",
  Comma: "COMMA",
  Colon: "COLON",
  /** Error token: a string literal without its closing quote. Never used by the syntax rules. */
  UnterminatedString: "UNTERMINATED_STRING",
  /** Error token: one character no other token may start with. Never used by the syntax rules. */
  BadChar: "BAD_CHAR",
} as const;
export type TokenKind = (typeof TokenKind)[keyof typeof TokenKind];

/**
 * One token. Invariants of every token list `parse` returns:
 * - the tokens are contiguous and in source order, and their `text`s concatenated equal the input exactly
 *   (valid and broken input alike; there is no end-of-file token);
 * - `text.length === span.end.offset - span.start.offset`, and `text` is never empty.
 */
export interface IToken {
  readonly kind: TokenKind;
  /** The exact source text of the token. */
  readonly text: string;
  readonly span: ISourceSpan;
}
