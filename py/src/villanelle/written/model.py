"""The low level: the config as written, editable, saved back (round 12 design.md §6; slices.md S3).

One model, TypeScript's (``ts/src/written/model.ts``): a live tree with named edit methods, snake_case and
synchronous. Fields are read-only properties; a block reads as a ``Sequence``; kinds are classes, so ``match``
narrows; a handle is the same object each time (``is``) for the graph's life and follows its tokens across other
edits. A detached handle raises ``DetachedError`` from every member but ``kind``. Copies, edges and resolutions are
snapshots of one derivation of the current texts (design rule 1), not handles.

Every body here raises NotImplementedError until slice S3 fills it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar, final, overload

from villanelle.origin import Place, Step
from villanelle.report import LocatedDiagnostic
from villanelle.syntax.cst import Syntax


def _todo() -> NotImplementedError:
    return NotImplementedError("the low level (slices.md S3)")


# --- Files ---


@final
class DocumentGraph:
    """The files one load read, and the values the program handed in."""

    @property
    def root(self) -> Document:
        raise _todo()

    @property
    def documents(self) -> Mapping[str, Document]:
        """Every file read, by resolved path, root first, then in first-read order. Never shrinks."""
        raise _todo()

    @property
    def handed(self) -> Mapping[str, str]:
        """Handed-in values by name (without ``$``), each as villanelle text. Never saved."""
        raise _todo()

    def set_handed(self, name: str, text: str | None, /) -> None:
        """Add, change or (None) remove one handed-in value without a reload. Raises BadTextError for a text that is
        not one or more values without a ``$name``; ValueError for a name that is not letters, digits and ``_``."""
        raise _todo()

    def edges(self) -> tuple[DocumentEdge, ...]:
        """Every copy of every extension line, in walk order."""
        raise _todo()

    def unread(self) -> tuple[DocumentEdge, ...]:
        """The edges naming a spec not resolved or a file not read yet."""
        raise _todo()

    def variables(self, name: str | None = None) -> tuple[Variable, ...]:
        """``set`` lines and parameters in document order, then handed-in values."""
        raise _todo()

    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """Syntax diagnostics per document, then what the binding found in walk order, except render's codes."""
        raise _todo()


@final
class Document:
    """One file as written."""

    @property
    def resolved_path(self) -> str:
        raise _todo()

    @property
    def source(self) -> str:
        """As read, or as last handed to a writer that returned."""
        raise _todo()

    @property
    def text(self) -> str:
        """Now; differs from ``source`` exactly when unsaved."""
        raise _todo()

    @property
    def syntax(self) -> Syntax:
        raise _todo()

    @property
    def body(self) -> WrittenBlock:
        raise _todo()

    def included_by(self) -> tuple[DocumentEdge, ...]:
        raise _todo()

    def replace_with_text(self, text: str, /) -> None:
        """Replace the whole text; every handle into it detaches; ``source`` is untouched."""
        raise _todo()


@final
@dataclass(frozen=True, slots=True, eq=False)
class Copy:
    """One place a statement is read."""

    statement: Statement
    via: tuple[Step, ...]
    """The include and ``use`` steps, innermost first; empty at the root."""


@final
@dataclass(frozen=True, slots=True, eq=False)
class DocumentEdge:
    """One copy of an extension line, and the files it matched."""

    copy: Copy
    specs: tuple[str, ...]
    targets: tuple[str, ...]


# --- Statements ---


class _Statement:
    """What every statement has."""

    __slots__ = ()

    @property
    def document(self) -> Document:
        raise _todo()

    @property
    def parent(self) -> Statement | None:
        raise _todo()

    @property
    def place(self) -> Place:
        raise _todo()

    @property
    def text(self) -> str:
        """Exact, with the comments it owns."""
        raise _todo()

    def copies(self) -> tuple[Copy, ...]:
        raise _todo()

    def replace_with_text(self, text: str, /) -> tuple[Statement, ...]:
        """Raises BadTextError. This handle detaches."""
        raise _todo()

    def remove(self) -> None:
        raise _todo()


