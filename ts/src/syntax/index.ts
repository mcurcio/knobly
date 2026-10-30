/**
 * The syntax layer's public API (spec 3; import path "knobly/syntax"): `parse` and the lossless syntax tree of one
 * text. Read-only, one text at a time, no I/O. Its types are generated (gen/api/syntax.ts).
 */

export { NodeKind, TokenKind } from "../gen/api/kinds.js";
export { MAX_NESTING } from "../gen/api/limits.js";
export type { Node, Syntax, Token, TokenRange } from "../gen/api/syntax.js";
import type { SyntaxFunctions } from "../gen/api/syntax.js";
import * as cst from "./cst.js";
import * as parser from "./parse.js";

// Each public function is typed by its generated signature, which carries the schema's doc.
export const parse: SyntaxFunctions["parse"] = parser.parse;
export const spanOf: SyntaxFunctions["spanOf"] = cst.spanOf;
export const textOf: SyntaxFunctions["textOf"] = cst.textOf;
