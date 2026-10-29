/**
 * The low level's public API (spec 6): the config as written, editable, saved back. The rendered layer reaches the
 * low level only through this module (spec 7.0; checked by ts/eslint.config.js), and the package entry re-exports it.
 */

export { formatDiagnostic } from "./format.js";
export { type ILoadOptions, type IProcessor, type IProcessorOptions, villanelle } from "./processor.js";
export type {
  ICopy,
  IDirectiveExpansion,
  IDocument,
  IDocumentEdge,
  IDocumentGraph,
  IExpansion,
  IExtensionLine,
  IIndex,
  IList,
  IOverrideVariable,
  IParameter,
  IReference,
  IReferenceResolution,
  IResolution,
  ISetLine,
  ISetVariable,
  ISlice,
  ISnippetLine,
  IStatementBase,
  IString,
  IUnreadableExpansion,
  IUnreadableLine,
  IUseLine,
  IValueBase,
  IValueExpansion,
  IVariableBase,
  IWord,
  IWrittenBlock,
  IWrittenDirective,
  Statement,
  StatementKind,
  Variable,
  VariableKind,
  WrittenValue,
} from "./model.js";
