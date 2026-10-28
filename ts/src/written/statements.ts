/**
 * The statement handles and the variables of the low level (round 12 design.md §5; slices.md 2.1). One object per
 * written thing for the graph's life; the document re-points it at its tokens after each edit, or detaches it.
 * Private to the package: programs see the interfaces of model.ts.
 */

import type { IPlace } from "../load/origin.js";
import { anatomyOf } from "../load/anatomy.js";
import type { INode } from "../syntax/cst.js";
import { textOf } from "../syntax/cst.js";
import type { IBinding } from "./bind.js";
import type { Block, Document } from "./document.js";
import { detached } from "./document.js";
import { NoSetLineError } from "./errors.js";
import type {
  ICopy,
  IDocument,
  IReference,
  IReferenceResolution,
  IResolution,
  ISetLine,
  ISnippetLine,
  IVariable,
  IWrittenBlock,
  Statement,
  WrittenValue,
} from "./model.js";
import type { ValueHandle } from "./values.js";

/** What every statement handle has. */
export abstract class StatementHandle {
  abstract readonly kind: Statement["kind"];
  /** Its directive or error node in the document's current parse; set by every build. */
  node!: INode;
  parentHandle: StatementHandle | undefined;
  /** Its values (none for a snippet or unreadable line). */
  valueList: ValueHandle[] = [];
  blockHandle: Block | undefined;
  detached = false;

  constructor(readonly doc: Document) {}

  /** @throws DetachedError when its tokens are gone. */
  live(): this {
    if (this.detached) throw detached("statement");
    return this;
  }

  get document(): IDocument {
    return this.live().doc;
  }

  get parent(): Statement | undefined {
    return this.live().parentHandle as Statement | undefined;
  }

  get place(): IPlace {
    this.live();
    return this.doc.place(this.doc.spanOf(this.doc.ownedRange(this.node)));
  }

  get text(): string {
    this.live();
    return textOf(this.doc.syntax, this.doc.ownedRange(this.node));
  }

  copies(): readonly ICopy[] {
    this.live();
    return this.doc.host.binding().copiesOf(this as unknown as Statement);
  }

  replaceWithText(text: string): readonly Statement[] {
    this.live();
    return this.doc.replaceStatement(this, text);
  }

  remove(): void {
    this.live();
    this.doc.removeStatement(this);
  }

  /** The value handles of this statement (for the reconcile and the document's walks). */
  valueHandles(): readonly ValueHandle[] {
    return this.valueList;
  }

  /** The text of its name token. */
  protected nameText(): string {
    return this.doc.syntax.tokens[this.node.start]?.text ?? "";
  }

  /** The token index of its first value-position token (a `set`'s `$name`, a snippet's or use's name). */
  firstArgToken(): number {
    const [first] = anatomyOf(this.doc.syntax.tokens, this.node).args;
    return typeof first === "number" ? first : this.node.start;
  }
}

export class WrittenDirective extends StatementHandle {
  constructor(
    doc: Document,
    readonly kind: "directive" | "extension",
  ) {
    super(doc);
  }

  get name(): string {
    return this.live().nameText();
  }

  get values(): readonly WrittenValue[] {
    return this.live().valueList as unknown as readonly WrittenValue[];
  }

  get block(): IWrittenBlock | undefined {
    return this.live().blockHandle;
  }

  rename(name: string): void {
    this.live();
    this.doc.renameStatement(this, name);
  }

  setValues(text: string): void {
    this.live();
    this.doc.setValues(this, this.valueList, this.node.start, text);
  }
}

export class SetLine extends StatementHandle {
  readonly kind = "set" as const;
  readonly variableHandle: SetVariable;

  constructor(doc: Document) {
    super(doc);
    this.variableHandle = new SetVariable(this);
  }

  get variable(): IVariable {
    return this.live().variableHandle;
  }

  get values(): readonly WrittenValue[] {
    return this.live().valueList as unknown as readonly WrittenValue[];
  }

  setValues(text: string): void {
    this.live();
    this.doc.setValues(this, this.valueList, this.variableToken, text);
  }

  /** The token index of its `$name`. */
  get variableToken(): number {
    return this.firstArgToken();
  }
}

export class SnippetLine extends StatementHandle {
  readonly kind = "snippet" as const;
  parameterHandles: ParameterVariable[] = [];

  get name(): string {
    this.live();
    return this.doc.syntax.tokens[this.firstArgToken()]?.text ?? "";
  }

  get parameters(): readonly IVariable[] {
    return this.live().parameterHandles;
  }

  get block(): IWrittenBlock {
    const block = this.live().blockHandle;
    if (block === undefined) throw new Error("a snippet line has a block");
    return block;
  }
}

export class UseLine extends StatementHandle {
  readonly kind = "use" as const;

