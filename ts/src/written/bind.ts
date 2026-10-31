/**
 * The binding (design rule 3; slices.md S1 "Internal contract: the binding"): one derivation of the graph's
 * current texts, overrides and read ledger. It walks the copies (the root, then each include and `use`
 * spliced in place), decides per copy what each `$name` and `use` reads, and expands written values for the
 * extension lines (an include's path) and for the expansion. It is the one home of the name-lookup rule, which
 * spec/expansion.md states: `graph.expand()` walks `items` and calls `valuesAt`, and never looks a name up.
 * Package-internal; pure (no I/O). It names nothing of the rendered layer (spec 5, "Layer direction").
 *
 * The walk is PR 3's `Expander` (cb08803) moved here, unchanged in what it decides and reports (rules 1-12 of
 * round 11's slices.md §1.2), with the read ledger in place of reading files during the walk.
 */

import { anatomyOf, type DirectiveAnatomy, itemsOf, valuesOf } from "../anatomy.js";
import { MAX_DEPTH, MAX_DIRECTIVES, MAX_EXPANDED_NESTING } from "../gen/api/limits.js";
import { hasGlob } from "../graph/glob.js";
import { compareCodePoints } from "../graph/order.js";
import { makeOverride, makePlace, makeStep } from "../origin.js";
import { makeLocated } from "../report.js";
import { spanOf, type ValueRef } from "../syntax/cst.js";
import { parseEntry } from "../syntax/parse.js";
import { isWordKind } from "../syntax/tokens.js";
import { typeNameOf } from "../text.js";
import { decodeString, integerOf } from "../values.js";
import type { Document } from "./document.js";
import { shapeOfAnatomy } from "./shape.js";
import { SetLine, SnippetLine, type StatementHandle } from "./statements.js";
import { ExpandedRecord } from "./value.js";
import { DiagnosticCode, describe } from "../gen/api/codes.js";
import { DiagnosticError } from "../gen/api/errors.js";
import { NodeKind, PlaceKind, StatementKind, statementOfKeyword, StepKind, TokenKind, UnreadableReason, ValueKind } from "../gen/api/kinds.js";
import type { LocatedDiagnostic, Override, Place, SourceSpan, Step } from "../gen/api/shared.js";
import type { Node, Syntax, Token } from "../gen/api/syntax.js";
import type { Copy, DocumentEdge, Extension, Reference, ReferenceResolution, Resolution, Statement, UseLine, Variable, WrittenValue } from "../gen/api/written.js";
import type * as api from "../gen/api/written.js";

/** What one container (the root's top level, or a directive's block) holds at one copy, in walk order. */
export type BoundItem = BoundDirective | BoundUnreadable;

/** One copy of a directive statement (kind "directive"), with its block's items at that copy. */
export interface BoundDirective {
  readonly tag: "directive";
  readonly copy: Copy;
  /** Undefined when written without a block. */
  readonly children: readonly BoundItem[] | undefined;
}

/**
 * One copy of a statement that cannot be read there: a syntax error, a malformed or repeated `set`/`snippet`/`use`,
 * an unknown snippet or wrong arity, an include that failed, a cycle, too deep, too many directives.
 */
export interface BoundUnreadable {
  readonly tag: "unreadable";
  readonly copy: Copy;
  readonly reason: UnreadableReason;
  /** Undefined when the problem is already one of a document's syntax diagnostics. */
  readonly diagnostic: LocatedDiagnostic | undefined;
}

/** A written value that cannot be expanded at a copy (E5001, E4001): the statement is unreadable there. */
export class BindingProblem extends Error {
  constructor(
    readonly reason: UnreadableReason,
    readonly diagnostic: LocatedDiagnostic,
  ) {
    super(diagnostic.message);
    this.name = "BindingProblem";
  }
}

/** Which files were read: the one piece of state besides the texts (design rule 1). */
export interface ReadLedger {
  /** The paths `spec` resolved to from `parentPath`, the Error the source rejected with, or undefined: not resolved yet. */
  resolved(parentPath: string, spec: string): readonly string[] | Error | undefined;
  /** The document read at `resolvedPath`, the Error its read rejected with, or undefined: not read yet. */
  readOf(resolvedPath: string): api.Document | Error | undefined;
}

/**
 * An override's values, read from its checked text. `problem` is the E4001 detail of a literal bound beyond the
 * integer range, which the grammar cannot see: the check of an override accepts it (spec 6.3), and each `$name` it
 * reaches is unreadable.
 */
export interface OverrideValues {
  readonly values: readonly ExpandedRecord[];
  readonly problem?: string;
}

/** An override: its variable handle and its values, already read and checked (override.ts). */
export interface OverrideInput extends OverrideValues {
  readonly variable: Variable;
}

/** The inputs of one derivation. */
export interface BindingInput {
  readonly root: api.Document;
  readonly extensions: ReadonlyMap<string, Extension>;
  readonly overrides: ReadonlyMap<string, OverrideInput>;
  readonly reads: ReadLedger;
}

