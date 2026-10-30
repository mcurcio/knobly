"""villanelle: a configuration language defined by one grammar (grammar/Villanelle.g4). One namespace per layer
(binding guide rule 9): this package root holds the shared and io names (positions, places, origins, diagnostics,
the error tree, config text, the document source and writer ports and the in-memory adapters);
``villanelle.syntax`` the lossless syntax tree (``parse``); ``villanelle.written`` the config as written (the low
level: ``Processor.load`` returns a ``DocumentGraph`` of editable documents, read further with ``graph.read()`` and
saved back with ``graph.save(writer)``); ``villanelle.rendered`` the rendered tree (``render(graph)``: variables,
snippets and included files expanded into directives a program reads). The core does no I/O: ``villanelle.files``
gives a filesystem source and writer, ``villanelle.include`` the include extension."""

# Every public signature is generated from spec/schema/api.json (villanelle._api); each module's __all__ equals the
# generated PUBLIC_NAMES for it (tests/test_api_names.py).

from villanelle._api.codes import DiagnosticCode
from villanelle._api.errors import (
    BadTextError,
    DetachedError,
    DiagnosticError,
    LostUpdateError,
    ReadError,
    SaveError,
    VillanelleError,
)
from villanelle._api.io import DocumentSource, DocumentWriter, FileWrite, LoadContext
from villanelle._api.kinds import PlaceKind, StepKind
from villanelle._api.limits import PROGRAM_CODE
from villanelle._api.shared import (
    Block,
    ConfigText,
    DirectiveOrigin,
    Locatable,
    Origin,
    ProgramCode,
    SourcePosition,
    SourceSpan,
)
from villanelle._diagnostics import Diagnostic
from villanelle._origin import Override, Place, Step
from villanelle._report import Collecting, Diagnostics, LocatedDiagnostic
from villanelle._source import check_lost_updates, memory_source, memory_writer
from villanelle._text import quote, text

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
    "VillanelleError",
    "check_lost_updates",
    "memory_source",
    "memory_writer",
    "quote",
    "text",
]
