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
export { DiagnosticCode, DiagnosticError, type IDiagnostic } from "./diagnostics.js";

export { type IToken, type TokenKind } from "./syntax/tokens.js";
export { type INode, type ISyntax, type ITokenRange, type NodeKind, spanOf, textOf, type ValueRef } from "./syntax/cst.js";
export { parse } from "./syntax/parse.js";
export { type IExpandedValue, type IIndexValue, type ISliceValue, type PlainValue, type ValueKind } from "./value.js";

export { type IDirectiveOrigin, type IOrigin, type IOverride, type IPlace, type IStep, type StepKind } from "./origin.js";
export { Diagnostics, type ILocatable, type ILocatedDiagnostic, type ProgramCode } from "./report.js";
export { type IDocumentSource, type IDocumentWriter, type IFileWrite, type ILoadContext, memorySource } from "./source.js";
export type { IExtension, IExtensionUse } from "./extension.js";
export { quote } from "./text.js";

export { formatDiagnostic } from "./written/format.js";
export { type ILoadOptions, type IProcessor, type IProcessorOptions, villanelle } from "./written/processor.js";
export type {
  ICopy,
  IDocument,
  IDocumentEdge,
  IDocumentGraph,
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

export {
  type Change,
  type ChangeKind,
  type IAdded,
  type IAddress,
  type IAddressStep,
  type IArgument,
  type IChanged,
  type IDirective,
  type IKeyOptions,
  type IRemoved,
  type IRendered,
  type IUnknown,
  type IUnreadable,
  type KeyRule,
  render,
  type UnreadableReason,
  type WalkControl,
} from "./rendered/index.js";
