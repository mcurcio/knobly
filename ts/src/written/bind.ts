/**
 * The binding (design rule 3; slices.md S1 "Internal contract: the binding"): one derivation of the graph's
 * current texts, overrides and read ledger. It walks the copies (the root, then each include and `use`
 * spliced in place), decides per copy what each `$name` and `use` reads, and expands written values for the
 * extension lines (an include's path) and for the rendered layer. It is the one home of the name-lookup rule:
 * `render (graph)` walks `items` and calls `argumentsAt`, and never looks a name up. Package-internal; pure (no I/O).
 * It names nothing of the rendered layer (spec 5, "Layer direction").
 *
 * The walk is PR 3's `Expander` (cb08803) moved here, unchanged in what it decides and reports (rules 1-12 of
 * round 11's slices.md §1.2), with the read ledger in place of reading files during the walk.
 */

import { anatomyOf, type IDirectiveAnatomy, itemsOf } from "../anatomy.js";
import { DiagnosticCode, messageOf } from "../diagnostics.js";
import { DiagnosticError } from "../errors.js";
import type { IExtension } from "../extension.js";
import type { UnreadableReason } from "../gen/api/kinds.js";
import { MAX_DEPTH, MAX_DIRECTIVES } from "../gen/api/limits.js";
import { compareCodePoints } from "../graph/order.js";
import { type IOverride, type IPlace, type IStep, makeOverride, makePlace, makeStep } from "../origin.js";
import { type ILocatedDiagnostic, makeLocated } from "../report.js";
import type { ISourceSpan } from "../span.js";
import { type INode, type ISyntax, spanOf, type ValueRef } from "../syntax/cst.js";
import { parse } from "../syntax/parse.js";
import { type IToken } from "../syntax/tokens.js";
import { decodeString, hasOnlyKnownEscapes, integerOf } from "../values.js";
import type { Document } from "./document.js";
import type {
  ICopy,
  IDocument,
  IDocumentEdge,
  IReference,
  IReferenceResolution,
  IResolution,
  ISnippetLine,
  IUseLine,
  Variable,
  Statement,
  WrittenValue,
} from "./model.js";
import { Bound } from "./expanded.js";
import { shapeOfAnatomy } from "./shape.js";
import { SetLine, SnippetLine, type StatementHandle } from "./statements.js";

/** What one container (the root's top level, or a directive's block) holds at one copy, in walk order. */
export type BoundItem = IBoundDirective | IBoundUnreadable;

/** One copy of a directive statement (kind "directive"), with its block's items at that copy. */
export interface IBoundDirective {
  readonly kind: "directive";
  readonly copy: ICopy;
  /** Undefined when written without a block. */
  readonly children: readonly BoundItem[] | undefined;
}

/**
 * One copy of a statement that cannot be read there: a syntax error, a malformed or repeated `set`/`snippet`/`use`,
 * an unknown snippet or wrong arity, an include that failed, a cycle, too deep, too many directives.
 */
export interface IBoundUnreadable {
  readonly kind: "unreadable";
  readonly copy: ICopy;
  readonly reason: UnreadableReason;
  /** Undefined when the problem is already one of a document's syntax diagnostics. */
  readonly diagnostic: ILocatedDiagnostic | undefined;
}

/** A written value that cannot be expanded at a copy (E5001, E4001, E4003): the statement is unreadable there. */
export class BindingProblem extends Error {
  constructor(
    readonly reason: UnreadableReason,
    readonly diagnostic: ILocatedDiagnostic,
  ) {
    super(diagnostic.message);
    this.name = "BindingProblem";
  }
}

/** Which files were read: the one piece of state besides the texts (design rule 1). */
export interface IReadLedger {
  /** The paths `spec` resolved to from `parentPath`, the Error the source rejected with, or undefined: not resolved yet. */
  resolved(parentPath: string, spec: string): readonly string[] | Error | undefined;
  /** The document read at `resolvedPath`, the Error its read rejected with, or undefined: not read yet. */
  readOf(resolvedPath: string): IDocument | Error | undefined;
}

/** An override: its variable handle and its values, already read and checked (override.ts). */
export interface IOverrideInput {
  readonly variable: Variable;
  readonly values: readonly Bound[];
}

/** The inputs of one derivation. */
export interface IBindingInput {
  readonly root: IDocument;
  readonly extensions: ReadonlyMap<string, IExtension>;
  readonly overrides: ReadonlyMap<string, IOverrideInput>;
  readonly reads: IReadLedger;
}

