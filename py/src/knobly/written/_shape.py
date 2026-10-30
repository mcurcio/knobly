"""The text-alone shape of a statement (round 12 slices.md 2.3; spec 2.5, 5): which kind a directive node is, and
the one problem that makes a ``@set``, ``@snippet`` or ``@use`` line unreadable by its text alone. The head token's
kind decides (milestone 5, a keyword sigil as CSS at-rules): a WORD heads a written directive whatever its text; an
AT_WORD heads a language statement (``@set``, ``@snippet``, ``@use``), an extension line (``@`` and a registered
extension's name), or else an unreadable line (the binding reports E3008). The one home of these shape rules: the
document classifies its statements with it, the edit checks use it, and the binding's walk reports the same codes at
the same places. Private; a port of ts/src/written/shape.ts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from knobly._anatomy import Anatomy, anatomy_of
from knobly._api.codes import DiagnosticCode
from knobly._api.kinds import NodeKind, StatementKind, TokenKind, statement_of_keyword
from knobly._api.syntax import Node, Token

ShapeKind: TypeAlias = StatementKind

_WORDS = frozenset({TokenKind.WORD, TokenKind.AT_WORD, TokenKind.INTEGER, TokenKind.DIGIT_WORD})
"""The bare-word tokens: a ``@snippet``'s or ``@use``'s snippet name is any of them."""


@dataclass(frozen=True, slots=True)
class Fault:
    """One problem of a line's text alone, at one token."""

    code: DiagnosticCode
    token: int
    """The token index it is placed on."""
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Shape:
    kind: ShapeKind
    fault: Fault | None = None
    """Why a ``@set``, ``@snippet`` or ``@use`` line is unreadable; None otherwise (for a syntax error node, and for an
    ``@name`` no extension owns: the binding reports that one, E3008)."""
    claims: str | None = None
    """A ``set``'s variable name, or a snippet's name (for the one-per-block rules)."""


def shape_of(tokens: tuple[Token, ...], node: Node, extensions: frozenset[str] | set[str]) -> Shape:
    """The shape of one node of a block, ignoring the one-per-block rules (E5002, E5005)."""
    if node.kind is not NodeKind.DIRECTIVE:
        return Shape(StatementKind.UNREADABLE)
    return shape_of_anatomy(tokens, anatomy_of(tokens, node), extensions)


def shape_of_anatomy(tokens: tuple[Token, ...], anatomy: Anatomy, extensions: frozenset[str] | set[str]) -> Shape:
    """The shape of a directive by its anatomy, ignoring the one-per-block rules (the binding's walk asks this too).
    ``extensions`` are the registered extensions' names, without ``@``."""
    name = tokens[anatomy.name]
    if name.kind is not TokenKind.AT_WORD:
        return Shape(StatementKind.DIRECTIVE)
    args = anatomy.args
    first = tokens[args[0]] if args and isinstance(args[0], int) else None
    rest = args[1:]
    keyword = statement_of_keyword(name.text[1:])
    if keyword is StatementKind.SET:
        if first is None or first.kind is not TokenKind.VARIABLE or not rest or anatomy.block is not None:
            return Shape(StatementKind.UNREADABLE, Fault(DiagnosticCode.BAD_SET, anatomy.name))
        return Shape(StatementKind.SET, None, first.text[1:])
    if keyword is StatementKind.SNIPPET:
        bad = Shape(StatementKind.UNREADABLE, Fault(DiagnosticCode.BAD_SNIPPET, anatomy.name))
        params: list[str] = []
        for ref in rest:
            token = tokens[ref] if isinstance(ref, int) else None
            if token is None or token.kind is not TokenKind.VARIABLE or token.text[1:] in params:
                return bad
            params.append(token.text[1:])
        if first is None or first.kind not in _WORDS or anatomy.block is None:
            return bad
        return Shape(StatementKind.SNIPPET, None, first.text)
    if keyword is StatementKind.USE:
        if first is None or first.kind not in _WORDS or anatomy.block is not None:
            return Shape(StatementKind.UNREADABLE, Fault(DiagnosticCode.BAD_USE, anatomy.name))
        return Shape(StatementKind.USE)
    return Shape(StatementKind.EXTENSION if name.text[1:] in extensions else StatementKind.UNREADABLE)


def parameter_tokens(tokens: tuple[Token, ...], node: Node) -> tuple[int, ...]:
    """A snippet line's parameter tokens (VARIABLE token indices), in order. Call only on a well-formed snippet."""
    return tuple(ref for ref in anatomy_of(tokens, node).args[1:] if isinstance(ref, int))


def block_shapes(
    tokens: tuple[Token, ...], nodes: Sequence[Node], extensions: frozenset[str] | set[str], claimed: Iterable[str] = ()
) -> list[Shape]:
    """The shapes of a block's nodes in order, with the one-per-block rules applied: a second ``set`` of a name is
    unreadable (E5002 at its ``$name``), a second ``snippet`` of a name too (E5005 at its name). ``claimed`` holds
    names a block already binds (a snippet body's parameters)."""
    sets = set(claimed)
    snippets: set[str] = set()
    out: list[Shape] = []
    for node in nodes:
        shape = shape_of(tokens, node, extensions)
        claims = shape.claims
        if shape.kind is StatementKind.SET and claims is not None:
            if claims in sets:
                at = anatomy_of(tokens, node).args[0]
                assert isinstance(at, int)
                shape = Shape(StatementKind.UNREADABLE, Fault(DiagnosticCode.VARIABLE_SET_TWICE, at, tokens[at].text))
            else:
                sets.add(claims)
        elif shape.kind is StatementKind.SNIPPET and claims is not None:
            if claims in snippets:
                at = anatomy_of(tokens, node).args[0]
                assert isinstance(at, int)
                shape = Shape(StatementKind.UNREADABLE, Fault(DiagnosticCode.SNIPPET_DEFINED_TWICE, at, claims))
            else:
                snippets.add(claims)
        out.append(shape)
    return out


def statement_nodes(container: Node) -> tuple[Node, ...]:
    """The statement nodes of a document or block node: its directive and error children."""
    return tuple(c for c in container.children if c.kind in (NodeKind.DIRECTIVE, NodeKind.ERROR))
