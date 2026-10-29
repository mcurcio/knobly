/**
 * The written value handles (round 12 design.md §5; slices.md 2.1): words, strings, lists, slices, indexes and
 * `$name` references, each pointing at its tokens in its document's current parse. Private to the package.
 *
 * A value's `set` keeps its handle (spec 6.1, milestone 5), and the handle takes the new value's kind: the object's
 * prototype becomes the new kind's class (`becomeKind`), the JavaScript form of the state pattern's class change. So
 * every kind's inner slots live on the shared base, one layout for all six, and `kind` is each class's getter.
 */

import type { IPlace } from "../origin.js";
import { textOf, type ValueRef } from "../syntax/cst.js";
import { type ConfigText, requireText } from "../text.js";
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

/** Where a value stands, which decides the entry rule its edits take (spec 2.8): a list item is told by its list. */
export type ValueRole = "value" | "bound" | "name";

export abstract class ValueHandle {
  abstract get kind(): ValueKind;
  /** Its token or node in the current parse; set by every build. */
  ref!: ValueRef;
  statementHandle!: StatementHandle;
  listHandle: ListValue | undefined;
  role: ValueRole = "value";
  detached = false;
  // Every kind's inner handles, on the shared base so a handle can change kind (set by every build).
  itemHandles: ValueHandle[] = [];
  nameHandle: ValueHandle | undefined;
  startHandle: ValueHandle | undefined;
  endHandle: ValueHandle | undefined;
  indexHandle: ValueHandle | undefined;

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

  set(text: ConfigText): void {
    this.live();
    requireText(text, "set", "text");
    this.doc.setValue(this, text);
  }

  replaceWithText(text: ConfigText): readonly WrittenValue[] {
    this.live();
    requireText(text, "replaceWithText", "text");
    return this.doc.replaceValue(this, text);
  }

  remove(): void {
    this.live();
    this.doc.removeValue(this);
  }

  /** The values inside it, in text order: a list's items, a slice's or index's name and bounds. */
  innerHandles(): readonly ValueHandle[] {
    return [];
  }

  private range(): { start: number; end: number } {
    const ref = this.ref;
    return typeof ref === "number" ? { start: ref, end: ref + 1 } : ref;
  }
}

export class WordValue extends ValueHandle implements IWord {
  get kind(): "word" {
    return "word";
  }
}

export class StringValue extends ValueHandle implements IString {
  get kind(): "string" {
    return "string";
  }
}

export class ListValue extends ValueHandle implements IList {
  get kind(): "list" {
    return "list";
  }

  get items(): readonly WrittenValue[] {
    return this.live().itemHandles as readonly WrittenValue[];
  }

  override innerHandles(): readonly ValueHandle[] {
    return this.itemHandles;
  }
}

/** A slice's or index's name value (its first token). */
function nameOf(value: ValueHandle): IWord | IReference {
  const name = value.live().nameHandle;
  if (name === undefined) throw new Error("a slice without its name");
  return name as IWord | IReference;
}

export class SliceValue extends ValueHandle implements ISlice {
  get kind(): "slice" {
    return "slice";
  }

  get name(): IWord | IReference {
    return nameOf(this);
  }

  get start(): IWord | IReference | undefined {
    return this.live().startHandle as IWord | IReference | undefined;
  }

  get end(): IWord | IReference | undefined {
    return this.live().endHandle as IWord | IReference | undefined;
  }

  override innerHandles(): readonly ValueHandle[] {
    return [this.nameHandle, this.startHandle, this.endHandle].filter((v): v is ValueHandle => v !== undefined);
  }
}

export class IndexValue extends ValueHandle implements IIndex {
  get kind(): "index" {
    return "index";
  }

  get name(): IWord | IReference {
    return nameOf(this);
  }

  get index(): IWord | IReference {
    const index = this.live().indexHandle;
    if (index === undefined) throw new Error("an index without its bound");
    return index as IWord | IReference;
  }

  override innerHandles(): readonly ValueHandle[] {
    return [this.nameHandle, this.indexHandle].filter((v): v is ValueHandle => v !== undefined);
  }
}

export class Reference extends ValueHandle implements IReference {
  get kind(): "reference" {
    return "reference";
  }

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

/** Each kind's class. */
const CLASSES = {
  word: WordValue,
  string: StringValue,
  list: ListValue,
  slice: SliceValue,
  index: IndexValue,
  reference: Reference,
} as const satisfies Record<ValueKind, new (doc: Document) => ValueHandle>;

/** A new handle of `kind`. */
export function newValue(doc: Document, kind: ValueKind): ValueHandle {
  return new CLASSES[kind](doc);
}

/**
 * Make a kept handle the new kind's (a value's `set`, spec 6.1): the same object, now of that kind's class, with no
 * inner handles until the build sets them.
 */
export function becomeKind(handle: ValueHandle, kind: ValueKind): void {
  if (handle.kind === kind) return;
  Object.setPrototypeOf(handle, CLASSES[kind].prototype);
  handle.itemHandles = [];
  handle.nameHandle = undefined;
  handle.startHandle = undefined;
  handle.endHandle = undefined;
  handle.indexHandle = undefined;
}