/** One derivation. Immutable; the graph makes a new one after any edit, `setOverride` or read. */
export interface Binding {
  /** The root document's top level at the root copy, includes and uses spliced in place. */
  readonly items: readonly BoundItem[];
  /** Every copy of every extension line, in walk order (a failed or unread one included). */
  readonly edges: readonly DocumentEdge[];
  /** The edges with a spec not resolved, or a target not read, in the ledger. */
  readonly unread: readonly DocumentEdge[];
  /** Every diagnostic the walk found, in walk order, render's codes included (the graph filters them). */
  readonly diagnostics: readonly LocatedDiagnostic[];
  /** Every copy of `statement`, in walk order. */
  copiesOf(statement: Statement): readonly Copy[];
  /** One per copy of the reference's statement, in walk order. */
  resolutionsOf(reference: Reference): readonly ReferenceResolution[];
  /** Every resolution, in walk order: what `Variable.wins()` and `shadowedAt()` filter. */
  resolutions(): readonly ReferenceResolution[];
  /** One per copy of the `use` line, in walk order. */
  snippetsOf(use: UseLine): readonly Resolution<api.SnippetLine>[];
  /** The edges whose `targets` include `resolvedPath`. */
  edgesInto(resolvedPath: string): readonly DocumentEdge[];
  /**
   * One written value at one copy of its statement, expanded with PR 3's origins: a `$name` becomes all its winner's
   * values (each with the variable step, then the copy's steps); a list's items expand the same way. The same
   * objects at every call of one derivation.
   * @throws BindingProblem E5001 (nothing visible), E4001 (slice bound)
   */
  valuesAt(value: WrittenValue, copy: Copy): readonly ExpandedRecord[];
}

/** What an unread edge still needs from the source: specs to resolve, or paths to read. */
export type ReadNeed =
  | { readonly tag: "resolve"; readonly parentPath: string; readonly specs: readonly string[] }
  | { readonly tag: "read"; readonly paths: readonly string[] };

/** The binding, plus what the read loop needs to know about each unread edge (read.ts). */
export interface BindingWithNeeds extends Binding {
  needOf(edge: DocumentEdge): ReadNeed | undefined;
}

/** Derive the binding of these inputs. Pure and synchronous. */
export function bind(input: BindingInput): BindingWithNeeds {
  return new Walk(input).run();
}

/** No extension names: the binding asks shape.ts only about `set`, `snippet` and `use` lines. */
const NO_EXTENSIONS: ReadonlySet<string> = new Set();

/**
 * An override's values, from its text parsed with the `valuesText` entry rule. Call only with text the check of an
 * override accepted (override.ts): values without a `$name`.
 */
export function readOverride(name: string, syntax: Syntax): OverrideValues {
  const overrideText: Text = {
    doc: undefined,
    syntax,
    resolvedPath: "",
    written: () => makeOverride(name),
    place: (span) => makePlace("", span),
  };
  const walk = new Walk(undefined);
  try {
    return { values: valuesOf(syntax.tokens, syntax.root).flatMap((ref) => walk.value(overrideText, ref, new Scope(undefined), [], undefined)) };
  } catch (error) {
    if (!(error instanceof Problem) || error.diagnostic === undefined) throw error;
    return { values: [], problem: error.diagnostic.message };
  }
}

/** The package's document behind an api.Document. @throws TypeError for a document this package did not make. */
export function asDocument(doc: api.Document): Document {
  const internal = doc as Partial<Document>;
  if (typeof internal.statementOf !== "function") throw new TypeError("not a document of this package");
  return doc as Document;
}

// --- The walk ---

/** One text being walked: a document, or an override's text. */
interface Text {
  readonly doc: Document | undefined;
  readonly syntax: Syntax;
  readonly resolvedPath: string;
  written(span: SourceSpan): Place | Override;
  place(span: SourceSpan): Place;
}

function documentText(doc: Document): Text {
  const place = (span: SourceSpan): Place => makePlace(doc.resolvedPath, span);
  return { doc, syntax: doc.syntax, resolvedPath: doc.resolvedPath, written: place, place };
}

/**
 * A statement that cannot be read: thrown inside a statement, caught where the statement is kept unreadable.
 * `diagnostic` is undefined when the problem is already reported (a syntax error inside an extension's block).
 */
class Problem extends Error {
  constructor(
    readonly reason: UnreadableReason,
    readonly diagnostic: LocatedDiagnostic | undefined,
  ) {
    super(diagnostic?.message ?? reason);
    this.name = "Problem";
  }
}

/** A problem with one of a directive's values: the directive is unreadable at that copy, and valuesAt throws it. */
class ValueProblem extends Problem {}

/**
 * One definition of a name: its variable, the values a reader gets (stored without the definer's steps), as written;
 * `problem` for an override whose values cannot be read (OverrideValues).
 */
interface Definition {
  readonly variable: Variable;
  readonly values: readonly ExpandedRecord[];
  readonly written: readonly WrittenValue[];
  readonly problem?: string;
}

/** One definition visible at a place, by how PR 3's lookup treats it. */
interface Entry {
  /** A snippet parameter, a `set`, or an include block's `set` (it wins over every `set` of the spliced files). */
  readonly tag: "parameter" | "set" | "forced";
  readonly definition: Definition;
}

/** A snippet definition: its parameters, its body and the scope of the block it was written in (lexical, rule 6). */
interface Snippet {
  readonly name: string;
  readonly params: readonly string[];
  readonly block: Node;
  readonly text: Text;
  readonly scope: ScopeView;
  readonly line: SnippetLine;
}

/** What a place can see: variables and snippets. */
interface ScopeView {
  /** Every definition of `name` visible here, innermost first (PR 3's `Scope.lookup` chain, F1-01). */
  entries(name: string, out: Entry[]): void;
  /** Every snippet of `name` visible here, innermost first. */
  snippets(name: string, out: Snippet[]): void;
}

