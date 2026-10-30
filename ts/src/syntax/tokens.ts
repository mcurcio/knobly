/**
 * Our token vocabulary. `TokenKind` is generated from grammar/Knobly.g4's lexer rules (tools/gen-api.py), so the
 * grammar is the one source of the names; ANTLR's types never cross the adapter in syntax/parse.ts. The `Token` type
 * is generated (gen/api/syntax.ts). Invariants of every token list `parse` returns: the tokens are contiguous and in
 * source order, and their `text`s concatenated equal the input exactly (valid and broken input alike; there is no
 * end-of-file token); `text.length === span.end.offset - span.start.offset`, and `text` is never empty.
 */

import { TokenKind } from "../gen/api/kinds.js";

/** The four tokens of a bare word (spec 3.1): all four are the value kind `word`. */
export function isWordKind(kind: TokenKind): boolean {
  return kind === TokenKind.WORD || kind === TokenKind.AT_WORD || kind === TokenKind.INTEGER || kind === TokenKind.DIGIT_WORD;
}
