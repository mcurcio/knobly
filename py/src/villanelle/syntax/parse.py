"""The adapter: the only module (with _walk.py) that touches the ANTLR runtime and the generated parser
(villanelle/_gen/, made by tools/gen.sh py). Everything it returns is ours: Token, Node, Diagnostic."""

from __future__ import annotations

from typing import Any

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from villanelle._gen.VillanelleLexer import VillanelleLexer
from villanelle._gen.VillanelleParser import VillanelleParser
from villanelle.diagnostics import Diagnostic, DiagnosticCode
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax._walk import to_cst
from villanelle.syntax.cst import Syntax
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


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _advance(position: SourcePosition, text: str) -> SourcePosition:
    """The position after ``text``, starting at ``position`` (UTF-16 units; a line ends after each "\\n")."""
    offset = position.offset + _utf16_length(text)
    last_newline = text.rfind("\n")
    if last_newline < 0:
        return SourcePosition(offset, position.line, position.column + _utf16_length(text))
    return SourcePosition(offset, position.line + text.count("\n"), _utf16_length(text[last_newline + 1 :]))


def _to_tokens(antlr_tokens: list[Any]) -> tuple[Token, ...]:
    """Our tokens, with positions computed from the token texts (ANTLR's columns count code points, not UTF-16)."""
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


def _code_for(token: Token | None, index: int) -> DiagnosticCode:
    if token is not None and (token.kind is TokenKind.BAD_CHAR or (token.kind is TokenKind.BOM and index > 0)):
        return DiagnosticCode.UNEXPECTED_CHARACTER
    if token is not None and token.kind is TokenKind.UNTERMINATED_STRING:
        return DiagnosticCode.UNTERMINATED_STRING
    return DiagnosticCode.UNEXPECTED_TOKEN


class _DiagnosticListener(ErrorListener):  # type: ignore[misc]
    """Reports each syntax error as our diagnostic, located by the offending token. The ambiguity reports stay the
    base class's no-ops: they are for grammar authors, and tools/check.sh proves there are none."""

    def __init__(self, tokens: tuple[Token, ...], end_of_text: SourceSpan) -> None:
        self.diagnostics: list[Diagnostic] = []
        self._tokens = tokens
        self._end_of_text = end_of_text

    def syntaxError(  # ANTLR calls it by this name
        self, recognizer: Any, offending: Any, line: int, column: int, msg: str, e: Any
    ) -> None:
        index: int = offending.tokenIndex if offending is not None else -1
        token = None if offending is None or offending.type == _EOF else self._tokens[index]
        span = token.span if token is not None else self._end_of_text
        self.diagnostics.append(Diagnostic(_code_for(token, index), msg, span))


def parse(text: str) -> Syntax:
    """Parse one text. Pure and total: it never raises for any input string, and never reads files.
    Errors are reported in ``diagnostics``; the tree still covers every token."""
    lexer = VillanelleLexer(InputStream(text))
    # The lexer is total by construction (BAD_CHAR matches every character no other token can start with), so it
    # never reports an error; its default listener would print to the console.
    lexer.removeErrorListeners()
    stream = CommonTokenStream(lexer)
    stream.fill()
    tokens = _to_tokens(stream.tokens)
    end = tokens[-1].span.end if tokens else _ORIGIN

    parser = VillanelleParser(stream)
    listener = _DiagnosticListener(tokens, SourceSpan(end, end))
    parser.removeErrorListeners()
    parser.addErrorListener(listener)
    root = to_cst(parser.document())
    return Syntax(tokens, root, tuple(listener.diagnostics))
