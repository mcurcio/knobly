/**
 * One file as written (round 12 slices.md 2.1-2.4): its text, its source, its tier-1 parse, and the tree of handles
 * over it. Every edit computes the new text, checks it (2.3), re-parses the whole document and reconciles the
 * handles (2.1). Private to the package; programs see IDocument and the statement and value interfaces.
 */

import { DiagnosticCode, type IDiagnostic } from "../diagnostics.js";
import type { IPlace } from "../load/origin.js";
import type { ISourcePosition, ISourceSpan } from "../span.js";
import { type INode, type ISyntax, NodeKind, spanOf, type ValueRef } from "../syntax/cst.js";
import { parse } from "../syntax/parse.js";
import { messageOf } from "../syntax/recovery.js";
import { type IToken, TokenKind } from "../syntax/tokens.js";
import { anatomyOf, itemsOf } from "../load/anatomy.js";
import { type IBinding, RESERVED } from "./bind.js";
import { BadTextError, DetachedError } from "./errors.js";
import type { IDocument, IDocumentEdge, IVariable, IWrittenBlock, IWrittenDirective, Statement, WrittenValue } from "./model.js";
import { blockShapes, type IShape, parameterTokens, type ShapeKind, statementNodes } from "./shape.js";
import {
  ParameterVariable,
  SetLine,
  SnippetLine,
  StatementHandle,
  UnreadableLine,
  UseLine,
  WrittenDirective,
} from "./statements.js";
import { IndexValue, ListValue, Reference, SliceValue, StringValue, ValueHandle, WordValue } from "./values.js";

/** What a document needs from the graph that holds it. */
export interface IDocumentHost {
  /** The registered extensions' directive names: a line starting with one is kind "extension". */
  readonly extensionNames: ReadonlySet<string>;
  /** The current derivation (cached per graph version). */
  binding(): IBinding;
  /** Every document of the graph, in `documents` order. */
  allDocuments(): readonly Document[];
  /** Called after every change to a text: the binding is stale. */
  changed(): void;
}

/** Anything a reconcile keeps or detaches. */
type Handle = StatementHandle | ValueHandle | ParameterVariable;

/** A handle's old token range, in offsets of the text before an edit. */
interface IOldEntry {
  readonly handle: Handle;
  readonly start: number;
  readonly end: number;
}

/** Matches the handles of a new parse to the old ones (2.1). */
class Reconcile {
  readonly created: Handle[] = [];

  constructor(
    private readonly old: Map<string, IOldEntry>,
    /** The replaced range in old offsets, and the length of what replaced it; undefined: keep nothing. */
    private readonly range: { readonly start: number; readonly end: number; readonly inserted: number } | undefined,
    /** The handle an edit keeps although the replaced range starts at its first token (`rename`, 2.1). */
    private readonly keep?: Handle,
  ) {}

  take(key: string, newStart: number): Handle | undefined {
    const { range } = this;
    if (range === undefined) return undefined;
    const delta = range.inserted - (range.end - range.start);
    let oldStart: number;
    if (newStart < range.start) oldStart = newStart;
    else if (newStart >= range.start + range.inserted) oldStart = newStart - delta;
    else if (newStart === range.start && this.keep !== undefined) {
      const id = `${key}@${String(range.start)}`;
      if (this.old.get(id)?.handle !== this.keep) return undefined;
      this.old.delete(id);
      return this.keep;
    } else return undefined;
    const id = `${key}@${String(oldStart)}`;
    const entry = this.old.get(id);
    if (entry === undefined) return undefined;
    const outside = entry.end <= range.start || entry.start >= range.end;
    const contains = entry.start <= range.start && entry.end >= range.end && (entry.start < range.start || entry.end > range.end);
    if (!outside && !contains) return undefined;
    this.old.delete(id);
    return entry.handle;
  }

  /** Handles left over: their tokens were replaced. */
  leftovers(): Handle[] {
    return [...this.old.values()].map((entry) => entry.handle);
  }
}

/** The statements of a document or of a block. */
export class Block implements IWrittenBlock {
  /** Set by every build. */
  items: StatementHandle[] = [];

  constructor(
    private readonly document: Document,
    /** The statement whose block this is; undefined for a document's body. */
    readonly owner: StatementHandle | undefined,
  ) {}

  get statements(): readonly Statement[] {
    this.owner?.live();
    return this.items as unknown as readonly Statement[];
  }

  directives(name?: string): readonly IWrittenDirective[] {
    return this.statements.filter((s): s is IWrittenDirective => s.kind === "directive" && (name === undefined || s.name === name));
  }

