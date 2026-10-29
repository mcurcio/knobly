"""``villanelle.written``: the low level, the config as written (spec 6). ``Processor.load`` returns a
``DocumentGraph`` of editable documents; ``graph.read()`` reads what is still unread, ``graph.save(writer)`` writes the
edits back and ``graph.expand()`` gives every copy as read, which the rendered layer builds on. It owns expansion
(vil-umh.8): the extension port (``Extension``, ``ExtensionUse``) and the expanded values (``ExpandedWord`` ...
``ExpandedIndex``, the union ``ExpandedValue``) live here. It never imports the rendered layer (spec 5, "Layer
direction"), and this module's ``__all__`` is the only part of it the rendered layer reaches (both checked by
tests/test_layers.py).

The records (``Copy``, ``DocumentEdge``, ``Resolution``, ``Expansion``, ``SliceValue`` ...), the ports and the kind
lists are generated from spec/schema/api.json (``villanelle._api``); every handle class here subclasses its
generated Protocol, so mypy checks each member against the schema. Import it as a namespace
(``from villanelle import written``; ``written.List``) or by name: ``from villanelle.written import *`` replaces
``typing.List``."""

from villanelle._api.kinds import StatementKind, UnreadableReason, ValueKind, VariableKind
from villanelle._api.limits import MAX_DEPTH, MAX_DIRECTIVES, MAX_SAFE_INTEGER, RESERVED, VARIABLE_NAME
from villanelle._api.written import (
    Copy,
    DirectiveExpansion,
    DocumentEdge,
    Expansion,
    Extension,
    ExtensionUse,
    IndexValue,
    ReferenceResolution,
    Resolution,
    SliceValue,
    UnreadableExpansion,
)
from villanelle.written.format import format_diagnostic
from villanelle.written.model import (
    Document,
    DocumentGraph,
    ExpansionBlock,
    ExtensionLine,
    Index,
    List,
    OverrideVariable,
    Parameter,
    Reference,
    SetLine,
    SetVariable,
    Slice,
    SnippetLine,
    Statement,
    String,
    UnreadableLine,
    UseLine,
    Variable,
    Word,
    WrittenBlock,
    WrittenDirective,
    WrittenValue,
)
from villanelle.written.processor import Processor
from villanelle.written.value import (
    ExpandedIndex,
    ExpandedList,
    ExpandedSlice,
    ExpandedString,
    ExpandedValue,
    ExpandedWord,
)

__all__ = [
    "MAX_DEPTH",
    "MAX_DIRECTIVES",
    "MAX_SAFE_INTEGER",
    "RESERVED",
    "VARIABLE_NAME",
    "Copy",
    "DirectiveExpansion",
    "Document",
    "DocumentEdge",
    "DocumentGraph",
    "ExpandedIndex",
    "ExpandedList",
    "ExpandedSlice",
    "ExpandedString",
    "ExpandedValue",
    "ExpandedWord",
    "Expansion",
    "ExpansionBlock",
    "Extension",
    "ExtensionLine",
    "ExtensionUse",
    "Index",
    "IndexValue",
    "List",
    "OverrideVariable",
    "Parameter",
    "Processor",
    "Reference",
    "ReferenceResolution",
    "Resolution",
    "SetLine",
    "SetVariable",
    "Slice",
    "SliceValue",
    "SnippetLine",
    "Statement",
    "StatementKind",
    "String",
    "UnreadableExpansion",
    "UnreadableLine",
    "UnreadableReason",
    "UseLine",
    "ValueKind",
    "Variable",
    "VariableKind",
    "Word",
    "WrittenBlock",
    "WrittenDirective",
    "WrittenValue",
    "format_diagnostic",
]
