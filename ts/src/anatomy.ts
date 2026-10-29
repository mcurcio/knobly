/**
 * Directive anatomy (vil-g7n.1.3): which parts of a `directive` node are its name, its values and its block.
 * The one home of this rule; Python ports it. Package-internal, shared.
 */

import { type INode, NodeKind, type ValueRef } from "./syntax/cst.js";
import type { IToken } from "./syntax/tokens.js";
import { TokenKind } from "./syntax/tokens.js";

export interface IDirectiveAnatomy {
  /** Index of the name token (`node.start`, a WORD). */
  readonly name: number;
  /** In source order: each WORD, STRING or VARIABLE token directly in the directive's range, and each slice or list child. */
  readonly values: readonly ValueRef[];
  /** The block child, when there is one. */
  readonly block: INode | undefined;
}

const VALUE_TOKENS: ReadonlySet<string> = new Set([TokenKind.Word, TokenKind.String, TokenKind.Variable]);
const VALUE_NODES: ReadonlySet<string> = new Set([NodeKind.Slice, NodeKind.List]);

/**
 * Split a directive node. Tokens after the name that no child covers are values when they are WORD, STRING or VARIABLE;
 * spaces, comments, separators and punctuation are not. Error children are never values.
 */
export function anatomyOf(tokens: readonly IToken[], node: INode): IDirectiveAnatomy {
  const { values, block } = split(tokens, node);
  return { name: node.start, values, block };
}

/** A `list` node's items in source order, by the same rule as a directive's values (the brackets come first). */
export function itemsOf(tokens: readonly IToken[], list: INode): readonly ValueRef[] {
  return split(tokens, list).values;
}

/** The value references and the block child of a directive or list node, after its first token. */
function split(tokens: readonly IToken[], node: INode): { values: ValueRef[]; block: INode | undefined } {
  const values: ValueRef[] = [];
  let block: INode | undefined;
  let next = 0;
  for (let i = node.start + 1; i < node.end; ) {
    const child = node.children[next];
    if (child !== undefined && child.start === i) {
      if (VALUE_NODES.has(child.kind)) values.push(child);
      else if (child.kind === NodeKind.Block) block = child;
      next++;
      i = Math.max(child.end, i + 1);
      continue;
    }
    const kind = tokens[i]?.kind;
    if (kind !== undefined && VALUE_TOKENS.has(kind)) values.push(i);
    i++;
  }
  return { values, block };
}
