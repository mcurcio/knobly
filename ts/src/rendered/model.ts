/**
 * The rendered tree (spec 7), the middle layer: what a program walks after `render (graph)`. Directives and values
 * are expanded (variables replaced, snippets and extension files spliced in), read-only, and each carries its
 * origin. It builds on the low level (a directive names its written directive, an argument its written values); the
 * low level names nothing here. Model: PostCSS's node tree (https://postcss.org/api/), read-only.
 */

import type { DiagnosticError } from "../diagnostics.js";
import type { UnreadableReason } from "../gen/api/kinds.js";
import type { IDirectiveOrigin } from "../origin.js";
import type { ILocatedDiagnostic, ProgramCode } from "../report.js";
import type { IExpandedValue } from "../value.js";
import type { IDocumentGraph, IReferenceResolution, IWrittenDirective, Statement, WrittenValue } from "../written/model.js";

export type { ChangeKind, UnreadableReason } from "../gen/api/kinds.js";

/**
 * One value of a directive, after expansion: an expanded value (kind, canonical text, origin, readers) with three
 * links to the low level (spec 7.3).
 */
export interface IArgument extends IExpandedValue {
  /**
   * The written value on the same line: the line of the statement this value is read in. For a value that came
   * through a variable it is the `$name` there (`chain[0].reference`); a list item that came through a variable
   * shares its list's `$name`; otherwise the value itself, which is also its `definition`. Never undefined. Editing
   * it edits that one written line, which every copy of the line shares: a file included twice has one line read in
   * both copies (`written.statement.copies()`), so the edit shows in both. To change one copy only, edit what that
   * copy is given instead (its include block's `set`, at the include step of `chain`).
   */
  readonly written: WrittenValue;
  /**
   * The written value at the end of its chain (for `$pixels`, the `2284` of its `set`); undefined for an override.
   * Editing it changes every use.
   */
  readonly definition: WrittenValue | undefined;
  /**
   * One per variable step of `origin.via`, from this value's own line toward where it is written (D7): `[0]` is the
   * `$name` written on the directive's line. Empty for a value written where it is read. A snapshot of the render's
   * derivation; the handles in it are live.
   */
  readonly chain: readonly IReferenceResolution[];
  /** A list's items, each an argument with its own origin. @throws DiagnosticError E4002 for any other kind. */
  items(): readonly IArgument[];
}

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

/**
 * A statement of a block (or of the top level) that could not be read, kept in its place so a reader and `diff`
 * know the block is incomplete. It has no name or address: what it would have been is unknown.
 */
export interface IUnreadable {
  /** Why it could not be read: syntax, expansion, value or extension. */
  readonly reason: UnreadableReason;
  /** Where the statement was written, and the uses and includes that brought it here. */
  readonly origin: IDirectiveOrigin;
  /** The statement that could not be read here. */
  readonly written: Statement;
}

/** What a walk callback may return: nothing to go on into the block, "skip" to pass over it, "stop" to end. */
export type WalkControl = "skip" | "stop";

/**
 * One directive after expansion. `set`, `snippet`, `use` and extension directives never appear: their results do,
 * in their place.
 */
export interface IDirective {
  readonly name: string;
  readonly values: readonly IArgument[];
  /** The block's readable directives; undefined when written without a block. */
  readonly block: readonly IDirective[] | undefined;
  /** The block's statements that could not be read; empty when there is no block or all were read. */
  readonly unreadable: readonly IUnreadable[];
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
  /** A located error placed on this directive's name. @throws TypeError when `code` has no "/". */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/**
 * The program's rule for naming a directive among its siblings, so it keeps its address when lines move (React's
 * list `key`). Passed to `IRendered.addresses` and `IRendered.diff` (D4); called once per directive of the render,
 * parents before children, with the rendered directive (D5). What it throws propagates (a program bug, not a config
 * problem). rasl names a node by its id:
 * `(d) => (d.name === "node" && d.parent?.name === "graph" ? d.values[1]?.text : undefined)`.
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
  readonly unreadable: readonly IUnreadable[];
  /** The root file at 0:0, zero width: where a problem with no line of its own is placed. */
  readonly origin: IDirectiveOrigin;
  /** Every file's syntax diagnostics (documents in order), then the walk's problems in walk order (D11). */
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
  /**
   * What differs from this render (the before) to `after`, by address under `options.key` (D4): removed and unknown
   * in this render's walk order, then added and changed in `after`'s. A directive missing from `after` is "unknown",
   * not "removed", when its block in `after` (or the top level) holds an unreadable statement. Any two renders may be
   * compared. @throws whatever the key rule throws
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
