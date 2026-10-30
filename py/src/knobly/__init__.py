"""knobly: a configuration language defined by one grammar (grammar/Knobly.g4). One namespace per layer:
this package root holds the shared and io names (positions, places, origins, diagnostics,
the error tree, config text, the document source and writer ports and the in-memory adapters);
``knobly.syntax`` the lossless syntax tree (``parse``); ``knobly.written`` the config as written (the low
level: ``Processor.load`` returns a ``DocumentGraph`` of editable documents, read further with ``graph.read()`` and
saved back with ``graph.save(writer)``); ``knobly.rendered`` the rendered tree (``render(graph)``: variables,
snippets and included files expanded into directives a program reads). The core does no I/O: ``knobly.files``
gives a filesystem source and writer, ``knobly.include`` the include extension."""

# Every public signature is generated from spec/schema/api.json (knobly._api); each module's __all__ equals the
# generated PUBLIC_NAMES for it (tests/test_api_names.py).

from knobly import _docs
from knobly._api.codes import DiagnosticCode
from knobly._api.errors import (
    BadTextError,
    DetachedError,
    DiagnosticError,
    KnoblyError,
    LostUpdateError,
    ReadError,
    SaveError,
)
from knobly._api.io import DocumentSource, DocumentWriter, FileWrite, LoadContext
from knobly._api.kinds import PlaceKind, StepKind
from knobly._api.limits import PROGRAM_CODE
from knobly._api.shared import (
    Block,
    ConfigText,
    DirectiveOrigin,
    Locatable,
    Origin,
    ProgramCode,
    SourcePosition,
    SourceSpan,
)
from knobly._diagnostics import Diagnostic
from knobly._origin import Override, Place, Step
from knobly._report import Collecting, Diagnostics, LocatedDiagnostic
from knobly._source import check_lost_updates, memory_source, memory_writer
from knobly._text import quote, text

__all__ = [
    "PROGRAM_CODE",
    "BadTextError",
    "Block",
    "Collecting",
    "ConfigText",
    "DetachedError",
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticError",
    "Diagnostics",
    "DirectiveOrigin",
    "DocumentSource",
    "DocumentWriter",
    "FileWrite",
    "KnoblyError",
    "LoadContext",
    "Locatable",
    "LocatedDiagnostic",
    "LostUpdateError",
    "Origin",
    "Override",
    "Place",
    "PlaceKind",
    "ProgramCode",
    "ReadError",
    "SaveError",
    "SourcePosition",
    "SourceSpan",
    "Step",
    "StepKind",
    "check_lost_updates",
    "memory_source",
    "memory_writer",
    "quote",
    "text",
]

_docs.document(__name__)
