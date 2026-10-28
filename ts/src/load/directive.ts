/**
 * The directive layer (R15 tier 2): what a program walks after a load. Directives and values are expanded
 * (variables replaced, snippets and extension files spliced in), read-only, and each carries its origin.
 * Model: PostCSS's node tree (https://postcss.org/api/), read-only.
 */

import type { DiagnosticError } from "../diagnostics.js";
import type { INode } from "../syntax/cst.js";
import type { IIndexValue, ISliceValue, ValueKind } from "../value.js";
import type { IDirectiveOrigin, IOrigin } from "./origin.js";
import type { ProgramCode } from "./report.js";

/**
 * A value read by villanelle's one rule. Quoting means text: `"8080"` and `"true"` are strings; only a bare word is
 * read as a number (NumberText) or as true/false (BooleanText).
 */
export type PlainValue = number | boolean | string | ISliceValue | IIndexValue | readonly PlainValue[];

/**
 * One value of a directive, after expansion: a `$name` has already become its value(s).
 * Invariants (checked at load, so readers never meet them): a string's escapes are the six of EscapeText; a slice or
 * index bound is an IntegerText.
 */
export interface IArgument {
  readonly kind: ValueKind;
  /**
   * The value's canonical text, the same in both languages: a word as written; a string as `"` + its decoded text
   * with `\`, `"`, newline, tab and carriage return escaped + `"`; a slice `name[start:end]` (either side may be
   * empty) and an index `name[i]` with decimal integers; a list `[` + its items' texts joined by `, ` + `]`.
   * Comments and line breaks are never part of it. Two values are the same exactly when their texts are equal.
   */
  readonly text: string;
  readonly origin: IOrigin;

  /** A bare word. @throws DiagnosticError E4002 for any other kind. */
  word(): string;
  /** A word or a string, decoded. @throws DiagnosticError E4002 for a list, slice or index. */
  string(): string;
  /** A word spelling a NumberText (JSON number: 8080, 0.5, -0.0176515; not 20hz). @throws E4002, E4004. */
  number(): number;
  /** A word spelling an IntegerText. @throws DiagnosticError E4002, E4005. */
  integer(): number;
  /** The word `true` or `false`. @throws DiagnosticError E4002, E4006. */
  boolean(): boolean;
  /** A list's items, each with its own origin. @throws DiagnosticError E4002 for any other kind. */
  items(): readonly IArgument[];
  /** A slice or an index. @throws DiagnosticError E4002 for any other kind. */
  slice(): ISliceValue | IIndexValue;
  /**
   * Any value by the one rule: a string is its decoded text; a word is a number if it spells a NumberText, a boolean
   * if `true`/`false`, else its text; a list is its items read the same way; a slice or an index is its value.
   * Never throws.
   */
  plain(): PlainValue;
  /**
   * A located error for the program to throw or report, placed on this value. For a handed-in value it is placed on
   * the `$name` that used it. @throws TypeError when `code` has no "/".
   */
  error(message: string, code: ProgramCode): DiagnosticError;
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
 * Where a directive lands in the expanded tree: its identity across loads. Unique within one load. A file included
 * at two places, or a snippet used twice, lands at two addresses (R21: "Allowed, per place").
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

export const UnreadableKind = {
  /** The parser could not read the statement (an error node, R6). */
  Syntax: "syntax",
  /** A variable, `set`, `snippet` or `use` failed (unknown name, wrong arity, cycle, limits). */
  Expansion: "expansion",
  /** A value broke a value rule checked at load (a non-integer slice bound, an unknown escape). */
  Value: "value",
  /** An extension directive failed (bad path, file not found, the source failed). */
  Extension: "extension",
} as const;
export type UnreadableKind = (typeof UnreadableKind)[keyof typeof UnreadableKind];

/**
 * A statement of a block (or of the top level) that could not be read, kept in its place so a reader and `diff`
 * know the block is incomplete. It has no name or address: what it would have been is unknown.
 */
export interface IUnreadable {
  readonly kind: UnreadableKind;
  /** Where the statement was written, and the uses and includes that brought it here. */
  readonly origin: IDirectiveOrigin;
  /** Its tier-1 node in the file `origin.written` names: the error node, or the directive node that failed. */
  readonly node: INode;
}

/** What a walk callback may return: nothing to go on into the block, "skip" to pass over it, "stop" to end. */
export type WalkControl = "skip" | "stop";

/**
 * One directive after expansion. `set`, `snippet`, `use` and extension directives never appear: their results do,
 * in their place.
 */
export interface IDirective {
  readonly name: string;
  readonly args: readonly IArgument[];
  /** The block's readable directives; undefined when written without a block. */
  readonly body: readonly IDirective[] | undefined;
  /** The block's statements that could not be read; empty when there is no block or all were read. */
  readonly unreadable: readonly IUnreadable[];
  /** The enclosing directive; undefined at the top level. */
  readonly parent: IDirective | undefined;
  readonly address: IAddress;
  /** Where its name was written, and the uses and includes that brought it here. */
  readonly origin: IDirectiveOrigin;
  /** Its directive node in the tier-1 tree of the file `origin.written` names (for editing, vil-uji). */
  readonly node: INode;

  /** Every directive inside this one (not itself), depth-first in written order; see WalkControl. */
  walk(visit: (directive: IDirective) => WalkControl | void): void;
  /** This directive or its nearest enclosing one that matches, as the DOM's Element.closest. */
  closest(predicate: (directive: IDirective) => boolean): IDirective | undefined;
  /** A located error placed on this directive's name. @throws TypeError when `code` has no "/". */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/** What the key rule sees of one directive: its expanded header, before its block is expanded. */
export interface IKeyInput {
  readonly name: string;
  /** Expanded values, readers and origins included. */
  readonly args: readonly IArgument[];
  /** Whether it was written with a block. */
  readonly hasBlock: boolean;
  /** The enclosing directive as the key rule saw it; undefined at the top level. */
  readonly parent: IKeyInput | undefined;
}

/**
 * The program's rule for naming a directive among its siblings, so it keeps its address when lines move (React's
 * list `key`). Called once per readable directive, parents before children, in expansion order. An exception it
 * throws ends the load (a program bug, not a config problem). rasl names a node by its id:
 * `(d) => (d.name === "node" && d.parent?.name === "graph" ? d.args[1]?.text : undefined)`.
 */
export type KeyRule = (directive: IKeyInput) => string | undefined;
