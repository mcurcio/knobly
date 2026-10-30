"""``villanelle.syntax``: the lossless syntax layer (spec 3): ``parse`` turns text into every token and a concrete
syntax tree over token ranges, with what went wrong; ``span_of`` and ``text_of`` read a range back."""

# The records (Token, TokenRange, Node, Syntax), the kind lists and MAX_NESTING are generated from spec/schema/api.json
# (villanelle._api); ANTLR types never leave the adapter (parse).

from villanelle import _docs
from villanelle._api.kinds import NodeKind, TokenKind
from villanelle._api.limits import MAX_NESTING
from villanelle._api.syntax import Node, Syntax, Token, TokenRange
from villanelle.syntax._cst import span_of, text_of
from villanelle.syntax._parse import parse

__all__ = [
    "MAX_NESTING",
    "Node",
    "NodeKind",
    "Syntax",
    "Token",
    "TokenKind",
    "TokenRange",
    "parse",
    "span_of",
    "text_of",
]

_docs.document(__name__)
