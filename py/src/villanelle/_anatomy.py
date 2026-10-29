"""Directive anatomy (vil-g7n.1.3): which tokens of a ``directive`` node are its name, its values and its block.
Private to the load layer; a port of ts/src/ast/anatomy.ts."""

from __future__ import annotations

from dataclasses import dataclass

from villanelle._api.kinds import NodeKind, TokenKind
from villanelle._api.syntax import Node, Token
from villanelle.syntax.cst import ValueRef

_VALUE_TOKENS = frozenset(
    {TokenKind.WORD, TokenKind.AT_WORD, TokenKind.INTEGER, TokenKind.DIGIT_WORD, TokenKind.STRING, TokenKind.VARIABLE}
)
_VALUE_NODES = frozenset({NodeKind.SLICE, NodeKind.LIST})


@dataclass(frozen=True, slots=True)
class Anatomy:
    name: int
    """Index of the head token (``node.start``): a WORD names a directive, an AT_WORD a language or extension
    statement."""
    args: tuple[ValueRef, ...]
    """In source order: each WORD, AT_WORD, INTEGER, DIGIT_WORD, STRING or VARIABLE token directly in the node's
    range, and each slice or list child."""
    block: Node | None


def anatomy_of(tokens: tuple[Token, ...], node: Node) -> Anatomy:
    """Split a directive node. Spaces, comments, separators, punctuation and error children are never values."""
    values, block = _split(tokens, node)
    return Anatomy(node.start, values, block)


def items_of(tokens: tuple[Token, ...], node: Node) -> tuple[ValueRef, ...]:
    """A ``list`` node's items in source order, by the same rule as a directive's values (the bracket comes first)."""
    return _split(tokens, node)[0]


def values_of(tokens: tuple[Token, ...], node: Node) -> tuple[ValueRef, ...]:
    """The values of an entry rule's text (``parse_entry``'s root), by the same rule, from its first token."""
    return _split(tokens, node, node.start)[0]


def _split(tokens: tuple[Token, ...], node: Node, first: int | None = None) -> tuple[tuple[ValueRef, ...], Node | None]:
    """The values and the block of ``node``, from token ``first`` (default: after its name or opening bracket)."""
    values: list[ValueRef] = []
    block: Node | None = None
    children = node.children
    following = 0
    i = node.start + 1 if first is None else first
    while i < node.end:
        child = children[following] if following < len(children) else None
        if child is not None and child.start == i:
            if child.kind in _VALUE_NODES:
                values.append(child)
            elif child.kind is NodeKind.BLOCK:
                block = child
            following += 1
            i = max(child.end, i + 1)
            continue
        if tokens[i].kind in _VALUE_TOKENS:
            values.append(i)
        i += 1
    return tuple(values), block
