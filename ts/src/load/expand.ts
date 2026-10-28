/**
 * Expansion (slices.md §1.2): one file's tier-1 tree in, readable directives and unreadable statements out.
 * Private to the load layer. Covers reserved `set` (rule 1), `set` (2), handed-in values (3), `$name` (4), the
 * value rules checked at load (10), unreadable statements (11) and diagnostics order (12). `snippet`, `use` and
 * extension directives are not expanded yet: they read as ordinary directives.
 */

import { anatomyOf, itemsOf } from "../ast/anatomy.js";
import { DiagnosticCode } from "../diagnostics.js";
import type { ISourceSpan } from "../span.js";
import { type INode, type ISyntax, NodeKind, spanOf, type ValueRef } from "../syntax/cst.js";
import { messageOf } from "../syntax/recovery.js";
import { TokenKind } from "../syntax/tokens.js";
import { ValueKind } from "../value.js";
import { type IDirective, type IKeyInput, type IUnreadable, type KeyRule, UnreadableKind } from "./directive.js";
import { type IHanded, type IPlace, type IStep, StepKind } from "./origin.js";
import type { ILocatedDiagnostic } from "./report.js";
import { Address, Argument, Directive } from "./tree.js";
import { decodeString, hasOnlyKnownEscapes, integerOf } from "./values.js";

/** One text being expanded: a file, or a value handed in by the program. */
export interface IText {
  readonly syntax: ISyntax;
  /** Where a span of this text was written, for origins. */
  written(span: ISourceSpan): IPlace | IHanded;
  /** The file place of a span, for diagnostics (a handed-in text never reports: its problems are TypeErrors). */
  place(span: ISourceSpan): IPlace;
}

/** A text of the file at `resolvedPath`. */
export function fileText(resolvedPath: string, syntax: ISyntax): IText {
  const place = (span: ISourceSpan): IPlace => ({ kind: "file", resolvedPath, span });
  return { syntax, written: place, place };
}

/** A statement that cannot be read: thrown inside a statement, caught where the statement is kept unreadable. */
export class Problem extends Error {
  constructor(
    readonly kind: UnreadableKind,
    readonly diagnostic: ILocatedDiagnostic,
  ) {
    super(diagnostic.message);
    this.name = "Problem";
  }
}

/** The variables visible in one block: its own `set` lines so far, then the enclosing block's. */
export class Scope {
  private readonly bound = new Map<string, readonly Argument[]>();
  private readonly claimed = new Set<string>();

  constructor(private readonly outer: Scope | undefined) {}

  lookup(name: string): readonly Argument[] | undefined {
    return this.bound.get(name) ?? this.outer?.lookup(name);
  }

  /** Claim `name` for this block's one `set`; false when a `set` already claimed it here. */
  claim(name: string): boolean {
    if (this.claimed.has(name)) return false;
    this.claimed.add(name);
    return true;
  }

  bind(name: string, values: readonly Argument[]): void {
    this.bound.set(name, values);
  }
}

/** What one container (the top level or a block) holds after expansion. */
interface IContainer {
  readonly body: IDirective[];
  readonly unreadable: IUnreadable[];
}

export class Expander {
  /** Load diagnostics in the order expansion meets them. */
  readonly diagnostics: ILocatedDiagnostic[] = [];
  /** What the key rule saw of each directive, so a child's key input can name its parent's. */
  private readonly keyInputs = new WeakMap<Directive, IKeyInput>();

  constructor(
    /** Values handed in by the program, each already read; they win over every `set` (L3). */
    private readonly handed: ReadonlyMap<string, readonly Argument[]>,
    private readonly key: KeyRule | undefined,
  ) {}

  /** Expand the statements of `scopeNode` (a document or block node) into `into`. */
  container(
    text: IText,
    scopeNode: INode,
    scope: Scope,
    via: readonly IStep[],
    parent: Directive | undefined,
    into: IContainer,
  ): void {
    const occurrences = new Map<string, number>();
    for (const node of scopeNode.children) {
      if (node.kind === NodeKind.Error) {
        into.unreadable.push(this.unreadable(text, node, via, UnreadableKind.Syntax));
        continue;
      }
      if (node.kind !== NodeKind.Directive) continue;
      try {
        const directive = this.statement(text, node, scope, via, parent, occurrences);
        if (directive === undefined) continue;
        into.body.push(directive.directive);
        if (directive.block !== undefined) {
          const { body } = directive.directive;
          this.container(text, directive.block, new Scope(scope), via, directive.directive, {
            body: body ?? [],
            unreadable: directive.directive.unreadable,
          });
        }
      } catch (error) {
        if (!(error instanceof Problem)) throw error;
        this.diagnostics.push(error.diagnostic);
        into.unreadable.push(this.unreadable(text, node, via, error.kind));
      }
    }
  }

