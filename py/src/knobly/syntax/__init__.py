"""``knobly.syntax``: the lossless syntax layer (spec 3): ``parse`` turns text into every token and a concrete
syntax tree over token ranges, with what went wrong; ``span_of`` and ``text_of`` read a range back."""

# The records (Token, TokenRange, Node, Syntax), the kind lists and MAX_NESTING are generated from spec/schema/api.json
# (knobly._api); ANTLR types never leave the adapter (parse).

from knobly import _docs
from knobly._api.kinds import NodeKind, TokenKind
from knobly._api.limits import MAX_NESTING
from knobly._api.syntax import Node, Syntax, Token, TokenRange
from knobly.syntax._cst import span_of, text_of
from knobly.syntax._parse import parse

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
