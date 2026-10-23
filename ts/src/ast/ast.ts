/**
 * The directive-level facade over ISyntax (layer 3; port of reference/rasl-config-ts/src/ast.ts).
 * Read-only: it never changes the syntax it wraps.
 */

import type { ISourceSpan } from "../span.js";
import { type INode, type ISyntax, type ITokenRange, spanOf, textOf, type ValueRef } from "../syntax/cst.js";
import { parse } from "../syntax/parse.js";
import { type Value, valueOf } from "../value.js";
import { anatomyOf, directivesOf } from "./anatomy.js";

/** A parsed document seen as directives. */
export interface IAstDocument {
  /** The syntax this facade wraps: tokens, tree and diagnostics. */
  readonly syntax: ISyntax;
  /** Top-level directives in source order. Error nodes are not directives and are skipped. */
  readonly children: IAstDirectiveList;
}

/**
 * Directives of one scope (the document or one block), in source order.
 * Identity: within one IAstDocument, every directive node yields one IAstDirective object, so `===` holds
 * between the results of any two accesses.
 */
export interface IAstDirectiveList extends Iterable<IAstDirective> {
  readonly length: number;
  /** Negative indexes count from the end, as Array.prototype.at does. */
  at(index: number): IAstDirective | undefined;
  toArray(): readonly IAstDirective[];
  find(predicate: (directive: IAstDirective) => boolean): IAstDirective | undefined;
  filter(predicate: (directive: IAstDirective) => boolean): readonly IAstDirective[];
  findByName(name: string): IAstDirective | undefined;
  filterByName(name: string): readonly IAstDirective[];
}

/** One value of a directive: a WORD or STRING token, a slice or a list. */
export interface IAstArgument {
  readonly ref: ValueRef;
  /** The value's exact source text. */
  readonly text: string;
  readonly span: ISourceSpan;
  /** `valueOf(document.syntax, ref)`, with the same errors. */
  value(): Value;
}

/** One directive: `name value... ;`, `name value...` at a line end, or `name value... { ... }`. */
export interface IAstDirective {
  readonly document: IAstDocument;
  /** The text of the directive's first token. */
  readonly name: string;
  /** The values after the name, in source order, without spaces, comments or punctuation. */
  readonly args: readonly IAstArgument[];
  /** The block's directives, or undefined when the directive has no block. */
  readonly body: IAstDirectiveList | undefined;
  /** From the name to the directive's last token (its `;`, its newline or its `}`). */
  readonly span: ISourceSpan;
  /** The underlying `directive` node. */
  readonly node: INode;
}

/** Wrap a syntax in the facade. Pure and cheap: directives are built on first access. */
export function createAst(syntax: ISyntax): IAstDocument {
  return new AstDocument(syntax);
}

/** `createAst(parse(text))`: the synchronous single-document entry point (vil-m8w). Never throws. */
export function parseDocument(text: string): IAstDocument {
  return createAst(parse(text));
}

/** Visit every directive depth-first, in source order; `parent` is undefined at the top level. */
export function walkDirectives(
  document: IAstDocument,
  visitor: (directive: IAstDirective, parent: IAstDirective | undefined) => void,
): void {
  const visit = (directive: IAstDirective, parent: IAstDirective | undefined): void => {
    visitor(directive, parent);
    for (const child of directive.body ?? []) visit(child, directive);
  };
  for (const child of document.children) visit(child, undefined);
}

/** Every directive named `name` at any depth, in walkDirectives order. */
export function findDirectives(document: IAstDocument, name: string): readonly IAstDirective[] {
  const found: IAstDirective[] = [];
  walkDirectives(document, (directive) => {
    if (directive.name === name) found.push(directive);
  });
  return found;
}

class AstDocument implements IAstDocument {
  readonly children: IAstDirectiveList;
  /** Identity: one AstDirective per directive node of this document. */
  readonly #directives = new WeakMap<INode, AstDirective>();

  constructor(readonly syntax: ISyntax) {
    this.children = new AstDirectiveList(this, directivesOf(syntax.root));
  }

  directive(node: INode): AstDirective {
    let directive = this.#directives.get(node);
    if (directive === undefined) {
      directive = new AstDirective(this, node);
      this.#directives.set(node, directive);
    }
    return directive;
  }
}

class AstDirectiveList implements IAstDirectiveList {
  readonly #document: AstDocument;
  readonly #nodes: readonly INode[];

  constructor(document: AstDocument, nodes: readonly INode[]) {
    this.#document = document;
    this.#nodes = nodes;
  }

  get length(): number {
    return this.#nodes.length;
  }

  at(index: number): IAstDirective | undefined {
    const node = this.#nodes.at(index);
    return node === undefined ? undefined : this.#document.directive(node);
  }

  toArray(): readonly IAstDirective[] {
    return this.#nodes.map((node) => this.#document.directive(node));
  }

  find(predicate: (directive: IAstDirective) => boolean): IAstDirective | undefined {
    for (const directive of this) if (predicate(directive)) return directive;
    return undefined;
  }

  filter(predicate: (directive: IAstDirective) => boolean): readonly IAstDirective[] {
    return this.toArray().filter(predicate);
  }

  findByName(name: string): IAstDirective | undefined {
    return this.find((directive) => directive.name === name);
  }

  filterByName(name: string): readonly IAstDirective[] {
    return this.filter((directive) => directive.name === name);
  }

  *[Symbol.iterator](): Iterator<IAstDirective> {
    for (const node of this.#nodes) yield this.#document.directive(node);
  }
}

class AstDirective implements IAstDirective {
  readonly name: string;
  readonly args: readonly IAstArgument[];
  readonly body: IAstDirectiveList | undefined;
  readonly span: ISourceSpan;

  constructor(
    readonly document: AstDocument,
    readonly node: INode,
  ) {
    const { syntax } = document;
    const anatomy = anatomyOf(syntax.tokens, node);
    this.name = syntax.tokens[anatomy.name]?.text ?? "";
    this.args = anatomy.args.map((ref) => new AstArgument(syntax, ref));
    this.body = anatomy.block === undefined ? undefined : new AstDirectiveList(document, directivesOf(anatomy.block));
    this.span = spanOf(syntax, node);
  }
}

class AstArgument implements IAstArgument {
  readonly text: string;
  readonly span: ISourceSpan;
  readonly #syntax: ISyntax;

  constructor(
    syntax: ISyntax,
    readonly ref: ValueRef,
  ) {
    this.#syntax = syntax;
    const range: ITokenRange = typeof ref === "number" ? { start: ref, end: ref + 1 } : ref;
    this.text = textOf(syntax, range);
    this.span = spanOf(syntax, range);
  }

  value(): Value {
    return valueOf(this.#syntax, this.ref);
  }
}
