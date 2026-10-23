/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * The directive-level facade over ISyntax (layer 3; port of reference/rasl-config-ts/src/ast.ts).
 * Read-only: it never changes the syntax it wraps.
 */

import type { ISourceSpan } from "../span.js";
import type { INode, ISyntax, ValueRef } from "../syntax/cst.js";
import type { Value } from "../value.js";

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
  throw new Error("not implemented");
}

/** `createAst(parse(text))`: the synchronous single-document entry point (vil-m8w). Never throws. */
export function parseDocument(text: string): IAstDocument {
  throw new Error("not implemented");
}

/** Visit every directive depth-first, in source order; `parent` is undefined at the top level. */
export function walkDirectives(
  document: IAstDocument,
  visitor: (directive: IAstDirective, parent: IAstDirective | undefined) => void,
): void {
  throw new Error("not implemented");
}

/** Every directive named `name` at any depth, in walkDirectives order. */
export function findDirectives(document: IAstDocument, name: string): readonly IAstDirective[] {
  throw new Error("not implemented");
}