@final
class WrittenDirective(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["directive", "extension"]:
        raise _todo()

    @property
    def name(self) -> str:
        """Read-only: change it with ``rename``."""
        raise _todo()

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        raise _todo()

    @property
    def block(self) -> WrittenBlock | None:
        raise _todo()

    def rename(self, name: str, /) -> None:
        raise _todo()

    def set_values(self, text: str, /) -> None:
        raise _todo()


@final
class SetLine(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["set"]:
        return "set"

    @property
    def variable(self) -> Variable:
        raise _todo()

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        """After the ``$name``."""
        raise _todo()

    def set_values(self, text: str, /) -> None:
        raise _todo()


@final
class SnippetLine(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["snippet"]:
        return "snippet"

    @property
    def name(self) -> str:
        raise _todo()

    @property
    def parameters(self) -> tuple[Variable, ...]:
        raise _todo()

    @property
    def block(self) -> WrittenBlock:
        raise _todo()


@final
class UseLine(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["use"]:
        return "use"

    @property
    def snippet_name(self) -> str:
        raise _todo()

    @property
    def snippet(self) -> SnippetLine | None:
        """By where written."""
        raise _todo()

    def snippets(self) -> tuple[Resolution[SnippetLine], ...]:
        """Per copy."""
        raise _todo()

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        raise _todo()

    def set_values(self, text: str, /) -> None:
        raise _todo()


@final
class UnreadableLine(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["unreadable"]:
        return "unreadable"


Statement: TypeAlias = WrittenDirective | SetLine | SnippetLine | UseLine | UnreadableLine


@final
class WrittenBlock(Sequence["Statement"]):
    """The statements of a document or a block: iterate, index, ``len``, ``in``."""

    __slots__ = ()

    @overload
    def __getitem__(self, index: int, /) -> Statement: ...

    @overload
    def __getitem__(self, index: slice, /) -> Sequence[Statement]: ...

    def __getitem__(self, index: int | slice, /) -> Statement | Sequence[Statement]:
        raise _todo()

    def __len__(self) -> int:
        raise _todo()

    def directives(self, name: str | None = None) -> tuple[WrittenDirective, ...]:
        raise _todo()

    def insert_statements(self, index: int, text: str, /) -> tuple[Statement, ...]:
        """Raises BadTextError; IndexError for an index outside 0..len."""
        raise _todo()

    def add_statements(self, text: str, /) -> tuple[Statement, ...]:
        raise _todo()


# --- Values ---


class _Value:
    """What every written value has."""

    __slots__ = ()

    @property
    def text(self) -> str:
        raise _todo()

    @property
    def place(self) -> Place:
        raise _todo()

    @property
    def statement(self) -> Statement:
        raise _todo()

    @property
    def list(self) -> List | None:
        """The list it is an item of."""
        raise _todo()

    def replace_with_text(self, text: str, /) -> tuple[WrittenValue, ...]:
        raise _todo()

    def remove(self) -> None:
        raise _todo()


@final
class Word(_Value):
    __slots__ = ()

    @property
    def kind(self) -> Literal["word"]:
        return "word"


@final
class String(_Value):
    __slots__ = ()

    @property
    def kind(self) -> Literal["string"]:
        return "string"


@final
class List(_Value):
    __slots__ = ()

    @property
    def kind(self) -> Literal["list"]:
        return "list"

    @property
    def items(self) -> tuple[WrittenValue, ...]:
        raise _todo()


@final
class Slice(_Value):
    __slots__ = ()

    @property
    def kind(self) -> Literal["slice"]:
        return "slice"

    @property
    def name(self) -> str:
        raise _todo()

    @property
    def start(self) -> Word | Reference | None:
        raise _todo()

    @property
    def end(self) -> Word | Reference | None:
        raise _todo()


@final
class Index(_Value):
    __slots__ = ()

    @property
    def kind(self) -> Literal["index"]:
        return "index"

    @property
    def name(self) -> str:
        raise _todo()

    @property
    def index(self) -> Word | Reference:
        raise _todo()


@final
class Reference(_Value):
    """One ``$name`` written as a value."""

    __slots__ = ()

    @property
    def kind(self) -> Literal["reference"]:
        return "reference"

    @property
    def name(self) -> str:
        raise _todo()

    @property
    def declaration(self) -> Variable | None:
        raise _todo()

    def resolutions(self) -> tuple[ReferenceResolution, ...]:
        raise _todo()


WrittenValue: TypeAlias = Word | String | List | Slice | Index | Reference


# --- Variables ---


@final
class Variable:
    """A ``set`` line's ``$name``, a snippet parameter, or a handed-in value."""

    __slots__ = ()

    @property
    def kind(self) -> Literal["set", "parameter", "handed"]:
        raise _todo()

    @property
    def name(self) -> str:
        raise _todo()

    @property
    def place(self) -> Place | None:
        raise _todo()

    @property
    def line(self) -> SetLine | SnippetLine | None:
        raise _todo()

    def references(self) -> tuple[Reference, ...]:
        raise _todo()

    def reaches(self) -> tuple[ReferenceResolution, ...]:
        raise _todo()

    def overridden(self) -> tuple[ReferenceResolution, ...]:
        raise _todo()

    def rename(self, name: str, /) -> None:
        raise _todo()

    def set_values(self, text: str, /) -> None:
        """Raises NoSetLineError for a parameter or a handed-in value."""
        raise _todo()


T = TypeVar("T", Variable, SnippetLine)


@dataclass(frozen=True, slots=True, eq=False)
class Resolution(Generic[T]):
    """At one copy: what a written name reads, and what it wins over (next first)."""

    copy: Copy
    winner: T | None
    overridden: tuple[T, ...]


@final
@dataclass(frozen=True, slots=True, eq=False)
class ReferenceResolution(Resolution[Variable]):
    """A ``$name`` at one copy; it renders to all of ``values``."""

    reference: Reference
    values: tuple[WrittenValue, ...]


__all__ = [
    "Copy",
    "Document",
    "DocumentEdge",
    "DocumentGraph",
    "Index",
    "List",
    "Reference",
    "ReferenceResolution",
    "Resolution",
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
]
