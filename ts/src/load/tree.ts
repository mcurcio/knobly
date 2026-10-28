/**
 * The objects a load builds: arguments, addresses, directives and the loaded result. Private to the load layer;
 * programs see them through the interfaces of directive.ts and processor.ts.
 */

import { DiagnosticCode, type DiagnosticError } from "../diagnostics.js";
import type { INode } from "../syntax/cst.js";
import type { IIndexValue, ISliceValue } from "../value.js";
import { ValueKind } from "../value.js";
import type { IAddress, IAddressStep, IArgument, IDirective, IUnreadable, PlainValue, WalkControl } from "./directive.js";
import type { IDocumentGraph } from "./graph.js";
import type { IDirectiveOrigin, IOrigin, IStep } from "./origin.js";
import type { ILoaded } from "./processor.js";
import type { ILocatedDiagnostic, ProgramCode } from "./report.js";
import { codeError, programError } from "./locate.js";
import { booleanOf, canonicalList, canonicalSlice, canonicalString, integerOf, numberOf } from "./values.js";

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
    if (this.data.kind !== ValueKind.Word) throw this.wrongKind("a word");
    return this.data.text;
  }

  string(): string {
    if (this.data.kind === ValueKind.Word) return this.data.text;
    if (this.data.kind === ValueKind.String) return this.data.value;
    throw this.wrongKind("a word or a string");
  }

  number(): number {
    const value = numberOf(this.word());
    if (value === undefined) throw codeError(this.origin, DiagnosticCode.NotANumber, this.text);
    return value;
  }

  integer(): number {
    const value = integerOf(this.word());
    if (value === undefined) throw codeError(this.origin, DiagnosticCode.NotAnInteger, this.text);
    return value;
  }

  boolean(): boolean {
    const value = booleanOf(this.word());
    if (value === undefined) throw codeError(this.origin, DiagnosticCode.NotABoolean, this.text);
    return value;
  }

  items(): readonly IArgument[] {
    if (this.data.kind !== ValueKind.List) throw this.wrongKind("a list");
    return this.data.items;
  }

  slice(): ISliceValue | IIndexValue {
    const { data } = this;
    if (data.kind === ValueKind.Index) return { kind: data.kind, name: data.name, index: data.index };
    if (data.kind !== ValueKind.Slice) throw this.wrongKind("a slice or an index");
    return {
      kind: data.kind,
      name: data.name,
      ...(data.start === undefined ? {} : { start: data.start }),
      ...(data.end === undefined ? {} : { end: data.end }),
    };
  }

  plain(): PlainValue {
    switch (this.data.kind) {
      case ValueKind.String:
        return this.data.value;
      case ValueKind.Word:
        return numberOf(this.data.text) ?? booleanOf(this.data.text) ?? this.data.text;
      case ValueKind.List:
        return this.data.items.map((item) => item.plain());
      case ValueKind.Slice:
      case ValueKind.Index:
        return this.slice();
    }
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }

  private wrongKind(wanted: string): DiagnosticError {
    return codeError(this.origin, DiagnosticCode.WrongValueKind, `wanted ${wanted}, found a ${this.kind}: ${this.text}`);
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
    return programError(this.origin, message, code);
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
    return programError(this.origin, message, code);
  }
}
