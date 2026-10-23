/**
 * villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4), with a lossless syntax
 * tree, typed values, a directive facade and an include graph. The core does no I/O: see "villanelle/node" and
 * "villanelle/browser" for loaders and writers.
 *
 * This barrel is frozen with the M1 interfaces (vil-g7n.1): slices fill bodies, they do not add exports.
 */

export type { ISourcePosition, ISourceSpan } from "./span.js";
export { DiagnosticCode, DiagnosticError, type IDiagnostic } from "./diagnostics.js";

export { type IToken, TokenKind } from "./syntax/tokens.js";
export { type INode, type ISyntax, type ITokenRange, NodeKind, spanOf, textOf, type ValueRef } from "./syntax/cst.js";
export { parse } from "./syntax/parse.js";
export {
  type IIndexValue,
  type ISliceValue,
  type IStringValue,
  type IWordValue,
  type Value,
  ValueKind,
  valueOf,
} from "./value.js";

export {
  createAst,
  findDirectives,
  type IAstArgument,
  type IAstDirective,
  type IAstDirectiveList,
  type IAstDocument,
  parseDocument,
  walkDirectives,
} from "./ast/ast.js";

export type { IDocumentEdge, IDocumentGraph, IDocumentNode, IGraphDiagnostic } from "./graph/graph.js";
export {
  composeLoaders,
  type DocumentLoader,
  type IDocumentWriter,
  type ILoadContext,
  type ILoadedDocument,
} from "./graph/io.js";
export { type IParseGraphOptions, parseGraph } from "./graph/parse-graph.js";
export { iterateDirectives } from "./graph/iterate.js";
export { save } from "./graph/save.js";
