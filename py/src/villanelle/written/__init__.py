"""``villanelle.written``: the low level, the config as written (spec 6). ``Processor.load`` returns a
``DocumentGraph`` of editable documents; ``graph.read()`` reads what is still unread, ``graph.save(writer)`` writes the
edits back and ``graph.expand()`` gives every copy as read, which the rendered layer builds on. It owns expansion
(vil-umh.8): the extension port (``Extension``, ``ExtensionUse``) and the expanded values (``ExpandedWord`` ...
``ExpandedIndex``, the union ``ExpandedValue``) live here. It never imports the rendered layer (spec 5, "Layer
direction"), and this module's ``__all__`` is the only part of it the rendered layer reaches (both checked by
tests/test_layers.py).

The written values ``Word``, ``String``, ``List``, ``Slice``, ``Index`` and ``Reference`` are exported from here only,
not from the package root (``from villanelle import written; written.List``), so ``from villanelle import *`` never
replaces ``typing.List``."""

from villanelle.written.extension import Extension, ExtensionUse
from villanelle.written.format import format_diagnostic
from villanelle.written.model import (
    Copy,
    DirectiveExpansion,
    Document,
    DocumentEdge,
    DocumentGraph,
    Expansion,
    ExtensionLine,
    Index,
    List,
    OverrideVariable,
    Parameter,
    Reference,
    ReferenceResolution,
    Resolution,
    SetLine,
    SetVariable,
    Slice,
    SnippetLine,
    Statement,
    String,
    UnreadableExpansion,
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
    IndexValue,
    PlainValue,
    SliceValue,
)

__all__ = [
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
    "Extension",
    "ExtensionLine",
    "ExtensionUse",
    "Index",
    "IndexValue",
    "List",
    "OverrideVariable",
    "Parameter",
    "PlainValue",
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
    "String",
    "UnreadableExpansion",
    "UnreadableLine",
    "UseLine",
    "Variable",
    "Word",
    "WrittenBlock",
    "WrittenDirective",
    "WrittenValue",
    "format_diagnostic",
]
