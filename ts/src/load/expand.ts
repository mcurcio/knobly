/**
 * Expansion (slices.md §1.2): files' tier-1 trees in, readable directives and unreadable statements out. Private to
 * the load layer. Rules: reserved names (1), `set` (2), handed-in values (3), `$name` (4), `snippet` (5), `use` (6),
 * extension directives (7) and their blocks (8), limits and cycles (9), value rules checked at load (10), unreadable
 * statements (11) and diagnostics order (12).
 */

import { DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import { compareCodePoints } from "../graph/order.js";
import type { ISourceSpan } from "../span.js";
import { type INode, type ISyntax, NodeKind, spanOf, type ValueRef } from "../syntax/cst.js";
import { parse } from "../syntax/parse.js";
import { messageOf } from "../syntax/recovery.js";
import { type IToken, TokenKind } from "../syntax/tokens.js";
import { ValueKind } from "../value.js";
import { anatomyOf, type IDirectiveAnatomy, itemsOf } from "./anatomy.js";
import { type IDirective, type IKeyInput, type IUnreadable, type KeyRule, UnreadableKind } from "./directive.js";
import type { IDocumentEdge, IDocumentNode } from "./graph.js";
import { type IDirectiveOrigin, type IHanded, type IPlace, type IStep, StepKind } from "./origin.js";
import type { IExtension } from "./processor.js";
import type { ILocatedDiagnostic } from "./report.js";
import type { IDocumentSource } from "./source.js";
import { Address, Argument, Directive } from "./tree.js";
import { decodeString, hasOnlyKnownEscapes, integerOf } from "./values.js";

/** `use` and extension directives may nest this many places deep (E5007 beyond). */
export const MAX_DEPTH = 16;
/** At most this many directives after expansion (E5008 beyond, and expansion stops). */
export const MAX_DIRECTIVES = 100_000;

/** The names reserved at a statement's start in every block, besides each registered extension's (L6). */
export const RESERVED: ReadonlySet<string> = new Set(["set", "snippet", "use"]);

/** One text being expanded: a file, or a value handed in by the program. */
export interface IText {
  readonly syntax: ISyntax;
  /** The file's resolvedPath; empty for a handed-in text. */
  readonly resolvedPath: string;
  /** Where a span of this text was written, for origins. */
  written(span: ISourceSpan): IPlace | IHanded;
  /** The file place of a span, for diagnostics (a handed-in text never reports: its problems are TypeErrors). */
  place(span: ISourceSpan): IPlace;
}

/** A text of the file at `resolvedPath`. */
export function fileText(resolvedPath: string, syntax: ISyntax): IText {
  const place = (span: ISourceSpan): IPlace => ({ kind: "file", resolvedPath, span });
  return { syntax, resolvedPath, written: place, place };
}

/**
 * A statement that cannot be read: thrown inside a statement, caught where the statement is kept unreadable.
 * `diagnostic` is undefined when the problem is already reported (a syntax error inside an extension's block).
 */
export class Problem extends Error {
  constructor(
    readonly kind: UnreadableKind,
    readonly diagnostic: ILocatedDiagnostic | undefined,
  ) {
    super(diagnostic?.message ?? kind);
    this.name = "Problem";
  }
}

/**
 * A snippet definition: its parameters, its body and the scope of the block it was written in (lexical, rule 6).
 * The body sees that scope as it stands when the `use` runs (S3-01), its own name included (a self-use is a cycle).
 */
interface ISnippet {
  readonly name: string;
  readonly params: readonly string[];
  readonly body: INode;
  readonly text: IText;
  readonly scope: IScopeView;
}

/** What `$name` reads at a place, and whether it is a snippet parameter. */
interface IBinding {
  readonly values: readonly Argument[];
  readonly parameter: boolean;
}

/** What a place can see: variables and snippets. */
interface IScopeView {
  /**
   * What `$name` reads here (F1-01). The nearest `set` or parameter binds (rule 2); an extension block's value wins
   * over every `set` inside the files it splices (rule 8), but not over a parameter nearer than it. `nearest` is the
   * nearest `set` value an inner scope already found.
   */
  lookup(name: string, nearest?: readonly Argument[]): IBinding | undefined;
  snippet(name: string): ISnippet | undefined;
}

/** A block's scope: it claims names for the one-per-block checks and binds them. */
interface IBlockScope extends IScopeView {
  /** Claim `name` for this block's one `set`; false when a `set` already claimed it here. */
  claim(name: string): boolean;
  bind(name: string, values: readonly Argument[]): void;
  /** Define a snippet in this block; false when this block already defines one of that name. */
  define(snippet: ISnippet): boolean;
}

/** The variables and snippets of one block: its own lines so far, then the enclosing view's. */
export class Scope implements IBlockScope {
  private readonly vars = new Map<string, readonly Argument[]>();
  private readonly params = new Map<string, readonly Argument[]>();
  private readonly claimed = new Set<string>();
  private readonly snippets = new Map<string, ISnippet>();

  constructor(private readonly outer: IScopeView | undefined) {}

  lookup(name: string, nearest?: readonly Argument[]): IBinding | undefined {
    let found = nearest;
    if (found === undefined) {
      const param = this.params.get(name);
      if (param !== undefined) return { values: param, parameter: true };
      found = this.vars.get(name);
    }
    if (this.outer !== undefined) return this.outer.lookup(name, found);
    return found === undefined ? undefined : { values: found, parameter: false };
  }

  snippet(name: string): ISnippet | undefined {
    return this.snippets.get(name) ?? this.outer?.snippet(name);
  }

  claim(name: string): boolean {
    if (this.claimed.has(name)) return false;
    this.claimed.add(name);
    return true;
  }

  bind(name: string, values: readonly Argument[]): void {
    this.vars.set(name, values);
  }

  /** Bind a snippet parameter: the body block's own binding of that name (S3-03). */
  param(name: string, values: readonly Argument[]): void {
    this.claimed.add(name);
    this.params.set(name, values);
  }

  define(snippet: ISnippet): boolean {
    if (this.snippets.has(snippet.name)) return false;
    this.snippets.set(snippet.name, snippet);
    return true;
  }

  /** The variables this block bound itself (an extension block's `set` lines). */
  own(): ReadonlyMap<string, readonly Argument[]> {
    return this.vars;
  }
}

/**
 * The including block's scope as a spliced file sees it: the file's top-level `set` and `snippet` lines claim, bind
 * and define in the including block (L2), and inside the spliced files the extension block's `set` lines win over
 * every `set` of the files, at any depth, but not over a parameter (rule 8, F1-01). After the extension line the
 * including block sees the file's own values (S3-05).
 */
class SpliceScope implements IBlockScope {
  constructor(
    private readonly target: IBlockScope,
    private readonly overrides: ReadonlyMap<string, readonly Argument[]>,
  ) {}

  lookup(name: string, nearest?: readonly Argument[]): IBinding | undefined {
    const forced = this.overrides.get(name);
    return forced === undefined ? this.target.lookup(name, nearest) : { values: forced, parameter: false };
  }

  snippet(name: string): ISnippet | undefined {
    return this.target.snippet(name);
  }

  claim(name: string): boolean {
    return this.target.claim(name);
  }

  bind(name: string, values: readonly Argument[]): void {
    this.target.bind(name, values);
  }

  define(snippet: ISnippet): boolean {
    return this.target.define(snippet);
  }
}

/** What one container (the top level or a block) holds after expansion. */
export interface IContainer {
  readonly body: IDirective[];
  readonly unreadable: IUnreadable[];
}

/** One place statements are expanded into: everything a statement needs to know about where it stands. */
interface IPlaceContext {
  readonly text: IText;
  readonly scope: IBlockScope;
  /** The steps that brought this text here, innermost first. */
  readonly via: readonly IStep[];
  /** The snippets and files being expanded around this place, outermost first; the root file is the first. */
  readonly open: readonly (ISnippet | string)[];
  readonly parent: Directive | undefined;
  readonly into: IContainer;
  /** Same-name-and-key counts of the container, shared by everything spliced into it. */
  readonly occurrences: Map<string, number>;
}

export class Expander {
  /** Load diagnostics in the order expansion meets them. */
  readonly diagnostics: ILocatedDiagnostic[] = [];
  /** Every file read, in first-read order (the root first). */
  readonly nodes = new Map<string, IDocumentNode>();
  readonly edges: IDocumentEdge[] = [];
  /** What the key rule saw of each directive, so a child's key input can name its parent's. */
  private readonly keyInputs = new WeakMap<Directive, IKeyInput>();
  /** One read per resolvedPath per load (R21), failures included. */
  private readonly reads = new Map<string, Promise<IText>>();
  private readonly extensions: ReadonlyMap<string, IExtension>;
  private count = 0;
  private stopped = false;

  constructor(
    private readonly source: IDocumentSource,
    extensions: readonly IExtension[],
    /** Values handed in by the program, each already read; they win over every `set` (L3). */
    private readonly handed: ReadonlyMap<string, readonly Argument[]>,
    private readonly key: KeyRule | undefined,
  ) {
    this.extensions = new Map(extensions.map((extension) => [extension.directive, extension]));
  }

  /** Read and parse a file once per load (R21); a rejection is kept, so a failed path is not read again either. */
  read(resolvedPath: string): Promise<IText> {
    let read = this.reads.get(resolvedPath);
    if (read === undefined) {
      read = this.source.read(resolvedPath).then((text) => {
        const syntax = parse(text);
        this.nodes.set(resolvedPath, { resolvedPath, source: text, syntax });
        return fileText(resolvedPath, syntax);
      });
      this.reads.set(resolvedPath, read);
    }
    return read;
  }

  /** Expand a whole file as the top level. */
  async root(text: IText, into: IContainer): Promise<void> {
    await this.statements(text.syntax.root, {
      text,
      scope: new Scope(undefined),
      via: [],
      open: [text.resolvedPath],
      parent: undefined,
      into,
      occurrences: new Map(),
    });
  }

  /** Expand the statements of `scopeNode` (a document or block node) at `context`. */
  private async statements(scopeNode: INode, context: IPlaceContext): Promise<void> {
    for (const node of scopeNode.children) {
      if (this.stopped) return;
      if (node.kind === NodeKind.Error) {
        context.into.unreadable.push(this.unreadable(context, node, UnreadableKind.Syntax));
        continue;
      }
      if (node.kind !== NodeKind.Directive) continue;
      try {
        await this.statement(node, context);
      } catch (error) {
        if (!(error instanceof Problem)) throw error;
        if (error.diagnostic !== undefined) this.diagnostics.push(error.diagnostic);
        context.into.unreadable.push(this.unreadable(context, node, error.kind));
      }
    }
  }

  /** One directive node: a reserved line does its work; any other becomes a directive and its block is expanded. */
  private async statement(node: INode, context: IPlaceContext): Promise<void> {
    const { tokens } = context.text.syntax;
    const anatomy = anatomyOf(tokens, node);
    const name = tokens[anatomy.name];
    if (name === undefined) throw new Error("a directive node has no name token");
    if (name.text === "set") return this.set(anatomy, name, context.text, context.scope, context.via);
    if (name.text === "snippet") return this.snippet(anatomy, name, context);
    if (name.text === "use") return this.use(anatomy, name, context);
    const extension = this.extensions.get(name.text);
    if (extension !== undefined) return this.extension(extension, anatomy, name, context);

    const { text, scope, via, parent, occurrences } = context;
    const args = anatomy.args.flatMap((ref) => this.value(text, ref, scope, via));
    if (++this.count > MAX_DIRECTIVES) {
      this.stopped = true;
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.TooManyDirectives, text, name.span, via, `more than ${String(MAX_DIRECTIVES)}`);
    }
    const hasBlock = anatomy.block !== undefined;
    const keyInput: IKeyInput = { name: name.text, args, hasBlock, parent: parent === undefined ? undefined : this.keyInputs.get(parent) };
    const key = this.key?.(keyInput);
    const slot = JSON.stringify([name.text, key ?? null]);
    const occurrence = occurrences.get(slot) ?? 0;
    occurrences.set(slot, occurrence + 1);
    const address = new Address(parent?.address, { name: name.text, key, occurrence });
    const origin = { written: text.place(name.span), via };
    const directive = new Directive(name.text, args, hasBlock, parent, address, origin, node);
    this.keyInputs.set(directive, keyInput);
    context.into.body.push(directive);
    if (anatomy.block === undefined || directive.body === undefined) return;
    await this.statements(anatomy.block, {
      text,
      scope: new Scope(scope),
      via,
      open: context.open,
      parent: directive,
      into: { body: directive.body, unreadable: directive.unreadable },
      occurrences: new Map(),
    });
  }

  /** `set $name value...;` (rule 2): binds from this line to the end of the enclosing block. */
  private set(anatomy: IDirectiveAnatomy, name: IToken, text: IText, scope: IBlockScope, via: readonly IStep[]): void {
    const { tokens } = text.syntax;
    const [first, ...values] = anatomy.args;
    const variable = typeof first === "number" ? tokens[first] : undefined;
    if (variable?.kind !== TokenKind.Variable || values.length === 0 || anatomy.block !== undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.BadSet, text, name.span, via);
    }
    const variableName = variable.text.slice(1);
    if (!scope.claim(variableName)) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.VariableSetTwice, text, variable.span, via, variable.text);
    }
    const bound = values.flatMap((ref) => this.value(text, ref, scope, via));
    // Stored without this line's own steps; a reader adds the variable step and its own (Argument.rebase).
    scope.bind(variableName, bound.map((value) => value.rebase(via.length, [])));
  }

  /** `snippet name $param... { body }` (rule 5): visible from this line to the end of its block. */
  private snippet(anatomy: IDirectiveAnatomy, keyword: IToken, context: IPlaceContext): void {
    const { text, scope, via } = context;
    const { tokens } = text.syntax;
    const [first, ...rest] = anatomy.args;
    const name = typeof first === "number" ? tokens[first] : undefined;
    const params: string[] = [];
    for (const ref of rest) {
      const token = typeof ref === "number" ? tokens[ref] : undefined;
      if (token?.kind !== TokenKind.Variable || params.includes(token.text.slice(1))) {
        throw this.problem(UnreadableKind.Expansion, DiagnosticCode.BadSnippet, text, keyword.span, via);
      }
      params.push(token.text.slice(1));
    }
    if (name?.kind !== TokenKind.Word || anatomy.block === undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.BadSnippet, text, keyword.span, via);
    }
    const snippet: ISnippet = { name: name.text, params, body: anatomy.block, text, scope };
    if (!scope.define(snippet)) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.SnippetDefinedTwice, text, name.span, via, name.text);
    }
  }

  /** `use name value...;` (rule 6): the snippet's body, spliced in place with its parameters bound. */
  private async use(anatomy: IDirectiveAnatomy, keyword: IToken, context: IPlaceContext): Promise<void> {
    const { text, scope, via, open } = context;
    const { tokens } = text.syntax;
    const [first, ...rest] = anatomy.args;
    const name = typeof first === "number" ? tokens[first] : undefined;
    if (name?.kind !== TokenKind.Word || anatomy.block !== undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.BadUse, text, keyword.span, via);
    }
    const snippet = scope.snippet(name.text);
    if (snippet === undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.UnknownSnippet, text, name.span, via, name.text);
    }
    const values = rest.flatMap((ref) => this.value(text, ref, scope, via));
    if (values.length !== snippet.params.length) {
      const detail = `${name.text} takes ${String(snippet.params.length)}, given ${String(values.length)}`;
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.SnippetArity, text, keyword.span, via, detail);
    }
    if (open.includes(snippet)) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.ExpansionCycle, text, keyword.span, via, name.text);
    }
    this.checkDepth(open, text, keyword, via);
    // Parameters are the body block's own bindings (a `set` of one there is E5002, S3-03), stored without the use
    // line's steps, as a `set` stores its values.
    const body = new Scope(snippet.scope);
    snippet.params.forEach((param, i) => {
      const value = values[i];
      if (value !== undefined) body.param(param, [value.rebase(via.length, [])]);
    });
    const step: IStep = { kind: StepKind.Use, name: name.text, at: text.place(keyword.span) };
    await this.statements(snippet.body, {
      ...context,
      text: snippet.text,
      scope: body,
      via: [step, ...via],
      open: [...open, snippet],
    });
  }

  /** An extension directive (rules 7 and 8): the files its specs name, spliced in place. */
  private async extension(extension: IExtension, anatomy: IDirectiveAnatomy, name: IToken, context: IPlaceContext): Promise<void> {
    const { text, scope, via, open } = context;
    const args = anatomy.args.flatMap((ref) => this.value(text, ref, scope, via));
    const overrides = this.extensionBlock(anatomy.block, text, scope, via);
    const origin: IDirectiveOrigin = { written: text.place(name.span), via };
    const fail = (code: DiagnosticCode, detail: string): Problem =>
      this.problem(UnreadableKind.Extension, code, text, name.span, via, detail);
    let specs: readonly string[];
    try {
      specs = [...extension.specs({ args, origin })];
    } catch (error) {
      if (error instanceof DiagnosticError) throw new Problem(UnreadableKind.Extension, error.diagnostic);
      throw fail(DiagnosticCode.ExtensionFailed, `${name.text}: ${reasonOf(error)}`);
    }
    const targets: string[] = [];
    this.edges.push({ directive: name.text, origin, specs, targets });
    const found: string[] = [];
    for (const spec of specs) {
      let paths: readonly string[];
      try {
        paths = await this.source.resolve(spec, { parentPath: text.resolvedPath });
      } catch (error) {
        throw fail(DiagnosticCode.IncludeResolverFailed, `${spec}: ${reasonOf(error)}`);
      }
      if (paths.length === 0) throw fail(DiagnosticCode.IncludeNotFound, spec);
      found.push(...[...paths].sort(compareCodePoints));
    }
    const cycle = found.find((path) => open.includes(path));
    if (cycle !== undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.ExpansionCycle, text, name.span, via, cycle);
    }
    this.checkDepth(open, text, name, via);
    const files: IText[] = [];
    for (const path of found) {
      try {
        files.push(await this.read(path));
      } catch (error) {
        throw fail(DiagnosticCode.IncludeResolverFailed, `${path}: ${reasonOf(error)}`);
      }
    }
    targets.push(...found);
    const step: IStep = { kind: StepKind.Extension, name: name.text, at: text.place(name.span) };
    const spliced = new SpliceScope(scope, overrides);
    for (const file of files) {
      await this.statements(file.syntax.root, {
        ...context,
        text: file,
        scope: spliced,
        via: [step, ...via],
        open: [...open, file.resolvedPath],
      });
    }
  }

  /** An extension directive's block: only `set` lines (E5012), bound for the spliced files. */
  private extensionBlock(
    block: INode | undefined,
    text: IText,
    scope: IBlockScope,
    via: readonly IStep[],
  ): ReadonlyMap<string, readonly Argument[]> {
    if (block === undefined) return new Map();
    const own = new Scope(scope);
    const { tokens } = text.syntax;
    for (const node of block.children) {
      // Already reported by the parser; the broken line may be a `set` the files need, so the include is unreadable.
      if (node.kind === NodeKind.Error) throw new Problem(UnreadableKind.Syntax, undefined);
      if (node.kind !== NodeKind.Directive) continue;
      const anatomy = anatomyOf(tokens, node);
      const name = tokens[anatomy.name];
      if (name === undefined) throw new Error("a directive node has no name token");
      // Kind `extension` (S3-07), placed at the line's name as every other directive-level code is (F1-02).
      if (name.text !== "set") {
        throw this.problem(UnreadableKind.Extension, DiagnosticCode.ExtensionBlockNotSet, text, name.span, via);
      }
      this.set(anatomy, name, text, own, via);
    }
    return own.own();
  }

  /** Rule 9's depth, checked after the cycle check (S3-10): a `use` or extension directive 17 places deep is E5007. */
  private checkDepth(open: readonly (ISnippet | string)[], text: IText, name: IToken, via: readonly IStep[]): void {
    // `open` holds the root file and every expansion around this place, so its length is this expansion's depth.
    if (open.length > MAX_DEPTH) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.ExpansionTooDeep, text, name.span, via, `more than ${String(MAX_DEPTH)}`);
    }
  }

  /** One written value, expanded: a `$name` becomes all its values (rule 4); a list's items expand the same way. */
  value(text: IText, ref: ValueRef, scope: IScopeView, via: readonly IStep[]): Argument[] {
    const { syntax } = text;
    const origin = { written: text.written(spanOfRef(syntax, ref)), via };
    if (typeof ref !== "number") {
      if (ref.kind === NodeKind.List) {
        const items = itemsOf(syntax.tokens, ref).flatMap((item) => this.value(text, item, scope, via));
        return [new Argument({ kind: ValueKind.List, items }, origin)];
      }
      return [this.slice(text, ref, scope, via)];
    }
    const token = syntax.tokens[ref];
    if (token === undefined) throw new Error(`no token ${String(ref)}`);
    switch (token.kind) {
      case TokenKind.Word:
        return [new Argument({ kind: ValueKind.Word, text: token.text }, origin)];
      case TokenKind.String:
        if (!hasOnlyKnownEscapes(token.text)) {
          throw this.problem(UnreadableKind.Value, DiagnosticCode.BadEscape, text, token.span, via, token.text);
        }
        return [new Argument({ kind: ValueKind.String, value: decodeString(token.text) }, origin)];
      case TokenKind.Variable:
        return this.variable(text, token.text, token.span, scope, via);
      default:
        throw new Error(`not a value token: ${token.kind}`);
    }
  }

  /** `$name`'s values as read at `span`: each with the variable step, then the reading place's steps. */
  private variable(text: IText, written: string, span: ISourceSpan, scope: IScopeView, via: readonly IStep[]): Argument[] {
    const name = written.slice(1);
    const binding = scope.lookup(name);
    // A handed-in value wins over every `set` (rule 3), never over a parameter the `use` line passed (F1-01).
    const values = binding?.parameter === true ? binding.values : (this.handed.get(name) ?? binding?.values);
    if (values === undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.UnknownVariable, text, span, via, written);
    }
    const step: IStep = { kind: StepKind.Variable, name, at: text.place(span) };
    return values.map((value) => value.rebase(0, [step, ...via]));
  }

  /** `name[bounds]`: each bound a literal IntegerText or a variable holding exactly one (rules 4 and 10). */
  private slice(text: IText, node: INode, scope: IScopeView, via: readonly IStep[]): Argument {
    const { tokens } = text.syntax;
    const name = tokens[node.start];
    const inner = tokens.slice(node.start + 2, node.end - 1);
    if (name === undefined) throw new Error("a slice node has no name token");
    const bound = (index: number): number | undefined => {
      const token = inner[index];
      return token === undefined ? undefined : this.bound(text, token.text, token.kind, token.span, scope, via);
    };
    const origin = { written: text.written(spanOf(text.syntax, node)), via };
    const colon = inner.findIndex((t) => t.kind === TokenKind.Colon);
    if (colon < 0) {
      return new Argument({ kind: ValueKind.Index, name: name.text, index: bound(0) ?? 0 }, origin);
    }
    const start = colon === 0 ? undefined : bound(0);
    const end = colon + 1 < inner.length ? bound(colon + 1) : undefined;
    return new Argument(
      { kind: ValueKind.Slice, name: name.text, ...(start === undefined ? {} : { start }), ...(end === undefined ? {} : { end }) },
      origin,
    );
  }

  /** One slice bound's integer. E4001 at the bound, or for a variable at its value's place via the variable. */
  private bound(text: IText, written: string, kind: TokenKind, span: ISourceSpan, scope: IScopeView, via: readonly IStep[]): number {
    if (kind === TokenKind.Word) {
      const value = integerOf(written);
      if (value === undefined) throw this.problem(UnreadableKind.Value, DiagnosticCode.NonIntegerBound, text, span, via, written);
      return value;
    }
    const values = this.variable(text, written, span, scope, via);
    const [only] = values;
    const word = values.length === 1 ? only?.wordText : undefined;
    const value = word === undefined ? undefined : integerOf(word);
    if (value !== undefined) return value;
    const at = only?.origin.written;
    if (at === undefined || at.kind === "handed") {
      // A handed-in value is written in no file: the problem is placed on the `$name` that used it.
      throw this.problem(UnreadableKind.Value, DiagnosticCode.NonIntegerBound, text, span, via, written);
    }
    throw new Problem(UnreadableKind.Value, {
      code: DiagnosticCode.NonIntegerBound,
      message: `${messageOf(DiagnosticCode.NonIntegerBound)}: ${written} is ${only?.text ?? ""}`,
      at,
      via: only?.origin.via ?? [],
    });
  }

  private problem(
    kind: UnreadableKind,
    code: DiagnosticCode,
    text: IText,
    span: ISourceSpan,
    via: readonly IStep[],
    detail?: string,
  ): Problem {
    const message = detail === undefined ? messageOf(code) : `${messageOf(code)}: ${detail}`;
    return new Problem(kind, { code, message, at: text.place(span), via });
  }

  private unreadable(context: IPlaceContext, node: INode, kind: UnreadableKind): IUnreadable {
    return { kind, origin: { written: context.text.place(spanOf(context.text.syntax, node)), via: context.via }, node };
  }
}

function spanOfRef(syntax: ISyntax, ref: ValueRef): ISourceSpan {
  return typeof ref === "number" ? spanOf(syntax, { start: ref, end: ref + 1 }) : spanOf(syntax, ref);
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
