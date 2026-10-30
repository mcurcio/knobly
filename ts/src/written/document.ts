/**
 * One file as written (round 12 slices.md 2.1-2.4): its text, its saved text, its tier-1 parse, and the tree of handles
 * over it. Every edit computes the new text, checks it (2.3), re-parses the whole document and reconciles the
 * handles (2.1). Private to the package; programs see `Document` and the statement and value interfaces.
 */

import { anatomyOf, itemsOf, valuesOf } from "../anatomy.js";
import { BlockBase } from "../block.js";
import { makeDiagnostic } from "../diagnostics.js";
import { makePlace } from "../origin.js";
import { spanOf, type ValueRef } from "../syntax/cst.js";
import { parse, parseEntry } from "../syntax/parse.js";
import { requireText } from "../text.js";
import type { Binding } from "./bind.js";
import { checkDirectiveName, checkVariableName } from "./names.js";
import { blockShapes, type Shape, isTextAlone, parameterTokens, type ShapeKind, statementNodes } from "./shape.js";
import {
  ExtensionLine,
  ParameterVariable,
  SetLine,
  SnippetLine,
  StatementHandle,
  UnreadableLine,
  UseLine,
  WrittenDirective,
} from "./statements.js";
import { becomeKind, IndexValue, ListValue, newValue, Reference, SliceValue, ValueHandle, type ValueRole } from "./values.js";
import { DiagnosticCode, describe } from "../gen/api/codes.js";
import { BadTextError, DetachedError, MisuseError } from "../gen/api/errors.js";
import type { ConfigText, Diagnostic, Place, SourcePosition, SourceSpan } from "../gen/api/shared.js";
import type { Node, Syntax, Token } from "../gen/api/syntax.js";
import type { DocumentEdge, Parameter, SetVariable, Statement, WrittenValue } from "../gen/api/written.js";
import type * as api from "../gen/api/written.js";
import { NodeKind, StatementKind, TokenKind, ValueKind } from "../gen/api/kinds.js";

/** What a document needs from the graph that holds it. */
export interface DocumentHost {
  /** The registered extensions' names: a line headed `@` and one of them is kind "extension". */
  readonly extensionNames: ReadonlySet<string>;
  /** The current derivation (cached per graph version). */
  binding(): Binding;
  /** Every document of the graph, in `documents` order. */
  allDocuments(): readonly Document[];
  /** Called after every change to a text: the binding is stale. */
  changed(): void;
}

/** Anything a reconcile keeps or detaches. */
type Handle = StatementHandle | ValueHandle | ParameterVariable;

/** A handle's old token range, in offsets of the text before an edit. */
interface OldEntry {
  readonly handle: Handle;
  readonly start: number;
  readonly end: number;
}

/** A reconcile key's family: `s` (statement), `v` (value) or `p` (parameter). */
/**
 * Text that holds only the grammar's spaces and line breaks (space, tab, CR, LF): what an edit given it removes or
 * inserts nothing for. Not `trim()`, which also strips U+FEFF and other Unicode spaces the grammar refuses.
 */
function isBlank(text: string): boolean {
  return /^[ \t\r\n]*$/u.test(text);
}

function familyOf(key: string): string {
  return /^[a-z]+/u.exec(key)?.[0] ?? "";
}

/** Matches the handles of a new parse to the old ones (2.1). */
class Reconcile {
  readonly created: Handle[] = [];

  constructor(
    private readonly old: Map<string, OldEntry>,
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
    else if (newStart === range.start) return this.atStart(key);
    else return this.keptInside(key);
    const id = `${key}@${String(oldStart)}`;
    const entry = this.old.get(id);
    if (entry === undefined) return undefined;
    const outside = entry.end <= range.start || entry.start >= range.end;
    const contains = entry.start <= range.start && entry.end >= range.end && (entry.start < range.start || entry.end > range.end);
    if (!outside && !contains) return undefined;
    this.old.delete(id);
    return entry.handle;
  }

