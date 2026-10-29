/**
 * A value as the binding expands it: the shared expanded value's data and origin, plus the low-level facts the
 * rendered layer adds to an argument (its definition and its chain of reference resolutions). Package-internal: an
 * extension use gets the plain `expanded()` value, which holds no handle; `render (graph)` builds its arguments
 * from these (spec 7.0, 7.3).
 */

import type { IOrigin, IStep } from "../origin.js";
import { type ExpandedData, ExpandedValue, ValueKind } from "../value.js";
import type { IReferenceResolution, WrittenValue } from "./model.js";

export class Bound {
  #expanded: ExpandedValue | undefined;

  constructor(
    readonly data: ExpandedData<Bound>,
    readonly origin: IOrigin,
    /** The written value at the end of its chain; undefined for an override. */
    readonly definition: WrittenValue | undefined = undefined,
    /** One per variable step of `origin.via`, the `$name` on the statement's own line first (D7). */
    readonly chain: readonly IReferenceResolution[] = [],
  ) {}

  /**
   * The written value on the line it is read in: the `$name` there for a value that came through a variable (a list
   * item shares its list's), else the value itself.
   */
  get written(): WrittenValue {
    const written = this.chain[0]?.reference ?? this.definition;
    if (written === undefined) throw new Error("an expanded value read on no line");
    return written;
  }

  /** Its canonical text. */
  get text(): string {
    return this.expanded().text;
  }

  /** The word's text when this is a word; undefined otherwise. Used for variable slice bounds. */
  get wordText(): string | undefined {
    return this.data.kind === ValueKind.Word ? this.data.text : undefined;
  }

  /** Its data with each list item made by `item` (the rendered layer's arguments, or plain expanded values). */
  dataWith<T>(item: (bound: Bound) => T): ExpandedData<T> {
    return this.data.kind === ValueKind.List ? { kind: ValueKind.List, items: this.data.items.map(item) } : this.data;
  }

  /** The shared expanded value: what an extension use holds. */
  expanded(): ExpandedValue {
    this.#expanded ??= new ExpandedValue(this.dataWith((item) => item.expanded()), this.origin);
    return this.#expanded;
  }

  /**
   * The same value having travelled further: the last `drop` steps of its origin (and of each list item's) are
   * replaced by `append`. A variable's value is stored with `drop` = the set line's own steps, and read with
   * `append` = the variable step and the reading place's steps, and that `$name`'s `resolution` first.
   */
  rebase(drop: number, append: readonly IStep[], resolution?: IReferenceResolution): Bound {
    const via = [...this.origin.via.slice(0, this.origin.via.length - drop), ...append];
    const origin: IOrigin = { place: this.origin.place, via };
    const data = this.dataWith((item) => item.rebase(drop, append, resolution));
    const chain = resolution === undefined ? this.chain : [resolution, ...this.chain];
    return new Bound(data, origin, this.definition, chain);
  }
}
