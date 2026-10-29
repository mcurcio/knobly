/**
 * Our token vocabulary. `TokenKind` is generated from grammar/Villanelle.g4's lexer rules (tools/gen-api.py), so the
 * grammar is the one source of the names; ANTLR's types never cross the adapter in syntax/parse.ts.
 */

import type { ISourceSpan } from "../span.js";

export type { TokenKind } from "../gen/api/kinds.js";
import type { TokenKind } from "../gen/api/kinds.js";

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

/** The three tokens of a bare word (spec 3.1): all three are the value kind `word`. */
export function isWordKind(kind: TokenKind): boolean {
  return kind === "WORD" || kind === "INTEGER" || kind === "DIGIT_WORD";
}
