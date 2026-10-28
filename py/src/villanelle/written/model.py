"""The low level: the config as written, editable, saved back (round 12 design.md §6; slices.md S3).

One model, TypeScript's (``ts/src/written/model.ts``): a live tree with named edit methods, snake_case and
synchronous. Fields are read-only properties; a block reads as a ``Sequence``; kinds are classes, so ``match``
narrows; a handle is the same object each time (``is``) for the graph's life and follows its tokens across other
edits. A detached handle raises ``DetachedError`` from every member but ``kind``. Copies, edges and resolutions are
snapshots of one derivation of the current texts (design rule 1), not handles.

The classes hold their state; the algorithms live in the private modules beside this one: ``_document`` (the
handle tree, splices and edit checks), ``_graph`` (the read ledger, the handed-in values and the binding cache) and
``_bind`` (the binding).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, Literal, TypeAlias, TypeVar, cast, final, overload

from villanelle.origin import Place, Step
from villanelle.report import LocatedDiagnostic
from villanelle.syntax.cst import Node, Syntax, ValueRef
from villanelle.written.errors import DetachedError, NoSetLineError

if TYPE_CHECKING:
    from villanelle.directives import Argument
    from villanelle.processor import Extension
    from villanelle.written._bind import Binding


def _detached(what: str) -> DetachedError:
    return DetachedError(f"this {what} was removed by an edit or its document's text was replaced")


# --- Files ---


@final
class DocumentGraph:
    """The files one load read, and the values the program handed in."""

    __slots__ = (
        "_cache",
        "_documents",
        "_extension_names",
        "_extensions",
        "_failed",
        "_handed_texts",
        "_handed_values",
        "_handed_variables",
        "_owner",
        "_resolutions",
        "_root",
        "_version",
    )

    _extensions: Mapping[str, Extension]
    _extension_names: frozenset[str]
    _documents: dict[str, Document]
    _root: Document | None
    _handed_texts: dict[str, str]
    _handed_values: dict[str, tuple[Argument, ...]]
    _handed_variables: dict[str, Variable]
    _resolutions: dict[tuple[str, str], tuple[str, ...] | Exception]
    _failed: dict[str, Exception]
    _version: int
    _cache: tuple[int, Binding] | None
    _owner: object

    def __init__(self, extensions: Mapping[str, Extension], handed: Mapping[str, str], owner: object) -> None:
        """Made by ``Processor.load`` only. Raises ValueError for a bad handed-in name or text (PR 3's rule)."""
        from villanelle.written import _graph

        _graph.init(self, extensions, handed, owner)

    @property
    def root(self) -> Document:
        if self._root is None:
            raise RuntimeError("the graph has no root yet")
        return self._root

    @property
    def documents(self) -> Mapping[str, Document]:
        """Every file read, by resolved path, root first, then in first-read order. Never shrinks."""
        return MappingProxyType(self._documents)

    @property
    def handed(self) -> Mapping[str, str]:
        """Handed-in values by name (without ``$``), each as villanelle text. Never saved."""
        return MappingProxyType(self._handed_texts)

    def set_handed(self, name: str, text: str | None, /) -> None:
        """Add, change or (None) remove one handed-in value without a reload. Raises BadTextError for a text that is
        not one or more values without a ``$name``; ValueError for a name that is not letters, digits and ``_``."""
        from villanelle.written import _graph

        _graph.set_handed(self, name, text)

    def edges(self) -> tuple[DocumentEdge, ...]:
        """Every copy of every extension line, in walk order."""
        return self._binding().edges

    def unread(self) -> tuple[DocumentEdge, ...]:
        """The edges naming a spec not resolved or a file not read yet."""
        return self._binding().unread

    def variables(self, name: str | None = None) -> tuple[Variable, ...]:
        """``set`` lines and parameters in document order, then handed-in values."""
        from villanelle.written import _document

        found = [v for doc in self._documents.values() for v in _document.variables(doc)]
        found.extend(self._handed_variables[n] for n in self._handed_texts)
        return tuple(v for v in found if name is None or v.name == name)

    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """Syntax diagnostics per document, then what the binding found in walk order, except render's codes."""
        from villanelle.written import _graph

        return _graph.diagnostics(self)

    def _binding(self) -> Binding:
        from villanelle.written import _graph

        return _graph.binding(self)


@final
class Document:
    """One file as written."""

    __slots__ = ("_body", "_graph", "_path", "_source", "_starts", "_statements", "_syntax", "_text", "_values")

    _graph: DocumentGraph
    _path: str
    _text: str
    _source: str
    _syntax: Syntax
    _starts: list[int]
    """Each token's start as a ``str`` index of ``_text``, then ``len(_text)``."""
    _body: WrittenBlock
    _statements: dict[int, Statement]
    """By the token index of its node's start, in the current parse."""
    _values: dict[int, WrittenValue]
    """By the token index of its first token, in the current parse."""

    def __init__(self, graph: DocumentGraph, resolved_path: str, text: str) -> None:
        """Made by the read loop only."""
        from villanelle.written import _document

        self._graph = graph
        self._path = resolved_path
        self._source = text
        self._body = WrittenBlock(self, None)
        _document.start(self, text)

    def __repr__(self) -> str:
        return f"Document({self._path!r})"

    @property
    def resolved_path(self) -> str:
        return self._path

    @property
    def source(self) -> str:
        """As read, or as last handed to a writer that returned."""
        return self._source

    @property
    def text(self) -> str:
        """Now; differs from ``source`` exactly when unsaved."""
        return self._text

    @property
    def syntax(self) -> Syntax:
        return self._syntax

    @property
    def body(self) -> WrittenBlock:
        return self._body

    def included_by(self) -> tuple[DocumentEdge, ...]:

        return tuple(e for e in self._graph._binding().edges if self._path in e.targets)

    def replace_with_text(self, text: str, /) -> None:
        """Replace the whole text; every handle into it detaches; ``source`` is untouched."""
        from villanelle.written import _document

        _document.replace_document(self, text)


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

    __slots__ = ("_block", "_detached", "_doc", "_node", "_parent", "_value_list")

    _doc: Document
    _node: Node
    _parent: Statement | None
    _value_list: list[WrittenValue]
    _block: WrittenBlock | None
    _detached: bool

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._parent = None
        self._value_list = []
        self._block = None
        self._detached = False

    def _live(self) -> None:
        if self._detached:
            raise _detached("statement")

    @property
    def document(self) -> Document:
        self._live()
        return self._doc

    @property
    def parent(self) -> Statement | None:
        self._live()
        return self._parent

    @property
    def place(self) -> Place:
        from villanelle.written import _document

        self._live()
        return _document.place(self._doc, _document.owned_range(self._doc, self._node))

    @property
    def text(self) -> str:
        """Exact, with the comments it owns."""
        from villanelle.written import _document

        self._live()
        return _document.text_of_range(self._doc, _document.owned_range(self._doc, self._node))

    def copies(self) -> tuple[Copy, ...]:

        self._live()
        return self._doc._graph._binding().copies_of(cast("Statement", self))

    def replace_with_text(self, text: str, /) -> tuple[Statement, ...]:
        """Raises BadTextError. This handle detaches."""
        from villanelle.written import _document

        self._live()
        return _document.replace_statement(cast("Statement", self), text)

    def remove(self) -> None:
        from villanelle.written import _document

        self._live()
        _document.remove_statement(cast("Statement", self))

    def __repr__(self) -> str:
        if self._detached:
            return f"{type(self).__name__}(detached)"
        return f"{type(self).__name__}({self.text!r})"


@final
class WrittenDirective(_Statement):
    __slots__ = ("_kind",)

    _kind: Literal["directive", "extension"]

    def __init__(self, doc: Document, kind: Literal["directive", "extension"]) -> None:
        super().__init__(doc)
        self._kind = kind

    @property
    def kind(self) -> Literal["directive", "extension"]:
        return self._kind

    @property
    def name(self) -> str:
        """Read-only: change it with ``rename``."""
        self._live()
        return self._doc._syntax.tokens[self._node.start].text

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._value_list)

    @property
    def block(self) -> WrittenBlock | None:
        self._live()
        return self._block

    def rename(self, name: str, /) -> None:
        from villanelle.written import _document

        self._live()
        _document.rename_directive(self, name)

    def set_values(self, text: str, /) -> None:
        from villanelle.written import _document

        self._live()
        _document.set_values(self, self._node.start, text)