  insertStatements(index: number, text: string): readonly Statement[] {
    this.owner?.live();
    if (!Number.isInteger(index) || index < 0 || index > this.items.length) {
      throw new RangeError(`statement index ${String(index)} is outside 0..${String(this.items.length)}`);
    }
    return this.document.insertStatements(this, index, text);
  }

  addStatements(text: string): readonly Statement[] {
    return this.insertStatements(this.statements.length, text);
  }
}

const TRIVIA: ReadonlySet<string> = new Set([TokenKind.Space, TokenKind.Newline]);

export class Document implements IDocument {
  private current: string;
  private saved: string;
  private parsed: ISyntax;
  readonly body: Block;
  private statementsByToken = new Map<number, StatementHandle>();
  private valuesByToken = new Map<number, ValueHandle>();

  constructor(
    readonly host: IDocumentHost,
    readonly resolvedPath: string,
    text: string,
  ) {
    this.current = text;
    this.saved = text;
    this.parsed = parse(text);
    this.body = new Block(this, undefined);
    this.build(new Reconcile(new Map(), undefined));
  }

  get source(): string {
    return this.saved;
  }

  get text(): string {
    return this.current;
  }

  get syntax(): ISyntax {
    return this.parsed;
  }

  includedBy(): readonly IDocumentEdge[] {
    return this.host.binding().edgesInto(this.resolvedPath);
  }

  replaceWithText(text: string): void {
    const reconcile = new Reconcile(this.entries(), undefined);
    this.current = text;
    this.parsed = parse(text);
    this.build(reconcile);
    for (const handle of reconcile.leftovers()) handle.detached = true;
    this.host.changed();
  }

  /** After a writer resolved: `source` becomes the text handed over. */
  markSaved(text: string): void {
    this.saved = text;
  }

  // --- Lookups for the binding and render ---

  /** The statement handle of a directive or error node of the current parse. */
  statementOf(node: INode): StatementHandle {
    const statement = this.statementsByToken.get(node.start);
    if (statement === undefined) throw new Error(`no statement at token ${String(node.start)} of ${this.resolvedPath}`);
    return statement;
  }

  /** The value handle of a value of the current parse. */
  valueOf(ref: ValueRef): ValueHandle {
    const value = this.valuesByToken.get(typeof ref === "number" ? ref : ref.start);
    if (value === undefined) throw new Error(`no value at token ${String(typeof ref === "number" ? ref : ref.start)}`);
    return value;
  }

  /** A place in this document. */
  place(span: ISourceSpan): IPlace {
    return { kind: "file", resolvedPath: this.resolvedPath, span };
  }

  /** The span of a token range of the current parse. */
  spanOf(range: { readonly start: number; readonly end: number }): ISourceSpan {
    return spanOf(this.parsed, range);
  }

  /** A statement's owned token range (2.2): from a comment line above it to its trailing comment. */
  ownedRange(node: INode): { start: number; end: number } {
    const { tokens } = this.parsed;
    let first = node.start;
    let last = node.end - 1;
    while (last > first && TRIVIA.has(tokens[last]?.kind ?? "")) last--;
    let j = last + 1;
    while (tokens[j]?.kind === TokenKind.Space) j++;
    if (tokens[j]?.kind === TokenKind.Comment) last = j;
    // Comment lines directly above, only when the statement starts its line.
    let k = first - 1;
    while (tokens[k]?.kind === TokenKind.Space) k--;
    if (k < 0 || tokens[k]?.kind === TokenKind.Newline || tokens[k]?.kind === TokenKind.Bom) {
      for (;;) {
        if (tokens[k]?.kind !== TokenKind.Newline) break;
        let m = k - 1;
        while (tokens[m]?.kind === TokenKind.Space) m--;
        if (tokens[m]?.kind !== TokenKind.Comment) break;
        const comment = m;
        m--;
        while (tokens[m]?.kind === TokenKind.Space) m--;
        if (!(m < 0 || tokens[m]?.kind === TokenKind.Newline || tokens[m]?.kind === TokenKind.Bom)) break;
        first = comment;
        k = m;
      }
    }
    return { start: first, end: last + 1 };
  }

  /** The offsets [start, end) of a token range. */
  offsets(range: { readonly start: number; readonly end: number }): { start: number; end: number } {
    const span = this.spanOf(range);
    return { start: span.start.offset, end: span.end.offset };
  }