/** A block's scope: it claims names for the one-per-block checks and binds them. */
interface BlockScope extends ScopeView {
  claim(name: string): boolean;
  bind(name: string, definition: Definition): void;
  define(snippet: Snippet): boolean;
}

/** The variables and snippets of one block: its own lines so far, then the enclosing view's. */
class Scope implements BlockScope {
  private readonly vars = new Map<string, Definition>();
  private readonly params = new Map<string, Definition>();
  private readonly claimed = new Set<string>();
  private readonly defined = new Map<string, Snippet>();

  constructor(private readonly outer: ScopeView | undefined) {}

  entries(name: string, out: Entry[]): void {
    const param = this.params.get(name);
    if (param !== undefined) out.push({ tag: "parameter", definition: param });
    const set = this.vars.get(name);
    if (set !== undefined) out.push({ tag: "set", definition: set });
    this.outer?.entries(name, out);
  }

  snippets(name: string, out: Snippet[]): void {
    const snippet = this.defined.get(name);
    if (snippet !== undefined) out.push(snippet);
    this.outer?.snippets(name, out);
  }

  claim(name: string): boolean {
    if (this.claimed.has(name)) return false;
    this.claimed.add(name);
    return true;
  }

  bind(name: string, definition: Definition): void {
    this.vars.set(name, definition);
  }

  /** Bind a snippet parameter: the body block's own binding of that name (S3-03). */
  param(name: string, definition: Definition): void {
    this.claimed.add(name);
    this.params.set(name, definition);
  }

  define(snippet: Snippet): boolean {
    if (this.defined.has(snippet.name)) return false;
    this.defined.set(snippet.name, snippet);
    return true;
  }

  /** The variables this block bound itself (an extension block's `set` lines). */
  own(): ReadonlyMap<string, Definition> {
    return this.vars;
  }
}

/**
 * The including block's scope as a spliced file sees it: the file's top-level `set` and `snippet` lines claim, bind
 * and define in the including block (L2), and inside the spliced files the extension block's `set` lines win over
 * every `set` of the files, at any depth, but not over a parameter (rule 8, F1-01).
 */
class SpliceScope implements BlockScope {
  constructor(
    private readonly target: BlockScope,
    private readonly overrides: ReadonlyMap<string, Definition>,
  ) {}

  entries(name: string, out: Entry[]): void {
    const forced = this.overrides.get(name);
    if (forced !== undefined) out.push({ tag: "forced", definition: forced });
    this.target.entries(name, out);
  }

  snippets(name: string, out: Snippet[]): void {
    this.target.snippets(name, out);
  }

  claim(name: string): boolean {
    return this.target.claim(name);
  }

  bind(name: string, definition: Definition): void {
    this.target.bind(name, definition);
  }

  define(snippet: Snippet): boolean {
    return this.target.define(snippet);
  }
}

/**
 * The winner among `entries` (innermost first) and an override: the precedence table of spec/expansion.md, the one
 * home of the rule (this is its code, not its statement).
 */
function pick(entries: readonly Entry[], override: Definition | undefined): Definition | undefined {
  let found: Entry | undefined;
  for (const entry of entries) {
    if (entry.tag === "parameter" && found === undefined) return entry.definition;
    if (entry.tag === "set" && found === undefined) found = entry;
    if (entry.tag === "forced") {
      found = entry;
      break;
    }
  }
  return override ?? found?.definition;
}

/** Every visible definition in the order the rule picks them, each as if those before it were removed (next first). */
function ordered(entries: readonly Entry[], override: Definition | undefined): Definition[] {
  const out: Definition[] = [];
  let left = [...entries];
  let given = override;
  for (;;) {
    const next = pick(left, given);
    if (next === undefined) return out;
    out.push(next);
    if (next === given) given = undefined;
    else left = left.filter((entry) => entry.definition !== next);
  }
}

/** One place statements are walked into. */
interface PlaceContext {
  readonly text: Text;
  readonly scope: BlockScope;
  /** The steps that brought this text here, innermost first. */
  readonly via: readonly Step[];
  /** The snippets and files being walked around this place, outermost first; the root file is the first. */
  readonly open: readonly (Snippet | string)[];
  readonly into: BoundItem[];
  /**
   * The expanded blocks around this place (spec 2.5): a directive's block is one more; a snippet's body and a spliced
   * file's top level stand where their line does.
   */
  readonly nesting: number;
}

/** A block or a document's top level to walk, into a place. */
type Opened = readonly [Node, PlaceContext];

/**
 * How many lists deep the deepest of `values` goes (spec 2.5: a list is one level, a word none). A loop, not a
 * recursion: a value may hold lists up to MAX_EXPANDED_NESTING deep.
 */
function nestingOf(values: Iterable<ExpandedRecord>): number {
  let deepest = 0;
  const stack: [ExpandedRecord, number][] = [];
  for (const value of values) stack.push([value, 1]);
  for (let top = stack.pop(); top !== undefined; top = stack.pop()) {
    const [value, level] = top;
    if (value.items === undefined) continue;
    deepest = Math.max(deepest, level);
    for (const item of value.items) stack.push([item, level + 1]);
  }
  return deepest;
}