/** One derivation. Immutable; the graph makes a new one after any edit, `setOverride` or read. */
export interface IBinding {
  /** The root document's top level at the root copy, includes and uses spliced in place. */
  readonly items: readonly BoundItem[];
  /** Every copy of every extension line, in walk order (a failed or unread one included). */
  readonly edges: readonly IDocumentEdge[];
  /** The edges with a spec not resolved, or a target not read, in the ledger. */
  readonly unread: readonly IDocumentEdge[];
  /** Every diagnostic the walk found, in walk order, render's codes included (the graph filters them). */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  /** Every copy of `statement`, in walk order. */
  copiesOf(statement: Statement): readonly ICopy[];
  /** One per copy of the reference's statement, in walk order. */
  resolutionsOf(reference: IReference): readonly IReferenceResolution[];
  /** Every resolution, in walk order: what `Variable.wins()` and `shadowedAt()` filter. */
  resolutions(): readonly IReferenceResolution[];
  /** One per copy of the `use` line, in walk order. */
  snippetsOf(use: IUseLine): readonly IResolution<ISnippetLine>[];
  /** The edges whose `targets` include `resolvedPath`. */
  edgesInto(resolvedPath: string): readonly IDocumentEdge[];
  /**
   * One written value at one copy of its statement, expanded with PR 3's origins: a `$name` becomes all its winner's
   * values (each with the variable step, then the copy's steps); a list's items expand the same way.
   * @throws BindingProblem E5001 (nothing visible), E4001 (slice bound), E4003 (escape)
   */
  argumentsAt(value: WrittenValue, copy: ICopy): readonly Bound[];
}

/** What an unread edge still needs from the source: specs to resolve, or paths to read. */
export type ReadNeed =
  | { readonly kind: "resolve"; readonly parentPath: string; readonly specs: readonly string[] }
  | { readonly kind: "read"; readonly paths: readonly string[] };

/** The binding, plus what the read loop needs to know about each unread edge (read.ts). */
export interface IBindingWithNeeds extends IBinding {
  needOf(edge: IDocumentEdge): ReadNeed | undefined;
}

/** Derive the binding of these inputs. Pure and synchronous. */
export function bind(input: IBindingInput): IBindingWithNeeds {
  return new Walk(input).run();
}

/** No extension names: the binding asks shape.ts only about `set`, `snippet` and `use` lines. */
const NO_EXTENSIONS: ReadonlySet<string> = new Set();

/**
 * An override's values, read as the values of a line `x <text>` (spec 6.3, the check of an override's last step).
 * Call only with text already checked as values without a `$name` (override.ts): what is left to refuse is an
 * unknown escape (E4003) or a non-integer bound (E4001), returned with its span in `x <text>`.
 */
export function readOverride(
  name: string,
  text: string,
): { readonly values: readonly Bound[] } | { readonly problem: { readonly code: DiagnosticCode; readonly span: ISourceSpan } } {
  const syntax = parse(`x ${text}`);
  const [node] = syntax.root.children;
  if (node?.kind !== "directive") throw new Error("override text was not checked as values");
  const overrideText: IText = {
    doc: undefined,
    syntax,
    resolvedPath: "",
    written: () => makeOverride(name),
    place: (span) => makePlace("", span),
  };
  const walk = new Walk(undefined);
  try {
    return { values: anatomyOf(syntax.tokens, node).values.flatMap((ref) => walk.value(overrideText, ref, new Scope(undefined), [], undefined)) };
  } catch (error) {
    if (!(error instanceof Problem) || error.diagnostic === undefined) throw error;
    return { problem: { code: error.diagnostic.code as DiagnosticCode, span: error.diagnostic.place.span } };
  }
}

/** The package's document behind an IDocument. @throws TypeError for a document this package did not make. */
export function asDocument(doc: IDocument): Document {
  const internal = doc as Partial<Document>;
  if (typeof internal.statementOf !== "function") throw new TypeError("not a document of this package");
  return doc as Document;
}

// --- The walk ---

/** One text being walked: a document, or an override's text. */
interface IText {
  readonly doc: Document | undefined;
  readonly syntax: ISyntax;
  readonly resolvedPath: string;
  written(span: ISourceSpan): IPlace | IOverride;
  place(span: ISourceSpan): IPlace;
}

function documentText(doc: Document): IText {
  const place = (span: ISourceSpan): IPlace => makePlace(doc.resolvedPath, span);
  return { doc, syntax: doc.syntax, resolvedPath: doc.resolvedPath, written: place, place };
}

