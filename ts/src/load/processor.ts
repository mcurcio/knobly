/**
 * Loading, rendering and change lists (R15 tier 2; round 12 design.md §5). A processor is made once with its
 * document source and extensions, as `postcss([plugins])` is; `load` reads a root file and everything it includes
 * into a document graph (the files as written); `read` reads what edits made unread; `render` builds the rendered
 * tree from the graph's current texts; `diff` compares two renders of the same processor by address, under the
 * caller's key rule (D4).
 */

import type { DiagnosticError } from "../diagnostics.js";
import { RESERVED } from "../written/bind.js";
import { DocumentGraph } from "../written/graph.js";
import type { IDocumentGraph } from "../written/model.js";
import { loadGraph, readUnread } from "../written/read.js";
import { diff } from "./diff.js";
import type { IAddress, IArgument, IDirective, IUnreadable, KeyRule, WalkControl } from "./directive.js";
import type { IDirectiveOrigin } from "./origin.js";
import { render } from "./render.js";
import type { ILocatedDiagnostic, ProgramCode } from "./report.js";
import type { IDocumentSource } from "./source.js";

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
}

/** How directives are named among same-name siblings; without a key rule, by position. */
export interface IKeyOptions {
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

/**
 * The rendered tree of one graph (PR 3's `ILoaded`, renamed). Problems are diagnostics; the root file owns the top
 * level, as a directive its block.
 */
export interface IRendered {
  /** The top-level readable directives, expanded. */
  readonly body: readonly IDirective[];
  /** Top-level statements that could not be read (R6: their siblings stay). */
  readonly unreadable: readonly IUnreadable[];
  /** The root file at 0:0, zero width: where a problem with no line of its own is placed. */
  readonly origin: IDirectiveOrigin;
  /** PR 3's content and order (D11): every file's syntax diagnostics (documents in order), then the walk's problems in walk order. */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  /** The graph it was rendered from. */
  readonly graph: IDocumentGraph;

  /** Every directive, depth-first in written order; see WalkControl. */
  walk(visit: (directive: IDirective) => WalkControl | void): void;
  /** A located error for a problem of the whole file, such as a required top-level directive left out. */
  error(message: string, code: ProgramCode): DiagnosticError;
  /**
   * Every directive's address under `options.key`, in walk order (the map's order). The key rule is called once per
   * directive, parents before children; what it throws propagates. The one home of the address rule; `diff` uses it.
   */
  addresses(options?: IKeyOptions): ReadonlyMap<IDirective, IAddress>;
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
 * One difference between two renders. An added, removed or unknown directive is listed alone, never with the
 * directives inside it (`walk` it); a changed one's block is compared at its own addresses.
 */
export type Change = IAdded | IRemoved | IChanged | IUnknown;

export interface IProcessor {
  /**
   * Read the root file at `path` (resolved through the source, as an included file's spec is, so the root has one
   * path in the graph) and every file its include lines name, once each (R21), repeating until nothing new is named.
   * Never rejects for anything in the text.
   * @throws (rejects) ReadError (a DiagnosticError: E3004 at the root path) when the source cannot resolve or read
   * the root; TypeError for bad handed-in variables
   */
  load(path: string, options?: ILoadOptions): Promise<IDocumentGraph>;
  /**
   * Resolve and read what `graph.unread()` names, repeating until nothing new is named; keeps every text and every
   * kept rejection (D12). Returns the resolvedPaths read, in read order. @throws TypeError for another processor's graph
   */
  read(graph: IDocumentGraph): Promise<readonly string[]>;
  /**
   * The rendered tree of the graph's current texts and handed-in values. Pure: reads no file; an unread include copy
   * renders as nothing (its edge is in `graph.unread()`).
   * @throws TypeError for a graph another processor made
   */
  render(graph: IDocumentGraph): IRendered;
  /**
   * What differs between two renders of this processor's graphs, by address under `options.key` (D4): removed and
   * unknown in `before`'s walk order, then added and changed in `after`'s. A directive missing from `after` is
   * "unknown", not "removed", when its block in `after` (or the top level) holds an unreadable statement.
   * @throws TypeError when either render came from another processor; whatever the key rule throws
   */
  diff(before: IRendered, after: IRendered, options?: IKeyOptions): readonly Change[];
}

/** Make a processor once, with its document source and extensions. */
export function villanelle(options: IProcessorOptions): IProcessor {
  const { source } = options;
  const extensions = new Map<string, IExtension>();
  for (const extension of options.extensions ?? []) {
    if (RESERVED.has(extension.directive) || extensions.has(extension.directive)) {
      throw new TypeError(`extension directive name taken: ${JSON.stringify(extension.directive)}`);
    }
    extensions.set(extension.directive, extension);
  }
  /** The graphs and renders this processor made: `read`, `render` and `diff` take only those (one set of extensions, D27). */
  const graphs = new WeakSet<IDocumentGraph>();
  const renders = new WeakSet<IRendered>();
  const own = (graph: IDocumentGraph, what: string): DocumentGraph => {
    if (!graphs.has(graph) || !(graph instanceof DocumentGraph)) throw new TypeError(`${what} takes only graphs this processor loaded`);
    return graph;
  };
  return {
    async load(path, loadOptions) {
      const graph = await loadGraph(source, extensions, path, new Map(Object.entries(loadOptions?.variables ?? {})));
      graphs.add(graph);
      return graph;
    },
    async read(graph) {
      return await readUnread(own(graph, "read"), source);
    },
    render(graph) {
      const rendered = render(own(graph, "render"));
      renders.add(rendered);
      return rendered;
    },
    diff(before, after, diffOptions) {
      if (!renders.has(before) || !renders.has(after)) throw new TypeError("diff compares only renders of this processor");
      return diff(before, after, diffOptions);
    },
  };
}
