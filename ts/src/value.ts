/**
 * The expanded value and its readers (spec 2.9): one value after expansion, with kind, canonical text, origin and
 * readers. Shared, below the low level and the rendered layer: an extension use holds expanded values, and a
 * rendered argument builds on one. Plain data: it holds no low-level handle.
 */

import { DiagnosticCode, type DiagnosticError } from "./diagnostics.js";
import { ValueKind } from "./gen/api/kinds.js";
import { codeError, programError } from "./locate.js";
import type { IOrigin } from "./origin.js";
import type { ProgramCode } from "./report.js";
import { booleanOf, canonicalList, canonicalSlice, canonicalString, integerOf, numberOf } from "./values.js";

export { ValueKind };

/**
 * `name[start:end]`, `name[start:]` or `name[:end]`. Bounds are integers (IntegerText, within the safe integer
 * range); what they mean (inclusive or exclusive end, negative counting) is the program's. The value's place is in
 * its value's origin.
 */
export interface ISliceValue {
  readonly kind: typeof ValueKind.Slice;
  readonly name: string;
  readonly start?: number;
  readonly end?: number;
}

/** `name[index]`: one element (vil-9ze.2). */
export interface IIndexValue {
  readonly kind: typeof ValueKind.Index;
  readonly name: string;
  readonly index: number;
}

/**
 * A value read by villanelle's one rule. Quoting means text: `"8080"` and `"true"` are strings; only a bare word is
 * read as a number (NumberText) or as true/false (BooleanText).
 */
export type PlainValue = number | boolean | string | ISliceValue | IIndexValue | readonly PlainValue[];

/**
 * One value after expansion: a `$name` has already become its value(s).
 * Invariants (checked at load, so readers never meet them): a string's escapes are the six of EscapeText; a slice or
 * index bound is an IntegerText.
 */
export interface IExpandedValue {
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
  /** A word spelling a NumberText (JSON number: 8080, 0.5, -0.0176515; not 20hz). @throws E4002, E4004. */
  number(): number;
  /** A word spelling an IntegerText. @throws DiagnosticError E4002, E4005. */
  integer(): number;
  /** The word `true` or `false`. @throws DiagnosticError E4002, E4006. */
  boolean(): boolean;
  /** A list's items, each with its own origin. @throws DiagnosticError E4002 for any other kind. */
  items(): readonly IExpandedValue[];
  /** A slice or an index. @throws DiagnosticError E4002 for any other kind. */
  slice(): ISliceValue | IIndexValue;
  /**
   * Any value by the one rule: a string is its decoded text; a word is a number if it spells a NumberText, a boolean
   * if `true`/`false`, else its text; a list is its items read the same way; a slice or an index is its value.
   * Never throws.
   */
  plain(): PlainValue;
  /**
   * A located error for the program to throw or report, placed on this value. For an override it is placed on the
   * `$name` that used it. @throws TypeError when `code` has no "/".
   */
  error(message: string, code: ProgramCode): DiagnosticError;
}

/** What an expanded value holds, by kind; a list holds its items (`TItem`). Package-internal. */
export type ExpandedData<TItem> =
  | { readonly kind: typeof ValueKind.Word; readonly text: string }
  | { readonly kind: typeof ValueKind.String; readonly value: string }
  | { readonly kind: typeof ValueKind.List; readonly items: readonly TItem[] }
  | { readonly kind: typeof ValueKind.Slice; readonly name: string; readonly start?: number; readonly end?: number }
  | { readonly kind: typeof ValueKind.Index; readonly name: string; readonly index: number };

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
 * The one home of the readers (spec 2.9). Package-internal: the low level makes these for an extension use, and the
 * rendered layer's argument extends it with its links to the low level (`TItem` is then the argument).
 */
export class ExpandedValue<TItem extends IExpandedValue = IExpandedValue> implements IExpandedValue {
  readonly kind: Exclude<ValueKind, "reference">;
  readonly text: string;
  readonly #data: ExpandedData<TItem>;

  constructor(
    data: ExpandedData<TItem>,
    readonly origin: IOrigin,
  ) {
    this.#data = data;
    this.kind = data.kind;
    this.text = canonicalTextOf(data);
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

  items(): readonly TItem[] {
    if (this.#data.kind !== ValueKind.List) throw this.wrongKind("a list");
    return this.#data.items;
  }

  slice(): ISliceValue | IIndexValue {
    const data = this.#data;
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
    const data = this.#data;
    switch (data.kind) {
      case ValueKind.String:
        return data.value;
      case ValueKind.Word:
        return numberOf(data.text) ?? booleanOf(data.text) ?? data.text;
      case ValueKind.List:
        return data.items.map((item) => item.plain());
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