/**
 * A statement that cannot be read: thrown inside a statement, caught where the statement is kept unreadable.
 * `diagnostic` is undefined when the problem is already reported (a syntax error inside an extension's block).
 */
class Problem extends Error {
  constructor(
    readonly reason: UnreadableReason,
    readonly diagnostic: ILocatedDiagnostic | undefined,
  ) {
    super(diagnostic?.message ?? reason);
    this.name = "Problem";
  }
}

/** A problem with one of a directive's values: the directive is unreadable at that copy, and argumentsAt throws it. */
class ValueProblem extends Problem {}

/** One definition of a name: its variable, the values a reader gets (stored without the definer's steps), as written. */
interface IDefinition {
  readonly variable: Variable;
  readonly values: readonly Bound[];
  readonly written: readonly WrittenValue[];
}

/** One definition visible at a place, by how PR 3's lookup treats it. */
interface IEntry {
  /** A snippet parameter, a `set`, or an include block's `set` (it wins over every `set` of the spliced files). */
  readonly kind: "parameter" | "set" | "forced";
  readonly definition: IDefinition;
}

/** A snippet definition: its parameters, its body and the scope of the block it was written in (lexical, rule 6). */
interface ISnippet {
  readonly name: string;
  readonly params: readonly string[];
  readonly block: INode;
  readonly text: IText;
  readonly scope: IScopeView;
  readonly line: SnippetLine;
}

/** What a place can see: variables and snippets. */
interface IScopeView {
  /** Every definition of `name` visible here, innermost first (PR 3's `Scope.lookup` chain, F1-01). */
  entries(name: string, out: IEntry[]): void;
  /** Every snippet of `name` visible here, innermost first. */
  snippets(name: string, out: ISnippet[]): void;
}

/** A block's scope: it claims names for the one-per-block checks and binds them. */
interface IBlockScope extends IScopeView {
  claim(name: string): boolean;
  bind(name: string, definition: IDefinition): void;
  define(snippet: ISnippet): boolean;
}

/** The variables and snippets of one block: its own lines so far, then the enclosing view's. */
class Scope implements IBlockScope {
  private readonly vars = new Map<string, IDefinition>();
  private readonly params = new Map<string, IDefinition>();
  private readonly claimed = new Set<string>();
  private readonly defined = new Map<string, ISnippet>();

  constructor(private readonly outer: IScopeView | undefined) {}

  entries(name: string, out: IEntry[]): void {
    const param = this.params.get(name);
    if (param !== undefined) out.push({ kind: "parameter", definition: param });
    const set = this.vars.get(name);
    if (set !== undefined) out.push({ kind: "set", definition: set });
    this.outer?.entries(name, out);
  }

  snippets(name: string, out: ISnippet[]): void {
    const snippet = this.defined.get(name);
    if (snippet !== undefined) out.push(snippet);
    this.outer?.snippets(name, out);
  }

  claim(name: string): boolean {
    if (this.claimed.has(name)) return false;
    this.claimed.add(name);
    return true;
  }

  bind(name: string, definition: IDefinition): void {
    this.vars.set(name, definition);
  }

  /** Bind a snippet parameter: the body block's own binding of that name (S3-03). */
  param(name: string, definition: IDefinition): void {
    this.claimed.add(name);
    this.params.set(name, definition);
  }

  define(snippet: ISnippet): boolean {
    if (this.defined.has(snippet.name)) return false;
    this.defined.set(snippet.name, snippet);
    return true;
  }

  /** The variables this block bound itself (an extension block's `set` lines). */
  own(): ReadonlyMap<string, IDefinition> {
    return this.vars;
  }
}

/**
 * The including block's scope as a spliced file sees it: the file's top-level `set` and `snippet` lines claim, bind
 * and define in the including block (L2), and inside the spliced files the extension block's `set` lines win over
 * every `set` of the files, at any depth, but not over a parameter (rule 8, F1-01).
 */
class SpliceScope implements IBlockScope {
  constructor(
    private readonly target: IBlockScope,
    private readonly overrides: ReadonlyMap<string, IDefinition>,
  ) {}

  entries(name: string, out: IEntry[]): void {
    const forced = this.overrides.get(name);
    if (forced !== undefined) out.push({ kind: "forced", definition: forced });
    this.target.entries(name, out);
  }