  /** The handles currently in the tree, by reconcile key. */
  private entries(): Map<string, IOldEntry> {
    const entries = new Map<string, IOldEntry>();
    const add = (key: string, handle: Handle, range: { start: number; end: number }): void => {
      const { start, end } = this.offsets(range);
      entries.set(`${key}@${String(start)}`, { handle, start, end });
    };
    const statement = (s: StatementHandle): void => {
      add(`s:${s.kind}`, s, this.trimmed(s.node));
      for (const v of s.valueHandles()) value(v);
      if (s instanceof SnippetLine) for (const p of s.parameterHandles) add("p", p, { start: p.token, end: p.token + 1 });
      for (const child of s.blockHandle?.items ?? []) statement(child);
    };
    const value = (v: ValueHandle): void => {
      add(`v:${v.kind}`, v, typeof v.ref === "number" ? { start: v.ref, end: v.ref + 1 } : v.ref);
      for (const inner of v.innerHandles()) value(inner);
    };
    for (const s of this.body.items) statement(s);
    return entries;
  }

  /** A node's range without trailing spaces and line breaks. */
  trimmed(node: INode): { start: number; end: number } {
    const { tokens } = this.parsed;
    let end = node.end;
    while (end > node.start + 1 && TRIVIA.has(tokens[end - 1]?.kind ?? "")) end--;
    return { start: node.start, end };
  }

  // --- Building the handle tree ---

  private build(reconcile: Reconcile): void {
    this.statementsByToken = new Map();
    this.valuesByToken = new Map();
    this.body.items = this.buildBlock(this.parsed.root, undefined, [], reconcile);
  }

  private buildBlock(container: INode, owner: StatementHandle | undefined, claimed: readonly string[], reconcile: Reconcile): StatementHandle[] {
    const nodes = statementNodes(container);
    const shapes = blockShapes(this.parsed.tokens, nodes, this.host.extensionNames, claimed);
    return nodes.map((node, i) => this.buildStatement(node, shapes[i] as IShape, owner, reconcile));
  }

  private buildStatement(node: INode, shape: IShape, owner: StatementHandle | undefined, reconcile: Reconcile): StatementHandle {
    const { tokens } = this.parsed;
    const start = tokens[node.start]?.span.start.offset ?? 0;
    const kept = reconcile.take(`s:${shape.kind}`, start);
    const handle = kept instanceof StatementHandle ? kept : this.newStatement(shape.kind);
    if (kept === undefined) reconcile.created.push(handle);
    handle.node = node;
    handle.parentHandle = owner;
    handle.detached = false;
    this.statementsByToken.set(node.start, handle);
    const anatomy = node.kind === NodeKind.Directive ? anatomyOf(tokens, node) : undefined;
    const values = (refs: readonly ValueRef[]): ValueHandle[] => refs.map((ref) => this.buildValue(ref, handle, undefined, false, reconcile));
    const block = (claimed: readonly string[]): void => {
      if (anatomy?.block === undefined) {
        handle.blockHandle = undefined;
        return;
      }
      handle.blockHandle ??= new Block(this, handle);
      handle.blockHandle.items = this.buildBlock(anatomy.block, handle, claimed, reconcile);
    };
    if (handle instanceof WrittenDirective) {
      handle.valueList = values(anatomy?.args ?? []);
      block([]);
    } else if (handle instanceof SetLine) {
      handle.valueList = values((anatomy?.args ?? []).slice(1));
      handle.blockHandle = undefined;
    } else if (handle instanceof UseLine) {
      handle.valueList = values((anatomy?.args ?? []).slice(1));
      handle.blockHandle = undefined;
    } else if (handle instanceof SnippetLine) {
      handle.valueList = [];
      handle.parameterHandles = parameterTokens(tokens, node).map((token) => {
        const offset = tokens[token]?.span.start.offset ?? 0;
        const keptParameter = reconcile.take("p", offset);
        const parameter = keptParameter instanceof ParameterVariable ? keptParameter : new ParameterVariable(handle);
        if (keptParameter === undefined) reconcile.created.push(parameter);
        parameter.token = token;
        parameter.detached = false;
        return parameter;
      });
      block(handle.parameterHandles.map((p) => p.name));
    } else {
      handle.valueList = [];
      handle.blockHandle = undefined;
    }
    return handle;
  }

  private newStatement(kind: ShapeKind): StatementHandle {
    switch (kind) {
      case "directive":
      case "extension":
        return new WrittenDirective(this, kind);
      case "set":
        return new SetLine(this);
      case "snippet":
        return new SnippetLine(this);
      case "use":
        return new UseLine(this);
      case "unreadable":
        return new UnreadableLine(this);
    }
  }

