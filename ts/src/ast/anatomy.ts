/**
 * Directive anatomy (vil-g7n.1.3): which parts of a `directive` node are its name, its values and its block.
 * The one home of this rule; the Python facade ports it.
 */

import { type INode, NodeKind, type ValueRef } from "../syntax/cst.js";
import type { IToken } from "../syntax/tokens.js";
import { TokenKind } from "../syntax/tokens.js";

export interface IDirectiveAnatomy {
  /** Index of the name token (`node.start`, a WORD). */
  readonly name: number;
  /** In source order: each WORD or STRING token directly in the directive's range, and each slice or list child. */
  readonly args: readonly ValueRef[];
  /** The block child, when there is one. */
  readonly block: INode | undefined;
}

const VALUE_TOKENS: ReadonlySet<string> = new Set([TokenKind.Word, TokenKind.String]);
const VALUE_NODES: ReadonlySet<string> = new Set([NodeKind.Slice, NodeKind.List]);

/**
 * Split a directive node. Tokens after the name that no child covers are values when they are WORD or STRING;
 * spaces, comments, separators and punctuation are not. Error children are never values.
 */
export function anatomyOf(tokens: readonly IToken[], node: INode): IDirectiveAnatomy {
  const args: ValueRef[] = [];
  let block: INode | undefined;
  let next = 0;
  for (let i = node.start + 1; i < node.end; ) {
    const child = node.children[next];
    if (child !== undefined && child.start === i) {
      if (VALUE_NODES.has(child.kind)) args.push(child);
      else if (child.kind === NodeKind.Block) block = child;
      next++;
      i = Math.max(child.end, i + 1);
      continue;
    }
    const kind = tokens[i]?.kind;
    if (kind !== undefined && VALUE_TOKENS.has(kind)) args.push(i);
    i++;
  }
  return { name: node.start, args, block };
}

/** The directive children of a scope (the document or a block), in source order; error nodes are skipped. */
export function directivesOf(scope: INode): readonly INode[] {
  return scope.children.filter((child) => child.kind === NodeKind.Directive);
}
