/**
 * The expanded value and its readers (spec 2.9): one value after expansion, with kind, canonical text, origin and
 * readers. Shared, below the low level and the rendered layer: an extension use and the graph's expansion hold
 * expanded values, and a rendered argument builds on one. Plain data: it holds no low-level handle.
 *
 * `ExpandedValue` is a union over the value kind list less `reference` (spec 2.10): each variant is its own type,
 * narrowed by `kind`, and only a list has `items`, only a slice `name`/`start`/`end`, only an index `name`/`index`.
 * The readers are on every variant by design: a value of the wrong kind is a problem in the config text, which the
 * program learns as a located E4002.
 */

import { DiagnosticCode } from "./diagnostics.js";
import type { DiagnosticError } from "./errors.js";
import type { ValueKind } from "./gen/api/kinds.js";
import { codeError, programError } from "./locate.js";
import type { IOrigin } from "./origin.js";
import type { ProgramCode } from "./report.js";
import { booleanOf, canonicalList, canonicalSlice, canonicalString, integerOf, numberOf } from "./values.js";

export type { ValueKind };

/**
 * `name[start:end]`, `name[start:]` or `name[:end]`. Bounds are integers (IntegerText, within the safe integer
 * range); what they mean (inclusive or exclusive end, negative counting) is the program's. The value's place is in
 * its value's origin.
 */
export interface ISliceValue {
  readonly kind: "slice";
  readonly name: string;
  readonly start?: number;
  readonly end?: number;
}

/** `name[index]`: one element (vil-9ze.2). */
export interface IIndexValue {
  readonly kind: "index";
  readonly name: string;
  readonly index: number;
}

/**
 * A value read by villanelle's one rule. Quoting means text: `"8080"` and `"true"` are strings; only a bare word is
 * read as a number (NumberText) or as true/false (BooleanText).
 */
export type PlainValue = number | boolean | string | ISliceValue | IIndexValue | readonly PlainValue[];

/**
 * What every expanded value has: kind, canonical text, origin, and the readers. Invariants (checked at load, so
 * readers never meet them): a string's escapes are the six of EscapeText; a slice or index bound is an IntegerText.
 */
export interface IExpandedValueBase {
  readonly kind: Exclude<ValueKind, "reference">;
  /**
   * The value's canonical text, the same in every binding: a word as written; a string as `"` + its decoded text
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
  /**
   * A word spelling a NumberText (JSON number: 8080, 0.5, -0.0176515; not 20hz), as a double; never negative zero
   * (spec/contract.md 3). @throws DiagnosticError E4002; E4004, also beyond the double range (`1e400`).
   */
  number(): number;
  /** A word spelling an IntegerText within plus or minus 2^53-1; never negative zero. @throws DiagnosticError E4002, E4005. */
  integer(): number;
  /** The word `true` or `false`. @throws DiagnosticError E4002, E4006. */
  boolean(): boolean;
  /** A list's items, each with its own origin. @throws DiagnosticError E4002 for any other kind. */
  list(): readonly ExpandedValue[];
  /** A slice or an index. @throws DiagnosticError E4002 for any other kind. */
  slice(): ISliceValue | IIndexValue;
  /**
   * Any value by the one rule: a string is its decoded text; a word is a number if `number()` would read it, a
   * boolean if `true`/`false`, else its text (so `1e400` is text); a list is its items read the same way; a slice or
   * an index is its value. Never throws.
   */
  plain(): PlainValue;
  /**
   * A located error for the program to throw or report, placed on this value. For an override it is placed on the
   * `$name` that used it. @throws TypeError when `code` has no "/".
   */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/** A bare word after expansion. */
export interface IExpandedWord extends IExpandedValueBase {
  readonly kind: "word";
}

/** A string after expansion. */
export interface IExpandedString extends IExpandedValueBase {
  readonly kind: "string";
}

/** A list after expansion. */
export interface IExpandedList extends IExpandedValueBase {
  readonly kind: "list";
  /** Its items, each with its own origin (the same as `list()`). */
  readonly items: readonly ExpandedValue[];
}

/** `name[start:end]` after expansion. */
export interface IExpandedSlice extends IExpandedValueBase {
  readonly kind: "slice";
  readonly name: string;
  readonly start: number | undefined;
  readonly end: number | undefined;
}

/** `name[index]` after expansion. */
export interface IExpandedIndex extends IExpandedValueBase {
  readonly kind: "index";
  readonly name: string;
  readonly index: number;
}

/** One value after expansion: a `$name` has already become its value(s). Narrow by `kind`. */
export type ExpandedValue = IExpandedWord | IExpandedString | IExpandedList | IExpandedSlice | IExpandedIndex;

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
    case "word":
      return data.text;
    case "string":
      return canonicalString(data.value);
    case "list":
      return canonicalList(data.items.map((item) => item.text));
    case "slice":
      return canonicalSlice(data.name, data);
    case "index":
      return canonicalSlice(data.name, data);
  }
}