  private buildValue(ref: ValueRef, statement: StatementHandle, list: ListValue | undefined, bound: boolean, reconcile: Reconcile): ValueHandle {
    const { tokens } = this.parsed;
    const index = typeof ref === "number" ? ref : ref.start;
    const kind = valueKindOf(tokens, ref);
    const start = tokens[index]?.span.start.offset ?? 0;
    const kept = reconcile.take(`v:${kind}`, start);
    const handle = kept instanceof ValueHandle ? kept : newValue(this, kind);
    if (kept === undefined) reconcile.created.push(handle);
    handle.ref = ref;
    handle.statementHandle = statement;
    handle.listHandle = list;
    handle.bound = bound;
    handle.detached = false;
    this.valuesByToken.set(index, handle);
    if (handle instanceof ListValue && typeof ref !== "number") {
      handle.itemHandles = itemsOf(tokens, ref).map((item) => this.buildValue(item, statement, handle, false, reconcile));
    } else if ((handle instanceof SliceValue || handle instanceof IndexValue) && typeof ref !== "number") {
      const inner: number[] = [];
      for (let i = ref.start + 2; i < ref.end - 1; i++) inner.push(i);
      const colon = inner.findIndex((i) => tokens[i]?.kind === TokenKind.Colon);
      const boundAt = (i: number | undefined): ValueHandle | undefined => {
        if (i === undefined) return undefined;
        const kindOf = tokens[i]?.kind;
        return kindOf === TokenKind.Word || kindOf === TokenKind.Variable ? this.buildValue(i, statement, undefined, true, reconcile) : undefined;
      };
      if (handle instanceof IndexValue) {
        handle.indexHandle = boundAt(inner[0]);
      } else {
        handle.startHandle = colon === 0 ? undefined : boundAt(inner[0]);
        handle.endHandle = colon + 1 < inner.length ? boundAt(inner[colon + 1]) : undefined;
      }
    }
    return handle;
  }

  // --- Edits (2.3, 2.4) ---

  /**
   * Replace the offsets [start, end) with `insert`, after `check` found nothing wrong with the resulting text
   * (it returns diagnostics located in the given text). Then re-parse, reconcile, and tell the host.
   * @returns the handles made for the inserted text. @throws BadTextError, changing nothing.
   */
  splice(start: number, end: number, insert: string, given: readonly IDiagnostic[], keep?: Handle): Handle[] {
    if (given.length > 0) throw new BadTextError(`bad text: ${given.map((d) => d.code).join(", ")}`, given);
    const text = this.current.slice(0, start) + insert + this.current.slice(end);
    const syntax = parse(text);
    const rules = ruleProblems(syntax, this.host.extensionNames, start, start + insert.length, insert);
    if (rules.length > 0) throw new BadTextError(`breaks a rule: ${rules.map((d) => d.code).join(", ")}`, rules);
    const reconcile = new Reconcile(this.entries(), { start, end, inserted: insert.length }, keep);
    this.current = text;
    this.parsed = syntax;
    this.build(reconcile);
    for (const handle of reconcile.leftovers()) handle.detached = true;
    this.host.changed();
    return reconcile.created;
  }

  /** The line break this document uses: its first, else `\n`. */
  lineBreak(): string {
    const match = /\r\n|\n/u.exec(this.current);
    return match?.[0] ?? "\n";
  }

  /** The leading whitespace of the line holding `offset`. */
  indentationAt(offset: number): string {
    const lineStart = this.current.lastIndexOf("\n", offset - 1) + 1;
    return /^[ \t]*/u.exec(this.current.slice(lineStart))?.[0] ?? "";
  }

  /** `remove()` of a statement (2.2): its owned span, and its lines when nothing else is on them. */
  removeStatement(statement: StatementHandle): void {
    const { start, end } = this.offsets(this.ownedRange(statement.node));
    const [from, to] = this.removalRange(start, end);
    this.splice(from, to, "", []);
  }

  /** The range a removal of [start, end) deletes: whole lines when nothing else is on them, else one space more. */
  private removalRange(start: number, end: number): [number, number] {
    const text = this.current;
    const lineStart = text.lastIndexOf("\n", start - 1) + 1;
    const newline = text.indexOf("\n", end);
    const lineEnd = newline < 0 ? text.length : newline;
    const before = text.slice(lineStart, start);
    const after = text.slice(end, lineEnd).replace(/\r$/u, "");
    if (/^[ \t\uFEFF]*$/u.test(before) && /^[ \t]*$/u.test(after)) {
      const bomless = text.startsWith("\uFEFF") && lineStart === 0 ? 1 : 0;
      return [lineStart + bomless, newline < 0 ? text.length : newline + 1];
    }
    if (text[end] === " " || text[end] === "\t") return [start, end + 1];
    if (start > 0 && (text[start - 1] === " " || text[start - 1] === "\t")) return [start - 1, end];
    return [start, end];
  }

