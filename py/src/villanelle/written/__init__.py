"""``villanelle.written``: the low level, the config as written (spec 6). ``Processor.load`` returns a
``DocumentGraph`` of editable documents; ``graph.read()`` reads what is still unread, ``graph.save(writer)`` writes the
edits back and ``graph.expand()`` gives every copy as read, which the rendered layer builds on. It never imports the
rendered layer (spec 5, "Layer direction"), and this module's ``__all__`` is the only part of it the rendered layer
reaches (both checked by tests/test_layers.py).

The written values ``Word``, ``String``, ``List``, ``Slice``, ``Index`` and ``Reference`` are exported from here only,
not from the package root (``from villanelle import written; written.List``), so ``from villanelle import *`` never
replaces ``typing.List``."""

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
    ValueExpansion,
    Variable,
    Word,
    WrittenBlock,
    WrittenDirective,
    WrittenValue,
)
from villanelle.written.processor import Processor

__all__ = [
    "Copy",
    "DirectiveExpansion",
    "Document",
    "DocumentEdge",
    "DocumentGraph",
    "Expansion",
    "ExtensionLine",
    "Index",
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
    "SnippetLine",
    "Statement",
    "String",
    "UnreadableExpansion",
    "UnreadableLine",
    "UseLine",
    "ValueExpansion",
    "Variable",
    "Word",
    "WrittenBlock",
    "WrittenDirective",
    "WrittenValue",
    "format_diagnostic",
]
