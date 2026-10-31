/**
 * knobly: a configuration language defined by one grammar (grammar/Knobly.g4). The package root holds the
 * shared layer (places, origins, diagnostics, errors, config text) and the I/O ports; each layer has its own import
 * path (binding guide rule 9): "knobly/syntax" is the lossless syntax tree of one text (`parse`);
 * "knobly/written" is the low level, the config as written (`knobly({ source }).load(path)` returns a document
 * graph of editable statements and values, which reads and saves itself); "knobly/rendered" builds on it
 * (`render(graph)` gives the directives after expansion, with origins, addresses, value readers and change lists).
 * The core does no I/O: see "knobly/node" and "knobly/browser" for document sources and writers, and
 * "knobly/include" for the include extension. Every type is generated from spec/schema/api.json (gen/api/).
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
  KnoblyError,
} from "./gen/api/errors.js";
export type { DocumentSource, DocumentWriter, FileWrite, LoadContext } from "./gen/api/io.js";
export { PlaceKind, Severity, StepKind, WalkControl } from "./gen/api/kinds.js";
export { PROGRAM_CODE } from "./gen/api/limits.js";
export type {
  Block,
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
import type { IoFunctions } from "./gen/api/io.js";
import type * as shared from "./gen/api/shared.js";
import { Diagnostics as DiagnosticsClass } from "./report.js";
import * as source from "./source.js";
import * as texts from "./text.js";

// Each public function and constructor is typed by its generated signature, which carries the schema's doc.
export const Diagnostics: shared.DiagnosticsConstructor = DiagnosticsClass;
export type Diagnostics = shared.Diagnostics;
export const checkLostUpdates: IoFunctions["checkLostUpdates"] = source.checkLostUpdates;
export const memorySource: IoFunctions["memorySource"] = source.memorySource;
export const memoryWriter: IoFunctions["memoryWriter"] = source.memoryWriter;
export const quote: shared.SharedFunctions["quote"] = texts.quote;
export const text: shared.SharedFunctions["text"] = texts.text;