@final
class SetLine(_Statement):
    __slots__ = ("_variable",)

    _variable: Variable

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._variable = Variable("set", line=self)

    @property
    def kind(self) -> Literal["set"]:
        return "set"

    @property
    def variable(self) -> Variable:
        self._live()
        return self._variable

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        """After the ``$name``."""
        self._live()
        return tuple(self._value_list)

    def set_values(self, text: str, /) -> None:
        from villanelle.written import _document

        self._live()
        _document.set_values(self, _document.first_arg_token(self), text)


@final
class SnippetLine(_Statement):
    __slots__ = ("_parameters",)

    _parameters: list[Variable]

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._parameters = []

    @property
    def kind(self) -> Literal["snippet"]:
        return "snippet"

    @property
    def name(self) -> str:
        from villanelle.written import _document

        self._live()
        return self._doc._syntax.tokens[_document.first_arg_token(self)].text

    @property
    def parameters(self) -> tuple[Variable, ...]:
        self._live()
        return tuple(self._parameters)

    @property
    def block(self) -> WrittenBlock:
        self._live()
        assert self._block is not None, "a snippet line has a block"
        return self._block


@final
class UseLine(_Statement):
    __slots__ = ()

    @property
    def kind(self) -> Literal["use"]:
        return "use"

    @property
    def snippet_name(self) -> str:
        from villanelle.written import _document

        self._live()
        return self._doc._syntax.tokens[_document.first_arg_token(self)].text

    @property
    def snippet(self) -> SnippetLine | None:
        """By where written."""
        from villanelle.written import _document

        name = self.snippet_name
        found = _document.above(self, lambda s: isinstance(s, SnippetLine) and s.name == name)
        return found if isinstance(found, SnippetLine) else None

    def snippets(self) -> tuple[Resolution[SnippetLine], ...]:
        """Per copy."""

        self._live()
        return self._doc._graph._binding().snippets_of(self)

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._value_list)

    def set_values(self, text: str, /) -> None:
        from villanelle.written import _document

        self._live()
        _document.set_values(self, _document.first_arg_token(self), text)


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

    __slots__ = ("_doc", "_items", "_owner")

    _doc: Document
    _owner: Statement | None
    _items: list[Statement]

    def __init__(self, doc: Document, owner: Statement | None) -> None:
        self._doc = doc
        self._owner = owner
        self._items = []

    def _live(self) -> list[Statement]:
        if self._owner is not None:
            self._owner._live()
        return self._items

    @overload
    def __getitem__(self, index: int, /) -> Statement: ...

    @overload
    def __getitem__(self, index: slice, /) -> Sequence[Statement]: ...

    def __getitem__(self, index: int | slice, /) -> Statement | Sequence[Statement]:
        items = self._live()
        return items[index] if isinstance(index, int) else tuple(items[index])

    def __len__(self) -> int:
        return len(self._live())

    def __iter__(self) -> Iterator[Statement]:
        return iter(tuple(self._live()))

    def __repr__(self) -> str:
        return f"WrittenBlock({list(self._live())!r})"

    def directives(self, name: str | None = None) -> tuple[WrittenDirective, ...]:
        return tuple(
            s
            for s in self._live()
            if isinstance(s, WrittenDirective) and s.kind == "directive" and (name is None or s.name == name)
        )

    def insert_statements(self, index: int, text: str, /) -> tuple[Statement, ...]:
        """Raises BadTextError; IndexError for an index outside 0..len."""
        from villanelle.written import _document

        self._live()
        return _document.insert_statements(self, index, text)

    def add_statements(self, text: str, /) -> tuple[Statement, ...]:
        return self.insert_statements(len(self), text)