  /** `replaceWithText` of a statement: zero or more statements, indented as it is. */
  replaceStatement(statement: StatementHandle, text: string): readonly Statement[] {
    const given = parse(text).diagnostics;
    if (text.trim() === "") {
      if (given.length > 0) throw new BadTextError("bad text", given);
      this.removeStatement(statement);
      return [];
    }
    const { start, end } = this.offsets(this.ownedRange(statement.node));
    const insert = this.reindent(text, this.indentationAt(start));
    const owner = statement.parentHandle;
    const created = this.splice(start, end, insert, given);
    return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === owner) as unknown as Statement[];
  }

  /** The given statements text with its common indentation removed, later lines prefixed with `indentation`. */
  reindent(text: string, indentation: string): string {
    const lines = text.replace(/^(?:[ \t]*\r?\n)+/u, "").replace(/(?:\r?\n[ \t]*)+$/u, "").split(/\r?\n/u);
    const common = Math.min(...lines.filter((l) => l.trim() !== "").map((l) => /^[ \t]*/u.exec(l)?.[0].length ?? 0));
    const eol = this.lineBreak();
    return lines.map((line, i) => (i === 0 ? line.slice(common) : line.trim() === "" ? "" : indentation + line.slice(common))).join(eol);
  }

  /**
   * `insertStatements` (2.4): the text's lines, common indentation removed, each prefixed with the siblings'
   * indentation (in an empty block: the parent's line indentation plus the document's unit), on lines of their own
   * before `statements[index]` (its owned comments stay with it), or after the last statement.
   */
  insertStatements(block: Block, index: number, text: string): readonly Statement[] {
    const given = parse(text).diagnostics;
    if (text.trim() === "") {
      if (given.length > 0) throw new BadTextError("bad text", given);
      return [];
    }
    const eol = this.lineBreak();
    const items = block.items;
    const lines = (indentation: string): string => indentation + this.reindent(text, indentation);
    let at: number;
    let insert: string;
    const first = items[0];
    if (first !== undefined) {
      const indentation = this.indentationAt(this.offsets(this.ownedRange(first.node)).start);
      const target = items[index];
      if (target !== undefined) {
        const start = this.offsets(this.ownedRange(target.node)).start;
        const lineStart = this.current.lastIndexOf("\n", start - 1) + 1;
        if (/^[ \t\uFEFF]*$/u.test(this.current.slice(lineStart, start))) {
          // On lines of their own before the target's line (a BOM stays first).
          at = lineStart + (lineStart === 0 && this.current.startsWith("\uFEFF") ? 1 : 0);
          insert = lines(indentation) + eol;
        } else {
          // The target shares its line with an earlier statement: the new lines go between them.
          at = start;
          insert = this.reindent(text, indentation) + eol + this.indentationAt(start);
        }
      } else {
        const last = items[items.length - 1] as StatementHandle;
        at = this.offsets(this.ownedRange(last.node)).end;
        insert = eol + lines(indentation);
      }
    } else if (block.owner === undefined) {
      // An empty document: at its end, on lines of their own.
      at = this.current.length;
      const open = this.current === "" || this.current.endsWith("\n") ? "" : eol;
      insert = open + lines("") + eol;
    } else {
      const { tokens } = this.parsed;
      const node = anatomyOf(tokens, block.owner.node).block;
      if (node === undefined) throw new Error("a block statement without a block node");
      const open = tokens[node.start]?.span.end.offset ?? 0;
      const close = tokens[node.end - 1]?.span.start.offset ?? open;
      const parentIndentation = this.indentationAt(this.offsets(block.owner.node).start);
      const indentation = parentIndentation + this.indentationUnit();
      if (/^[ \t\r\n]*$/u.test(this.current.slice(open, close))) {
        // `{}` (or only whitespace between): `{`, the lines, the parent's indentation, `}`.
        const created = this.splice(open, close, eol + lines(indentation) + eol + parentIndentation, given);
        return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === block.owner) as unknown as Statement[];
      }
      // Only comments inside: the lines go before the `}` line.
      const lineStart = this.current.lastIndexOf("\n", close - 1) + 1;
      if (/^[ \t]*$/u.test(this.current.slice(lineStart, close))) {
        at = lineStart;
        insert = lines(indentation) + eol;
      } else {
        at = close;
        insert = eol + lines(indentation) + eol + parentIndentation;
      }
    }
    const created = this.splice(at, at, insert, given);
    return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === block.owner) as unknown as Statement[];
  }

  /** The document's indentation unit: the leading whitespace of its first indented line, else four spaces (D14). */
  private indentationUnit(): string {
    return /^([ \t]+)\S/mu.exec(this.current)?.[1] ?? "    ";
  }

  /**
   * `rename` of a directive: its name token. Refused (E2001 at 0:0, D-S1-10): not one WORD; `set`, `snippet`, `use`
   * or a registered extension's name; or the line is an extension line. The statement keeps its handle.
   */
  renameStatement(statement: StatementHandle, name: string): void {
    const refuse = (): BadTextError =>
      new BadTextError(`cannot rename to ${JSON.stringify(name)}`, [at(name, 0, DiagnosticCode.UnexpectedToken)]);
    if (statement.kind !== "directive") throw refuse();
    const { tokens } = parse(name);
    const [only] = tokens;
    if (tokens.length !== 1 || only?.kind !== TokenKind.Word || only.text !== name) throw refuse();
    if (RESERVED.has(name) || this.host.extensionNames.has(name)) throw refuse();
    const token = this.parsed.tokens[statement.node.start];
    if (token === undefined) throw new Error("a statement without a name token");
    this.splice(token.span.start.offset, token.span.end.offset, name, [], statement);
  }

  /**
   * `IVariable.rename`: its `$name` token only (2.3). Refused: not `[A-Za-z0-9_]+` (E2001 at 0:0); a second `set`
   * of the name in its block (E5002), by the text-alone rules. The variable keeps its handle.
   */
  renameVariable(token: number, name: string, keep: Handle): void {
    if (!/^[A-Za-z0-9_]+$/u.test(name)) {
      throw new BadTextError(`not a variable name: ${JSON.stringify(name)}`, [at(name, 0, DiagnosticCode.UnexpectedToken)]);
    }
    const span = this.parsed.tokens[token]?.span;
    if (span === undefined) throw new Error("a variable without its token");
    this.splice(span.start.offset, span.end.offset, `$${name}`, [], keep);
  }

  /** `setValues` of a statement's values (2.4): first value to last; with none, after `after` (a token index). */
  setValues(statement: StatementHandle, values: readonly ValueHandle[], after: number, text: string): void {
    const given = valuesTextProblems(text, false);
    const { tokens } = this.parsed;
    const first = values[0];
    const last = values.at(-1);
    if (first === undefined || last === undefined) {
      if (text.trim() === "") return;
      const offset = tokens[after]?.span.end.offset ?? 0;
      this.splice(offset, offset, ` ${text}`, given);
      return;
    }
    const start = this.valueOffsets(first).start;
    const end = this.valueOffsets(last).end;
    if (text.trim() === "") {
      let from = first.ref === undefined ? start : this.tokenIndexOf(first);
      while (tokens[from - 1]?.kind === TokenKind.Space) from--;
      this.splice(tokens[from]?.span.start.offset ?? start, end, "", given);
      return;
    }
    void statement;
    this.splice(start, end, text, given);
  }

  /** `replaceWithText` of a value. */
  replaceValue(value: ValueHandle, text: string): readonly WrittenValue[] {
    if (value.bound) {
      const problems = boundTextProblems(text);
      if (problems.length > 0) throw new BadTextError("a slice bound takes one word or $name", problems);
    }
    const given = value.bound ? [] : valuesTextProblems(text, value.listHandle !== undefined);
    if (text.trim() === "") {
      this.removeValue(value);
      return [];
    }
    const { start, end } = this.valueOffsets(value);
    const container = value.listHandle;
    const statement = value.statementHandle;
    const created = this.splice(start, end, text, given);
    return created.filter(
      (h): h is ValueHandle => h instanceof ValueHandle && h.listHandle === container && h.statementHandle === statement && !h.bound,
    ) as unknown as WrittenValue[];
  }

  /** `remove()` of a value (2.4): with the space before it; in a list, with its comma. */
  removeValue(value: ValueHandle): void {
    const { tokens } = this.parsed;
    const { start, end } = this.valueOffsets(value);
    const list = value.listHandle;
    if (list !== undefined) {
      const items = list.itemHandles;
      const i = items.indexOf(value);
      const next = items[i + 1];
      const previous = items[i - 1];
      if (next !== undefined) {
        this.splice(start, this.valueOffsets(next).start, "", []);
      } else if (previous !== undefined) {
        this.splice(this.valueOffsets(previous).end, end, "", []);
      } else {
        this.splice(start, end, "", []);
      }
      return;
    }
    let from = this.tokenIndexOf(value);
    while (tokens[from - 1]?.kind === TokenKind.Space) from--;
    this.splice(tokens[from]?.span.start.offset ?? start, end, "", []);
  }

  private tokenIndexOf(value: ValueHandle): number {
    return typeof value.ref === "number" ? value.ref : value.ref.start;
  }

  valueOffsets(value: ValueHandle): { start: number; end: number } {
    const ref = value.ref;
    return this.offsets(typeof ref === "number" ? { start: ref, end: ref + 1 } : ref);
  }

  // --- Declarations by where written (2.6) ---

  /** The variable a reference binds to by where it is written; undefined when free. */
  declarationOf(reference: Reference): IVariable | undefined {
    const name = reference.name;
    for (let s = reference.statementHandle.parentHandle; s !== undefined; s = s.parentHandle) {
      if (s instanceof SnippetLine) {
        const parameter = s.parameterHandles.find((p) => p.name === name);
        if (parameter !== undefined) return parameter;
      }
    }
    const found = this.above(reference.statementHandle, (s) => s instanceof SetLine && s.variableHandle.name === name);
    return found instanceof SetLine ? found.variableHandle : undefined;
  }

  /** The nearest statement above `statement` in its block or an enclosing block that matches. */
  above(statement: StatementHandle, match: (s: StatementHandle) => boolean): StatementHandle | undefined {
    for (let s: StatementHandle | undefined = statement; s !== undefined; s = s.parentHandle) {
      const block = s.parentHandle?.blockHandle ?? this.body;
      const items = block.items;
      for (let i = items.indexOf(s) - 1; i >= 0; i--) {
        const candidate = items[i] as StatementHandle;
        if (match(candidate)) return candidate;
      }
    }
    return undefined;
  }

  /** Every reference value of this document, in text order. */
  references(): Reference[] {
    const out: Reference[] = [];
    const value = (v: ValueHandle): void => {
      if (v instanceof Reference) out.push(v);
      for (const inner of v.innerHandles()) value(inner);
    };
    const statement = (s: StatementHandle): void => {
      for (const v of s.valueHandles()) value(v);
      for (const child of s.blockHandle?.items ?? []) statement(child);
    };
    for (const s of this.body.items) statement(s);
    return out;
  }

  /** Every `set` and snippet line's variables, in text order. */
  variables(): IVariable[] {
    const out: IVariable[] = [];
    const statement = (s: StatementHandle): void => {
      if (s instanceof SetLine) out.push(s.variableHandle);
      if (s instanceof SnippetLine) out.push(...s.parameterHandles);
      for (const child of s.blockHandle?.items ?? []) statement(child);
    };
    for (const s of this.body.items) statement(s);
    return out;
  }
}

