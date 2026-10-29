/**
 * The syntax layer's public API (spec 3; import path "villanelle/syntax"): `parse` and the lossless syntax tree of one
 * text. Read-only, one text at a time, no I/O. Its types are generated (gen/api/syntax.ts).
 */

export { NodeKind, TokenKind } from "../gen/api/kinds.js";
export { MAX_NESTING } from "../gen/api/limits.js";
export type { Node, Syntax, Token, TokenRange } from "../gen/api/syntax.js";
export { spanOf, textOf } from "./cst.js";
export { parse } from "./parse.js";