  get snippetName(): string {
    this.live();
    return this.doc.syntax.tokens[this.firstArgToken()]?.text ?? "";
  }

  get snippet(): ISnippetLine | undefined {
    const name = this.snippetName;
    const found = this.doc.above(this, (s) => s instanceof SnippetLine && s.name === name);
    return found as SnippetLine | undefined;
  }

  snippets(): readonly IResolution<ISnippetLine>[] {
    this.live();
    return this.doc.host.binding().snippetsOf(this);
  }

  get values(): readonly WrittenValue[] {
    return this.live().valueList as unknown as readonly WrittenValue[];
  }

  setValues(text: string): void {
    this.live();
    this.doc.setValues(this, this.valueList, this.firstArgToken(), text);
  }
}

export class UnreadableLine extends StatementHandle {
  readonly kind = "unreadable" as const;
}

// --- Variables ---

/** What `reaches()` and `overridden()` share. */
abstract class VariableBase {
  abstract readonly kind: IVariable["kind"];
  abstract readonly name: string;
  protected abstract graphBinding(): IBinding;

  reaches(): readonly IReferenceResolution[] {
    return this.graphBinding()
      .resolutions()
      .filter((r) => r.winner === (this as unknown as IVariable));
  }

  overridden(): readonly IReferenceResolution[] {
    return this.graphBinding()
      .resolutions()
      .filter((r) => r.overridden.includes(this as unknown as IVariable));
  }
}

/** A `set` line's `$name`: the same object as that line's `variable`. */
export class SetVariable extends VariableBase implements IVariable {
  readonly kind = "set" as const;

  constructor(private readonly setLine: SetLine) {
    super();
  }

  get name(): string {
    this.setLine.live();
    return this.setLine.doc.syntax.tokens[this.setLine.variableToken]?.text.slice(1) ?? "";
  }

  get place(): IPlace {
    const { doc } = this.setLine.live();
    const token = this.setLine.variableToken;
    return doc.place(doc.spanOf({ start: token, end: token + 1 }));
  }

  get line(): ISetLine {
    return this.setLine.live();
  }

  protected graphBinding(): IBinding {
    return this.setLine.live().doc.host.binding();
  }

  references(): readonly IReference[] {
    this.setLine.live();
    return allReferences(this.setLine.doc).filter((r) => r.declaration === this);
  }

  rename(name: string): void {
    this.setLine.live();
    this.setLine.doc.renameVariable(this.setLine.variableToken, name, this.setLine);
  }

  setValues(text: string): void {
    this.setLine.setValues(text);
  }
}

/** A snippet parameter's `$name`. */
export class ParameterVariable extends VariableBase implements IVariable {
  readonly kind = "parameter" as const;
  /** Its VARIABLE token index in the current parse; set by every build. */
  token = 0;
  detached = false;

  constructor(private readonly snippetLine: SnippetLine) {
    super();
  }

  private alive(): SnippetLine {
    if (this.detached) throw detached("parameter");
    return this.snippetLine.live();
  }

  get name(): string {
    return this.alive().doc.syntax.tokens[this.token]?.text.slice(1) ?? "";
  }

  get place(): IPlace {
    const { doc } = this.alive();
    return doc.place(doc.spanOf({ start: this.token, end: this.token + 1 }));
  }

  get line(): ISnippetLine {
    return this.alive();
  }

  protected graphBinding(): IBinding {
    return this.alive().doc.host.binding();
  }

  references(): readonly IReference[] {
    return allReferences(this.alive().doc).filter((r) => r.declaration === this);
  }

  rename(name: string): void {
    const line = this.alive();
    line.doc.renameVariable(this.token, name, this);
  }

  setValues(text: string): void {
    this.alive();
    void text;
    throw new NoSetLineError(`$${this.name} is a snippet parameter: edit the use line's values`);
  }
}

/** A value the program handed in: one per name for the graph's life (D28). */
export class HandedVariable extends VariableBase implements IVariable {
  readonly kind = "handed" as const;
  readonly place = undefined;
  readonly line = undefined;

  constructor(
    readonly name: string,
    private readonly binding: () => IBinding,
  ) {
    super();
  }

  protected graphBinding(): IBinding {
    return this.binding();
  }

  references(): readonly IReference[] {
    return [];
  }

  rename(name: string): void {
    void name;
    throw new NoSetLineError(`$${this.name} is handed in: use setHanded`);
  }

  setValues(text: string): void {
    void text;
    throw new NoSetLineError(`$${this.name} is handed in: use setHanded`);
  }
}

/** Every reference of the graph a document belongs to, documents in order. */
function allReferences(doc: Document): IReference[] {
  return doc.host.allDocuments().flatMap((d) => d.references());
}
