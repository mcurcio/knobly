"""``villanelle.written``: the low level, the config as written (spec 6). ``Processor.load`` returns a
``DocumentGraph`` of editable documents; ``graph.read()`` reads what is still unread and ``graph.save(writer)``
writes the edits back. It never imports the rendered layer (spec 5, "Layer direction")."""

from villanelle.written.errors import BadTextError, DetachedError, EditError, NoSetLineError, ReadError, SaveError
from villanelle.written.format import format_diagnostic
from villanelle.written.model import (
    Copy,
    Document,
    DocumentEdge,
    DocumentGraph,
    Index,
    List,
    Reference,
    ReferenceResolution,
    Resolution,
    SetLine,
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

__all__ = [
    "BadTextError",
    "Copy",
    "DetachedError",
    "Document",
    "DocumentEdge",
    "DocumentGraph",
    "EditError",
    "Index",
    "List",
    "NoSetLineError",
    "Processor",
    "ReadError",
    "Reference",
    "ReferenceResolution",
    "Resolution",
    "SaveError",
    "SetLine",
    "Slice",
    "SnippetLine",
    "Statement",
    "String",
    "UnreadableLine",
    "UseLine",
    "Variable",
    "Word",
    "WrittenBlock",
    "WrittenDirective",
    "WrittenValue",
    "format_diagnostic",
]
