"""A Pygments lexer for knobly, run by the grammar itself.

The lexer is not a second copy of the token rules: it scans with the longest-match DFA that knobly's own parser
generator builds from grammar/Knobly.g4, and classes each token by the highlight model, grammar/highlight.json,
through tools/highlight/gen.py (the TypeScript highlighter and the TextMate grammar read the same model). So a block
highlights exactly the tokens the parsers see, and the same way every other knobly highlighter does. A token kind
with no class fails construction (tools/check.sh refuses one too), so a token added to the grammar cannot go
unstyled.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator, Tuple

from pygments.lexer import Lexer
from pygments.token import Text, _TokenType, string_to_tokentype

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "tools" / "highlight"))
import gen as highlight  # noqa: E402

_MODEL = highlight.load()  # raises ModelError for a token kind with no class
_STYLE = {name: string_to_tokentype(c["pygments"]) for name, c in _MODEL.classes.items()}
# Per token kind (DFA accept index): its style, its style as a statement's first token, whether it starts one, and
# whether it is filler between a start and a statement's first token (the head rule, grammar/highlight.json).
_OWN = [string_to_tokentype(_MODEL.token_pygments[t]) for t in _MODEL.tokens]
_HEAD = [_STYLE[_MODEL.head_class[t]] if t in _MODEL.head_class else _OWN[i] for i, t in enumerate(_MODEL.tokens)]
_STARTS = [t in _MODEL.starts for t in _MODEL.tokens]
_FILLER = [t in _MODEL.filler for t in _MODEL.tokens]


def _match(text: str, at: int) -> Tuple[int, int]:
    """The longest match at `at` as (token index, end): every DFA state but the start accepts, so run until no move
    applies (tools/highlight/gen.py checks the property)."""
    state, i = 0, at
    while i < len(text):
        cp = ord(text[i])
        nxt = next((t for lo, hi, t in _MODEL.trans[state] if lo <= cp <= hi), -1)
        if nxt < 0:
            break
        state, i = nxt, i + 1
    return _MODEL.accept[state], i


class KnoblyLexer(Lexer):
    name = "knobly"
    aliases = ["knobly"]
    filenames = ["*.knobly"]

    def get_tokens_unprocessed(self, text: str) -> Iterator[Tuple[int, _TokenType, str]]:
        at, head = 0, True
        while at < len(text):
            kind, end = _match(text, at)
            if kind < 0:  # unreachable: the start state takes every code point (tools/highlight/gen.py checks it)
                yield at, Text, text[at]
                at += 1
                continue
            yield at, _HEAD[kind] if head else _OWN[kind], text[at:end]
            head = _STARTS[kind] or (head and _FILLER[kind])
            at = end