/**
 * The data of an expanded value, read through its public members only, with a list's items as `items` (what the
 * rendered layer builds an argument from: spec 7.0). Package-internal.
 */
export function dataOf<TItem>(value: ExpandedValue, items: readonly TItem[]): ExpandedData<TItem> {
  switch (value.kind) {
    case "word":
      return { kind: "word", text: value.text };
    case "string":
      return { kind: "string", value: value.string() };
    case "list":
      return { kind: "list", items };
    case "slice":
      return {
        kind: "slice",
        name: value.name,
        ...(value.start === undefined ? {} : { start: value.start }),
        ...(value.end === undefined ? {} : { end: value.end }),
      };
    case "index":
      return { kind: "index", name: value.name, index: value.index };
  }
}

/**
 * The one home of the readers (spec 2.9). Package-internal: `expandedValue` makes the shared variants from it, and
 * the rendered layer's arguments extend it with their links to the low level (`TItem` is then the argument). A
 * member a kind does not have (`items` on a word) is not set on the object at all.
 */
export class ExpandedRecord<TItem extends ExpandedValue = ExpandedValue> {
  readonly kind: Exclude<ValueKind, "reference">;
  readonly text: string;
  declare readonly items?: readonly TItem[];
  declare readonly name?: string;
  declare readonly start?: number | undefined;
  declare readonly end?: number | undefined;
  declare readonly index?: number;
  readonly #data: ExpandedData<TItem>;

  constructor(
    data: ExpandedData<TItem>,
    readonly origin: IOrigin,
  ) {
    this.#data = data;
    this.kind = data.kind;
    this.text = canonicalTextOf(data);
    switch (data.kind) {
      case "list":
        this.items = data.items;
        break;
      case "slice":
        this.name = data.name;
        this.start = data.start;
        this.end = data.end;
        break;
      case "index":
        this.name = data.name;
        this.index = data.index;
        break;
      default:
        break;
    }
  }

  word(): string {
    if (this.#data.kind !== "word") throw this.wrongKind("a word");
    return this.#data.text;
  }

  string(): string {
    if (this.#data.kind === "word") return this.#data.text;
    if (this.#data.kind === "string") return this.#data.value;
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

  list(): readonly TItem[] {
    if (this.#data.kind !== "list") throw this.wrongKind("a list");
    return this.#data.items;
  }

  slice(): ISliceValue | IIndexValue {
    const data = this.#data;
    if (data.kind === "index") return { kind: data.kind, name: data.name, index: data.index };
    if (data.kind !== "slice") throw this.wrongKind("a slice or an index");
    return {
      kind: data.kind,
      name: data.name,
      ...(data.start === undefined ? {} : { start: data.start }),
      ...(data.end === undefined ? {} : { end: data.end }),
    };
  }

  plain(): PlainValue {
    const data = this.#data;
    switch (data.kind) {
      case "string":
        return data.value;
      case "word":
        return numberOf(data.text) ?? booleanOf(data.text) ?? data.text;
      case "list":
        return data.items.map((item) => item.plain());
      case "slice":
      case "index":
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

/** The shared expanded value of this data: the variant its kind names. Package-internal. */
export function expandedValue(data: ExpandedData<ExpandedValue>, origin: IOrigin): ExpandedValue {
  return new ExpandedRecord(data, origin) as ExpandedValue;
}
