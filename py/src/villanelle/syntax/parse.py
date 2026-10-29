"""The adapter: the only module (with _walk.py) that touches the ANTLR runtime and the generated parser
(villanelle/_gen/, made by tools/gen.sh py). Everything it returns is ours: Token, Node, Diagnostic."""

from __future__ import annotations

from typing import Any, Literal, TypeAlias

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.Errors import RecognitionException

from villanelle._gen.VillanelleLexer import VillanelleLexer
from villanelle._gen.VillanelleParser import VillanelleParser
from villanelle.diagnostics import Diagnostic, DiagnosticCode
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax._recovery import RawDiagnostic, install_recovery, message_of, nesting_overflow
from villanelle.syntax._walk import to_cst, to_entry_cst
from villanelle.syntax.cst import Node, NodeKind, Syntax, span_of
from villanelle.syntax.tokens import Token, TokenKind

_EOF = -1
_ORIGIN = SourcePosition(offset=0, line=0, column=0)


def _kind_by_type() -> dict[int, TokenKind]:
    """ANTLR token type -> our TokenKind, from the generated lexer's names; raises at import on an unknown name."""
    known = {kind.value for kind in TokenKind}
    by_type: dict[int, TokenKind] = {}
    for token_type, name in enumerate(VillanelleLexer.symbolicNames):
        if name == "<INVALID>":
            continue
        if name not in known:
            raise RuntimeError(f"grammar token {name} is not a TokenKind")
        by_type[token_type] = TokenKind(name)
    return by_type


_KIND_BY_TYPE = _kind_by_type()


def _advance(position: SourcePosition, text: str) -> SourcePosition:
    """The position after ``text``, starting at ``position`` (code points; a line ends after each "\\n")."""
    offset = position.offset + len(text)
    last_newline = text.rfind("\n")
    if last_newline < 0:
        return SourcePosition(offset, position.line, position.column + len(text))
    return SourcePosition(offset, position.line + text.count("\n"), len(text) - last_newline - 1)


def _to_tokens(antlr_tokens: list[Any]) -> tuple[Token, ...]:
    """Our tokens, with positions computed from the token texts, in code points (spec/contract.md 1)."""
    tokens: list[Token] = []
    at = _ORIGIN
    for antlr_token in antlr_tokens:
        if antlr_token.type == _EOF:
            continue
        kind = _KIND_BY_TYPE.get(antlr_token.type)
        if kind is None:
            raise RuntimeError(f"unknown ANTLR token type {antlr_token.type}")
        text: str = antlr_token.text
        end = _advance(at, text)
        tokens.append(Token(kind, text, SourceSpan(at, end)))
        at = end
    return tuple(tokens)


def _lex(text: str) -> tuple[CommonTokenStream, tuple[Token, ...]]:
    lexer = VillanelleLexer(InputStream(text))
    # The lexer is total by construction (BAD_CHAR matches every character no other token can start with), so it
    # never reports an error; its default listener would print to the console.
    lexer.removeErrorListeners()
    stream = CommonTokenStream(lexer)
    stream.fill()
    return stream, _to_tokens(stream.tokens)


def parse(text: str) -> Syntax:
    """Parse one text. Pure and total: it never raises for any input string, and never reads files.
    Errors are reported in ``diagnostics``; the tree still covers every token."""
    stream, tokens = _lex(text)
    n = len(tokens)

    # The depth guard runs first: deep enough nesting would overflow the stack of the recursive parser.
    too_deep = nesting_overflow([t.kind for t in tokens])
    if too_deep is not None:
        root = Node(NodeKind.DOCUMENT, 0, n, (Node(NodeKind.ERROR, 0, n, ()),))
        code = DiagnosticCode.NESTING_TOO_DEEP
        return _located(tokens, root, [RawDiagnostic(code, too_deep, too_deep + 1, message_of(code))])

    parser = VillanelleParser(stream)
    raw: list[RawDiagnostic] = []
    # With recovery installed the parser reports nothing to listeners; drop the default console listener anyway.
    parser.removeErrorListeners()
    install_recovery(parser, raw.append)
    root = to_cst(parser.document())
    return _located(tokens, root, raw)


EntryRule: TypeAlias = Literal["valuesText", "itemsText", "boundText", "nameText"]
"""The grammar's entry rules (spec 2.8): a text a program gives an edit or an override, parsed on its own."""


def parse_entry(text: str, rule: EntryRule) -> Syntax:
    """Parse ``text`` alone with one entry rule of the grammar, with the same recovery and codes as ``parse``. The
    diagnostics are the parse's first error only, placed in ``text`` (spec 2.8). The root is a ``document`` node over
    every token whose children are the text's slice and list nodes (``villanelle._anatomy.values_of`` reads its
    values); with an error it has no children. Private to the package: the edits and the check of an override call
    it, never a probe document."""
    stream, tokens = _lex(text)
    n = len(tokens)
    too_deep = nesting_overflow([t.kind for t in tokens])
    if too_deep is not None:
        code = DiagnosticCode.NESTING_TOO_DEEP
        at = too_deep
        return _located(tokens, Node(NodeKind.DOCUMENT, 0, n, ()), [RawDiagnostic(code, at, at + 1, message_of(code))])
    parser = VillanelleParser(stream)
    raw: list[RawDiagnostic] = []
    parser.removeErrorListeners()
    install_recovery(parser, raw.append)
    try:
        tree = getattr(parser, rule)()
    except RecognitionException:
        tree = None  # the error is in ``raw``: an entry rule has no statement to resume at
    root = Node(NodeKind.DOCUMENT, 0, n, ()) if raw or tree is None else to_entry_cst(tree, n)
    return _located(tokens, root, raw[:1])


def _located(tokens: tuple[Token, ...], root: Node, raw: list[RawDiagnostic]) -> Syntax:
    """The syntax result, with each token-range diagnostic turned into a source span (the one place that does)."""
    unlocated = Syntax(tokens, root, ())
    diagnostics = tuple(Diagnostic(d.code, d.message, span_of(unlocated, d)) for d in raw)
    return Syntax(tokens, root, diagnostics)
