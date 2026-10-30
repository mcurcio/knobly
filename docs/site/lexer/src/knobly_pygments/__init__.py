"""A Pygments lexer for knobly, run by the grammar itself.

The lexer is not a second copy of the token rules: it builds the longest-match DFA that knobly's own parser generator
builds from grammar/Knobly.g4 (tools/parser/g4.py and lexer.py) and scans with it, so a block highlights exactly the
tokens the parsers see. The only thing kept here is how each token kind looks. A token kind with no style fails
construction, so a token added to the grammar cannot go unstyled.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator, Tuple

from pygments.lexer import Lexer
from pygments.token import Comment, Error, Keyword, Name, Number, Punctuation, String, Text, Whitespace, _TokenType

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tools" / "parser"))
import g4  # noqa: E402
import lexer as g4lexer  # noqa: E402

STYLE = {
    "BOM": Whitespace,
    "SPACE": Whitespace,
    "NEWLINE": Whitespace,
    "COMMENT": Comment.Single,
    "VARIABLE": Name.Variable,
    "WORD": Name,
    "AT_WORD": Keyword,
    "INTEGER": Number.Integer,
    "DIGIT_WORD": Number,
    "STRING": String,
    "LBRACE": Punctuation,
    "RBRACE": Punctuation,
    "LBRACK": Punctuation,
    "RBRACK": Punctuation,
    "SEMI": Punctuation,
    "COMMA": Punctuation,
    "TILDE": Punctuation,
    "UNTERMINATED_STRING": Error,
    "BAD_ESCAPE": Error,
    "LONE_DOLLAR": Error,
    "BAD_CHAR": Error,
}
# A statement's first word is its name (grammar rule `header`): a directive's, or an '@' statement's keyword.
HEAD = {"WORD": Name.Function, "AT_WORD": Keyword}
# The tokens before a statement's first word: the start, ';', '{', '}' (rule `statements`), and filler between.
STARTS = {"SEMI", "LBRACE", "RBRACE"}
FILLER = {"BOM", "SPACE", "NEWLINE", "COMMENT"}

_DFA = g4lexer.build(g4.read(REPO / "grammar" / "Knobly.g4"))
_missing = sorted(set(_DFA.tokens) - STYLE.keys())
if _missing:
    raise RuntimeError(f"knobly_pygments: no style for the token kinds {', '.join(_missing)}")


class KnoblyLexer(Lexer):
    name = "knobly"
    aliases = ["knobly"]
    filenames = ["*.knobly"]

    def get_tokens_unprocessed(self, text: str) -> Iterator[Tuple[int, _TokenType, str]]:
        at, head = 0, True
        while at < len(text):
            kind, end = _DFA.match(text, at)
            if kind < 0:  # no token starts here (only possible past the grammar's alphabet): one character, unlexed
                yield at, Text, text[at]
                at += 1
                continue
            name = _DFA.tokens[kind]
            yield at, HEAD[name] if head and name in HEAD else STYLE[name], text[at:end]
            head = name in STARTS or (head and name in FILLER)
            at = end
