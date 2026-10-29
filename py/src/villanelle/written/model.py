"""The low level: the config as written, editable, saved back (round 12 design.md §6; slices.md S3).

One model, TypeScript's (``ts/src/written/model.ts``): a live tree with named edit methods, snake_case and
synchronous. Fields are read-only properties; a block reads as a ``Sequence``; kinds are classes, so ``match``
narrows; a handle is the same object each time (``is``) for the graph's life and follows its tokens across other
edits. A detached handle raises ``DetachedError`` from every member but ``kind``. Copies, edges and resolutions are
snapshots of one derivation of the current texts (design rule 1), not handles.

The classes hold their state; the algorithms live in the private modules beside this one: ``_document`` (the
handle tree, splices and edit checks), ``_graph`` (the read ledger, the overrides and the binding cache) and ``_bind``
(the binding).

Every edit that takes new values takes villanelle text only, as ``text``: anything but a str raises TypeError before
anything changes (use ``villanelle.quote`` for a program string, ``str()`` for a number).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, Literal, TypeAlias, TypeVar, cast, final, overload

from villanelle._api.kinds import VariableKind
from villanelle._text import require_text
from villanelle.origin import Place, Step
from villanelle.report import LocatedDiagnostic
from villanelle.syntax.cst import Node, Syntax, ValueRef
from villanelle.written.errors import DetachedError, NoSetLineError

if TYPE_CHECKING:
    from villanelle.extension import Extension
    from villanelle.source import DocumentSource
    from villanelle.written._bind import Binding, BoundValue
    from villanelle.written.save import DocumentWriter


def _detached(what: str) -> DetachedError:
    return DetachedError(f"this {what} was removed by an edit or its document's text was replaced")


# --- Files ---


@final
class DocumentGraph:
    """The files one load read, and the overrides the program passed in. It keeps the document source it was loaded
    through, so ``read`` needs nothing else (the core still does no I/O: the source does)."""

    __slots__ = (
        "_cache",
        "_documents",
        "_extension_names",
        "_extensions",
        "_failed",
        "_override_texts",
        "_override_values",
        "_override_variables",
        "_resolutions",
        "_root",
        "_source",
        "_version",
    )

    _source: DocumentSource
    _extensions: Mapping[str, Extension]
    _extension_names: frozenset[str]
    _documents: dict[str, Document]
    _root: Document | None
    _override_texts: dict[str, str]
    _override_values: dict[str, tuple[BoundValue, ...]]
    _override_variables: dict[str, Variable]
    _resolutions: dict[tuple[str, str], tuple[str, ...] | Exception]
    _failed: dict[str, Exception]
    _version: int
    _cache: tuple[int, Binding] | None

    def __init__(
        self, source: DocumentSource, extensions: Mapping[str, Extension], overrides: Mapping[str, str]
    ) -> None:
        """Made by ``Processor.load`` only. Checks each override as ``set_override`` does (one check)."""
        from villanelle.written import _graph

        _graph.init(self, source, extensions, overrides)

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
    def overrides(self) -> Mapping[str, str]:
        """The overrides by name (without ``$``), each as villanelle text, in order; a read-only view (change it with
        ``set_override``). Never saved."""
        return MappingProxyType(self._override_texts)

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """Syntax diagnostics per document, then what the binding found in walk order, except render's codes."""
        from villanelle.written import _graph

        return _graph.diagnostics(self)

    def set_override(self, name: str, text: str | None, /) -> None:
        """Add, change or (None) remove one override without a reload; it wins over every ``set`` of its name. Raises
        TypeError for a name or text that is not a str (``quote()`` a program string); ValueError for a name that is
        not letters, digits and ``_``; BadTextError for a text that is not one or more values without a ``$name``,
        located in that text."""
        from villanelle.written import _graph

        _graph.set_override(self, name, text)

    def read(self) -> list[str]:
        """Resolve and read what ``unread()`` names through the graph's document source, repeating until nothing new
        is named; keeps every text and every kept rejection (D12). Returns the resolved paths read, in read order."""
        from villanelle.written import _read

        return _read.read_unread(self)

    def save(self, writer: DocumentWriter, /) -> list[str]:
        """Hand every document whose ``text`` differs from its ``saved_text`` to ``writer`` in one batch, in
        ``documents`` order; with none, the writer is not called. When the writer returns, each written document's
        ``saved_text`` becomes the text given to it; when it raises, nothing changes and ``SaveError`` is raised from
        it. Returns the resolved paths given to the writer."""
        from villanelle.written.errors import SaveError
        from villanelle.written.save import FileWrite

        batch = [
            FileWrite(doc._path, doc._text, doc._saved) for doc in self._documents.values() if doc._text != doc._saved
        ]
        if not batch:
            return []
        try:
            writer.write(tuple(batch))
        except Exception as error:
            raise SaveError(f"the writer raised: {error}", batch) from error
        for file in batch:
            self._documents[file.resolved_path]._saved = file.text
        return [file.resolved_path for file in batch]

    def edges(self) -> tuple[DocumentEdge, ...]:
        """Every copy of every extension line, in walk order."""
        return self._binding().edges

    def unread(self) -> tuple[DocumentEdge, ...]:
        """The edges naming a spec not resolved or a file not read yet."""
        return self._binding().unread

    def variables(self, name: str | None = None) -> tuple[Variable, ...]:
        """``set`` lines and parameters in document order, then overrides."""
        from villanelle.written import _document

        found = [v for doc in self._documents.values() for v in _document.variables(doc)]
        found.extend(self._override_variables[n] for n in self._override_texts)
        return tuple(v for v in found if name is None or v.name == name)

    def _binding(self) -> Binding:
        from villanelle.written import _graph

        return _graph.binding(self)


