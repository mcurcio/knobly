/**
 * Loading and change lists (R15 tier 2). A processor is made once with its document source, extensions and key
 * rule, as `postcss([plugins])` is; `load` reads a root file and everything it splices in; `diff` compares two loads
 * of the same processor by address.
 */

import { DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import type { ISourceSpan } from "../span.js";
import { NodeKind } from "../syntax/cst.js";
import { parse } from "../syntax/parse.js";
import { messageOf } from "../syntax/recovery.js";
import { TokenKind } from "../syntax/tokens.js";
import { anatomyOf } from "./anatomy.js";
import { diff } from "./diff.js";
import type { IAddress, IArgument, IDirective, IUnreadable, KeyRule, WalkControl } from "./directive.js";
import { Expander, type IText, Problem, RESERVED, Scope } from "./expand.js";
import type { IDocumentGraph } from "./graph.js";
import type { IDirectiveOrigin, IPlace } from "./origin.js";
import type { ILocatedDiagnostic, ProgramCode } from "./report.js";
import type { IDocumentSource } from "./source.js";
import { type Argument, Loaded } from "./tree.js";

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
   * Read the root file at `path` (as the source names it) and everything it splices in. `path` is resolved through
   * the source first, as an included file's spec is, so the root has one path in the graph. Never rejects for anything
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
  const { source, key } = options;
  const extensions = [...(options.extensions ?? [])];
  const names = new Set<string>();
  for (const extension of extensions) {
    if (RESERVED.has(extension.directive) || names.has(extension.directive)) {
      throw new TypeError(`extension directive name taken: ${JSON.stringify(extension.directive)}`);
    }
    names.add(extension.directive);
  }
  /** The loads this processor made: `diff` compares only those (one key rule, one set of extensions). */
  const made = new WeakSet<ILoaded>();
  return {
    async load(written, loadOptions) {
      const handed = readHanded(loadOptions?.variables ?? {});
      const expander = new Expander(source, extensions, handed, key);
      const fail = (reason: string): DiagnosticError => {
        const code = DiagnosticCode.IncludeResolverFailed;
        const at = { kind: "file", resolvedPath: written, span: { start: START, end: START } } as const;
        return new DiagnosticError({ code, message: `${messageOf(code)}: ${written}: ${reason}`, at, via: [] });
      };
      // The root is resolved through the source as an included file's spec is (F1-04), so one file has one path.
      let paths: readonly string[];
      try {
        paths = await source.resolve(written, { parentPath: "" });
      } catch (error) {
        throw fail(reasonOf(error));
      }
      const [path] = paths;
      if (path === undefined || paths.length > 1) {
        throw fail(paths.length === 0 ? "no such file" : `names ${String(paths.length)} files`);
      }
      let file;
      try {
        file = await expander.read(path);
      } catch (error) {
        throw fail(reasonOf(error));
      }
      const top = { body: [] as IDirective[], unreadable: [] as IUnreadable[] };
      await expander.root(file, top);
      const nodes = expander.nodes;
      const root = nodes.get(path);
      if (root === undefined) throw new Error(`root file not in the graph: ${path}`);
      const syntaxDiagnostics = [...nodes.values()].flatMap((node) =>
        node.syntax.diagnostics.map((d) => ({ code: d.code, message: d.message, at: place(node.resolvedPath, d.span), via: [] })),
      );
      const graph: IDocumentGraph = { root, nodes, edges: expander.edges };
      const origin = { written: place(path, { start: START, end: START }), via: [] };
      const loaded = new Loaded(top.body, top.unreadable, origin, [...syntaxDiagnostics, ...expander.diagnostics], graph);
      made.add(loaded);
      return loaded;
    },
    diff(before, after) {
      if (!made.has(before) || !made.has(after)) throw new TypeError("diff compares only loads of this processor");
      return diff(before, after);
    },
  };
}

const START = { offset: 0, line: 0, column: 0 } as const;
const VARIABLE_NAME = /^[A-Za-z0-9_]+$/;

function place(resolvedPath: string, span: ISourceSpan): IPlace {
  return { kind: "file", resolvedPath, span };
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * The values handed in by the program, each text read as the values of one directive. TypeError for a bad name, or
 * a text that is not one or more values (a syntax error, a variable, an unknown escape, a non-integer bound).
 */
function readHanded(variables: Readonly<Record<string, string>>): ReadonlyMap<string, readonly Argument[]> {
  const handed = new Map<string, readonly Argument[]>();
  const nowhere: IDocumentSource = { resolve: () => Promise.resolve([]), read: () => Promise.reject(new Error("no files")) };
  const reader = new Expander(nowhere, [], new Map(), undefined);
  for (const [name, written] of Object.entries(variables)) {
    if (!VARIABLE_NAME.test(name)) throw new TypeError(`handed-in variable name must be letters, digits and _: ${JSON.stringify(name)}`);
    const bad = (why: string): TypeError => new TypeError(`handed-in variable ${name}: ${why}: ${JSON.stringify(written)}`);
    if (typeof written !== "string") throw bad("not a string");
    const syntax = parse(`x ${written}`);
    const [node, ...rest] = syntax.root.children;
    if (syntax.diagnostics.length > 0 || node?.kind !== NodeKind.Directive || rest.length > 0) throw bad("not a run of values");
    if (syntax.tokens.some((t) => t.kind === TokenKind.Variable)) throw bad("a handed-in value may not use a variable");
    const text: IText = {
      syntax,
      resolvedPath: "",
      written: () => ({ kind: "handed", variable: name }),
      place: (span) => place("", span),
    };
    const { args, block } = anatomyOf(syntax.tokens, node);
    if (args.length === 0 || block !== undefined) throw bad("not a run of values");
    try {
      handed.set(name, args.flatMap((ref) => reader.value(text, ref, new Scope(undefined), [])));
    } catch (error) {
      if (error instanceof Problem) throw bad(error.message);
      throw error;
    }
  }
  return handed;
}