class Walk implements BindingWithNeeds {
  readonly items: BoundItem[] = [];
  readonly edges: DocumentEdge[] = [];
  readonly unread: DocumentEdge[] = [];
  readonly diagnostics: LocatedDiagnostic[] = [];
  private readonly needs = new Map<DocumentEdge, ReadNeed>();
  private readonly copies = new Map<Statement, Copy[]>();
  private readonly byReference = new Map<Reference, ReferenceResolution[]>();
  private readonly allResolutions: ReferenceResolution[] = [];
  private readonly byUse = new Map<UseLine, Resolution<api.SnippetLine>[]>();
  private readonly expanded = new Map<Copy, Map<WrittenValue, readonly ExpandedRecord[]> | BindingProblem>();
  private readonly overrides: ReadonlyMap<string, Definition>;
  private count = 0;
  private stopped = false;

  constructor(private readonly input: BindingInput | undefined) {
    const overrides = new Map<string, Definition>();
    for (const [name, o] of input?.overrides ?? []) {
      overrides.set(name, { variable: o.variable, values: o.values, written: [], ...(o.problem === undefined ? {} : { problem: o.problem }) });
    }
    this.overrides = overrides;
  }

  run(): this {
    const input = this.input;
    if (input === undefined) throw new Error("no input");
    const root = asDocument(input.root);
    const top = { text: documentText(root), scope: new Scope(undefined), via: [], open: [root.resolvedPath], into: this.items, nesting: 0 };
    this.walk([root.syntax.root, top]);
    return this;
  }

  // --- Binding ---

  needOf(edge: DocumentEdge): ReadNeed | undefined {
    return this.needs.get(edge);
  }

  copiesOf(statement: Statement): readonly Copy[] {
    return this.copies.get(statement) ?? [];
  }

  resolutionsOf(reference: Reference): readonly ReferenceResolution[] {
    return this.byReference.get(reference) ?? [];
  }

  resolutions(): readonly ReferenceResolution[] {
    return this.allResolutions;
  }

  snippetsOf(use: UseLine): readonly Resolution<api.SnippetLine>[] {
    return this.byUse.get(use) ?? [];
  }

  edgesInto(resolvedPath: string): readonly DocumentEdge[] {
    return this.edges.filter((edge) => edge.targets.includes(resolvedPath));
  }

  valuesAt(value: WrittenValue, copy: Copy): readonly ExpandedRecord[] {
    const found = this.expanded.get(copy);
    if (found instanceof BindingProblem) throw found;
    const values = found?.get(value);
    if (values === undefined) throw new Error("valuesAt: the value is not read at that copy");
    return values;
  }

  // --- The walk (PR 3's Expander) ---

  private copyOf(statement: StatementHandle, via: readonly Step[]): Copy {
    const copy: Copy = { statement: statement as unknown as Statement, via };
    const list = this.copies.get(copy.statement);
    if (list === undefined) this.copies.set(copy.statement, [copy]);
    else list.push(copy);
    return copy;
  }

  /**
   * Walk statements depth first in written order (spec/expansion.md 2). A loop over a stack of open blocks, not a
   * recursion: expansion nests blocks deeper than any one text (up to MAX_EXPANDED_NESTING, E5013), and a statement's
   * own work is done before the blocks it opens are walked, so the stack keeps the order.
   */
  private walk(start: Opened): void {
    const stack: [Iterator<Node>, PlaceContext][] = [[start[0].children[Symbol.iterator](), start[1]]];
    while (!this.stopped) {
      const top = stack.at(-1);
      if (top === undefined) return;
      const next = top[0].next();
      if (next.done === true) {
        stack.pop();
        continue;
      }
      const opened = this.item(next.value, top[1]);
      for (let i = opened.length - 1; i >= 0; i--) {
        const [block, context] = opened[i] as Opened;
        stack.push([block.children[Symbol.iterator](), context]);
      }
    }
  }

  /** One statement of a walked block, kept readable or unreadable; the blocks it opens, in walk order. */
  private item(node: Node, context: PlaceContext): readonly Opened[] {
    const doc = context.text.doc;
    if (doc === undefined) throw new Error("an override's text has no statements");
    if (node.kind !== NodeKind.Directive && node.kind !== NodeKind.Error) return [];
    const copy = this.copyOf(doc.statementOf(node), context.via);
    if (node.kind === NodeKind.Error) {
      context.into.push({ tag: "unreadable", copy, reason: UnreadableReason.Syntax, diagnostic: undefined });
      return [];
    }
    try {
      return this.statement(node, copy, context);
    } catch (error) {
      if (!(error instanceof Problem)) throw error;
      if (error.diagnostic !== undefined) this.diagnostics.push(error.diagnostic);
      if (error instanceof ValueProblem && error.diagnostic !== undefined) {
        this.expanded.set(copy, new BindingProblem(error.reason, error.diagnostic));
      }
      context.into.push({ tag: "unreadable", copy, reason: error.reason, diagnostic: error.diagnostic });
      return [];
    }
  }

