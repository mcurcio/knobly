/**
 * Part of the adapter (see parse.ts): turns ANTLR's parse tree into our CST. Concept rules become nodes over token
 * ranges; grammar-internal rules are transparent. Ported from design/experiments/v4/antlr/ts/cst.ts.
 */

import KnoblyParser from "../gen/KnoblyParser.js";
import type { Node } from "../gen/api/syntax.js";
import { NodeKind } from "../gen/api/kinds.js";


/** The parts of an ANTLR token the walk reads (antlr4's typings are incomplete; the cast lives in parse.ts). */
export interface AntlrToken {
  readonly type: number;
  readonly tokenIndex: number;
  readonly text: string;
}

/** The parts of an ANTLR parse-tree node the walk reads: a rule context or a terminal (error) node. */
export interface AntlrTree {
  /** Set on terminal nodes only. */
  readonly symbol?: AntlrToken;
  readonly ruleIndex?: number;
  readonly children?: readonly AntlrTree[] | null;
  readonly parentCtx?: unknown;
  /** Set on rule contexts: the first token the rule saw. */
  readonly start?: AntlrToken;
  /** Set on rule contexts: the recognition error the rule ended with, or null. */
  readonly exception?: unknown;
  /** Present (and true) on error nodes only; antlr4's plain terminal nodes do not define it. */
  isErrorNode?(): boolean;
}

/** Grammar rule name -> concept node kind. Every other rule is transparent. */
const CONCEPTS: Readonly<Record<string, NodeKind>> = {
  document: "document",
  directive: "directive",
  block: "block",
  slicedWord: "slice",
  list: "list",
};

/** Rule index -> concept kind, built once; throws at load if the grammar lost a concept rule. */
const CONCEPT_BY_RULE: ReadonlyMap<number, NodeKind> = new Map(
  Object.entries(CONCEPTS).map(([rule, kind]) => {
    const index = KnoblyParser.ruleNames.indexOf(rule);
    if (index < 0) throw new Error(`grammar has no rule "${rule}" for CST node kind "${kind}"`);
    return [index, kind];
  }),
);

/**
 * A walk item in source order: a concept node, an error run (error terminals, or a broken statement: spec 3.2), or a
 * plain terminal.
 */
type Item =
  | { readonly tag: "node"; readonly node: Node }
  | { readonly tag: "error"; readonly start: number; readonly end: number; readonly parent: unknown }
  | { readonly tag: "token"; readonly index: number };

const BLOCK_RULE = KnoblyParser.ruleNames.indexOf("block");

/** EOF (type -1) and tokens conjured by error recovery (tokenIndex < 0) are not source tokens. */
function isSourceToken(token: AntlrToken): boolean {
  return token.type !== -1 && token.tokenIndex >= 0;
}

function items(tree: AntlrTree): Item[] {
  if (tree.symbol !== undefined) {
    if (!isSourceToken(tree.symbol)) return [];
    const index = tree.symbol.tokenIndex;
    return [tree.isErrorNode?.() === true ? { tag: "error", start: index, end: index + 1, parent: tree.parentCtx } : { tag: "token", index }];
  }
  const kids = (tree.children ?? []).flatMap(items);
  const kind = tree.ruleIndex === undefined ? undefined : CONCEPT_BY_RULE.get(tree.ruleIndex);
  if (kind === undefined) return kids;
  const node = makeNode(kind, kids, tree);
  // A directive that ended with a recognition error before any block is a broken statement: it folds into one error
  // node with the tokens recovery skipped after it (spec 3.2). One whose block was entered keeps its node.
  const broken =
    kind === NodeKind.Directive && tree.exception != null && !(tree.children ?? []).some((child) => child.ruleIndex === BLOCK_RULE);
  return broken ? [{ tag: "error", start: node.start, end: node.end, parent: tree.parentCtx }] : [{ tag: "node", node }];
}

function makeNode(kind: NodeKind, kids: readonly Item[], ctx: AntlrTree): Node {
  const children: Node[] = [];
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < kids.length; i++) {
    const kid = kids[i];
    if (kid === undefined) continue;
    if (kid.tag === "error") {
      // A run of error items under one parse-tree parent becomes one error node.
      let last = kid;
      for (let next = kids[i + 1]; next?.tag === "error" && next.parent === kid.parent; next = kids[i + 1]) {
        last = next;
        i++;
      }
      children.push({ kind: "error", start: kid.start, end: last.end, children: [] });
      lo = Math.min(lo, kid.start);
      hi = Math.max(hi, last.end);
    } else if (kid.tag === "token") {
      lo = Math.min(lo, kid.index);
      hi = Math.max(hi, kid.index + 1);
    } else {
      children.push(kid.node);
      lo = Math.min(lo, kid.node.start);
      hi = Math.max(hi, kid.node.end);
    }
  }
  if (lo === Infinity) lo = hi = ctx.start?.tokenIndex ?? 0;
  return { kind, start: lo, end: hi, children };
}

/** The CST of a `document` parse tree. */
export function toCst(document: AntlrTree): Node {
  const [root] = items(document);
  if (root?.tag !== "node" || root.node.kind !== NodeKind.Document) throw new Error("parse tree root is not a document");
  return root.node;
}

/** The CST of an entry rule's parse tree: a `document` node over all `count` tokens, its concept nodes as children. */
export function toEntryCst(tree: AntlrTree, count: number): Node {
  const children = items(tree).flatMap((item) => (item.tag === "node" ? [item.node] : []));
  return { kind: "document", start: 0, end: count, children };
}