  /** One directive node: a `set` (nothing to return) or a readable directive and the block still to expand. */
  private statement(
    text: IText,
    node: INode,
    scope: Scope,
    via: readonly IStep[],
    parent: Directive | undefined,
    occurrences: Map<string, number>,
  ): { directive: Directive; block: INode | undefined } | undefined {
    const { tokens } = text.syntax;
    const anatomy = anatomyOf(tokens, node);
    const nameToken = tokens[anatomy.name];
    if (nameToken === undefined) throw new Error("a directive node has no name token");
    if (nameToken.text === "set") {
      this.set(text, node, scope, via);
      return undefined;
    }
    const args = anatomy.args.flatMap((ref) => this.value(text, ref, scope, via));
    const hasBlock = anatomy.block !== undefined;
    const keyInput: IKeyInput = { name: nameToken.text, args, hasBlock, parent: parent === undefined ? undefined : this.keyInputs.get(parent) };
    const key = this.key?.(keyInput);
    const slot = JSON.stringify([nameToken.text, key ?? null]);
    const occurrence = occurrences.get(slot) ?? 0;
    occurrences.set(slot, occurrence + 1);
    const address = new Address(parent?.address, { name: nameToken.text, key, occurrence });
    const origin = { written: text.place(nameToken.span), via };
    const directive = new Directive(nameToken.text, args, hasBlock, parent, address, origin, node);
    this.keyInputs.set(directive, keyInput);
    return { directive, block: anatomy.block };
  }

  /** `set $name value...;` (rule 2): binds from this line to the end of the enclosing block. */
  private set(text: IText, node: INode, scope: Scope, via: readonly IStep[]): void {
    const { tokens } = text.syntax;
    const { name, args, block } = anatomyOf(tokens, node);
    const [first, ...values] = args;
    const variable = typeof first === "number" ? tokens[first] : undefined;
    if (variable?.kind !== TokenKind.Variable || values.length === 0 || block !== undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.BadSet, text, spanOfRef(text.syntax, name), via, "");
    }
    const variableName = variable.text.slice(1);
    if (!scope.claim(variableName)) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.VariableSetTwice, text, variable.span, via, variable.text);
    }
    const bound = values.flatMap((ref) => this.value(text, ref, scope, via));
    // Stored without this line's own steps; a reader adds the variable step and its own (Argument.rebase).
    scope.bind(variableName, bound.map((value) => value.rebase(via.length, [])));
  }

  /** One written value, expanded: a `$name` becomes all its values (rule 4); a list's items expand the same way. */
  value(text: IText, ref: ValueRef, scope: Scope, via: readonly IStep[]): Argument[] {
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
  private variable(text: IText, written: string, span: ISourceSpan, scope: Scope, via: readonly IStep[]): Argument[] {
    const name = written.slice(1);
    const values = this.handed.get(name) ?? scope.lookup(name);
    if (values === undefined) {
      throw this.problem(UnreadableKind.Expansion, DiagnosticCode.UnknownVariable, text, span, via, written);
    }
    const step: IStep = { kind: StepKind.Variable, name, at: text.place(span) };
    return values.map((value) => value.rebase(0, [step, ...via]));
  }

  /** `name[bounds]`: each bound a literal IntegerText or a variable holding exactly one (rules 4 and 10). */
  private slice(text: IText, node: INode, scope: Scope, via: readonly IStep[]): Argument {
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
  private bound(text: IText, written: string, kind: TokenKind, span: ISourceSpan, scope: Scope, via: readonly IStep[]): number {
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
    detail: string,
  ): Problem {
    const message = detail === "" ? messageOf(code) : `${messageOf(code)}: ${detail}`;
    return new Problem(kind, { code, message, at: text.place(span), via });
  }

  private unreadable(text: IText, node: INode, via: readonly IStep[], kind: UnreadableKind): IUnreadable {
    return { kind, origin: { written: text.place(spanOf(text.syntax, node)), via }, node };
  }
}

function spanOfRef(syntax: ISyntax, ref: ValueRef): ISourceSpan {
  return typeof ref === "number" ? spanOf(syntax, { start: ref, end: ref + 1 }) : spanOf(syntax, ref);
}
