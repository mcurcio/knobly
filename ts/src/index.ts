/**
 * villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4). Tier 1 is the lossless
 * syntax tree of one text (`parse`). The low level is the config as written: `villanelle({ source }).load(path)`
 * returns a document graph of editable statements and values, which reads (`graph.read()`) and saves
 * (`graph.save(writer)`) itself. The rendered tree builds on it: `render(graph)` gives the directives after
 * expansion, with origins, addresses, value readers and change lists (`rendered.diff(after)`). The core does no I/O:
 * see "villanelle/node" and "villanelle/browser" for document sources and writers, and "villanelle/include" for the
 * include extension.
 */

export type { ISourcePosition, ISourceSpan } from "./span.js";
export { DiagnosticCode, type IDiagnostic } from "./diagnostics.js";
export { BadTextError, DetachedError, DiagnosticError, EditError, ReadError, SaveError, VillanelleError } from "./errors.js";

export type { IToken, TokenKind } from "./syntax/tokens.js";
export { type INode, type ISyntax, type ITokenRange, type NodeKind, spanOf, textOf, type ValueRef } from "./syntax/cst.js";
export { parse } from "./syntax/parse.js";
export type {
  ExpandedValue,
  IExpandedIndex,
  IExpandedList,
  IExpandedSlice,
  IExpandedString,
  IExpandedValueBase,
  IExpandedWord,
  IIndexValue,
  ISliceValue,
  PlainValue,
  ValueKind,
} from "./value.js";

export type { IDirectiveOrigin, IOrigin, IOverride, IPlace, IStep, PlaceKind, StepKind } from "./origin.js";
export { Diagnostics, type ILocatable, type ILocatedDiagnostic, type ProgramCode } from "./report.js";
export {
  type IDocumentSource,
  type IDocumentWriter,
  type IFileWrite,
  type ILoadContext,
  memorySource,
  memoryWriter,
} from "./source.js";
export type { IExtension, IExtensionUse } from "./extension.js";
export { quote } from "./text.js";

export * from "./written/index.js";
export * from "./rendered/index.js";