  /**
   * A handle of the new parse starting where the replaced range starts (spec 6.1): an old one of the same key whose
   * tokens hold the range and more (a slice around its replaced name), else the one the edit keeps, of its family
   * (statement, value, parameter) whatever its kind (a value's `set` that changes its kind), else none.
   */
  private atStart(key: string): Handle | undefined {
    const range = this.range;
    if (range === undefined) return undefined;
    const id = `${key}@${String(range.start)}`;
    const entry = this.old.get(id);
    if (entry !== undefined && entry.handle !== this.keep && range.end > range.start && entry.end > range.end) {
      this.old.delete(id);
      return entry.handle;
    }
    if (this.keep === undefined) return undefined;
    for (const [oldId, old] of this.old) {
      if (old.handle !== this.keep) continue;
      if (familyOf(oldId) !== familyOf(key) || old.start !== range.start) return undefined;
      this.old.delete(oldId);
      return this.keep;
    }
    return undefined;
  }

  /**
   * A value built inside what replaced the range but not at its start (a value's `set` given text with a leading
   * gap, spec 6.1): the value the edit keeps, for the first such value built (the new value; its own items, bounds
   * and name are built after it), whatever its kind.
   */
  private keptInside(key: string): Handle | undefined {
    if (this.keep === undefined || familyOf(key) !== "v") return undefined;
    for (const [oldId, old] of this.old) {
      if (old.handle !== this.keep) continue;
      if (familyOf(oldId) !== "v") return undefined;
      this.old.delete(oldId);
      return this.keep;
    }
    return undefined;
  }

  /** Handles left over: their tokens were replaced. */
  leftovers(): Handle[] {
    return [...this.old.values()].map((entry) => entry.handle);
  }
}

/** The statements of a document or of a block (spec 2.11): live, so each member re-reads the current statements. */
export class Block extends BlockBase<Statement, api.WrittenDirective> implements api.WrittenBlock {
  /** Set by every build. */
  handles: StatementHandle[] = [];

  constructor(
    private readonly document: Document,
    /** The statement whose block this is; undefined for a document's top level. */
    readonly owner: StatementHandle | undefined,
  ) {
    super();
  }

  protected contents(): readonly Statement[] {
    this.owner?.live();
    return this.handles as readonly Statement[];
  }

  protected blockOf(statement: Statement): Iterable<Statement> | undefined {
    return (statement as unknown as StatementHandle).blockHandle;
  }

  protected isDirective(statement: Statement, name: string | undefined): statement is api.WrittenDirective {
    return statement.kind === StatementKind.Directive && (name === undefined || statement.name === name);
  }

  insertStatements(index: number, text: ConfigText): readonly Statement[] {
    this.owner?.live();
    requireText(text, "insertStatements", "text");
    if (!Number.isInteger(index) || index < 0 || index > this.handles.length) {
      throw new RangeError(`statement index ${String(index)} is outside 0..${String(this.handles.length)}`);
    }
    return this.document.insertStatements(this, index, text);
  }

  addStatements(text: ConfigText): readonly Statement[] {
    this.owner?.live();
    requireText(text, "addStatements", "text");
    return this.insertStatements(this.handles.length, text);
  }
}

const TRIVIA: ReadonlySet<string> = new Set([TokenKind.SPACE, TokenKind.NEWLINE]);

export class Document implements api.Document {
  private current: string;
  private saved: string;
  private parsed: Syntax;
  readonly block: Block;
  private statementsByToken = new Map<number, StatementHandle>();
  private valuesByToken = new Map<number, ValueHandle>();

  constructor(
    readonly host: DocumentHost,
    readonly resolvedPath: string,
    text: string,
  ) {
    this.current = text;
    this.saved = text;
    this.parsed = parse(text);
    this.block = new Block(this, undefined);
    this.build(new Reconcile(new Map(), undefined));
  }

  get savedText(): string {
    return this.saved;
  }

  get text(): string {
    return this.current;
  }

  get syntax(): Syntax {
    return this.parsed;
  }

  includedBy(): readonly DocumentEdge[] {
    return this.host.binding().edgesInto(this.resolvedPath);
  }

  replaceWithText(text: ConfigText): void {
    requireText(text, "replaceWithText", "text");
    const reconcile = new Reconcile(this.entries(), undefined);
    this.current = text;
    this.parsed = parse(text);
    this.build(reconcile);
    for (const handle of reconcile.leftovers()) handle.detached = true;
    this.host.changed();
  }

  /** After a writer resolved: `savedText` becomes the text handed over. */
  markSaved(text: string): void {
    this.saved = text;
  }

  // --- Lookups for the binding and render ---

