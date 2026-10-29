/**
 * Directive anatomy (vil-g7n.1.3): which parts of a `directive` node are its name, its values and its block.
 * The one home of this rule; Python ports it. Package-internal, shared.
 */

import { type INode, type ValueRef } from "./syntax/cst.js";
import type { IToken } from "./syntax/tokens.js";

export interface IDirectiveAnatomy {
  /** Index of the name token (`node.start`, a WORD). */
  readonly name: number;
  /** In source order: each word (WORD, INTEGER, DIGIT_WORD), STRING or VARIABLE token directly in the directive's range, and each slice or list child. */
  readonly values: readonly ValueRef[];
  /** The block child, when there is one. */
  readonly block: INode | undefined;
}

const VALUE_TOKENS: ReadonlySet<string> = new Set(["WORD", "INTEGER", "DIGIT_WORD", "STRING", "VARIABLE"]);
const VALUE_NODES: ReadonlySet<string> = new Set(["slice", "list"]);

/**
 * Split a directive node. Tokens after the name that no child covers are values when they are words, STRING or VARIABLE;
 * spaces, comments, separators and punctuation are not. Error children are never values.
 */
export function anatomyOf(tokens: readonly IToken[], node: INode): IDirectiveAnatomy {
  const { values, block } = split(tokens, node, node.start + 1);
  return { name: node.start, values, block };
}

/** A `list` node's items in source order, by the same rule as a directive's values (the brackets come first). */
export function itemsOf(tokens: readonly IToken[], list: INode): readonly ValueRef[] {
  return split(tokens, list, list.start + 1).values;
}

/** The values of a text parsed with an entry rule (`parseEntry`): every value, by the same rule, from its first token. */
export function valuesOf(tokens: readonly IToken[], root: INode): readonly ValueRef[] {
  return split(tokens, root, root.start).values;
}

/** The value references and the block child of a node, from token `from`. */
function split(tokens: readonly IToken[], node: INode, from: number): { values: ValueRef[]; block: INode | undefined } {
  const values: ValueRef[] = [];
  let block: INode | undefined;
  let next = 0;
  for (let i = from; i < node.end; ) {
    const child = node.children[next];
    if (child !== undefined && child.start === i) {
      if (VALUE_NODES.has(child.kind)) values.push(child);
      else if (child.kind === "block") block = child;
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
