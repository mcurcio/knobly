/**
 * The statement handles and the variables of the low level (round 12 design.md §5; slices.md 2.1). One object per
 * written thing for the graph's life; the document re-points it at its tokens after each edit, or detaches it.
 * Private to the package: programs see the interfaces of model.ts.
 */

import { anatomyOf } from "../anatomy.js";
import type { StatementKind } from "../gen/api/kinds.js";
import type { IPlace } from "../origin.js";
import type { INode } from "../syntax/cst.js";
import { textOf } from "../syntax/cst.js";
import { type ConfigText, requireText } from "../text.js";
import type { IBinding } from "./bind.js";
import type { Block, Document } from "./document.js";
import { detached } from "./document.js";
import type {
  ICopy,
  IDocument,
  IExtensionLine,
  IOverrideVariable,
  IParameter,
  IReference,
  IReferenceResolution,
  IResolution,
  ISetLine,
  ISetVariable,
  ISnippetLine,
  IUnreadableLine,
  IUseLine,
  IWrittenBlock,
  IWrittenDirective,
  Statement,
  Variable,
  WrittenValue,
} from "./model.js";
import type { ValueHandle } from "./values.js";

/** What every statement handle has. */
export abstract class StatementHandle {
  abstract readonly kind: StatementKind;
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

  get parent(): IWrittenDirective | IExtensionLine | ISnippetLine | undefined {
    return this.live().parentHandle as IWrittenDirective | IExtensionLine | ISnippetLine | undefined;
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

  replaceWithText(text: ConfigText): readonly Statement[] {
    this.live();
    requireText(text, "replaceWithText", "text");
    return this.doc.replaceStatement(this, text);
  }

  remove(): void {
    this.live();
    this.doc.removeStatement(this);
  }

  insertBefore(text: ConfigText): readonly Statement[] {
    this.live();
    requireText(text, "insertBefore", "text");
    const block = this.containingBlock();
    return block.insertStatements(block.items.indexOf(this), text);
  }

  insertAfter(text: ConfigText): readonly Statement[] {
    this.live();
    requireText(text, "insertAfter", "text");
    const block = this.containingBlock();
    return block.insertStatements(block.items.indexOf(this) + 1, text);
  }

  /** The block that holds it: its parent's, or its document's top level. */
  private containingBlock(): Block {
    return this.parentHandle?.blockHandle ?? this.doc.block;
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
    const [first] = anatomyOf(this.doc.syntax.tokens, this.node).values;
    return typeof first === "number" ? first : this.node.start;
  }
}

/** What a directive and an extension line share: a name, values and an optional block. */
abstract class NamedLine extends StatementHandle {
  get name(): string {
    return this.live().nameText();
  }

  get values(): readonly WrittenValue[] {
    return this.live().valueList as readonly WrittenValue[];
  }

  get block(): IWrittenBlock | undefined {
    return this.live().blockHandle;
  }

  set(text: ConfigText): void {
    this.live();
    requireText(text, "set", "text");
    this.doc.replaceValues(this, this.valueList, this.node.start, text);
  }
}

export class WrittenDirective extends NamedLine implements IWrittenDirective {
  readonly kind = "directive";

  rename(name: string): void {
    this.live();
    requireText(name, "rename", "name");
    this.doc.renameStatement(this, name);
  }
}

/** `@name` where a registered extension owns `name` (an include line): no `rename`. */
export class ExtensionLine extends NamedLine implements IExtensionLine {
  readonly kind = "extension";

  /** The extension's name: its `@name` token without the `@`. */
  override get name(): string {
    return this.live().nameText().slice(1);
  }
}

export class SetLine extends StatementHandle implements ISetLine {
  readonly kind = "set";
  readonly variableHandle: SetVariable;

  constructor(doc: Document) {
    super(doc);
    this.variableHandle = new SetVariable(this);
  }

  get variable(): ISetVariable {
    return this.live().variableHandle;
  }

  get values(): readonly WrittenValue[] {
    return this.live().valueList as readonly WrittenValue[];
  }

  set(text: ConfigText): void {
    this.live();
    requireText(text, "set", "text");
    this.doc.replaceValues(this, this.valueList, this.variableToken, text);
  }

  /** The token index of its `$name`. */
  get variableToken(): number {
    return this.firstArgToken();
  }
}

export class SnippetLine extends StatementHandle implements ISnippetLine {
  readonly kind = "snippet";
  parameterHandles: ParameterVariable[] = [];

  get name(): string {
    this.live();
    return this.doc.syntax.tokens[this.firstArgToken()]?.text ?? "";
  }

  get parameters(): readonly IParameter[] {
    return this.live().parameterHandles;
  }

  get block(): IWrittenBlock {
    const block = this.live().blockHandle;
    if (block === undefined) throw new Error("a snippet line has a block");
    return block;
  }
}

export class UseLine extends StatementHandle implements IUseLine {
  readonly kind = "use";

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
    return this.live().valueList as readonly WrittenValue[];
  }

  set(text: ConfigText): void {
    this.live();
    requireText(text, "set", "text");
    this.doc.replaceValues(this, this.valueList, this.firstArgToken(), text);
  }
}

export class UnreadableLine extends StatementHandle implements IUnreadableLine {
  readonly kind = "unreadable";
}

// --- Variables ---

/** What `wins()` and `shadowedAt()` share. */
abstract class VariableBase {
  protected abstract graphBinding(): IBinding;

  wins(): readonly IReferenceResolution[] {
    return this.graphBinding()
      .resolutions()
      .filter((r) => r.winner === (this as unknown));
  }

  shadowedAt(): readonly IReferenceResolution[] {
    return this.graphBinding()
      .resolutions()
      .filter((r) => r.shadowed.includes(this as unknown as Variable));
  }
}

/** A `set` line's `$name`: the same object as that line's `variable`. */
export class SetVariable extends VariableBase implements ISetVariable {
  readonly kind = "set";

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
    requireText(name, "rename", "name");
    this.setLine.doc.renameVariable(this.setLine.variableToken, name, this.setLine);
  }

  set(text: ConfigText): void {
    this.setLine.set(text);
  }
}

/** A snippet parameter's `$name`. */
export class ParameterVariable extends VariableBase implements IParameter {
  readonly kind = "parameter";
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
    requireText(name, "rename", "name");
    line.doc.renameVariable(this.token, name, this);
  }
}

/** An override: one per name for the graph's life (D28). Written in no file: no place, line, rename or set. */
export class OverrideVariable extends VariableBase implements IOverrideVariable {
  readonly kind = "override";

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
}

/** Any variable handle. */
export type VariableHandle = SetVariable | ParameterVariable | OverrideVariable;

/** Every reference of the graph a document belongs to, documents in order. */
function allReferences(doc: Document): IReference[] {
  return doc.host.allDocuments().flatMap((d) => d.references());
}