  /**
   * One directive node. Its head's token kind decides (spec 2.5): an `@` statement does its work (`@set`, `@snippet`,
   * `@use`, an extension's `@name`; any other `@name` is E3008); a WORD head is a directive, and its block is walked.
   * Returns the blocks it opens.
   */
  private statement(node: Node, copy: Copy, context: PlaceContext): readonly Opened[] {
    const { tokens } = context.text.syntax;
    const anatomy = anatomyOf(tokens, node);
    const name = tokens[anatomy.name];
    if (name === undefined) throw new Error("a directive node has no name token");
    if (name.kind === TokenKind.AT_WORD) {
      switch (statementOfKeyword(name.text.slice(1))) {
        case StatementKind.Set:
          this.set(anatomy, copy, context.text, context.scope, context.via, context.nesting);
          return [];
        case StatementKind.Snippet:
          this.snippet(anatomy, copy, context);
          return [];
        case StatementKind.Use:
          return this.use(anatomy, name, copy, context);
        default:
          break;
      }
      const extension = this.input?.extensions.get(name.text.slice(1));
      if (extension !== undefined) return this.extension(extension, anatomy, name, copy, context);
      throw this.problem(DiagnosticCode.UnknownExtension, context.text, name.span, context.via, name.text);
    }

    const { text, scope, via } = context;
    const statement = copy.statement as unknown as StatementHandle;
    const values = new Map<WrittenValue, readonly ExpandedRecord[]>();
    for (const value of statement.valueList) {
      try {
        values.set(value as unknown as WrittenValue, this.value(text, value.ref, scope, via, copy));
      } catch (error) {
        if (error instanceof Problem && !(error instanceof ValueProblem)) throw new ValueProblem(error.reason, error.diagnostic);
        throw error;
      }
    }
    this.checkNesting(context.nesting, anatomy.block !== undefined, [...values.values()].flat(), text, name, via);
    this.expanded.set(copy, values);
    if (++this.count > MAX_DIRECTIVES) {
      this.stopped = true;
      throw this.problem(DiagnosticCode.TooManyDirectives, text, name.span, via, `more than ${String(MAX_DIRECTIVES)}`);
    }
    const children: BoundItem[] | undefined = anatomy.block === undefined ? undefined : [];
    context.into.push({ tag: "directive", copy, children });
    if (anatomy.block === undefined || children === undefined) return [];
    return [[anatomy.block, { text, scope: new Scope(scope), via, open: context.open, into: children, nesting: context.nesting + 1 }]];
  }

  /** A `set`, `snippet` or `use` line's text-alone shape (shape.ts, the one home of those rules), or its problem. */
  private wellFormed(anatomy: DirectiveAnatomy, text: Text, via: readonly Step[]): void {
    const { fault } = shapeOfAnatomy(text.syntax.tokens, anatomy, NO_EXTENSIONS);
    if (fault !== undefined) throw this.problem(fault.code, text, fault.span, via);
  }

