from __future__ import annotations

import re

from conftest import REPO

from villanelle.syntax import TokenKind


def grammar_token_names() -> list[str]:
    """The grammar's token names: every lexer rule that is not a fragment (several rules may share a line)."""
    text = (REPO / "grammar" / "Villanelle.g4").read_text(encoding="utf-8")
    return re.findall(r"(?:^|;)\s*([A-Z][A-Z_]*)\s*:", text, flags=re.MULTILINE)


def test_token_kind_names_exactly_the_grammar_tokens() -> None:
    assert sorted(kind.value for kind in TokenKind) == sorted(grammar_token_names())
    assert all(kind.name == kind.value for kind in TokenKind)
