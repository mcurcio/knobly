"""villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4), with a lossless syntax tree
(tier 1: ``parse``) and a load layer (tier 2: ``Processor``) that expands variables, snippets and included files into
directives a program reads. The core does no I/O: ``villanelle.files`` gives a filesystem source."""

from villanelle.diagnostics import Diagnostic, DiagnosticCode, DiagnosticError
from villanelle.directives import (
    Address,
    AddressStep,
    Argument,
    Directive,
    KeyInput,
    KeyRule,
    PlainValue,
    Unreadable,
    UnreadableKind,
    walk,
)
from villanelle.graph import DocumentEdge, DocumentGraph, DocumentNode
from villanelle.origin import DirectiveOrigin, Handed, Origin, Place, Step, StepKind
from villanelle.processor import (
    Added,
    Change,
    Changed,
    Extension,
    ExtensionUse,
    Loaded,
    Processor,
    Removed,
    Unknown,
)
from villanelle.report import Collecting, Diagnostics, Locatable, LocatedDiagnostic, format_diagnostic
from villanelle.source import DocumentSource, LoadContext, memory_source
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax.cst import Node, NodeKind, Syntax, TokenRange, ValueRef, span_of, text_of
from villanelle.syntax.parse import parse
from villanelle.syntax.tokens import Token, TokenKind
from villanelle.value import IndexValue, SliceValue, ValueKind

__all__ = [
    "Added",
    "Address",
    "AddressStep",
    "Argument",
    "Change",
    "Changed",
    "Collecting",
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticError",
    "Diagnostics",
    "Directive",
    "DirectiveOrigin",
    "DocumentEdge",
    "DocumentGraph",
    "DocumentNode",
    "DocumentSource",
    "Extension",
    "ExtensionUse",
    "Handed",
    "IndexValue",
    "KeyInput",
    "KeyRule",
    "LoadContext",
    "Loaded",
    "Locatable",
    "LocatedDiagnostic",
    "Node",
    "NodeKind",
    "Origin",
    "Place",
    "PlainValue",
    "Processor",
    "Removed",
    "SliceValue",
    "SourcePosition",
    "SourceSpan",
    "Step",
    "StepKind",
    "Syntax",
    "Token",
    "TokenKind",
    "TokenRange",
    "Unknown",
    "Unreadable",
    "UnreadableKind",
    "ValueKind",
    "ValueRef",
    "format_diagnostic",
    "memory_source",
    "parse",
    "span_of",
    "text_of",
    "walk",
]
