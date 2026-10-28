/**
 * Loading and change lists (R15 tier 2). A processor is made once with its document source, extensions and key
 * rule, as `postcss([plugins])` is; `load` reads a root file and everything it splices in; `diff` compares two loads
 * of the same processor by address.
 */

import type { DiagnosticError } from "../diagnostics.js";
import type { IAddress, IArgument, IDirective, IUnreadable, KeyRule, WalkControl } from "./directive.js";
import type { IDocumentGraph } from "./graph.js";
import type { IDirectiveOrigin } from "./origin.js";
import type { ILocatedDiagnostic, ProgramCode } from "./report.js";
import type { IDocumentSource } from "./source.js";
import { notImplemented } from "./todo.js";

/** One use of an extension directive, as the extension sees it. */
export interface IExtensionUse {
  /** The directive's values, expanded. */
  readonly args: readonly IArgument[];
  readonly origin: IDirectiveOrigin;
}

/**
 * An extension (R20): owns one directive name and turns each use of it into specs of files to splice in its place.
 * Pure: the load resolves and reads the specs through its document source, parses each file once, applies the
 * use's block of `set` lines to the spliced files, and enforces depth, cycles and limits. While registered, the
 * name is reserved at a line's start, as `set`, `snippet` and `use` are.
 */
export interface IExtension {
  readonly directive: string;
  /**
   * The specs for one use, in splice order. Throw a DiagnosticError (from an argument's or the use's place) for a
   * located failure; any other exception becomes E3006 at the directive.
   */
  specs(use: IExtensionUse): readonly string[];
}

export interface IProcessorOptions {
  readonly source: IDocumentSource;
  readonly extensions?: readonly IExtension[];
  /** Without one, a directive is named by its position among same-name siblings. */
  readonly key?: KeyRule;
}

export interface ILoadOptions {
  /**
   * Variables handed in by the program, by name without `$`. Each text is read as a run of values ("8080 443" is two
   * values). A handed-in variable wins over every `set` of its name, which acts as the default (L3).
   * The load rejects with TypeError for a name that is not letters, digits and `_`, or a text that is not one or
   * more values.
   */
  readonly variables?: Readonly<Record<string, string>>;
}

/** What one load produced. Problems are diagnostics; the root file owns the top level, as a directive its block. */
export interface ILoaded {
  /** The top-level readable directives, expanded. */
  readonly body: readonly IDirective[];
  /** Top-level statements that could not be read (R6: their siblings stay). */
  readonly unreadable: readonly IUnreadable[];
  /** The root file at 0:0, zero width: where a problem with no line of its own is placed. */
  readonly origin: IDirectiveOrigin;
  /** Every file's syntax diagnostics (files in first-read order), then expansion problems in expansion order. */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  readonly graph: IDocumentGraph;

  /** Every directive, depth-first in written order; see WalkControl. */
  walk(visit: (directive: IDirective) => WalkControl | void): void;
  /** A located error for a problem of the whole file, such as a required top-level directive left out. */
  error(message: string, code: ProgramCode): DiagnosticError;
}

export const ChangeKind = {
  Added: "added",
  Removed: "removed",
  /** Same address; its own values (by text) or whether it has a block differ. */
  Changed: "changed",
  /** It was in `before`; in `after` its block holds an unreadable statement that may be it. */
  Unknown: "unknown",
} as const;
export type ChangeKind = (typeof ChangeKind)[keyof typeof ChangeKind];

export interface IAdded {
  readonly kind: typeof ChangeKind.Added;
  readonly address: IAddress;
  readonly after: IDirective;
}

export interface IRemoved {
  readonly kind: typeof ChangeKind.Removed;
  readonly address: IAddress;
  readonly before: IDirective;
}

export interface IChanged {
  readonly kind: typeof ChangeKind.Changed;
  readonly address: IAddress;
  readonly before: IDirective;
  readonly after: IDirective;
}

export interface IUnknown {
  readonly kind: typeof ChangeKind.Unknown;
  readonly address: IAddress;
  readonly before: IDirective;
}

/**
 * One difference between two loads. An added, removed or unknown directive is listed alone, never with the
 * directives inside it (`walk` it); a changed one's block is compared at its own addresses.
 */
export type Change = IAdded | IRemoved | IChanged | IUnknown;

export interface IProcessor {
  /**
   * Read the root file at `path` (as the source names it) and everything it splices in. Never rejects for anything
   * in the text. @throws (rejects) DiagnosticError E3004 placed at the root file when the source cannot read it;
   * TypeError for bad handed-in variables; whatever the key rule throws.
   */
  load(path: string, options?: ILoadOptions): Promise<ILoaded>;
  /**
   * What differs between two loads of this processor, by address: removed and unknown in `before`'s walk order, then
   * added and changed in `after`'s. A directive missing from `after` is "unknown", not "removed", when its block in
   * `after` (or the top level) holds an unreadable statement.
   * @throws TypeError when either load came from another processor.
   */
  diff(before: ILoaded, after: ILoaded): readonly Change[];
}

/** Make a processor once, with its document source, extensions and key rule. */
export function villanelle(options: IProcessorOptions): IProcessor {
  throw notImplemented("villanelle", options);
}