  /**
   * `@set $name value...;` (rule 2): binds from this line to the end of the enclosing block. `nesting`: the expanded
   * blocks around the line, for E5013.
   */
  private set(anatomy: DirectiveAnatomy, copy: Copy, text: Text, scope: BlockScope, via: readonly Step[], nesting: number): void {
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...values] = anatomy.values;
    const variable = tokens[first as number] as Token;
    const variableName = variable.text.slice(1);
    if (!scope.claim(variableName)) {
      throw this.problem(DiagnosticCode.VariableSetTwice, text, variable.span, via, variable.text);
    }
    const line = copy.statement as unknown as StatementHandle;
    if (!(line instanceof SetLine)) throw new Error("a set line that claims its name is kind set");
    const bound = values.flatMap((ref) => this.value(text, ref, scope, via, copy));
    this.checkNesting(nesting, false, bound, text, tokens[anatomy.name] as Token, via);
    // Stored without this line's own steps; a reader adds the variable step and its own (ExpandedRecord.rebase).
    scope.bind(variableName, {
      variable: line.variableHandle,
      values: bound.map((value) => ExpandedRecord.rebase(value, via.length, [])),
      written: line.valueList as unknown as WrittenValue[],
    });
  }

  /** `@snippet name $param... { body }` (rule 5): visible from this line to the end of its block. */
  private snippet(anatomy: DirectiveAnatomy, copy: Copy, context: PlaceContext): void {
    const { text, scope, via } = context;
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...rest] = anatomy.values;
    const name = tokens[first as number] as Token;
    const params = rest.map((ref) => (tokens[ref as number] as Token).text.slice(1));
    if (anatomy.block === undefined) throw new Error("a well-formed snippet has a block");
    const line = copy.statement as unknown as StatementHandle;
    const defined = line instanceof SnippetLine && scope.define({ name: name.text, params, block: anatomy.block, text, scope, line });
    if (!defined) {
      throw this.problem(DiagnosticCode.SnippetDefinedTwice, text, name.span, via, name.text);
    }
  }

  /** `@use name value...;` (rule 6): the snippet's body, spliced in place with its parameters bound. */
  private use(anatomy: DirectiveAnatomy, keyword: Token, copy: Copy, context: PlaceContext): readonly Opened[] {
    const { text, scope, via, open } = context;
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...rest] = anatomy.values;
    const name = tokens[first as number] as Token;
    const visible: Snippet[] = [];
    scope.snippets(name.text, visible);
    const [snippet, ...others] = visible;
    const use = copy.statement as unknown as UseLine;
    const resolution: Resolution<api.SnippetLine> = {
      copy,
      winner: snippet?.line,
      shadowed: others.map((s) => s.line as unknown as api.SnippetLine),
    };
    const list = this.byUse.get(use);
    if (list === undefined) this.byUse.set(use, [resolution]);
    else list.push(resolution);
    if (snippet === undefined) {
      throw this.problem(DiagnosticCode.UnknownSnippet, text, name.span, via, name.text);
    }
    const written: WrittenValue[] = [];
    const values = rest.flatMap((ref) => {
      const expanded = this.value(text, ref, scope, via, copy);
      const handle = text.doc?.valueOf(ref) as unknown as WrittenValue;
      for (let i = 0; i < expanded.length; i++) written.push(handle);
      return expanded;
    });
    this.checkNesting(context.nesting, false, values, text, keyword, via);
    if (values.length !== snippet.params.length) {
      const detail = `${name.text} takes ${String(snippet.params.length)}, given ${String(values.length)}`;
      throw this.problem(DiagnosticCode.SnippetArity, text, keyword.span, via, detail);
    }
    if (open.includes(snippet)) {
      throw this.problem(DiagnosticCode.ExpansionCycle, text, keyword.span, via, name.text);
    }
    this.checkDepth(open, text, keyword, via);
    // Parameters are the body block's own bindings (a `set` of one there is E5002, S3-03), stored without the use
    // line's steps, as a `set` stores its values.
    const body = new Scope(snippet.scope);
    snippet.params.forEach((param, i) => {
      const value = values[i];
      const variable = snippet.line.parameterHandles[i];
      const writtenValue = written[i];
      if (value !== undefined && variable !== undefined) {
        body.param(param, { variable, values: [ExpandedRecord.rebase(value, via.length, [])], written: writtenValue === undefined ? [] : [writtenValue] });
      }
    });
    const step = makeStep("use", name.text, text.place(keyword.span));
    return [[snippet.block, { ...context, text: snippet.text, scope: body, via: [step, ...via], open: [...open, snippet] }]];
  }

  /** An extension directive (rules 7 and 8): the files its specs name, spliced in place. */
  private extension(extension: Extension, anatomy: DirectiveAnatomy, name: Token, copy: Copy, context: PlaceContext): readonly Opened[] {
    const { text, scope, via, open } = context;
    const specs: string[] = [];
    const targets: string[] = [];
    const edge: DocumentEdge = { copy, specs, targets };
    this.edges.push(edge);
    const values = anatomy.values.flatMap((ref) => this.value(text, ref, scope, via, copy));
    this.checkNesting(context.nesting, false, values, text, name, via);
    const forced = this.extensionBlock(anatomy.block, text, scope, via, context.nesting);
    const origin = { place: text.place(name.span), via };
    const fail = (code: DiagnosticCode, detail: string): Problem =>
      this.problem(code, text, name.span, via, detail);
    let given: unknown;
    try {
      given = extension.specs({ values: values.map((record) => ExpandedRecord.asValue(record)), origin });
    } catch (error) {
      if (error instanceof DiagnosticError) throw new Problem(UnreadableReason.Extension, error.diagnostic);
      throw fail(DiagnosticCode.ExtensionFailed, `${extension.directive}: ${reasonOf(error)}`);
    }
    // The port's result is checked at run time (spec 5, kno-umh.12): a list of texts, nothing else.
    if (!isTexts(given)) throw fail(DiagnosticCode.ExtensionFailed, `${extension.directive}: specs returned ${typeNameOf(given)}, not an array of strings`);
    specs.push(...given);
    /** A copy whose files are not resolved or read yet: unreadable with reason `unread`, E3007 (spec 6.10). */
    const unread = (need: ReadNeed): Problem => {
      this.needs.set(edge, need);
      this.unread.push(edge);
      return this.problem(DiagnosticCode.UnreadCopy, text, name.span, via, extension.directive);
    };
    const reads = this.input?.reads;
    if (reads === undefined) throw new Error("no read ledger");
    const found: string[] = [];
    for (const spec of specs) {
      const paths = reads.resolved(text.resolvedPath, spec);
      if (paths === undefined) throw unread({ tag: "resolve", parentPath: text.resolvedPath, specs: [...specs] });
      if (paths instanceof Error) throw fail(DiagnosticCode.IncludeResolverFailed, `${spec}: ${paths.message}`);
      // An empty glob is the warning W3005 (spec 4.1, 2.3): recorded, and the line goes on; the glob rule decides.
      if (paths.length === 0 && hasGlob(spec)) this.warn(DiagnosticCode.IncludeMatchedNothing, text, name.span, via, spec);
      else if (paths.length === 0) throw fail(DiagnosticCode.IncludeNotFound, spec);
      found.push(...[...paths].sort(compareCodePoints));
    }
    const cycle = found.find((path) => open.includes(path));
    if (cycle !== undefined) {
      throw this.problem(DiagnosticCode.ExpansionCycle, text, name.span, via, cycle);
    }
    this.checkDepth(open, text, name, via);
    const files: Document[] = [];
    for (const path of found) {
      const doc = reads.readOf(path);
      if (doc === undefined) throw unread({ tag: "read", paths: found });
      if (doc instanceof Error) throw fail(DiagnosticCode.IncludeResolverFailed, `${path}: ${doc.message}`);
      files.push(asDocument(doc));
    }
    targets.push(...found);
    // The step's name is the extension's, without `@`, as a variable step's is without `$`; its place the `@name`.
    const step = makeStep(StepKind.Extension, extension.directive, text.place(name.span));
    const spliced = new SpliceScope(scope, forced);
    return files.map((file) => [
      file.syntax.root,
      { ...context, text: documentText(file), scope: spliced, via: [step, ...via], open: [...open, file.resolvedPath] },
    ]);
  }

  /**
   * An extension directive's block: only `set` lines (E5012), bound for the spliced files. Its lines stand at the
   * extension line's `nesting`: the block is gone after expansion.
   */
  private extensionBlock(block: Node | undefined, text: Text, scope: BlockScope, via: readonly Step[], nesting: number): ReadonlyMap<string, Definition> {
    if (block === undefined) return new Map();
    const own = new Scope(scope);
    const { tokens } = text.syntax;
    const doc = text.doc;
    for (const node of block.children) {
      // Already reported by the parser; the broken line may be a `set` the files need, so the include is unreadable.
      if (node.kind === NodeKind.Error) throw new Problem(UnreadableReason.Syntax, undefined);
      if (node.kind !== NodeKind.Directive || doc === undefined) continue;
      const anatomy = anatomyOf(tokens, node);
      const name = tokens[anatomy.name];
      if (name === undefined) throw new Error("a directive node has no name token");
      // Kind `extension` (S3-07), placed at the line's name as every other directive-level code is (F1-02).
      if (name.kind !== TokenKind.AT_WORD || statementOfKeyword(name.text.slice(1)) !== StatementKind.Set) {
        throw this.problem(DiagnosticCode.ExtensionBlockNotSet, text, name.span, via);
      }
      this.set(anatomy, this.copyOf(doc.statementOf(node), via), text, own, via, nesting);
    }
    return own.own();
  }

  /** Rule 9's depth, checked after the cycle check (S3-10): a `use` or extension directive 17 places deep is E5007. */
  private checkDepth(open: readonly (Snippet | string)[], text: Text, name: Token, via: readonly Step[]): void {
    // `open` holds the root file and every expansion around this place, so its length is this expansion's depth.
    if (open.length > MAX_DEPTH) {
      throw this.problem(DiagnosticCode.ExpansionTooDeep, text, name.span, via, `more than ${String(MAX_DEPTH)}`);
    }
  }

  /**
   * E5013 at the statement's name (spec 2.5): the line stands inside `nesting` expanded blocks, and its block (when
   * `block`) or a list among its values would sit deeper than MAX_EXPANDED_NESTING. Checked before the values are
   * kept or the block walked, so no walk over the expanded tree goes deeper.
   */
  private checkNesting(nesting: number, block: boolean, values: Iterable<ExpandedRecord>, text: Text, name: Token, via: readonly Step[]): void {
    if (Math.max(nesting + (block ? 1 : 0), nesting + nestingOf(values)) > MAX_EXPANDED_NESTING) {
      throw this.problem(DiagnosticCode.ExpandedNestingTooDeep, text, name.span, via);
    }
  }

  /** One written value, expanded: a `$name` becomes all its values (rule 4); a list's items expand the same way. */
  value(text: Text, ref: ValueRef, scope: ScopeView, via: readonly Step[], copy: Copy | undefined): ExpandedRecord[] {
    const { syntax } = text;
    const origin = { place: text.written(spanOfRef(syntax, ref)), via };
    const written = text.doc?.valueOf(ref) as unknown as WrittenValue | undefined;
    if (typeof ref !== "number") {
      if (ref.kind === NodeKind.List) {
        const items = itemsOf(syntax.tokens, ref).flatMap((item) => this.value(text, item, scope, via, copy));
        return [new ExpandedRecord({ kind: "list", items }, origin, written)];
      }
      return [this.slice(text, ref, scope, via, copy, written)];
    }
    const token = syntax.tokens[ref];
    if (token === undefined) throw new Error(`no token ${String(ref)}`);
    if (isWordKind(token.kind)) return [new ExpandedRecord({ kind: "word", text: token.text }, origin, written)];
    switch (token.kind) {
      case TokenKind.STRING:
        return [new ExpandedRecord({ kind: "string", value: decodeString(token.text) }, origin, written)];
      case TokenKind.VARIABLE:
        return this.variable(text, token, scope, via, copy, written?.kind === ValueKind.Reference ? written : undefined);
      default:
        throw new Error(`not a value token: ${token.kind}`);
    }
  }

  /**
   * `$name`'s values as read here: each with the variable step, then the reading place's steps (and a resolution for
   * `reference`, its written handle: the token's own value, or a slice's name).
   */
  private variable(
    text: Text,
    token: Token,
    scope: ScopeView,
    via: readonly Step[],
    copy: Copy | undefined,
    reference: Reference | undefined,
  ): ExpandedRecord[] {
    const name = token.text.slice(1);
    const entries: Entry[] = [];
    scope.entries(name, entries);
    const [winner, ...others] = ordered(entries, this.overrides.get(name));
    let resolution: ReferenceResolution | undefined;
    if (copy !== undefined && reference !== undefined) {
      resolution = { copy, reference, winner: winner?.variable, shadowed: others.map((d) => d.variable), values: winner?.written ?? [] };
      this.allResolutions.push(resolution);
      const list = this.byReference.get(reference);
      if (list === undefined) this.byReference.set(reference, [resolution]);
      else list.push(resolution);
    }
    if (winner === undefined) {
      throw this.problem(DiagnosticCode.UnknownVariable, text, token.span, via, token.text);
    }
    if (winner.problem !== undefined) {
      // An override is written in no file: its problem is placed on the `$name` that used it.
      throw new Problem("value", makeLocated(DiagnosticCode.NonIntegerBound, winner.problem, text.place(token.span), via));
    }
    const step = makeStep(StepKind.Variable, name, text.place(token.span));
    return winner.values.map((value) => ExpandedRecord.rebase(value, 0, [step, ...via], resolution));
  }

  /**
   * `name[bounds]` (rules 4 and 10): the name a word, or a variable holding exactly one word (E4007 otherwise); each
   * bound a literal INTEGER or a variable holding exactly one IntegerText (E4001 otherwise). Read where written.
   */
  private slice(
    text: Text,
    node: Node,
    scope: ScopeView,
    via: readonly Step[],
    copy: Copy | undefined,
    written: WrittenValue | undefined,
  ): ExpandedRecord {
    const { tokens } = text.syntax;
    const nameToken = tokens[node.start];
    if (nameToken === undefined) throw new Error("a slice node has no name token");
    const writtenName = written?.kind === ValueKind.Slice || written?.kind === ValueKind.Index ? written.name : undefined;
    const name = this.sliceName(text, nameToken, scope, via, copy, writtenName?.kind === ValueKind.Reference ? writtenName : undefined);
    const inner: number[] = [];
    for (let i = node.start + 2; i < node.end - 1; i++) inner.push(i);
    const bound = (index: number): number | undefined => {
      const at = inner[index];
      const token = at === undefined ? undefined : tokens[at];
      return token === undefined || at === undefined ? undefined : this.bound(text, at, token, scope, via, copy);
    };
    const origin = { place: text.written(spanOf(text.syntax, node)), via };
    const tilde = inner.findIndex((i) => tokens[i]?.kind === TokenKind.TILDE);
    if (tilde < 0) {
      return new ExpandedRecord({ kind: "index", name, index: bound(0) ?? 0 }, origin, written);
    }
    const start = tilde === 0 ? undefined : bound(0);
    const end = tilde + 1 < inner.length ? bound(tilde + 1) : undefined;
    return new ExpandedRecord(
      { kind: "slice", name, ...(start === undefined ? {} : { start }), ...(end === undefined ? {} : { end }) },
      origin,
      written,
    );
  }

  /**
   * A slice's name: a word's text, or the one word its variable holds, a word that may name a slice (the grammar's
   * `sliceNameText`: a WORD or an AT_WORD, so never `5`, `1.5` or `-`); E4007 otherwise, placed as E4001 is.
   */
  private sliceName(text: Text, token: Token, scope: ScopeView, via: readonly Step[], copy: Copy | undefined, reference: Reference | undefined): string {
    if (token.kind !== TokenKind.VARIABLE) return token.text;
    const values = this.variable(text, token, scope, via, copy, reference);
    const [only] = values;
    if (values.length === 1 && only?.kind === ValueKind.Word && parseEntry(only.text, "sliceNameText").diagnostics.length === 0) return only.text;
    throw this.throughVariable(DiagnosticCode.BadSliceName, text, token, via, only);
  }

  /**
   * One slice bound's integer. E4001 at a literal beyond the integer range (the grammar makes every other literal an
   * INTEGER), or for a variable at its value's place via the variable.
   */
  private bound(text: Text, ref: number, token: Token, scope: ScopeView, via: readonly Step[], copy: Copy | undefined): number {
    if (token.kind === TokenKind.INTEGER) {
      const value = integerOf(token.text);
      if (value === undefined) throw this.problem(DiagnosticCode.NonIntegerBound, text, token.span, via, token.text);
      return value;
    }
    const values = this.variable(text, token, scope, via, copy, text.doc?.valueOf(ref) as unknown as Reference | undefined);
    const [only] = values;
    const word = values.length === 1 && only?.kind === ValueKind.Word ? only.text : undefined;
    const value = word === undefined ? undefined : integerOf(word);
    if (value !== undefined) return value;
    throw this.throughVariable(DiagnosticCode.NonIntegerBound, text, token, via, only);
  }

  /**
   * A slice name's or bound's problem through a variable: at its (first) value's place via the variable, or at the
   * `$name` when that value is an override's (written in no file).
   */
  private throughVariable(code: DiagnosticCode, text: Text, token: Token, via: readonly Step[], only: ExpandedRecord | undefined): Problem {
    const place = only?.origin.place;
    if (place === undefined || place.kind === PlaceKind.Override) return this.problem(code, text, token.span, via, token.text);
    return located(code, place, only?.origin.via ?? [], `${token.text} is ${only?.text ?? ""}`);
  }

  private problem(code: DiagnosticCode, text: Text, span: SourceSpan, via: readonly Step[], detail?: string): Problem {
    return located(code, text.place(span), via, detail);
  }

  /** A warning (spec 2.3): kept in the list in walk order, and nothing stops; its code makes no statement unreadable. */
  private warn(code: DiagnosticCode, text: Text, span: SourceSpan, via: readonly Step[], detail?: string): void {
    this.diagnostics.push(makeLocated(code, describe(code, detail).message, text.place(span), via));
  }
}

/** A statement's problem with knobly's code: its message and its unreadable reason, from the code (`describe`). */
function located(code: DiagnosticCode, place: Place, via: readonly Step[], detail?: string): Problem {
  const { message, reason } = describe(code, detail);
  if (reason === null) throw new Error(`${code} makes no statement unreadable`);
  return new Problem(reason, makeLocated(code, message, place, via));
}

function spanOfRef(syntax: Syntax, ref: ValueRef): SourceSpan {
  return typeof ref === "number" ? spanOf(syntax, { start: ref, end: ref + 1 }) : spanOf(syntax, ref);
}

/** Whether a port's result is an array of strings (spec 4.1, 5). */
export function isTexts(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