@final
class Document:
    """One file as written."""

    __slots__ = ("_block", "_graph", "_path", "_saved", "_starts", "_statements", "_syntax", "_text", "_values")

    _graph: DocumentGraph
    _path: str
    _text: str
    _saved: str
    _syntax: Syntax
    _starts: list[int]
    """Each token's start as a ``str`` index of ``_text``, then ``len(_text)``."""
    _block: WrittenBlock
    _statements: dict[int, Statement]
    """By the token index of its node's start, in the current parse."""
    _values: dict[int, WrittenValue]
    """By the token index of its first token, in the current parse."""

    def __init__(self, graph: DocumentGraph, resolved_path: str, text: str) -> None:
        """Made by the read loop only."""
        from villanelle.written import _document

        self._graph = graph
        self._path = resolved_path
        self._saved = text
        self._block = WrittenBlock(self, None)
        _document.start(self, text)

    def __repr__(self) -> str:
        return f"Document({self._path!r})"

    @property
    def resolved_path(self) -> str:
        return self._path

    @property
    def saved_text(self) -> str:
        """As read, or as last given to a writer that returned."""
        return self._saved

    @property
    def text(self) -> str:
        """Now; differs from ``saved_text`` exactly when unsaved."""
        return self._text

    @property
    def syntax(self) -> Syntax:
        return self._syntax

    @property
    def block(self) -> WrittenBlock:
        """Its top-level statements."""
        return self._block

    def included_by(self) -> tuple[DocumentEdge, ...]:

        return tuple(e for e in self._graph._binding().edges if self._path in e.targets)

    def replace_with_text(self, text: str, /) -> None:
        """Replace the whole text; every handle into it detaches; ``saved_text`` is untouched. TypeError for a
        ``text`` that is not a str."""
        from villanelle.written import _document

        _document.replace_document(self, require_text(text, member="replace_with_text", parameter="text"))


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
        """Zero or more statements in its place, indented as it is. Raises TypeError for a ``text`` that is not a str,
        BadTextError for one that is not statements. This handle detaches."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="replace_with_text", parameter="text")
        return _document.replace_statement(cast("Statement", self), given)

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
        """Change its name to one word. TypeError for a ``name`` that is not a str; BadTextError for a reserved or
        extension name, or more than one word."""
        from villanelle.written import _document

        self._live()
        _document.rename_directive(self, require_text(name, member="rename", parameter="name"))

    def set(self, text: str, /) -> None:
        """Replace this statement's values with ``text`` (villanelle values: ``stmt.set(quote(host))``,
        ``stmt.set(str(port))``); an empty text removes them. Not the language's ``set`` line: this edits any
        statement's values. TypeError for a ``text`` that is not a str; BadTextError for one that is not values."""
        from villanelle.written import _document

        self._live()
        _document.replace_values(self, self._node.start, require_text(text, member="set", parameter="text"))


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

    def set(self, text: str, /) -> None:
        """Replace the values after the ``$name`` with ``text``, as ``WrittenDirective.set`` does."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


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

    def set(self, text: str, /) -> None:
        """Replace the values after the snippet name with ``text``, as ``WrittenDirective.set`` does."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


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
        """Raises TypeError for a ``text`` that is not a str; BadTextError for one that is not statements; IndexError
        for an index outside 0..len."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="insert_statements", parameter="text")
        return _document.insert_statements(self, index, given)

    def add_statements(self, text: str, /) -> tuple[Statement, ...]:
        """``insert_statements`` at the end."""
        from villanelle.written import _document

        items = self._live()
        given = require_text(text, member="add_statements", parameter="text")
        return _document.insert_statements(self, len(items), given)


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
        """Zero or more values in its place. TypeError for a ``text`` that is not a str; BadTextError for one that is
        not values (a slice bound: one word or ``$name``)."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="replace_with_text", parameter="text")
        return _document.replace_value(cast("WrittenValue", self), given)

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
    """A ``set`` line's ``$name``, a snippet parameter, or an override."""

    __slots__ = ("_detached", "_graph", "_kind", "_line", "_override_name", "_token")

    _kind: VariableKind
    _line: SetLine | SnippetLine | None
    _token: int
    """A parameter's VARIABLE token index in the current parse."""
    _override_name: str
    _graph: DocumentGraph | None
    _detached: bool

    def __init__(
        self,
        kind: VariableKind,
        *,
        line: SetLine | SnippetLine | None = None,
        name: str = "",
        graph: DocumentGraph | None = None,
    ) -> None:
        """Made by the documents and the graph only."""
        self._kind = kind
        self._line = line
        self._token = 0
        self._override_name = name
        self._graph = graph
        self._detached = False

    def __repr__(self) -> str:
        if self._kind == "override":
            return f"Variable('override', {self._override_name!r})"
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
        if self._kind == "override":
            assert self._graph is not None
            return self._graph
        return self._owner()._doc._graph

    @property
    def kind(self) -> VariableKind:
        return self._kind

    @property
    def name(self) -> str:
        if self._kind == "override":
            return self._override_name
        return self._owner()._doc._syntax.tokens[self._variable_token()].text[1:]

    @property
    def place(self) -> Place | None:
        from villanelle.written import _document

        if self._kind == "override":
            return None
        token = self._variable_token()
        return _document.place(self._owner()._doc, (token, token + 1))

    @property
    def line(self) -> SetLine | SnippetLine | None:
        if self._kind == "override":
            return None
        return self._owner()

    def references(self) -> tuple[Reference, ...]:
        from villanelle.written import _document

        if self._kind == "override":
            return ()
        graph = self._owner()._doc._graph
        return tuple(r for doc in graph._documents.values() for r in _document.references(doc) if r.declaration is self)

    def wins(self) -> tuple[ReferenceResolution, ...]:
        """The resolutions it wins: every ``$name`` at a copy that reads it."""
        return tuple(r for r in self._graph_of()._binding().resolutions if r.winner is self)

    def shadowed_at(self) -> tuple[ReferenceResolution, ...]:
        """The resolutions where it is visible but another definition wins."""
        return tuple(r for r in self._graph_of()._binding().resolutions if any(v is self for v in r.shadowed))

    def rename(self, name: str, /) -> None:
        """Change its ``$name`` (only this one; references keep theirs). TypeError for a ``name`` that is not a str;
        NoSetLineError for an override; BadTextError for a name that is not letters, digits and ``_``."""
        from villanelle.written import _document

        if self._kind != "override":
            self._owner()
        given = require_text(name, member="rename", parameter="name")
        if self._kind == "override":
            raise NoSetLineError(f"${self._override_name} is an override: use set_override")
        _document.rename_variable(self._owner(), self._variable_token(), given)

    def set(self, text: str, /) -> None:
        """Replace its ``set`` line's values with ``text``, as ``SetLine.set`` does. TypeError for a ``text`` that is
        not a str; NoSetLineError for a parameter (edit the use line's values) or an override (use
        ``set_override``)."""
        if self._kind != "override":
            self._owner()
        given = require_text(text, member="set", parameter="text")
        if self._kind == "override":
            raise NoSetLineError(f"${self._override_name} is an override: use set_override")
        line = self._owner()
        if not isinstance(line, SetLine):
            raise NoSetLineError(f"${self.name} is a snippet parameter: edit the use line's values")
        line.set(given)


T = TypeVar("T", Variable, SnippetLine)


@dataclass(frozen=True, slots=True, eq=False)
class Resolution(Generic[T]):
    """At one copy: what a written name reads, and what it shadows (next first)."""

    copy: Copy
    winner: T | None
    shadowed: tuple[T, ...]


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
