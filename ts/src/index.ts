/**
 * villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4). Tier 1 is the lossless
 * syntax tree of one text (`parse`). The low level is the config as written (`villanelle({ source }).load(path)`
 * returns a document graph: editable statements and values, saved back with `save`); the rendered tree is built from
 * it (`processor.render(graph)`): directives after expansion, with origins, addresses, value readers and change lists. The core does no I/O: see "villanelle/node"
 * and "villanelle/browser" for document sources and writers, and "villanelle/include" for the include extension.
 */

export type { ISourcePosition, ISourceSpan } from "./span.js";
export { DiagnosticCode, DiagnosticError, type IDiagnostic } from "./diagnostics.js";

export { type IToken, TokenKind } from "./syntax/tokens.js";
export { type INode, type ISyntax, type ITokenRange, NodeKind, spanOf, textOf, type ValueRef } from "./syntax/cst.js";
export { parse } from "./syntax/parse.js";
export { type IIndexValue, type ISliceValue, ValueKind } from "./value.js";

export { type IDirectiveOrigin, type IHanded, type IOrigin, type IPlace, type IStep, StepKind } from "./load/origin.js";
export { Diagnostics, formatDiagnostic, type ILocatable, type ILocatedDiagnostic, type ProgramCode } from "./load/report.js";
export {
  type IAddress,
  type IAddressStep,
  type IArgument,
  type IDirective,
  type IUnreadable,
  type KeyRule,
  type PlainValue,
  UnreadableKind,
  type WalkControl,
} from "./load/directive.js";
export { type IDocumentSource, type ILoadContext, memorySource } from "./load/source.js";
export {
  type Change,
  ChangeKind,
  type IAdded,
  type IChanged,
  type IExtension,
  type IExtensionUse,
  type IKeyOptions,
  type ILoadOptions,
  type IProcessor,
  type IProcessorOptions,
  type IRemoved,
  type IRendered,
  type IUnknown,
  villanelle,
} from "./load/processor.js";
export type {
  ICopy,
  IDocument,
  IDocumentEdge,
  IDocumentGraph,
  IDocumentWriter,
  IFileWrite,
  IIndex,
  IList,
  IReference,
  IReferenceResolution,
  IResolution,
  ISetLine,
  ISlice,
  ISnippetLine,
  IStatementBase,
  IString,
  IUnreadableLine,
  IUseLine,
  IValueBase,
  IVariable,
  IWord,
  IWrittenBlock,
  IWrittenDirective,
  Statement,
  WrittenValue,
} from "./written/model.js";
export { BadTextError, DetachedError, EditError, NoSetLineError, ReadError, SaveError } from "./written/errors.js";
export { quote, save } from "./written/save.js";