function valueKindOf(tokens: readonly IToken[], ref: ValueRef): WrittenValue["kind"] {
  if (typeof ref !== "number") {
    if (ref.kind === NodeKind.List) return "list";
    for (let i = ref.start + 2; i < ref.end - 1; i++) if (tokens[i]?.kind === TokenKind.Colon) return "slice";
    return ref.end - ref.start > 3 ? "index" : "slice";
  }
  switch (tokens[ref]?.kind) {
    case TokenKind.String:
      return "string";
    case TokenKind.Variable:
      return "reference";
    default:
      return "word";
  }
}

function newValue(document: Document, kind: WrittenValue["kind"]): ValueHandle {
  switch (kind) {
    case "word":
      return new WordValue(document);
    case "string":
      return new StringValue(document);
    case "list":
      return new ListValue(document);
    case "slice":
      return new SliceValue(document);
    case "index":
      return new IndexValue(document);
    case "reference":
      return new Reference(document);
  }
}

/** The position of `offset` in `text` (0-based line and UTF-16 column). */
export function positionIn(text: string, offset: number): ISourcePosition {
  const at = Math.max(0, Math.min(offset, text.length));
  const before = text.slice(0, at);
  const line = before.split("\n").length - 1;
  return { offset: at, line, column: at - (before.lastIndexOf("\n") + 1) };
}

