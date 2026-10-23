"""Part of the adapter (see parse.py): turns ANTLR's parse tree into our CST. Concept rules become nodes over token
ranges; grammar-internal rules are transparent. Ported from design/experiments/v4/antlr/py/cst.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from antlr4 import ParserRuleContext
from antlr4.tree.Tree import ErrorNode, TerminalNode

from villanelle._gen.VillanelleParser import VillanelleParser
from villanelle.syntax.cst import Node, NodeKind

# Grammar rule name -> concept node kind. Every other rule is transparent.
_CONCEPTS: dict[str, NodeKind] = {
    "document": NodeKind.DOCUMENT,
    "directive": NodeKind.DIRECTIVE,
    "lastDirective": NodeKind.DIRECTIVE,
    "block": NodeKind.BLOCK,
    "slicedWord": NodeKind.SLICE,
    "list": NodeKind.LIST,
}


def _concept_by_rule() -> dict[int, NodeKind]:
    """Rule index -> concept kind; raises at import if the grammar lost a concept rule."""
    rule_names: list[str] = list(VillanelleParser.ruleNames)
    by_rule: dict[int, NodeKind] = {}
    for rule, kind in _CONCEPTS.items():
        if rule not in rule_names:
            raise RuntimeError(f'grammar has no rule "{rule}" for CST node kind "{kind}"')
        by_rule[rule_names.index(rule)] = kind
    return by_rule


_CONCEPT_BY_RULE = _concept_by_rule()


@dataclass(frozen=True, slots=True)
class _NodeItem:
    node: Node


@dataclass(frozen=True, slots=True)
class _ErrorItem:
    index: int
    parent: object


@dataclass(frozen=True, slots=True)
class _TokenItem:
    index: int


_Item = _NodeItem | _ErrorItem | _TokenItem


def _items(tree: Any) -> list[_Item]:
    if isinstance(tree, TerminalNode):
        symbol = tree.symbol
        # EOF (type -1) and tokens conjured by error recovery (tokenIndex < 0) are not source tokens.
        if symbol.type == -1 or symbol.tokenIndex < 0:
            return []
        index: int = symbol.tokenIndex
        return [_ErrorItem(index, tree.parentCtx) if isinstance(tree, ErrorNode) else _TokenItem(index)]
    kids = [item for child in (tree.children or []) for item in _items(child)]
    kind = _CONCEPT_BY_RULE.get(tree.getRuleIndex())
    return kids if kind is None else [_NodeItem(_make_node(kind, kids, tree))]


def _make_node(kind: NodeKind, kids: list[_Item], ctx: ParserRuleContext) -> Node:
    children: list[Node] = []
    lo: int | None = None
    hi: int | None = None

    def cover(a: int, b: int) -> None:
        nonlocal lo, hi
        lo = a if lo is None else min(lo, a)
        hi = b if hi is None else max(hi, b)

    i = 0
    while i < len(kids):
        kid = kids[i]
        if isinstance(kid, _ErrorItem):
            # A run of error terminals under one parse-tree parent becomes one error node.
            last = kid
            while i + 1 < len(kids):
                nxt = kids[i + 1]
                if not (isinstance(nxt, _ErrorItem) and nxt.parent is kid.parent):
                    break
                last = nxt
                i += 1
            children.append(Node(NodeKind.ERROR, kid.index, last.index + 1, ()))
            cover(kid.index, last.index + 1)
        elif isinstance(kid, _TokenItem):
            cover(kid.index, kid.index + 1)
        else:
            children.append(kid.node)
            cover(kid.node.start, kid.node.end)
        i += 1
    if lo is None or hi is None:
        lo = hi = ctx.start.tokenIndex if ctx.start is not None else 0
    return Node(kind, lo, hi, tuple(children))


def to_cst(document: ParserRuleContext) -> Node:
    """The CST of a ``document`` parse tree."""
    items = _items(document)
    root = items[0] if items else None
    if not isinstance(root, _NodeItem) or root.node.kind is not NodeKind.DOCUMENT:
        raise RuntimeError("parse tree root is not a document")
    return root.node
