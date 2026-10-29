/**
 * The written value handles (round 12 design.md §5; slices.md 2.1): words, strings, lists, slices, indexes and
 * `$name` references, each pointing at its tokens in its document's current parse. Private to the package.
 */

import type { IPlace } from "../origin.js";
import { textOf, type ValueRef } from "../syntax/cst.js";
import { requireText } from "../text.js";
import type { Document } from "./document.js";
import { detached } from "./document.js";
import type { ValueKind } from "../gen/api/kinds.js";
import type {
  IIndex,
  IList,
  IParameter,
  IReference,
  IReferenceResolution,
  ISetVariable,
  ISlice,
  IString,
  IWord,
  Statement,
  WrittenValue,
} from "./model.js";
import type { StatementHandle } from "./statements.js";

export abstract class ValueHandle {
  abstract readonly kind: ValueKind;
  /** Its token or node in the current parse; set by every build. */
  ref!: ValueRef;
  statementHandle!: StatementHandle;
  listHandle: ListValue | undefined;
  /** Whether it is a slice or index bound. */
  bound = false;
  detached = false;

  constructor(readonly doc: Document) {}

  live(): this {
    if (this.detached) throw detached("value");
    return this;
  }

  get text(): string {
    this.live();
    return textOf(this.doc.syntax, this.range());
  }

  get place(): IPlace {
    this.live();
    return this.doc.place(this.doc.spanOf(this.range()));
  }

  get statement(): Statement {
    return this.live().statementHandle as Statement;
  }

  get list(): IList | undefined {
    return this.live().listHandle;
  }

  replaceWithText(text: string): readonly WrittenValue[] {
    this.live();
    requireText(text, "replaceWithText", "text");
    return this.doc.replaceValue(this, text);
  }

  remove(): void {
    this.live();
    this.doc.removeValue(this);
  }

  /** The values inside it: a list's items, a slice's or index's bounds. */
  innerHandles(): readonly ValueHandle[] {
    return [];
  }

  private range(): { start: number; end: number } {
    const ref = this.ref;
    return typeof ref === "number" ? { start: ref, end: ref + 1 } : ref;
  }
}

export class WordValue extends ValueHandle implements IWord {
  readonly kind = "word";
}

export class StringValue extends ValueHandle implements IString {
  readonly kind = "string";
}

export class ListValue extends ValueHandle implements IList {
  readonly kind = "list";
  itemHandles: ValueHandle[] = [];

  get items(): readonly WrittenValue[] {
    return this.live().itemHandles as readonly WrittenValue[];
  }

  override innerHandles(): readonly ValueHandle[] {
    return this.itemHandles;
  }
}

/** The name token's text of a slice or index node. */
function sliceName(value: ValueHandle): string {
  value.live();
  const ref = value.ref;
  return typeof ref === "number" ? "" : (value.doc.syntax.tokens[ref.start]?.text ?? "");
}

export class SliceValue extends ValueHandle implements ISlice {
  readonly kind = "slice";
  startHandle: ValueHandle | undefined;
  endHandle: ValueHandle | undefined;

  get name(): string {
    return sliceName(this);
  }

  get start(): IWord | IReference | undefined {
    return this.live().startHandle as IWord | IReference | undefined;
  }

  get end(): IWord | IReference | undefined {
    return this.live().endHandle as IWord | IReference | undefined;
  }

  override innerHandles(): readonly ValueHandle[] {
    return [this.startHandle, this.endHandle].filter((v): v is ValueHandle => v !== undefined);
  }
}

export class IndexValue extends ValueHandle implements IIndex {
  readonly kind = "index";
  indexHandle: ValueHandle | undefined;

  get name(): string {
    return sliceName(this);
  }

  get index(): IWord | IReference {
    const index = this.live().indexHandle;
    if (index === undefined) throw new Error("an index without its bound");
    return index as IWord | IReference;
  }

  override innerHandles(): readonly ValueHandle[] {
    return this.indexHandle === undefined ? [] : [this.indexHandle];
  }
}

export class Reference extends ValueHandle implements IReference {
  readonly kind = "reference";

  get name(): string {
    return this.text.slice(1);
  }

  get declaration(): ISetVariable | IParameter | undefined {
    this.live();
    return this.doc.declarationOf(this);
  }

  resolutions(): readonly IReferenceResolution[] {
    this.live();
    return this.doc.host.binding().resolutionsOf(this);
  }
}