# --- Values ---


class _Value:
    """What every written value has."""

    __slots__ = ("_bound", "_detached", "_doc", "_list", "_ref", "_statement")

    _doc: Document
    _ref: ValueRef
    _statement: Statement
    _list: List | None
    _bound: bool
    """Whether it is a slice or index bound."""
    _detached: bool

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._list = None
        self._bound = False
        self._detached = False

    def _live(self) -> None:
        if self._detached:
            raise _detached("value")

    def _inner(self) -> tuple[WrittenValue, ...]:
        """The values inside it: a list's items, a slice's or index's bounds."""
        return ()

    @property
    def text(self) -> str:
        from villanelle.written import _document

        self._live()
        return _document.text_of_range(self._doc, _document.ref_range(self._ref))

    @property
    def place(self) -> Place:
        from villanelle.written import _document

        self._live()
        return _document.place(self._doc, _document.ref_range(self._ref))

    @property
    def statement(self) -> Statement:
        self._live()
        return self._statement

    @property
    def list(self) -> List | None:
        """The list it is an item of."""
        self._live()
        return self._list

    def replace_with_text(self, text: str, /) -> tuple[WrittenValue, ...]:
        from villanelle.written import _document

        self._live()
        return _document.replace_value(cast("WrittenValue", self), text)

    def remove(self) -> None:
        from villanelle.written import _document

        self._live()
        _document.remove_value(cast("WrittenValue", self))

    def __repr__(self) -> str:
        if self._detached:
            return f"{type(self).__name__}(detached)"
        return f"{type(self).__name__}({self.text!r})"


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
    __slots__ = ("_items",)

    _items: list[WrittenValue]

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._items = []

    def _inner(self) -> tuple[WrittenValue, ...]:
        return tuple(self._items)

    @property
    def kind(self) -> Literal["list"]:
        return "list"

    @property
    def items(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._items)


