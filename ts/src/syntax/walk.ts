/**
 * Part of the adapter (see parse.ts): turns ANTLR's parse tree into our CST. Concept rules become nodes over token
 * ranges; grammar-internal rules are transparent. Ported from design/experiments/v4/antlr/ts/cst.ts.
 */

import VillanelleParser from "../gen/VillanelleParser.js";

import type { NodeKind } from "./cst.js";
import { type INode } from "./cst.js";

/** The parts of an ANTLR token the walk reads (antlr4's typings are incomplete; the cast lives in parse.ts). */
export interface IAntlrToken {
  readonly type: number;
  readonly tokenIndex: number;
  readonly text: string;
}

/** The parts of an ANTLR parse-tree node the walk reads: a rule context or a terminal (error) node. */
export interface IAntlrTree {
  /** Set on terminal nodes only. */
  readonly symbol?: IAntlrToken;
  readonly ruleIndex?: number;
  readonly children?: readonly IAntlrTree[] | null;
  readonly parentCtx?: unknown;
  /** Set on rule contexts: the first token the rule saw. */
  readonly start?: IAntlrToken;
  /** Present (and true) on error nodes only; antlr4's plain terminal nodes do not define it. */
  isErrorNode?(): boolean;
}

/** Grammar rule name -> concept node kind. Every other rule is transparent. */
const CONCEPTS: Readonly<Record<string, NodeKind>> = {
  document: "document",
  directive: "directive",
  lastDirective: "directive",
  block: "block",
  slicedWord: "slice",
  list: "list",
};

/** Rule index -> concept kind, built once; throws at load if the grammar lost a concept rule. */
const CONCEPT_BY_RULE: ReadonlyMap<number, NodeKind> = new Map(
  Object.entries(CONCEPTS).map(([rule, kind]) => {
    const index = VillanelleParser.ruleNames.indexOf(rule);
    if (index < 0) throw new Error(`grammar has no rule "${rule}" for CST node kind "${kind}"`);
    return [index, kind];
  }),
);

/** A walk item in source order: a concept node, an error terminal, or a plain terminal. */
type Item =
  | { readonly tag: "node"; readonly node: INode }
  | { readonly tag: "error"; readonly index: number; readonly parent: unknown }
  | { readonly tag: "token"; readonly index: number };

/** EOF (type -1) and tokens conjured by error recovery (tokenIndex < 0) are not source tokens. */
function isSourceToken(token: IAntlrToken): boolean {
  return token.type !== -1 && token.tokenIndex >= 0;
}

function items(tree: IAntlrTree): Item[] {
  if (tree.symbol !== undefined) {
    if (!isSourceToken(tree.symbol)) return [];
    const index = tree.symbol.tokenIndex;
    return [tree.isErrorNode?.() === true ? { tag: "error", index, parent: tree.parentCtx } : { tag: "token", index }];
  }
  const kids = (tree.children ?? []).flatMap(items);
  const kind = tree.ruleIndex === undefined ? undefined : CONCEPT_BY_RULE.get(tree.ruleIndex);
  return kind === undefined ? kids : [{ tag: "node", node: makeNode(kind, kids, tree) }];
}

function makeNode(kind: NodeKind, kids: readonly Item[], ctx: IAntlrTree): INode {
  const children: INode[] = [];
  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < kids.length; i++) {
    const kid = kids[i];
    if (kid === undefined) continue;
    if (kid.tag === "error") {
      // A run of error terminals under one parse-tree parent becomes one error node.
      let last = kid;
      for (let next = kids[i + 1]; next?.tag === "error" && next.parent === kid.parent; next = kids[i + 1]) {
        last = next;
        i++;
      }
      children.push({ kind: "error", start: kid.index, end: last.index + 1, children: [] });
      lo = Math.min(lo, kid.index);
      hi = Math.max(hi, last.index + 1);
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
export function toCst(document: IAntlrTree): INode {
  const [root] = items(document);
  if (root?.tag !== "node" || root.node.kind !== "document") throw new Error("parse tree root is not a document");
  return root.node;
}
