/**
 * villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4). The package root holds the
 * shared layer (places, origins, diagnostics, errors, config text) and the I/O ports; each layer has its own import
 * path (binding guide rule 9): "villanelle/syntax" is the lossless syntax tree of one text (`parse`);
 * "villanelle/written" is the low level, the config as written (`villanelle({ source }).load(path)` returns a document
 * graph of editable statements and values, which reads and saves itself); "villanelle/rendered" builds on it
 * (`render(graph)` gives the directives after expansion, with origins, addresses, value readers and change lists).
 * The core does no I/O: see "villanelle/node" and "villanelle/browser" for document sources and writers, and
 * "villanelle/include" for the include extension. Every type is generated from spec/schema/api.json (gen/api/).
 */

export { DiagnosticCode } from "./gen/api/codes.js";
export {
  BadTextError,
  DetachedError,
  DiagnosticError,
  LostUpdateError,
  MisuseError,
  ReadError,
  SaveError,
  VillanelleError,
} from "./gen/api/errors.js";
export type { DocumentSource, DocumentWriter, FileWrite, LoadContext } from "./gen/api/io.js";
export { PlaceKind, StepKind, WalkControl } from "./gen/api/kinds.js";
export { PROGRAM_CODE } from "./gen/api/limits.js";
export type {
  ConfigText,
  Diagnostic,
  DirectiveOrigin,
  Locatable,
  LocatedDiagnostic,
  Origin,
  Override,
  Place,
  ProgramCode,
  SourcePosition,
  SourceSpan,
  Step,
} from "./gen/api/shared.js";
export { Diagnostics } from "./report.js";
export { checkLostUpdates, memorySource, memoryWriter } from "./source.js";
export { quote, text } from "./text.js";