def _slice_name(value: _Value) -> str:
    value._live()
    ref = value._ref
    return "" if isinstance(ref, int) else value._doc._syntax.tokens[ref.start].text


@final
class Slice(_Value):
    __slots__ = ("_end", "_start")

    _start: Word | Reference | None
    _end: Word | Reference | None

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._start = None
        self._end = None

    def _inner(self) -> tuple[WrittenValue, ...]:
        return tuple(v for v in (self._start, self._end) if v is not None)

    @property
    def kind(self) -> Literal["slice"]:
        return "slice"

    @property
    def name(self) -> str:
        return _slice_name(self)

    @property
    def start(self) -> Word | Reference | None:
        self._live()
        return self._start

    @property
    def end(self) -> Word | Reference | None:
        self._live()
        return self._end


@final
class Index(_Value):
    __slots__ = ("_index",)

    _index: Word | Reference | None

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._index = None

    def _inner(self) -> tuple[WrittenValue, ...]:
        return () if self._index is None else (self._index,)

    @property
    def kind(self) -> Literal["index"]:
        return "index"

    @property
    def name(self) -> str:
        return _slice_name(self)

    @property
    def index(self) -> Word | Reference:
        self._live()
        assert self._index is not None, "an index has its bound"
        return self._index


@final
class Reference(_Value):
    """One ``$name`` written as a value."""

    __slots__ = ()

    @property
    def kind(self) -> Literal["reference"]:
        return "reference"

    @property
    def name(self) -> str:
        return self.text[1:]

    @property
    def declaration(self) -> Variable | None:
        from villanelle.written import _document

        self._live()
        return _document.declaration_of(self)

    def resolutions(self) -> tuple[ReferenceResolution, ...]:

        self._live()
        return self._doc._graph._binding().resolutions_of(self)