  /** The statement handle of a directive or error node of the current parse. */
  statementOf(node: Node): StatementHandle {
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
  place(span: SourceSpan): Place {
    return makePlace(this.resolvedPath, span);
  }

  /** The span of a token range of the current parse. */
  spanOf(range: { readonly start: number; readonly end: number }): SourceSpan {
    return spanOf(this.parsed, range);
  }

  /** A statement's owned token range (2.2): from a comment line above it to its trailing comment. */
  ownedRange(node: Node): { start: number; end: number } {
    const { tokens } = this.parsed;
    let first = node.start;
    let last = node.end - 1;
    while (last > first && TRIVIA.has(tokens[last]?.kind ?? "")) last--;
    let j = last + 1;
    while (tokens[j]?.kind === TokenKind.SPACE) j++;
    if (tokens[j]?.kind === TokenKind.COMMENT) last = j;
    // Comment lines directly above, only when the statement starts its line.
    let k = first - 1;
    while (tokens[k]?.kind === TokenKind.SPACE) k--;
    if (k < 0 || tokens[k]?.kind === TokenKind.NEWLINE || tokens[k]?.kind === TokenKind.BOM) {
      for (;;) {
        if (tokens[k]?.kind !== TokenKind.NEWLINE) break;
        let m = k - 1;
        while (tokens[m]?.kind === TokenKind.SPACE) m--;
        if (tokens[m]?.kind !== TokenKind.COMMENT) break;
        const comment = m;
        m--;
        while (tokens[m]?.kind === TokenKind.SPACE) m--;
        if (!(m < 0 || tokens[m]?.kind === TokenKind.NEWLINE || tokens[m]?.kind === TokenKind.BOM)) break;
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
  private entries(): Map<string, OldEntry> {
    const entries = new Map<string, OldEntry>();
    const add = (key: string, handle: Handle, range: { start: number; end: number }): void => {
      const { start, end } = this.offsets(range);
      entries.set(`${key}@${String(start)}`, { handle, start, end });
    };
    const statement = (s: StatementHandle): void => {
      add(`s:${s.kind}`, s, this.trimmed(s.node));
      for (const v of s.valueHandles()) value(v);
      if (s instanceof SnippetLine) for (const p of s.parameterHandles) add("p", p, { start: p.token, end: p.token + 1 });
      for (const child of s.blockHandle?.handles ?? []) statement(child);
    };
    const value = (v: ValueHandle): void => {
      add(`v:${v.kind}`, v, typeof v.ref === "number" ? { start: v.ref, end: v.ref + 1 } : v.ref);
      for (const inner of v.innerHandles()) value(inner);
    };
    for (const s of this.block.handles) statement(s);
    return entries;
  }

  /** A node's range without trailing spaces and line breaks. */
  trimmed(node: Node): { start: number; end: number } {
    const { tokens } = this.parsed;
    let end = node.end;
    while (end > node.start + 1 && TRIVIA.has(tokens[end - 1]?.kind ?? "")) end--;
    return { start: node.start, end };
  }

  // --- Building the handle tree ---

  private build(reconcile: Reconcile): void {
    this.statementsByToken = new Map();
    this.valuesByToken = new Map();
    this.block.handles = this.buildBlock(this.parsed.root, undefined, [], reconcile);
  }

  private buildBlock(container: Node, owner: StatementHandle | undefined, claimed: readonly string[], reconcile: Reconcile): StatementHandle[] {
    const nodes = statementNodes(container);
    const shapes = blockShapes(this.parsed.tokens, nodes, this.host.extensionNames, claimed);
    return nodes.map((node, i) => this.buildStatement(node, shapes[i] as Shape, owner, reconcile));
  }

  private buildStatement(node: Node, shape: Shape, owner: StatementHandle | undefined, reconcile: Reconcile): StatementHandle {
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
    const values = (refs: readonly ValueRef[]): ValueHandle[] => refs.map((ref) => this.buildValue(ref, handle, undefined, "value", reconcile));
    const block = (claimed: readonly string[]): void => {
      if (anatomy?.block === undefined) {
        handle.blockHandle = undefined;
        return;
      }
      handle.blockHandle ??= new Block(this, handle);
      handle.blockHandle.handles = this.buildBlock(anatomy.block, handle, claimed, reconcile);
    };
    if (handle instanceof WrittenDirective || handle instanceof ExtensionLine) {
      handle.valueList = values(anatomy?.values ?? []);
      block([]);
    } else if (handle instanceof SetLine) {
      handle.valueList = values((anatomy?.values ?? []).slice(1));
      handle.blockHandle = undefined;
    } else if (handle instanceof UseLine) {
      handle.valueList = values((anatomy?.values ?? []).slice(1));
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
      case StatementKind.Directive:
        return new WrittenDirective(this);
      case StatementKind.Extension:
        return new ExtensionLine(this);
      case StatementKind.Set:
        return new SetLine(this);
      case StatementKind.Snippet:
        return new SnippetLine(this);
      case StatementKind.Use:
        return new UseLine(this);
      case StatementKind.Unreadable:
        return new UnreadableLine(this);
    }
  }

  private buildValue(ref: ValueRef, statement: StatementHandle, list: ListValue | undefined, role: ValueRole, reconcile: Reconcile): ValueHandle {
    const { tokens } = this.parsed;
    const index = typeof ref === "number" ? ref : ref.start;
    const kind = valueKindOf(tokens, ref);
    const start = tokens[index]?.span.start.offset ?? 0;
    const kept = reconcile.take(`v:${kind}`, start);
    const handle = kept instanceof ValueHandle ? kept : newValue(this, kind);
    if (kept === undefined) reconcile.created.push(handle);
    becomeKind(handle, kind);
    handle.ref = ref;
    handle.statementHandle = statement;
    handle.listHandle = list;
    handle.role = role;
    handle.detached = false;
    // A slice and its name start at the same token: the index keeps the slice (its name is `slice.name`).
    if (role !== "name") this.valuesByToken.set(index, handle);
    if (handle instanceof ListValue && typeof ref !== "number") {
      handle.itemHandles = itemsOf(tokens, ref).map((item) => this.buildValue(item, statement, handle, "value", reconcile));
    } else if ((handle instanceof SliceValue || handle instanceof IndexValue) && typeof ref !== "number") {
      handle.nameHandle = this.buildValue(ref.start, statement, undefined, "name", reconcile);
      const inner: number[] = [];
      for (let i = ref.start + 2; i < ref.end - 1; i++) inner.push(i);
      const tilde = inner.findIndex((i) => tokens[i]?.kind === TokenKind.TILDE);
      const boundAt = (i: number | undefined): ValueHandle | undefined => {
        if (i === undefined) return undefined;
        const kindOf = tokens[i]?.kind;
        return kindOf === TokenKind.INTEGER || kindOf === TokenKind.VARIABLE ? this.buildValue(i, statement, undefined, "bound", reconcile) : undefined;
      };
      if (handle instanceof IndexValue) {
        handle.indexHandle = boundAt(inner[0]);
      } else {
        handle.startHandle = tilde === 0 ? undefined : boundAt(inner[0]);
        handle.endHandle = tilde + 1 < inner.length ? boundAt(inner[tilde + 1]) : undefined;
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
  splice(start: number, end: number, insert: string | Insert, given: readonly Diagnostic[], keep?: Handle): Handle[] {
    if (given.length > 0) throw new BadTextError(given);
    const spliced = typeof insert === "string" ? insertOf(insert, [[0, insert.length]]) : insert;
    const text = this.current.slice(0, start) + spliced.text + this.current.slice(end);
    const syntax = parse(text);
    const rules = ruleProblems(syntax, this.host.extensionNames, start, spliced);
    if (rules.length > 0) throw new BadTextError(rules);
    const reconcile = new Reconcile(this.entries(), { start, end, inserted: spliced.text.length }, keep);
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
  replaceStatement(statement: StatementHandle, text: ConfigText): readonly Statement[] {
    const given = parseEntry(text, "statementsText").diagnostics;
    if (isBlank(text)) {
      if (given.length > 0) throw new BadTextError(given);
      this.removeStatement(statement);
      return [];
    }
    const { start, end } = this.offsets(this.ownedRange(statement.node));
    const insert = insertOf(text, this.reindent(text, this.indentationAt(start)));
    const owner = statement.parentHandle;
    const created = this.splice(start, end, insert, given);
    return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === owner) as Statement[];
  }

  /**
   * The given statements text with its common indentation removed, later lines prefixed with `indentation`, as
   * pieces of an insert (each line's text keeps its place in the given text, for 2.3's locations).
   */
  reindent(text: string, indentation: string): Piece[] {
    const lead = /^(?:[ \t]*\r?\n)+/u.exec(text)?.[0].length ?? 0;
    const rest = text.slice(lead);
    const body = rest.slice(0, rest.length - (/(?:\r?\n[ \t]*)+$/u.exec(rest)?.[0].length ?? 0));
    const lines: { readonly text: string; readonly at: number }[] = [];
    let from = 0;
    for (const match of body.matchAll(/\r?\n/gu)) {
      lines.push({ text: body.slice(from, match.index), at: lead + from });
      from = match.index + match[0].length;
    }
    lines.push({ text: body.slice(from), at: lead + from });
    const common = Math.min(...lines.filter((l) => l.text.trim() !== "").map((l) => /^[ \t]*/u.exec(l.text)?.[0].length ?? 0));
    const eol = this.lineBreak();
    const pieces: Piece[] = [];
    lines.forEach((line, i) => {
      if (i > 0) pieces.push(eol);
      if (i > 0 && line.text.trim() === "") return;
      if (i > 0) pieces.push(indentation);
      pieces.push([line.at + common, line.at + line.text.length]);
    });
    return pieces;
  }

  /**
   * `insertStatements` (2.4): the text's lines, common indentation removed, each prefixed with the siblings'
   * indentation (in an empty block: the parent's line indentation plus the document's unit), on lines of their own
   * before `statements[index]` (its owned comments stay with it), or after the last statement.
   */
  insertStatements(block: Block, index: number, text: ConfigText): readonly Statement[] {
    const given = parseEntry(text, "statementsText").diagnostics;
    if (isBlank(text)) {
      if (given.length > 0) throw new BadTextError(given);
      return [];
    }
    const eol = this.lineBreak();
    const items = block.handles;
    const lines = (indentation: string): Piece[] => [indentation, ...this.reindent(text, indentation)];
    let at: number;
    let insert: Piece[];
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
          insert = [...lines(indentation), eol];
        } else {
          // The target shares its line with an earlier statement: the new lines go between them.
          at = start;
          insert = [...this.reindent(text, indentation), eol, this.indentationAt(start)];
        }
      } else {
        const last = items[items.length - 1] as StatementHandle;
        at = this.offsets(this.ownedRange(last.node)).end;
        insert = [eol, ...lines(indentation)];
      }
    } else if (block.owner === undefined) {
      // An empty document: at its end, on lines of their own.
      at = this.current.length;
      const open = this.current === "" || this.current.endsWith("\n") ? "" : eol;
      insert = [open, ...lines(""), eol];
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
        const created = this.splice(open, close, insertOf(text, [eol, ...lines(indentation), eol, parentIndentation]), given);
        return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === block.owner) as Statement[];
      }
      // Only comments inside: the lines go before the `}` line.
      const lineStart = this.current.lastIndexOf("\n", close - 1) + 1;
      if (/^[ \t]*$/u.test(this.current.slice(lineStart, close))) {
        at = lineStart;
        insert = [...lines(indentation), eol];
      } else {
        at = close;
        insert = [eol, ...lines(indentation), eol, parentIndentation];
      }
    }
    const created = this.splice(at, at, insertOf(text, insert), given);
    return created.filter((h): h is StatementHandle => h instanceof StatementHandle && h.parentHandle === block.owner) as Statement[];
  }

  /** The document's indentation unit: the leading whitespace of its first indented line, else four spaces (D14). */
  private indentationUnit(): string {
    return /^([ \t]+)\S/mu.exec(this.current)?.[1] ?? "    ";
  }

  /**
   * `rename` of a directive: its name token. A bad name is a misuse error (spec 2.8: the `nameText` entry rule, and
   * nothing else: no directive name is reserved). The statement keeps its handle.
   */
  renameStatement(statement: WrittenDirective, name: string): void {
    checkDirectiveName(name);
    const token = this.parsed.tokens[statement.node.start];
    if (token === undefined) throw new Error("a statement without a name token");
    this.splice(token.span.start.offset, token.span.end.offset, name, [], statement);
  }

  /**
   * `SetVariable.rename` and `Parameter.rename`: its `$name` token only (2.3). A bad name is a misuse error (the one
   * variable name check); a second `set` of the name in its block is E5002, by the text-alone rules. The variable
   * keeps its handle.
   */
  renameVariable(token: number, name: string, keep: Handle): void {
    checkVariableName(name);
    const span = this.parsed.tokens[token]?.span;
    if (span === undefined) throw new Error("a variable without its token");
    this.splice(span.start.offset, span.end.offset, insertOf(name, ["$", [0, name.length]]), [], keep);
  }

  /**
   * `set` of a statement's values (2.4): first value to last; with none, after `after` (a token index). A text that
   * holds no value must be empty (spec 2.8, milestone 5): `set("")` clears the values, `set("# c\n")` is E2001 at 0:0.
   */
  replaceValues(statement: StatementHandle, values: readonly ValueHandle[], after: number, text: ConfigText): void {
    const syntax = parseEntry(text, "valuesText");
    const given = syntax.diagnostics;
    if (given.length === 0 && text !== "" && valuesOf(syntax.tokens, syntax.root).length === 0) {
      throw new BadTextError([at(text, 0, DiagnosticCode.UnexpectedToken)]);
    }
    const { tokens } = this.parsed;
    const first = values[0];
    const last = values.at(-1);
    if (first === undefined || last === undefined) {
      if (text === "") return;
      const offset = tokens[after]?.span.end.offset ?? 0;
      this.splice(offset, offset, insertOf(text, [" ", [0, text.length]]), given);
      return;
    }
    const start = this.valueOffsets(first).start;
    const end = this.valueOffsets(last).end;
    if (text === "") {
      let from = first.ref === undefined ? start : this.tokenIndexOf(first);
      while (tokens[from - 1]?.kind === TokenKind.SPACE) from--;
      this.splice(tokens[from]?.span.start.offset ?? start, end, "", given);
      return;
    }
    void statement;
    this.splice(start, end, text, given);
  }

  /**
   * A value's `set` (spec 6.1, 6.6): exactly one value (`valueText`; a bound `boundText`, a slice's name
   * `sliceNameText`), in place of this one, keeping its handle, which takes the new value's kind.
   */
  setValue(value: ValueHandle, text: ConfigText): void {
    const rule = value.role === "bound" ? "boundText" : value.role === "name" ? "sliceNameText" : "valueText";
    const given = parseEntry(text, rule).diagnostics;
    const { start, end } = this.valueOffsets(value);
    this.splice(start, end, text, given, value);
  }

  /**
   * `replaceWithText` of a value, checked with the grammar's entry rule for where it stands (spec 2.8): `boundText`
   * for a slice bound, `itemsText` for a list item, else `valuesText`.
   */
  replaceValue(value: ValueHandle, text: ConfigText): readonly WrittenValue[] {
    const rule = value.role === "bound" ? "boundText" : value.role === "name" ? "sliceNameText" : value.listHandle !== undefined ? "itemsText" : "valuesText";
    const given = parseEntry(text, rule).diagnostics;
    if (value.role !== "value" && given.length > 0) throw new BadTextError(given);
    if (isBlank(text)) {
      if (given.length > 0) throw new BadTextError(given);
      this.removeValue(value);
      return [];
    }
    const { start, end } = this.valueOffsets(value);
    const container = value.listHandle;
    const statement = value.statementHandle;
    const created = this.splice(start, end, text, given);
    return created.filter(
      (h): h is ValueHandle =>
        h instanceof ValueHandle && h.listHandle === container && h.statementHandle === statement && h.role === value.role,
    ) as WrittenValue[];
  }

  /**
   * `remove()` of a value (2.4): with the space before it. In a list, the item and its comma only (the one after it,
   * else the one before it); comments and line breaks between them stay, and a line left empty goes (D-F1-3).
   */
  removeValue(value: ValueHandle): void {
    const { tokens } = this.parsed;
    if (value.role === "name" || (value.role === "bound" && this.isOnlyBound(value))) {
      throw new MisuseError("remove(): a slice's or index's name, and its only bound, cannot be removed: set it, or remove the slice");
    }
    const { start, end } = this.valueOffsets(value);
    if (value.listHandle !== undefined) {
      const skipped: ReadonlySet<string> = new Set([TokenKind.SPACE, TokenKind.NEWLINE, TokenKind.COMMENT]);
      const ref = value.ref;
      const first = typeof ref === "number" ? ref : ref.start;
      const last = typeof ref === "number" ? ref : ref.end - 1;
      let after = last + 1;
      while (skipped.has(tokens[after]?.kind ?? "")) after++;
      if (tokens[after]?.kind === TokenKind.COMMA) {
        const commaEnd = tokens[after]?.span.end.offset ?? end;
        const between = this.current.slice(end, tokens[after]?.span.start.offset ?? end);
        if (/^[ \t]*$/u.test(between)) {
          const [from, to] = this.removalRange(start, commaEnd);
          this.splice(from, to, "", []);
        } else {
          this.splice(start, commaEnd, between.replace(/^[ \t]+/u, ""), []);
        }
        return;
      }
      let before = first - 1;
      while (skipped.has(tokens[before]?.kind ?? "")) before--;
      if (tokens[before]?.kind === TokenKind.COMMA) {
        const commaStart = tokens[before]?.span.start.offset ?? start;
        const between = this.current.slice(tokens[before]?.span.end.offset ?? start, start);
        this.splice(commaStart, end, /^[ \t]*$/u.test(between) ? "" : between.replace(/[ \t]+$/u, ""), []);
        return;
      }
      this.splice(start, end, "", []);
      return;
    }
    let from = this.tokenIndexOf(value);
    while (tokens[from - 1]?.kind === TokenKind.SPACE) from--;
    this.splice(tokens[from]?.span.start.offset ?? start, end, "", []);
  }

  /** Whether a bound is its slice's or index's only one (`b[1]`, `x[0~]`): removing it leaves no bound (spec 6.6). */
  private isOnlyBound(bound: ValueHandle): boolean {
    const { tokens } = this.parsed;
    let open = this.tokenIndexOf(bound);
    while (open > 0 && tokens[open]?.kind !== TokenKind.LBRACK) open--;
    let bounds = 0;
    for (let i = open + 1; i < tokens.length && tokens[i]?.kind !== TokenKind.RBRACK; i++) {
      const kind = tokens[i]?.kind;
      if (kind === TokenKind.INTEGER || kind === TokenKind.VARIABLE) bounds++;
    }
    return bounds <= 1;
  }

  private tokenIndexOf(value: ValueHandle): number {
    return typeof value.ref === "number" ? value.ref : value.ref.start;
  }

  valueOffsets(value: ValueHandle): { start: number; end: number } {
    const ref = value.ref;
    return this.offsets(typeof ref === "number" ? { start: ref, end: ref + 1 } : ref);
  }

  // --- Declarations by where written (2.6) ---

  /**
   * The variable a reference binds to by where it is written; undefined when free. Nearest first, as the binding
   * picks (2.5): block by block outward, the `set` lines above in that block, then the parameters of the snippet
   * whose body it is (D-F1-8).
   */
  declarationOf(reference: Reference): SetVariable | Parameter | undefined {
    const name = reference.name;
    for (let s: StatementHandle | undefined = reference.statementHandle; s !== undefined; s = s.parentHandle) {
      const parent = s.parentHandle;
      const items = (parent?.blockHandle ?? this.block).handles;
      for (let i = items.indexOf(s) - 1; i >= 0; i--) {
        const candidate = items[i];
        if (candidate instanceof SetLine && candidate.variableHandle.name === name) return candidate.variableHandle;
      }
      if (parent instanceof SnippetLine) {
        const parameter = parent.parameterHandles.find((p) => p.name === name);
        if (parameter !== undefined) return parameter;
      }
    }
    return undefined;
  }

  /** The nearest statement above `statement` in its block or an enclosing block that matches. */
  above(statement: StatementHandle, match: (s: StatementHandle) => boolean): StatementHandle | undefined {
    for (let s: StatementHandle | undefined = statement; s !== undefined; s = s.parentHandle) {
      const block = s.parentHandle?.blockHandle ?? this.block;
      const items = block.handles;
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
      for (const child of s.blockHandle?.handles ?? []) statement(child);
    };
    for (const s of this.block.handles) statement(s);
    return out;
  }

  /** Every `set` and snippet line's variables, in text order. */
  variables(): (SetVariable | Parameter)[] {
    const out: (SetVariable | Parameter)[] = [];
    const statement = (s: StatementHandle): void => {
      if (s instanceof SetLine) out.push(s.variableHandle);
      if (s instanceof SnippetLine) out.push(...s.parameterHandles);
      for (const child of s.blockHandle?.handles ?? []) statement(child);
    };
    for (const s of this.block.handles) statement(s);
    return out;
  }
}

function valueKindOf(tokens: readonly Token[], ref: ValueRef): WrittenValue["kind"] {
  if (typeof ref !== "number") {
    if (ref.kind === NodeKind.List) return ValueKind.List;
    for (let i = ref.start + 2; i < ref.end - 1; i++) if (tokens[i]?.kind === TokenKind.TILDE) return ValueKind.Slice;
    return ref.end - ref.start > 3 ? ValueKind.Index : ValueKind.Slice;
  }
  switch (tokens[ref]?.kind) {
    case TokenKind.STRING:
      return ValueKind.String;
    case TokenKind.VARIABLE:
      return ValueKind.Reference;
    default:
      return ValueKind.Word;
  }
}

/** The position of `offset` in `text` (0-based line and UTF-16 column). */
export function positionIn(text: string, offset: number): SourcePosition {
  const at = Math.max(0, Math.min(offset, text.length));
  const before = text.slice(0, at);
  const line = before.split("\n").length - 1;
  return { offset: at, line, column: at - (before.lastIndexOf("\n") + 1) };
}

function at(given: string, offset: number, code: DiagnosticCode): Diagnostic {
  const position = positionIn(given, offset);
  return makeDiagnostic(code, describe(code).message, { start: position, end: position });
}

/** A piece of an insert: text the edit adds, or the range [from, to) of the caller's text it copies. */
type Piece = string | readonly [number, number];

/** What an edit splices in: its text, the caller's text, and for each UTF-16 unit its offset there (-1: added). */
interface Insert {
  readonly text: string;
  readonly given: string;
  readonly origin: readonly number[];
}

function insertOf(given: string, pieces: readonly Piece[]): Insert {
  let text = "";
  const origin: number[] = [];
  for (const piece of pieces) {
    if (typeof piece === "string") {
      text += piece;
      for (let i = 0; i < piece.length; i++) origin.push(-1);
    } else {
      text += given.slice(piece[0], piece[1]);
      for (let i = piece[0]; i < piece[1]; i++) origin.push(i);
    }
  }
  return { text, given, origin };
}

/**
 * The text-alone rules (E5002, E5005, E5009-E5011) a spliced text would break, on the statements the splice
 * touches (a `set` claiming a name of a snippet parameter the splice touches counts too): located in the caller's
 * text when the problem lies in what it gave (2.3), else at 0:0.
 */
function ruleProblems(syntax: Syntax, extensions: ReadonlySet<string>, from: number, insert: Insert): Diagnostic[] {
  const out: Diagnostic[] = [];
  const { tokens } = syntax;
  const to = from + insert.text.length;
  const overlaps = (s: number, e: number): boolean => (from === to ? s < from && e > from : s < to && e > from);
  const touches = (node: Node): boolean => {
    const span = spanOf(syntax, node);
    return overlaps(span.start.offset, span.end.offset);
  };
  const report = (fault: { code: DiagnosticCode; span: SourceSpan }): void => {
    const offset = fault.span.start.offset;
    const origin = offset >= from && offset < to ? (insert.origin[offset - from] ?? -1) : -1;
    out.push(at(insert.given, Math.max(origin, 0), fault.code));
  };
  const visit = (container: Node, claimed: readonly string[], touchedClaims: ReadonlySet<string>): void => {
    const nodes = statementNodes(container);
    const shapes = blockShapes(tokens, nodes, extensions, claimed);
    nodes.forEach((node, i) => {
      const shape = shapes[i] as Shape;
      if (shape.fault !== undefined && isTextAlone(shape.fault)) {
        const code = shape.fault.code;
        let involved = touches(node);
        if (!involved && (code === DiagnosticCode.VariableSetTwice || code === DiagnosticCode.SnippetDefinedTwice)) {
          const name = shape.fault.detail?.replace(/^\$/u, "") ?? "";
          involved =
            (code === DiagnosticCode.VariableSetTwice && touchedClaims.has(name)) ||
            nodes.slice(0, i).some((other, j) => touches(other) && (shapes[j] as Shape).claims === name);
        }
        if (involved) report(shape.fault);
      }
      if (node.kind !== NodeKind.Directive) return;
      const { block } = anatomyOf(tokens, node);
      if (block === undefined || shape.kind === StatementKind.Unreadable) return;
      const params = shape.kind === StatementKind.Snippet ? parameterTokens(tokens, node) : [];
      const names = params.map((t) => tokens[t]?.text.slice(1) ?? "");
      const touched = new Set(
        params.flatMap((t) => {
          const span = tokens[t]?.span;
          return span !== undefined && overlaps(span.start.offset, span.end.offset) ? [tokens[t]?.text.slice(1) ?? ""] : [];
        }),
      );
      visit(block, names, touched);
    });
  };
  visit(syntax.root, [], new Set());
  return out;
}

/** Throw DetachedError for a handle whose tokens are gone. */
export function detached(what: string): DetachedError {
  return new DetachedError(`this ${what} was removed by an edit or its document's text was replaced`);
}
