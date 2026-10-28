/**
 * The objects a load builds: arguments, addresses, directives and the loaded result. Private to the load layer;
 * programs see them through the interfaces of directive.ts and processor.ts.
 */

import type { DiagnosticError } from "../diagnostics.js";
import type { INode } from "../syntax/cst.js";
import type { IIndexValue, ISliceValue } from "../value.js";
import { ValueKind } from "../value.js";
import type { IAddress, IAddressStep, IArgument, IDirective, IUnreadable, PlainValue, WalkControl } from "./directive.js";
import type { IDocumentGraph } from "./graph.js";
import type { IDirectiveOrigin, IOrigin, IStep } from "./origin.js";
import type { ILoaded } from "./processor.js";
import type { ILocatedDiagnostic, ProgramCode } from "./report.js";
import { notImplemented } from "./todo.js";
import { canonicalList, canonicalSlice, canonicalString } from "./values.js";

/** What an argument holds, by kind. */
export type ArgumentData =
  | { readonly kind: typeof ValueKind.Word; readonly text: string }
  | { readonly kind: typeof ValueKind.String; readonly value: string }
  | { readonly kind: typeof ValueKind.List; readonly items: readonly Argument[] }
  | { readonly kind: typeof ValueKind.Slice; readonly name: string; readonly start?: number; readonly end?: number }
  | { readonly kind: typeof ValueKind.Index; readonly name: string; readonly index: number };

/** The canonical text of a value (slices.md §1.3). */
function textOf(data: ArgumentData): string {
  switch (data.kind) {
    case ValueKind.Word:
      return data.text;
    case ValueKind.String:
      return canonicalString(data.value);
    case ValueKind.List:
      return canonicalList(data.items.map((item) => item.text));
    case ValueKind.Slice:
      return canonicalSlice(data.name, data);
    case ValueKind.Index:
      return canonicalSlice(data.name, data);
  }
}

export class Argument implements IArgument {
  readonly kind: ValueKind;
  readonly text: string;

  constructor(
    private readonly data: ArgumentData,
    readonly origin: IOrigin,
  ) {
    this.kind = data.kind;
    this.text = textOf(data);
  }

  /**
   * The same value having travelled further: the last `drop` steps of its origin (and of each list item's) are
   * replaced by `append`. A variable's value is stored with `drop` = the set line's own steps, and read with
   * `append` = the variable step and the reading place's steps.
   */
  rebase(drop: number, append: readonly IStep[]): Argument {
    const via = [...this.origin.via.slice(0, this.origin.via.length - drop), ...append];
    const origin: IOrigin = { written: this.origin.written, via };
    const data = this.data.kind === ValueKind.List ? { ...this.data, items: this.data.items.map((i) => i.rebase(drop, append)) } : this.data;
    return new Argument(data, origin);
  }

  /** The word's text when this is a word; undefined otherwise. Used by the load for variable slice bounds. */
  get wordText(): string | undefined {
    return this.data.kind === ValueKind.Word ? this.data.text : undefined;
  }

  word(): string {
    throw notImplemented("IArgument.word");
  }

  string(): string {
    throw notImplemented("IArgument.string");
  }

  number(): number {
    throw notImplemented("IArgument.number");
  }

  integer(): number {
    throw notImplemented("IArgument.integer");
  }

  boolean(): boolean {
    throw notImplemented("IArgument.boolean");
  }

  items(): readonly IArgument[] {
    throw notImplemented("IArgument.items");
  }

  slice(): ISliceValue | IIndexValue {
    throw notImplemented("IArgument.slice");
  }

  plain(): PlainValue {
    throw notImplemented("IArgument.plain");
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    throw notImplemented("IArgument.error", message, code);
  }
}

export class Address implements IAddress {
  readonly steps: readonly IAddressStep[];
  readonly text: string;

  constructor(
    readonly parent: Address | undefined,
    step: IAddressStep,
  ) {
    this.steps = [...(parent?.steps ?? []), step];
    this.text = JSON.stringify(this.steps.map((s) => [s.name, s.key ?? null, s.occurrence]));
  }

  toString(): string {
    return this.steps
      .map((s) => `${s.name}${s.key === undefined ? "" : ` ${JSON.stringify(s.key)}`}${s.occurrence === 0 ? "" : ` #${String(s.occurrence)}`}`)
      .join(" > ");
  }
}

/** Visit `body` and the blocks below it depth-first; false when a visit returned "stop". */
function walkBody(body: readonly IDirective[], visit: (directive: IDirective) => WalkControl | void): boolean {
  for (const directive of body) {
    const control = visit(directive);
    if (control === "stop") return false;
    if (control !== "skip" && !walkBody(directive.body ?? [], visit)) return false;
  }
  return true;
}

export class Directive implements IDirective {
  /** Filled by the load while it expands the block; undefined when written without one. */
  readonly body: IDirective[] | undefined;
  readonly unreadable: IUnreadable[] = [];

  constructor(
    readonly name: string,
    readonly args: readonly IArgument[],
    hasBlock: boolean,
    readonly parent: Directive | undefined,
    readonly address: Address,
    readonly origin: IDirectiveOrigin,
    readonly node: INode,
  ) {
    this.body = hasBlock ? [] : undefined;
  }

  walk(visit: (directive: IDirective) => WalkControl | void): void {
    walkBody(this.body ?? [], visit);
  }

  closest(predicate: (directive: IDirective) => boolean): IDirective | undefined {
    return predicate(this) ? this : this.parent?.closest(predicate);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    throw notImplemented("IDirective.error", message, code);
  }
}

export class Loaded implements ILoaded {
  constructor(
    readonly body: readonly IDirective[],
    readonly unreadable: readonly IUnreadable[],
    readonly origin: IDirectiveOrigin,
    readonly diagnostics: readonly ILocatedDiagnostic[],
    readonly graph: IDocumentGraph,
  ) {}

  walk(visit: (directive: IDirective) => WalkControl | void): void {
    walkBody(this.body, visit);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    throw notImplemented("ILoaded.error", message, code);
  }
}