/** A diagnostic of a wrapped text, moved into the given text (which starts at `shift` of the wrapped one). */
function shifted(given: string, shift: number, d: IDiagnostic): IDiagnostic {
  const start = positionIn(given, d.span.start.offset - shift);
  const end = positionIn(given, d.span.end.offset - shift);
  return { code: d.code, message: d.message, span: { start, end } };
}

function at(given: string, offset: number, code: DiagnosticCode): IDiagnostic {
  const position = positionIn(given, offset);
  return { code, message: messageOf(code), span: { start: position, end: position } };
}

/**
 * 2.3's check of a values text: parsed as the values of one directive (`x <text>;`; in a list, `x [<text>];`).
 * Its syntax diagnostics, shifted to the given text; when it is more than values, one E2001 at the first such token.
 */
export function valuesTextProblems(text: string, inList: boolean): IDiagnostic[] {
  const prefix = inList ? "x [" : "x ";
  const syntax = parse(`${prefix}${text}${inList ? "];" : ";"}`);
  if (syntax.diagnostics.length > 0) return syntax.diagnostics.map((d) => shifted(text, prefix.length, d));
  let depth = 0;
  for (const token of syntax.tokens) {
    const offset = token.span.start.offset;
    if (offset < prefix.length || offset >= prefix.length + text.length) continue;
    if (token.kind === TokenKind.LBrack) depth++;
    if (token.kind === TokenKind.RBrack) depth--;
    const more =
      token.kind === TokenKind.Semi ||
      token.kind === TokenKind.LBrace ||
      token.kind === TokenKind.RBrace ||
      (inList && depth < 0) ||
      (!inList && token.kind === TokenKind.Comma && depth === 0);
    if (more) return [at(text, offset - prefix.length, DiagnosticCode.UnexpectedToken)];
  }
  return [];
}

