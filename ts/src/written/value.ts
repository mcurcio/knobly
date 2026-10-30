/**
 * The expanded value and its readers (spec 2.9): one value after expansion, with kind, canonical text, origin, its
 * links to the lines it came through, and the readers. The low level owns it (vil-umh.8, spec 6.10): an extension use
 * holds expanded values, a directive expansion's `values` are expanded values, and a rendered directive's values are
 * the very same objects. A snapshot (worked out once per expansion) that holds live handles.
 *
 * `ExpandedValue` (generated, gen/api/written.ts) is a union over the value kind list less `reference` (spec 2.10): each variant is its own type,
 * narrowed by `kind`, and only a list has `items`, only a slice `name`/`start`/`end`, only an index `name`/`index`.
 * The readers are on every variant by design: a value of the wrong kind is a problem in the config text, which the
 * program learns as a located E4002.
 */

import type { Origin, ProgramCode, Step } from "../gen/api/shared.js";
import type { ExpandedValue, IndexValue, ReferenceResolution, SliceValue, WrittenValue } from "../gen/api/written.js";
import { codeError, programError } from "../locate.js";
import { booleanOf, canonicalList, canonicalSlice, canonicalString, integerOf, numberOf } from "../values.js";
import { DiagnosticCode } from "../gen/api/codes.js";
import type { DiagnosticError } from "../gen/api/errors.js";
import { ValueKind } from "../gen/api/kinds.js";

/** What an expanded value holds, by kind; a list holds its items (`TItem`). Package-internal. */
export type ExpandedData<TItem> =
  | { readonly kind: "word"; readonly text: string }
  | { readonly kind: "string"; readonly value: string }
  | { readonly kind: "list"; readonly items: readonly TItem[] }
  | { readonly kind: "slice"; readonly name: string; readonly start?: number; readonly end?: number }
  | { readonly kind: "index"; readonly name: string; readonly index: number };

/** The canonical text of a value (spec 2.9). */
export function canonicalTextOf(data: ExpandedData<{ readonly text: string }>): string {
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

/**
 * The one home of the expanded value and its readers (spec 2.9): the record behind every variant of ExpandedValue.
 * Package-internal: the binding's walk makes them (bind.ts) and `rebase`s a variable's values to each place that
 * reads them. A member a kind does not have (`items` on a word) is not set on the object at all.
 */
export class ExpandedRecord {
  readonly kind: Exclude<ValueKind, typeof ValueKind.Reference>;
  readonly text: string;
  declare readonly items?: readonly ExpandedRecord[];
  declare readonly name?: string;
  declare readonly start?: number | undefined;
  declare readonly end?: number | undefined;
  declare readonly index?: number;
  readonly #data: ExpandedData<ExpandedRecord>;

  constructor(
    data: ExpandedData<ExpandedRecord>,
    readonly origin: Origin,
    /** The written value at the end of its chain; undefined for an override. */
    readonly definition: WrittenValue | undefined = undefined,
    /** One per variable step of `origin.via`, the `$name` on the statement's own line first. */
    readonly chain: readonly ReferenceResolution[] = [],
  ) {
    this.#data = data;
    this.kind = data.kind;
    this.text = canonicalTextOf(data);
    switch (data.kind) {
      case ValueKind.List:
        this.items = data.items;
        break;
      case ValueKind.Slice:
        this.name = data.name;
        this.start = data.start;
        this.end = data.end;
        break;
      case ValueKind.Index:
        this.name = data.name;
        this.index = data.index;
        break;
      default:
        break;
    }
  }

  word(): string {
    if (this.#data.kind !== ValueKind.Word) throw this.wrongKind("a word");
    return this.#data.text;
  }

  string(): string {
    if (this.#data.kind === ValueKind.Word) return this.#data.text;
    if (this.#data.kind === ValueKind.String) return this.#data.value;
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

  get written(): WrittenValue {
    const written = this.chain[0]?.reference ?? this.definition;
    if (written === undefined) throw new Error("an expanded value read on no line");
    return written;
  }

  list(): readonly ExpandedValue[] {
    if (this.#data.kind !== ValueKind.List) throw this.wrongKind("a list");
    return this.#data.items as readonly ExpandedValue[];
  }

  slice(): SliceValue | IndexValue {
    const data = this.#data;
    if (data.kind === ValueKind.Index) return { kind: data.kind, name: data.name, index: data.index };
    if (data.kind !== ValueKind.Slice) throw this.wrongKind("a slice or an index");
    return { kind: data.kind, name: data.name, start: data.start, end: data.end };
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }

  /**
   * The same value having travelled further: the last `drop` steps of its origin (and of each list item's) are
   * replaced by `append`. A variable's value is stored with `drop` = the set line's own steps, and read with
   * `append` = the variable step and the reading place's steps, and that `$name`'s `resolution` first.
   */
  static rebase(value: ExpandedRecord, drop: number, append: readonly Step[], resolution?: ReferenceResolution): ExpandedRecord {
    const via = [...value.origin.via.slice(0, value.origin.via.length - drop), ...append];
    const data = value.#data;
    const moved = data.kind === ValueKind.List ? { kind: ValueKind.List, items: data.items.map((item) => ExpandedRecord.rebase(item, drop, append, resolution)) } : data;
    const chain = resolution === undefined ? value.chain : [resolution, ...value.chain];
    return new ExpandedRecord(moved, { place: value.origin.place, via }, value.definition, chain);
  }

  /** A record as the public union (a static, so a program sees no member it does not need). */
  static asValue(value: ExpandedRecord): ExpandedValue {
    return value as unknown as ExpandedValue;
  }

  private wrongKind(wanted: string): DiagnosticError {
    return codeError(this.origin, DiagnosticCode.WrongValueKind, `wanted ${wanted}, found a ${this.kind}: ${this.text}`);
  }
}
