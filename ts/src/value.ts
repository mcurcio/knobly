/**
 * Value kinds and the slice and index shapes a program reads through the load layer (`IArgument.kind`,
 * `IArgument.slice()`, `IArgument.plain()`).
 */

export const ValueKind = {
  Word: "word",
  String: "string",
  /** `[0.04, 1, 0.5]`: read through `IArgument.items()`. */
  List: "list",
  Slice: "slice",
  Index: "index",
} as const;
export type ValueKind = (typeof ValueKind)[keyof typeof ValueKind];

/**
 * `name[start:end]`, `name[start:]` or `name[:end]`. Bounds are integers (IntegerText, within the safe integer
 * range); what they mean (inclusive or exclusive end, negative counting) is the program's. The value's place is in
 * its argument's origin.
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