/** A slice bound's text: exactly one WORD or `$name` (E2001 otherwise). */
function boundTextProblems(text: string): IDiagnostic[] {
  const syntax = parse(`x ${text};`);
  const tokens = syntax.tokens.filter((t) => t.span.start.offset >= 2 && t.span.start.offset < 2 + text.length);
  const bad = tokens.find((t) => t.kind !== TokenKind.Word && t.kind !== TokenKind.Variable);
  if (bad !== undefined) return [at(text, bad.span.start.offset - 2, DiagnosticCode.UnexpectedToken)];
  if (tokens.length !== 1) return [at(text, tokens[1]?.span.start.offset === undefined ? 0 : tokens[1].span.start.offset - 2, DiagnosticCode.UnexpectedToken)];
  return [];
}

/**
 * The text-alone rules (E5002, E5005, E5009-E5011) a spliced text would break, on the statements the splice
 * touches: located in the inserted text when the problem lies in it, else at 0:0.
 */
function ruleProblems(syntax: ISyntax, extensions: ReadonlySet<string>, from: number, to: number, inserted: string): IDiagnostic[] {
  const out: IDiagnostic[] = [];
  const { tokens } = syntax;
  const touches = (node: INode): boolean => {
    const span = spanOf(syntax, node);
    const [s, e] = [span.start.offset, span.end.offset];
    return from === to ? s < from && e > from : s < to && e > from;
  };
  const report = (fault: { code: DiagnosticCode; span: ISourceSpan }): void => {
    const offset = fault.span.start.offset;
    const inside = offset >= from && offset < to;
    out.push(inside ? at(inserted, offset - from, fault.code) : at(inserted, 0, fault.code));
  };
  const visit = (container: INode, claimed: readonly string[]): void => {
    const nodes = statementNodes(container);
    const shapes = blockShapes(tokens, nodes, extensions, claimed);
    nodes.forEach((node, i) => {
      const shape = shapes[i] as IShape;
      if (shape.fault !== undefined) {
        const code = shape.fault.code;
        let involved = touches(node);
        if (!involved && (code === DiagnosticCode.VariableSetTwice || code === DiagnosticCode.SnippetDefinedTwice)) {
          const name = shape.fault.detail?.replace(/^\$/u, "");
          involved = nodes.slice(0, i).some((other, j) => touches(other) && (shapes[j] as IShape).claims === name);
        }
        if (involved) report(shape.fault);
      }
      if (node.kind !== NodeKind.Directive) return;
      const { block } = anatomyOf(tokens, node);
      if (block === undefined || shape.kind === "unreadable") return;
      const params = shape.kind === "snippet" ? parameterTokens(tokens, node).map((t) => tokens[t]?.text.slice(1) ?? "") : [];
      visit(block, params);
    });
  };
  visit(syntax.root, []);
  return out;
}

/** Throw DetachedError for a handle whose tokens are gone. */
export function detached(what: string): DetachedError {
  return new DetachedError(`this ${what} was removed by an edit or its document's text was replaced`);
}