WrittenValue: TypeAlias = Word | String | List | Slice | Index | Reference


# --- Variables ---


@final
class Variable:
    """A ``set`` line's ``$name``, a snippet parameter, or a handed-in value."""

    __slots__ = ("_detached", "_graph", "_handed_name", "_kind", "_line", "_token")

    _kind: Literal["set", "parameter", "handed"]
    _line: SetLine | SnippetLine | None
    _token: int
    """A parameter's VARIABLE token index in the current parse."""
    _handed_name: str
    _graph: DocumentGraph | None
    _detached: bool

    def __init__(
        self,
        kind: Literal["set", "parameter", "handed"],
        *,
        line: SetLine | SnippetLine | None = None,
        name: str = "",
        graph: DocumentGraph | None = None,
    ) -> None:
        """Made by the documents and the graph only."""
        self._kind = kind
        self._line = line
        self._token = 0
        self._handed_name = name
        self._graph = graph
        self._detached = False

    def __repr__(self) -> str:
        if self._kind == "handed":
            return f"Variable('handed', {self._handed_name!r})"
        return f"Variable({self._kind!r}, {self.place!r})"

    def _owner(self) -> SetLine | SnippetLine:
        """Its line, live. Raises DetachedError."""
        if self._detached:
            raise _detached("parameter")
        line = self._line
        assert line is not None
        line._live()
        return line

    def _variable_token(self) -> int:
        from villanelle.written import _document

        line = self._owner()
        return _document.first_arg_token(line) if self._kind == "set" else self._token

    def _graph_of(self) -> DocumentGraph:
        if self._kind == "handed":
            assert self._graph is not None
            return self._graph
        return self._owner()._doc._graph

    @property
    def kind(self) -> Literal["set", "parameter", "handed"]:
        return self._kind

    @property
    def name(self) -> str:
        if self._kind == "handed":
            return self._handed_name
        return self._owner()._doc._syntax.tokens[self._variable_token()].text[1:]

    @property
    def place(self) -> Place | None:
        from villanelle.written import _document

        if self._kind == "handed":
            return None
        token = self._variable_token()
        return _document.place(self._owner()._doc, (token, token + 1))

    @property
    def line(self) -> SetLine | SnippetLine | None:
        if self._kind == "handed":
            return None
        return self._owner()

    def references(self) -> tuple[Reference, ...]:
        from villanelle.written import _document

        if self._kind == "handed":
            return ()
        graph = self._owner()._doc._graph
        return tuple(r for doc in graph._documents.values() for r in _document.references(doc) if r.declaration is self)

    def reaches(self) -> tuple[ReferenceResolution, ...]:
        return tuple(r for r in self._graph_of()._binding().resolutions if r.winner is self)

    def overridden(self) -> tuple[ReferenceResolution, ...]:
        return tuple(r for r in self._graph_of()._binding().resolutions if any(v is self for v in r.overridden))

    def rename(self, name: str, /) -> None:
        from villanelle.written import _document

        if self._kind == "handed":
            raise NoSetLineError(f"${self._handed_name} is handed in: use set_handed")
        _document.rename_variable(self._owner(), self._variable_token(), name)

    def set_values(self, text: str, /) -> None:
        """Raises NoSetLineError for a parameter or a handed-in value."""
        if self._kind == "handed":
            raise NoSetLineError(f"${self._handed_name} is handed in: use set_handed")
        line = self._owner()
        if not isinstance(line, SetLine):
            raise NoSetLineError(f"${self.name} is a snippet parameter: edit the use line's values")
        line.set_values(text)


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
