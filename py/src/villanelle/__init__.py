"""villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4), with a lossless syntax tree
and typed values. The core does no I/O."""

from villanelle.diagnostics import Diagnostic, DiagnosticCode, DiagnosticError
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax.cst import Node, NodeKind, Syntax, TokenRange, ValueRef, span_of, text_of
from villanelle.syntax.parse import parse
from villanelle.syntax.tokens import Token, TokenKind
from villanelle.value import IndexValue, SliceValue, StringValue, Value, ValueKind, WordValue, value_of

__all__ = [
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticError",
    "IndexValue",
    "Node",
    "NodeKind",
    "SliceValue",
    "SourcePosition",
    "SourceSpan",
    "StringValue",
    "Syntax",
    "Token",
    "TokenKind",
    "TokenRange",
    "Value",
    "ValueKind",
    "ValueRef",
    "WordValue",
    "parse",
    "span_of",
    "text_of",
    "value_of",
]
