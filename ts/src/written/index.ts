/**
 * The low level's public API (spec 6; import path "villanelle/written"): the config as written, editable, saved back.
 * The rendered layer reaches the low level only through this module (spec 7.0; checked by ts/eslint.config.js). Its
 * types are generated (gen/api/written.ts), but for `LoadOptions` and `Processor` (processor.ts says why).
 */

export { StatementKind, UnreadableReason, ValueKind, VariableKind } from "../gen/api/kinds.js";
export { MAX_DEPTH, MAX_DIRECTIVES, MAX_SAFE_INTEGER, RESERVED, VARIABLE_NAME } from "../gen/api/limits.js";
export type {
  Copy,
  DirectiveExpansion,
  Document,
  DocumentEdge,
  DocumentGraph,
  ExpandedIndex,
  ExpandedList,
  ExpandedSlice,
  ExpandedString,
  ExpandedValue,
  ExpandedWord,
  Expansion,
  ExpansionBlock,
  Extension,
  ExtensionLine,
  ExtensionUse,
  Index,
  IndexValue,
  List,
  OverrideVariable,
  Parameter,
  ProcessorOptions,
  Reference,
  ReferenceResolution,
  Resolution,
  SetLine,
  SetVariable,
  Slice,
  SliceValue,
  SnippetLine,
  Statement,
  String,
  UnreadableExpansion,
  UnreadableLine,
  UseLine,
  Variable,
  Word,
  WrittenBlock,
  WrittenDirective,
  WrittenValue,
} from "../gen/api/written.js";
export { formatDiagnostic } from "./format.js";
export { type LoadOptions, type Processor, villanelle } from "./processor.js";
