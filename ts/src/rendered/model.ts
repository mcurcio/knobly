/**
 * The rendered tree (spec 7), the middle layer: what a program walks after `render (graph)`. Directives and values
 * are expanded (variables replaced, snippets and extension files spliced in), read-only, and each carries its
 * origin. It builds on the low level's own objects (spec 7.0, vil-umh.8): a directive's values are its directive
 * expansion's expanded values, its unreadable statements are unreadable expansions, and it names its written
 * directive; the low level names nothing here. Model: PostCSS's node tree (https://postcss.org/api/), read-only.
 */

import type { DiagnosticError } from "../errors.js";
import type { IDirectiveOrigin } from "../origin.js";
import type { ILocatedDiagnostic, ProgramCode } from "../report.js";
import type { ExpandedValue, IDocumentGraph, IUnreadableExpansion, IWrittenDirective } from "../written/index.js";

export type { ChangeKind, UnreadableReason } from "../gen/api/kinds.js";

/** One step of an address. */
export interface IAddressStep {
  readonly name: string;
  /** What the key rule returned for this directive; undefined when it returned nothing or there is no rule. */
  readonly key: string | undefined;
  /** 0-based, among earlier siblings with the same name and key. */
  readonly occurrence: number;
}

/**
 * Where a directive lands in the expanded tree: its identity across renders, under one key rule
 * (`IRendered.addresses`). Unique within one render. A file included at two places, or a snippet used twice, lands
 * at two addresses (R21: "Allowed, per place").
 */
export interface IAddress {
  /** From the top level down to this directive. */
  readonly steps: readonly IAddressStep[];
  /**
   * The canonical string, the same bytes in both languages: `JSON.stringify(steps.map((s) => [s.name, s.key ?? null,
   * s.occurrence]))`. Use it as a Map key.
   */
  readonly text: string;
  /** The enclosing directive's address; undefined at the top level. */
  readonly parent: IAddress | undefined;
  /**
   * For people: each step as its name, then ` ` + JSON-quoted key when there is one, then ` #n` when the occurrence
   * is not 0, joined by ` > `: `graph > node "leds" > max_count`.
   */
  toString(): string;
}

/** What a walk callback may return: nothing to go on into the block, "skip" to pass over it, "stop" to end. */
export type WalkControl = "skip" | "stop";

/**
 * One directive after expansion. `set`, `snippet`, `use` and extension directives never appear: their results do,
 * in their place.
 */
export interface IDirective {
  readonly name: string;
  /** Its directive expansion's expanded values, the same objects (spec 7.3). */
  readonly values: readonly ExpandedValue[];
  /** The block's readable directives; undefined when written without a block. */
  readonly block: readonly IDirective[] | undefined;
  /** The block's statements that could not be read; empty when there is no block or all were read. */
  readonly unreadable: readonly IUnreadableExpansion[];
  /** The enclosing directive; undefined at the top level. */
  readonly parent: IDirective | undefined;
  /** Where its name was written, and the uses and includes that brought it here. */
  readonly origin: IDirectiveOrigin;
  /** The written directive this is a copy of: the same object for every copy of one line (closes vil-uji). */
  readonly written: IWrittenDirective;

  /** Every directive inside this one (not itself), depth-first in written order; see WalkControl. */
  walk(visit: (directive: IDirective) => WalkControl | void): void;
  /** This directive or its nearest enclosing one that matches, as the DOM's Element.closest. */
  closest(predicate: (directive: IDirective) => boolean): IDirective | undefined;
  /** A located error placed on this directive's name. @throws MisuseError when `code` has no "/". */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/**
 * The program's rule for naming a directive among its siblings, so it keeps its address when lines move (React's
 * list `key`). Passed to `IRendered.addresses` and `IRendered.diff` (D4); called once per directive of the render,
 * parents before children, with the rendered directive (D5). What it throws propagates (a program bug, not a config
 * problem). It returns a string or undefined; anything else makes `addresses` and `diff` throw a TypeError. rasl
 * names a node by its id, a word, read with `word()` (a value's `text` is its canonical text: a string's keeps
 * its quotes): `(d) => (d.name === "node" && d.parent?.name === "graph" ? d.values[1]?.word() : undefined)`.
 */
export type KeyRule = (directive: IDirective) => string | undefined;

/** How directives are named among same-name siblings; without a key rule, by position. */
export interface IKeyOptions {
  readonly key?: KeyRule;
}

/**
 * The rendered tree of one graph. Problems are diagnostics; the root file owns the top level, as a directive its
 * block.
 */
export interface IRendered {
  /** The top-level readable directives, expanded. */
  readonly block: readonly IDirective[];
  /** Top-level statements that could not be read (R6: their siblings stay). */
  readonly unreadable: readonly IUnreadableExpansion[];
  /** The root file at 0:0, zero width: where a problem with no line of its own is placed. */
  readonly origin: IDirectiveOrigin;
  /** The graph's `diagnostics`: the one list (spec 7.1). */
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
   * @throws TypeError when the key rule returns anything but a string or undefined
   */
  addresses(options?: IKeyOptions): ReadonlyMap<IDirective, IAddress>;
  /**
   * What differs from this render (the before) to `after`, by address under `options.key` (D4): removed and unknown
   * in this render's walk order, then added and changed in `after`'s. A directive missing from `after` is "unknown",
   * not "removed", when its block in `after` (or the top level) holds an unreadable statement. Any two renders may be
   * compared. @throws whatever the key rule throws, and TypeError when it returns anything but a string or undefined
   */
  diff(after: IRendered, options?: IKeyOptions): readonly Change[];
}

export interface IAdded {
  readonly kind: "added";
  readonly address: IAddress;
  readonly after: IDirective;
}

export interface IRemoved {
  readonly kind: "removed";
  readonly address: IAddress;
  readonly before: IDirective;
}

/** Same address; its own values (by text) or whether it has a block differ. */
export interface IChanged {
  readonly kind: "changed";
  readonly address: IAddress;
  readonly before: IDirective;
  readonly after: IDirective;
}

/** It was in `before`; in `after` its block holds an unreadable statement that may be it. */
export interface IUnknown {
  readonly kind: "unknown";
  readonly address: IAddress;
  readonly before: IDirective;
}

/**
 * One difference between two renders. An added, removed or unknown directive is listed alone, never with the
 * directives inside it (`walk` it); a changed one's block is compared at its own addresses.
 */
export type Change = IAdded | IRemoved | IChanged | IUnknown;