  snippets(name: string, out: ISnippet[]): void {
    this.target.snippets(name, out);
  }

  claim(name: string): boolean {
    return this.target.claim(name);
  }

  bind(name: string, definition: IDefinition): void {
    this.target.bind(name, definition);
  }

  define(snippet: ISnippet): boolean {
    return this.target.define(snippet);
  }
}

/**
 * The winner among `entries` (innermost first) and an override, by PR 3's rule: the nearest `set` or parameter; an
 * include block's `set` wins over every `set` nearer than it, but a nearer parameter wins over it; an override wins
 * over every `set` and include-block `set`, never over a parameter.
 */
function pick(entries: readonly IEntry[], override: IDefinition | undefined): IDefinition | undefined {
  let found: IEntry | undefined;
  for (const entry of entries) {
    if (entry.kind === "parameter" && found === undefined) return entry.definition;
    if (entry.kind === "set" && found === undefined) found = entry;
    if (entry.kind === "forced") {
      found = entry;
      break;
    }
  }
  return override ?? found?.definition;
}

/** Every visible definition in the order the rule picks them, each as if those before it were removed (next first). */
function ordered(entries: readonly IEntry[], override: IDefinition | undefined): IDefinition[] {
  const out: IDefinition[] = [];
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
interface IPlaceContext {
  readonly text: IText;
  readonly scope: IBlockScope;
  /** The steps that brought this text here, innermost first. */
  readonly via: readonly IStep[];
  /** The snippets and files being walked around this place, outermost first; the root file is the first. */
  readonly open: readonly (ISnippet | string)[];
  readonly into: BoundItem[];
}

class Walk implements IBindingWithNeeds {
  readonly items: BoundItem[] = [];
  readonly edges: IDocumentEdge[] = [];
  readonly unread: IDocumentEdge[] = [];
  readonly diagnostics: ILocatedDiagnostic[] = [];
  private readonly needs = new Map<IDocumentEdge, ReadNeed>();
  private readonly copies = new Map<Statement, ICopy[]>();
  private readonly byReference = new Map<IReference, IReferenceResolution[]>();
  private readonly allResolutions: IReferenceResolution[] = [];
  private readonly byUse = new Map<IUseLine, IResolution<ISnippetLine>[]>();
  private readonly expanded = new Map<ICopy, Map<WrittenValue, readonly Bound[]> | BindingProblem>();
  private readonly overrides: ReadonlyMap<string, IDefinition>;
  private count = 0;
  private stopped = false;

  constructor(private readonly input: IBindingInput | undefined) {
    const overrides = new Map<string, IDefinition>();
    for (const [name, o] of input?.overrides ?? []) overrides.set(name, { variable: o.variable, values: o.values, written: [] });
    this.overrides = overrides;
  }

  run(): this {
    const input = this.input;
    if (input === undefined) throw new Error("no input");
    const root = asDocument(input.root);
    this.statements(root.syntax.root, {
      text: documentText(root),
      scope: new Scope(undefined),
      via: [],
      open: [root.resolvedPath],
      into: this.items,
    });
    return this;
  }

  // --- IBinding ---

  needOf(edge: IDocumentEdge): ReadNeed | undefined {
    return this.needs.get(edge);
  }

  copiesOf(statement: Statement): readonly ICopy[] {
    return this.copies.get(statement) ?? [];
  }

  resolutionsOf(reference: IReference): readonly IReferenceResolution[] {
    return this.byReference.get(reference) ?? [];
  }

  resolutions(): readonly IReferenceResolution[] {
    return this.allResolutions;
  }

  snippetsOf(use: IUseLine): readonly IResolution<ISnippetLine>[] {
    return this.byUse.get(use) ?? [];
  }

  edgesInto(resolvedPath: string): readonly IDocumentEdge[] {
    return this.edges.filter((edge) => edge.targets.includes(resolvedPath));
  }

  argumentsAt(value: WrittenValue, copy: ICopy): readonly Bound[] {
    const found = this.expanded.get(copy);
    if (found instanceof BindingProblem) throw found;
    const values = found?.get(value);
    if (values === undefined) throw new Error("argumentsAt: the value is not read at that copy");
    return values;
  }

  // --- The walk (PR 3's Expander) ---

  private copyOf(statement: StatementHandle, via: readonly IStep[]): ICopy {
    const copy: ICopy = { statement: statement as unknown as Statement, via };
    const list = this.copies.get(copy.statement);
    if (list === undefined) this.copies.set(copy.statement, [copy]);
    else list.push(copy);
    return copy;
  }

  /** Walk the statements of `scopeNode` (a document or block node) at `context`. */
  private statements(scopeNode: INode, context: IPlaceContext): void {
    const doc = context.text.doc;
    if (doc === undefined) throw new Error("an override's text has no statements");
    for (const node of scopeNode.children) {
      if (this.stopped) return;
      if (node.kind !== "directive" && node.kind !== "error") continue;
      const copy = this.copyOf(doc.statementOf(node), context.via);
      if (node.kind === "error") {
        context.into.push({ kind: "unreadable", copy, reason: "syntax", diagnostic: undefined });
        continue;
      }
      try {
        this.statement(node, copy, context);
      } catch (error) {
        if (!(error instanceof Problem)) throw error;
        if (error.diagnostic !== undefined) this.diagnostics.push(error.diagnostic);
        if (error instanceof ValueProblem && error.diagnostic !== undefined) {
          this.expanded.set(copy, new BindingProblem(error.reason, error.diagnostic));
        }
        context.into.push({ kind: "unreadable", copy, reason: error.reason, diagnostic: error.diagnostic });
      }
    }
  }

  /** One directive node: a reserved line does its work; any other becomes a directive and its block is walked. */
  private statement(node: INode, copy: ICopy, context: IPlaceContext): void {
    const { tokens } = context.text.syntax;
    const anatomy = anatomyOf(tokens, node);
    const name = tokens[anatomy.name];
    if (name === undefined) throw new Error("a directive node has no name token");
    if (name.text === "set") return this.set(anatomy, copy, context.text, context.scope, context.via);
    if (name.text === "snippet") return this.snippet(anatomy, copy, context);
    if (name.text === "use") return this.use(anatomy, name, copy, context);
    const extension = this.input?.extensions.get(name.text);
    if (extension !== undefined) return this.extension(extension, anatomy, name, copy, context);

    const { text, scope, via } = context;
    const statement = copy.statement as unknown as StatementHandle;
    const values = new Map<WrittenValue, readonly Bound[]>();
    for (const value of statement.valueList) {
      try {
        values.set(value as unknown as WrittenValue, this.value(text, value.ref, scope, via, copy));
      } catch (error) {
        if (error instanceof Problem && !(error instanceof ValueProblem)) throw new ValueProblem(error.reason, error.diagnostic);
        throw error;
      }
    }
    this.expanded.set(copy, values);
    if (++this.count > MAX_DIRECTIVES) {
      this.stopped = true;
      throw this.problem("expansion", DiagnosticCode.TooManyDirectives, text, name.span, via, `more than ${String(MAX_DIRECTIVES)}`);
    }
    const children: BoundItem[] | undefined = anatomy.block === undefined ? undefined : [];
    context.into.push({ kind: "directive", copy, children });
    if (anatomy.block === undefined || children === undefined) return;
    this.statements(anatomy.block, { text, scope: new Scope(scope), via, open: context.open, into: children });
  }

  /** A `set`, `snippet` or `use` line's text-alone shape (shape.ts, the one home of those rules), or its problem. */
  private wellFormed(anatomy: IDirectiveAnatomy, text: IText, via: readonly IStep[]): void {
    const { fault } = shapeOfAnatomy(text.syntax.tokens, anatomy, NO_EXTENSIONS);
    if (fault !== undefined) throw this.problem("expansion", fault.code, text, fault.span, via);
  }

  /** `set $name value...;` (rule 2): binds from this line to the end of the enclosing block. */
  private set(anatomy: IDirectiveAnatomy, copy: ICopy, text: IText, scope: IBlockScope, via: readonly IStep[]): void {
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...values] = anatomy.values;
    const variable = tokens[first as number] as IToken;
    const variableName = variable.text.slice(1);
    if (!scope.claim(variableName)) {
      throw this.problem("expansion", DiagnosticCode.VariableSetTwice, text, variable.span, via, variable.text);
    }
    const line = copy.statement as unknown as StatementHandle;
    if (!(line instanceof SetLine)) throw new Error("a set line that claims its name is kind set");
    const bound = values.flatMap((ref) => this.value(text, ref, scope, via, copy));
    // Stored without this line's own steps; a reader adds the variable step and its own (Bound.rebase).
    scope.bind(variableName, {
      variable: line.variableHandle,
      values: bound.map((value) => value.rebase(via.length, [])),
      written: line.valueList as unknown as WrittenValue[],
    });
  }

  /** `snippet name $param... { body }` (rule 5): visible from this line to the end of its block. */
  private snippet(anatomy: IDirectiveAnatomy, copy: ICopy, context: IPlaceContext): void {
    const { text, scope, via } = context;
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...rest] = anatomy.values;
    const name = tokens[first as number] as IToken;
    const params = rest.map((ref) => (tokens[ref as number] as IToken).text.slice(1));
    if (anatomy.block === undefined) throw new Error("a well-formed snippet has a block");
    const line = copy.statement as unknown as StatementHandle;
    const defined = line instanceof SnippetLine && scope.define({ name: name.text, params, block: anatomy.block, text, scope, line });
    if (!defined) {
      throw this.problem("expansion", DiagnosticCode.SnippetDefinedTwice, text, name.span, via, name.text);
    }
  }

  /** `use name value...;` (rule 6): the snippet's body, spliced in place with its parameters bound. */
  private use(anatomy: IDirectiveAnatomy, keyword: IToken, copy: ICopy, context: IPlaceContext): void {
    const { text, scope, via, open } = context;
    const { tokens } = text.syntax;
    this.wellFormed(anatomy, text, via);
    const [first, ...rest] = anatomy.values;
    const name = tokens[first as number] as IToken;
    const visible: ISnippet[] = [];
    scope.snippets(name.text, visible);
    const [snippet, ...others] = visible;
    const use = copy.statement as unknown as IUseLine;
    const resolution: IResolution<ISnippetLine> = {
      copy,
      winner: snippet?.line,
      shadowed: others.map((s) => s.line as unknown as ISnippetLine),
    };
    const list = this.byUse.get(use);
    if (list === undefined) this.byUse.set(use, [resolution]);
    else list.push(resolution);
    if (snippet === undefined) {
      throw this.problem("expansion", DiagnosticCode.UnknownSnippet, text, name.span, via, name.text);
    }
    const written: WrittenValue[] = [];
    const values = rest.flatMap((ref) => {
      const expanded = this.value(text, ref, scope, via, copy);
      const handle = text.doc?.valueOf(ref) as unknown as WrittenValue;
      for (let i = 0; i < expanded.length; i++) written.push(handle);
      return expanded;
    });
    if (values.length !== snippet.params.length) {
      const detail = `${name.text} takes ${String(snippet.params.length)}, given ${String(values.length)}`;
      throw this.problem("expansion", DiagnosticCode.SnippetArity, text, keyword.span, via, detail);
    }
    if (open.includes(snippet)) {
      throw this.problem("expansion", DiagnosticCode.ExpansionCycle, text, keyword.span, via, name.text);
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
        body.param(param, { variable, values: [value.rebase(via.length, [])], written: writtenValue === undefined ? [] : [writtenValue] });
      }
    });
    const step = makeStep("use", name.text, text.place(keyword.span));
    this.statements(snippet.block, { ...context, text: snippet.text, scope: body, via: [step, ...via], open: [...open, snippet] });
  }

  /** An extension directive (rules 7 and 8): the files its specs name, spliced in place. */
  private extension(extension: IExtension, anatomy: IDirectiveAnatomy, name: IToken, copy: ICopy, context: IPlaceContext): void {
    const { text, scope, via, open } = context;
    const specs: string[] = [];
    const targets: string[] = [];
    const edge: IDocumentEdge = { copy, specs, targets };
    this.edges.push(edge);
    const values = anatomy.values.flatMap((ref) => this.value(text, ref, scope, via, copy));
    const forced = this.extensionBlock(anatomy.block, text, scope, via);
    const origin = { place: text.place(name.span), via };
    const fail = (code: DiagnosticCode, detail: string): Problem =>
      this.problem("extension", code, text, name.span, via, detail);
    try {
      specs.push(...extension.specs({ values: values.map((value) => value.expanded()), origin }));
    } catch (error) {
      specs.length = 0;
      if (error instanceof DiagnosticError) throw new Problem("extension", error.diagnostic);
      throw fail(DiagnosticCode.ExtensionFailed, `${name.text}: ${reasonOf(error)}`);
    }
    const reads = this.input?.reads;
    if (reads === undefined) throw new Error("no read ledger");
    const found: string[] = [];
    for (const spec of specs) {
      const paths = reads.resolved(text.resolvedPath, spec);
      if (paths === undefined) {
        this.needs.set(edge, { kind: "resolve", parentPath: text.resolvedPath, specs: [...specs] });
        this.unread.push(edge);
        return;
      }
      if (paths instanceof Error) throw fail(DiagnosticCode.IncludeResolverFailed, `${spec}: ${paths.message}`);
      if (paths.length === 0) throw fail(DiagnosticCode.IncludeNotFound, spec);
      found.push(...[...paths].sort(compareCodePoints));
    }
    const cycle = found.find((path) => open.includes(path));
    if (cycle !== undefined) {
      throw this.problem("expansion", DiagnosticCode.ExpansionCycle, text, name.span, via, cycle);
    }
    this.checkDepth(open, text, name, via);
    const files: Document[] = [];
    for (const path of found) {
      const doc = reads.readOf(path);
      if (doc === undefined) {
        this.needs.set(edge, { kind: "read", paths: found });
        this.unread.push(edge);
        return;
      }
      if (doc instanceof Error) throw fail(DiagnosticCode.IncludeResolverFailed, `${path}: ${doc.message}`);
      files.push(asDocument(doc));
    }
    targets.push(...found);
    const step = makeStep("extension", name.text, text.place(name.span));
    const spliced = new SpliceScope(scope, forced);
    for (const file of files) {
      this.statements(file.syntax.root, {
        ...context,
        text: documentText(file),
        scope: spliced,
        via: [step, ...via],
        open: [...open, file.resolvedPath],
      });
    }
  }

  /** An extension directive's block: only `set` lines (E5012), bound for the spliced files. */
  private extensionBlock(block: INode | undefined, text: IText, scope: IBlockScope, via: readonly IStep[]): ReadonlyMap<string, IDefinition> {
    if (block === undefined) return new Map();
    const own = new Scope(scope);
    const { tokens } = text.syntax;
    const doc = text.doc;
    for (const node of block.children) {
      // Already reported by the parser; the broken line may be a `set` the files need, so the include is unreadable.
      if (node.kind === "error") throw new Problem("syntax", undefined);
      if (node.kind !== "directive" || doc === undefined) continue;
      const anatomy = anatomyOf(tokens, node);
      const name = tokens[anatomy.name];
      if (name === undefined) throw new Error("a directive node has no name token");
      // Kind `extension` (S3-07), placed at the line's name as every other directive-level code is (F1-02).
      if (name.text !== "set") {
        throw this.problem("extension", DiagnosticCode.ExtensionBlockNotSet, text, name.span, via);
      }
      this.set(anatomy, this.copyOf(doc.statementOf(node), via), text, own, via);
    }
    return own.own();
  }

  /** Rule 9's depth, checked after the cycle check (S3-10): a `use` or extension directive 17 places deep is E5007. */
  private checkDepth(open: readonly (ISnippet | string)[], text: IText, name: IToken, via: readonly IStep[]): void {
    // `open` holds the root file and every expansion around this place, so its length is this expansion's depth.
    if (open.length > MAX_DEPTH) {
      throw this.problem("expansion", DiagnosticCode.ExpansionTooDeep, text, name.span, via, `more than ${String(MAX_DEPTH)}`);
    }
  }

  /** One written value, expanded: a `$name` becomes all its values (rule 4); a list's items expand the same way. */
  value(text: IText, ref: ValueRef, scope: IScopeView, via: readonly IStep[], copy: ICopy | undefined): Bound[] {
    const { syntax } = text;
    const origin = { place: text.written(spanOfRef(syntax, ref)), via };
    const written = text.doc?.valueOf(ref) as unknown as WrittenValue | undefined;
    if (typeof ref !== "number") {
      if (ref.kind === "list") {
        const items = itemsOf(syntax.tokens, ref).flatMap((item) => this.value(text, item, scope, via, copy));
        return [new Bound({ kind: "list", items }, origin, written)];
      }
      return [this.slice(text, ref, scope, via, copy, written)];
    }
    const token = syntax.tokens[ref];
    if (token === undefined) throw new Error(`no token ${String(ref)}`);
    switch (token.kind) {
      case "WORD":
        return [new Bound({ kind: "word", text: token.text }, origin, written)];
      case "STRING":
        if (!hasOnlyKnownEscapes(token.text)) {
          throw this.problem("value", DiagnosticCode.BadEscape, text, token.span, via, token.text);
        }
        return [new Bound({ kind: "string", value: decodeString(token.text) }, origin, written)];
      case "VARIABLE":
        return this.variable(text, ref, token, scope, via, copy);
      default:
        throw new Error(`not a value token: ${token.kind}`);
    }
  }

  /** `$name`'s values as read here: each with the variable step, then the reading place's steps (and a resolution). */
  private variable(text: IText, ref: number, token: IToken, scope: IScopeView, via: readonly IStep[], copy: ICopy | undefined): Bound[] {
    const name = token.text.slice(1);
    const entries: IEntry[] = [];
    scope.entries(name, entries);
    const [winner, ...others] = ordered(entries, this.overrides.get(name));
    let resolution: IReferenceResolution | undefined;
    const reference = text.doc?.valueOf(ref) as unknown as IReference | undefined;
    if (copy !== undefined && reference !== undefined) {
      resolution = { copy, reference, winner: winner?.variable, shadowed: others.map((d) => d.variable), values: winner?.written ?? [] };
      this.allResolutions.push(resolution);
      const list = this.byReference.get(reference);
      if (list === undefined) this.byReference.set(reference, [resolution]);
      else list.push(resolution);
    }
    if (winner === undefined) {
      throw this.problem("expansion", DiagnosticCode.UnknownVariable, text, token.span, via, token.text);
    }
    const step = makeStep("variable", name, text.place(token.span));
    return winner.values.map((value) => value.rebase(0, [step, ...via], resolution));
  }

  /** `name[bounds]`: each bound a literal IntegerText or a variable holding exactly one (rules 4 and 10). */
  private slice(
    text: IText,
    node: INode,
    scope: IScopeView,
    via: readonly IStep[],
    copy: ICopy | undefined,
    written: WrittenValue | undefined,
  ): Bound {
    const { tokens } = text.syntax;
    const name = tokens[node.start];
    if (name === undefined) throw new Error("a slice node has no name token");
    const inner: number[] = [];
    for (let i = node.start + 2; i < node.end - 1; i++) inner.push(i);
    const bound = (index: number): number | undefined => {
      const at = inner[index];
      const token = at === undefined ? undefined : tokens[at];
      return token === undefined || at === undefined ? undefined : this.bound(text, at, token, scope, via, copy);
    };
    const origin = { place: text.written(spanOf(text.syntax, node)), via };
    const colon = inner.findIndex((i) => tokens[i]?.kind === "COLON");
    if (colon < 0) {
      return new Bound({ kind: "index", name: name.text, index: bound(0) ?? 0 }, origin, written);
    }
    const start = colon === 0 ? undefined : bound(0);
    const end = colon + 1 < inner.length ? bound(colon + 1) : undefined;
    return new Bound(
      { kind: "slice", name: name.text, ...(start === undefined ? {} : { start }), ...(end === undefined ? {} : { end }) },
      origin,
      written,
    );
  }

  /** One slice bound's integer. E4001 at the bound, or for a variable at its value's place via the variable. */
  private bound(text: IText, ref: number, token: IToken, scope: IScopeView, via: readonly IStep[], copy: ICopy | undefined): number {
    if (token.kind === "WORD") {
      const value = integerOf(token.text);
      if (value === undefined) throw this.problem("value", DiagnosticCode.NonIntegerBound, text, token.span, via, token.text);
      return value;
    }
    const values = this.variable(text, ref, token, scope, via, copy);
    const [only] = values;
    const word = values.length === 1 ? only?.wordText : undefined;
    const value = word === undefined ? undefined : integerOf(word);
    if (value !== undefined) return value;
    const place = only?.origin.place;
    if (place === undefined || place.kind === "override") {
      // An override is written in no file: the problem is placed on the `$name` that used it.
      throw this.problem("value", DiagnosticCode.NonIntegerBound, text, token.span, via, token.text);
    }
    const message = `${messageOf(DiagnosticCode.NonIntegerBound)}: ${token.text} is ${only?.text ?? ""}`;
    throw new Problem("value", makeLocated(DiagnosticCode.NonIntegerBound, message, place, only?.origin.via ?? []));
  }

  private problem(reason: UnreadableReason, code: DiagnosticCode, text: IText, span: ISourceSpan, via: readonly IStep[], detail?: string): Problem {
    const message = detail === undefined ? messageOf(code) : `${messageOf(code)}: ${detail}`;
    return new Problem(reason, makeLocated(code, message, text.place(span), via));
  }
}

function spanOfRef(syntax: ISyntax, ref: ValueRef): ISourceSpan {
  return typeof ref === "number" ? spanOf(syntax, { start: ref, end: ref + 1 }) : spanOf(syntax, ref);
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
