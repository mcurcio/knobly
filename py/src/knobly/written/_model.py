"""The low level: the config as written, editable, saved back (round 12 design.md §6; slices.md S3; spec 6).

One model, TypeScript's (``ts/src/written/model.ts``): a live tree with named edit methods, snake_case and
synchronous. Fields are read-only properties; a block reads as a ``Sequence``; every variant is its own class with a
``kind`` of its generated list and the ``__match_args__`` its generated Protocol carries, so ``match`` narrows
(``case SetLine(variable, values):``), and an operation exists only on the variants where it can succeed (spec 6.5,
6.7); a handle is the same object each time (``is``) for the graph's life and follows its tokens across other edits.
A detached handle raises ``DetachedError`` from every member but ``kind``. Copies, edges, resolutions and expansions
are snapshots of one derivation of the current texts (design rule 1), not handles.

The classes hold their state; the algorithms live in the private modules beside this one: ``_document`` (the handle
tree, splices and edit checks), ``_graph`` (the read ledger, the overrides and the binding cache), ``_bind`` (the
binding) and ``_expand`` (the expansion ``expand()`` returns).

Every edit that takes new values takes config text only, as ``text`` (``ConfigText``, spec 6.9): made by
``villanelle.quote`` from a program string or by ``villanelle.text`` from a text already written as villanelle text,
so a type checker refuses a plain str; at run time anything but a str raises TypeError before anything changes."""

from __future__ import annotations

import builtins
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypeAlias, cast, final

from villanelle._api import written as api
from villanelle._api.errors import DetachedError
from villanelle._api.kinds import StatementKind, ValueKind, VariableKind
from villanelle._api.shared import ConfigText
from villanelle._api.syntax import Node, Syntax
from villanelle._api.written import Copy, DirectiveExpansion, DocumentEdge, Expansion, ReferenceResolution, Resolution
from villanelle._block import BlockBase
from villanelle._origin import Place
from villanelle._text import require_text
from villanelle.syntax._cst import ValueRef

if TYPE_CHECKING:
    from villanelle._api.io import DocumentSource, DocumentWriter
    from villanelle._api.written import Extension
    from villanelle._report import LocatedDiagnostic
    from villanelle.written._bind import Binding, OverrideValues


def _detached(what: str) -> DetachedError:
    return DetachedError(f"this {what} was removed by an edit or its document's text was replaced")


# --- Files ---


@final
class DocumentGraph(api.DocumentGraph):
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
    _override_texts: dict[str, ConfigText]
    _override_values: dict[str, OverrideValues]
    _override_variables: dict[str, OverrideVariable]
    _resolutions: dict[tuple[str, str], tuple[str, ...] | Exception]
    _failed: dict[str, Exception]
    _version: int
    _cache: tuple[int, Binding] | None

    def __init__(
        self, source: DocumentSource, extensions: Mapping[str, Extension], overrides: Mapping[str, ConfigText]
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
        return MappingProxyType(self._documents)

    @property
    def overrides(self) -> Mapping[str, ConfigText]:
        return MappingProxyType(self._override_texts)

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        from villanelle.written import _graph

        return _graph.diagnostics(self)

    def set_override(self, name: str, text: ConfigText | None, /) -> None:
        from villanelle.written import _graph

        _graph.set_override(self, name, text)

    def read(self) -> tuple[str, ...]:
        from villanelle.written import _read

        return tuple(_read.read_unread(self))

    def save(self, writer: DocumentWriter, /) -> tuple[str, ...]:
        from villanelle._api.errors import LostUpdateError, SaveError
        from villanelle._api.io import FileWrite

        if not callable(getattr(writer, "write", None)):
            raise TypeError(
                "save() argument 'writer' must be a document writer (an object with a write method), "
                f"not {type(writer).__name__}"
            )
        batch = [
            FileWrite(doc._path, doc._text, doc._saved) for doc in self._documents.values() if doc._text != doc._saved
        ]
        if not batch:
            return ()
        paths = tuple(file.resolved_path for file in batch)
        try:
            writer.write(tuple(batch))
        except LostUpdateError:
            raise
        except Exception as error:
            raise SaveError(f"the writer raised: {error}", paths) from error
        for file in batch:
            self._documents[file.resolved_path]._saved = file.text
        return paths

    def edges(self) -> tuple[DocumentEdge, ...]:
        return self._binding().edges

    def unread(self) -> tuple[DocumentEdge, ...]:
        return self._binding().unread

    def variables(self, name: str | None = None) -> tuple[Variable, ...]:
        from villanelle.written import _document

        found: list[Variable] = [v for doc in self._documents.values() for v in _document.variables(doc)]
        found.extend(self._override_variables[n] for n in self._override_texts)
        return tuple(v for v in found if name is None or v.name == name)

    def expand(self) -> Expansion:
        from villanelle.written import _expand

        return _expand.expand(self)

    def _binding(self) -> Binding:
        from villanelle.written import _graph

        return _graph.binding(self)


@final
class Document(api.Document):
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
        return self._saved

    @property
    def text(self) -> str:
        return self._text

    @property
    def syntax(self) -> Syntax:
        return self._syntax

    @property
    def block(self) -> WrittenBlock:
        return self._block

    def included_by(self) -> tuple[DocumentEdge, ...]:
        return tuple(e for e in self._graph._binding().edges if self._path in e.targets)

    def replace_with_text(self, text: ConfigText, /) -> None:
        from villanelle.written import _document

        _document.replace_document(self, require_text(text, member="replace_with_text", parameter="text"))


# --- Statements ---


class _Statement:
    """What every statement has. Private: the public type is the union ``Statement``."""

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
    def kind(self) -> StatementKind:
        raise NotImplementedError

    @property
    def document(self) -> Document:
        self._live()
        return self._doc

    @property
    def parent(self) -> WrittenDirective | ExtensionLine | SnippetLine | None:
        self._live()
        return cast("WrittenDirective | ExtensionLine | SnippetLine | None", self._parent)

    @property
    def place(self) -> Place:
        from villanelle.written import _document

        self._live()
        return _document.place(self._doc, _document.owned_range(self._doc, self._node))

    @property
    def text(self) -> str:
        from villanelle.written import _document

        self._live()
        return _document.text_of_range(self._doc, _document.owned_range(self._doc, self._node))

    def copies(self) -> tuple[Copy, ...]:
        self._live()
        return self._doc._graph._binding().copies_of(cast("Statement", self))

    def replace_with_text(self, text: ConfigText, /) -> tuple[Statement, ...]:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="replace_with_text", parameter="text")
        return _document.replace_statement(cast("Statement", self), given)

    def remove(self) -> None:
        from villanelle.written import _document

        self._live()
        _document.remove_statement(cast("Statement", self))

    def insert_before(self, text: ConfigText, /) -> tuple[Statement, ...]:
        return self._insert(text, "insert_before", 0)

    def insert_after(self, text: ConfigText, /) -> tuple[Statement, ...]:
        return self._insert(text, "insert_after", 1)

    def _insert(self, text: ConfigText, member: str, after: int) -> tuple[Statement, ...]:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member=member, parameter="text")
        block = self._doc._block if self._parent is None else self._parent._block
        assert block is not None, "a statement's parent has a block"
        index = next(i for i, item in enumerate(block._items) if item is self)
        return _document.insert_statements(block, index + after, given)

    def __repr__(self) -> str:
        if self._detached:
            return f"{type(self).__name__}(detached)"
        return f"{type(self).__name__}({self.text!r})"


class _NamedLine(_Statement):
    """A directive line: a name, values and maybe a block (written directives and extension lines)."""

    __slots__ = ()

    @property
    def name(self) -> str:
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

    def set(self, text: ConfigText, /) -> None:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(cast("Statement", self), self._node.start, given)


@final
class WrittenDirective(_NamedLine, api.WrittenDirective):
    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.DIRECTIVE]:
        return StatementKind.DIRECTIVE

    def rename(self, name: str, /) -> None:
        from villanelle.written import _document

        self._live()
        _document.rename_directive(self, require_text(name, member="rename", parameter="name"))


@final
class ExtensionLine(_NamedLine, api.ExtensionLine):
    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.EXTENSION]:
        return StatementKind.EXTENSION

    @property
    def name(self) -> str:
        return super().name[1:]


@final
class SetLine(_Statement, api.SetLine):
    __slots__ = ("_variable",)

    _variable: SetVariable

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._variable = SetVariable(self)

    @property
    def kind(self) -> Literal[StatementKind.SET]:
        return StatementKind.SET

    @property
    def variable(self) -> SetVariable:
        self._live()
        return self._variable

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._value_list)

    def set(self, text: ConfigText, /) -> None:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


@final
class SnippetLine(_Statement, api.SnippetLine):
    __slots__ = ("_parameters",)

    _parameters: list[Parameter]

    def __init__(self, doc: Document) -> None:
        super().__init__(doc)
        self._parameters = []

    @property
    def kind(self) -> Literal[StatementKind.SNIPPET]:
        return StatementKind.SNIPPET

    @property
    def name(self) -> str:
        from villanelle.written import _document

        self._live()
        return self._doc._syntax.tokens[_document.first_arg_token(self)].text

    @property
    def parameters(self) -> tuple[Parameter, ...]:
        self._live()
        return tuple(self._parameters)

    @property
    def block(self) -> WrittenBlock:
        self._live()
        assert self._block is not None, "a snippet line has a block"
        return self._block


@final
class UseLine(_Statement, api.UseLine):
    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.USE]:
        return StatementKind.USE

    @property
    def snippet_name(self) -> str:
        from villanelle.written import _document

        self._live()
        return self._doc._syntax.tokens[_document.first_arg_token(self)].text

    @property
    def snippet(self) -> SnippetLine | None:
        from villanelle.written import _document

        name = self.snippet_name
        found = _document.above(self, lambda s: isinstance(s, SnippetLine) and s.name == name)
        return found if isinstance(found, SnippetLine) else None

    def snippets(self) -> tuple[Resolution[SnippetLine], ...]:
        self._live()
        return self._doc._graph._binding().snippets_of(self)

    @property
    def values(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._value_list)

    def set(self, text: ConfigText, /) -> None:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


@final
class UnreadableLine(_Statement, api.UnreadableLine):
    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.UNREADABLE]:
        return StatementKind.UNREADABLE


Statement: TypeAlias = WrittenDirective | ExtensionLine | SetLine | SnippetLine | UseLine | UnreadableLine
"""One statement of a block, by kind. Match it by class: ``case SetLine(variable, values):``."""


@final
class WrittenBlock(BlockBase["Statement", "WrittenDirective"], api.WrittenBlock):
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

    def _members(self) -> list[Statement]:
        return self._live()

    def _directive(self, item: Statement, /) -> WrittenDirective | None:
        return item if isinstance(item, WrittenDirective) else None

    def _name(self, directive: WrittenDirective, /) -> str:
        return directive.name

    def _inner(self, item: Statement, /) -> WrittenBlock | None:
        return item._block

    def insert_statements(self, index: int, text: ConfigText, /) -> tuple[Statement, ...]:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="insert_statements", parameter="text")
        return _document.insert_statements(self, index, given)

    def add_statements(self, text: ConfigText, /) -> tuple[Statement, ...]:
        from villanelle.written import _document

        items = self._live()
        given = require_text(text, member="add_statements", parameter="text")
        return _document.insert_statements(self, len(items), given)


# --- Values ---

ValuePart: TypeAlias = Literal["value", "bound", "name"]
"""Where a written value stands: a line's value or a list item; a slice's or index's bound; a slice's or index's
name. It picks the entry rule its ``set`` and ``replace_with_text`` take."""


class _Value:
    """What every written value has. Private: the public type is the union ``WrittenValue``. The six value classes
    share this one slot layout (each adds no slot), so a ``set`` that writes a value of another kind keeps the handle
    and reassigns its class (Python Cookbook recipe 8.19's ``__class__`` state pattern)."""

    __slots__ = (
        "_detached",
        "_doc",
        "_end",
        "_index",
        "_items",
        "_list",
        "_name",
        "_part",
        "_ref",
        "_start",
        "_statement",
    )

    _doc: Document
    _ref: ValueRef
    _statement: Statement
    _list: List | None
    _part: ValuePart
    _detached: bool
    _items: builtins.list[WrittenValue]
    """A list's items (empty for any other kind)."""
    _name: Word | Reference | None
    """A slice's or index's name (None for any other kind)."""
    _start: Word | Reference | None
    _end: Word | Reference | None
    _index: Word | Reference | None
    """A slice's bounds, an index's bound (None for any other kind)."""

    def __init__(self, doc: Document) -> None:
        self._doc = doc
        self._list = None
        self._part = "value"
        self._detached = False
        self._clear()

    def _clear(self) -> None:
        """No inner values: what a (re)build starts from."""
        self._items = []
        self._name = None
        self._start = None
        self._end = None
        self._index = None

    def _live(self) -> None:
        if self._detached:
            raise _detached("value")

    def _inner(self) -> tuple[WrittenValue, ...]:
        """The values inside it, in text order: a list's items, a slice's or index's name and bounds."""
        parts = (self._name, self._start, self._end, self._index)
        return (*self._items, *(v for v in parts if v is not None))

    @property
    def kind(self) -> ValueKind:
        raise NotImplementedError

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
        self._live()
        return self._list

    def set(self, text: ConfigText, /) -> None:
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.set_value(cast("WrittenValue", self), given)

    def replace_with_text(self, text: ConfigText, /) -> tuple[WrittenValue, ...]:
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
class Word(_Value, api.Word):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.WORD]:
        return ValueKind.WORD


@final
class String(_Value, api.String):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.STRING]:
        return ValueKind.STRING


@final
class List(_Value, api.List):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.LIST]:
        return ValueKind.LIST

    @property
    def items(self) -> tuple[WrittenValue, ...]:
        self._live()
        return tuple(self._items)


@final
class Slice(_Value, api.Slice):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.SLICE]:
        return ValueKind.SLICE

    @property
    def name(self) -> Word | Reference:
        self._live()
        assert self._name is not None, "a slice has its name"
        return self._name

    @property
    def start(self) -> Word | Reference | None:
        self._live()
        return self._start

    @property
    def end(self) -> Word | Reference | None:
        self._live()
        return self._end


@final
class Index(_Value, api.Index):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.INDEX]:
        return ValueKind.INDEX

    @property
    def name(self) -> Word | Reference:
        self._live()
        assert self._name is not None, "an index has its name"
        return self._name

    @property
    def index(self) -> Word | Reference:
        self._live()
        assert self._index is not None, "an index has its bound"
        return self._index


@final
class Reference(_Value, api.Reference):
    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.REFERENCE]:
        return ValueKind.REFERENCE

    @property
    def name(self) -> str:
        return self.text[1:]

    @property
    def declaration(self) -> SetVariable | Parameter | None:
        from villanelle.written import _document

        self._live()
        return _document.declaration_of(self)

    def resolutions(self) -> tuple[ReferenceResolution, ...]:
        self._live()
        return self._doc._graph._binding().resolutions_of(self)


WrittenValue: TypeAlias = Word | String | List | Slice | Index | Reference
"""One value as written, by kind. Match it by class: ``case List(items):``."""


# --- Variables ---


class _Variable:
    """What every variable has: ``kind``, ``name``, ``references()``, ``wins()``, ``shadowed_at()``. Private: the
    public type is the union ``Variable``."""

    __slots__ = ()

    @property
    def kind(self) -> VariableKind:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    def _graph_of(self) -> DocumentGraph:
        raise NotImplementedError

    def references(self) -> tuple[Reference, ...]:
        from villanelle.written import _document

        graph = self._graph_of()
        me: object = self
        return tuple(r for doc in graph._documents.values() for r in _document.references(doc) if r.declaration is me)

    def wins(self) -> tuple[ReferenceResolution, ...]:
        me: object = self
        return tuple(r for r in self._graph_of()._binding().resolutions if r.winner is me)

    def shadowed_at(self) -> tuple[ReferenceResolution, ...]:
        me: object = self
        return tuple(r for r in self._graph_of()._binding().resolutions if any(v is me for v in r.shadowed))


@final
class SetVariable(_Variable, api.SetVariable):
    __slots__ = ("_line",)

    _line: SetLine

    def __init__(self, line: SetLine) -> None:
        """Made by its set line only."""
        self._line = line

    def __repr__(self) -> str:
        if self._line._detached:
            return "SetVariable(detached)"
        return f"SetVariable({self.name!r})"

    def _token(self) -> int:
        from villanelle.written import _document

        self._line._live()
        return _document.first_arg_token(self._line)

    def _graph_of(self) -> DocumentGraph:
        self._line._live()
        return self._line._doc._graph

    @property
    def kind(self) -> Literal[VariableKind.SET]:
        return VariableKind.SET

    @property
    def name(self) -> str:
        return self._line._doc._syntax.tokens[self._token()].text[1:]

    @property
    def place(self) -> Place:
        from villanelle.written import _document

        token = self._token()
        return _document.place(self._line._doc, (token, token + 1))

    @property
    def line(self) -> SetLine:
        self._line._live()
        return self._line

    def rename(self, name: str, /) -> None:
        from villanelle.written import _document

        token = self._token()
        given = require_text(name, member="rename", parameter="name")
        _document.rename_variable(self._line, token, given)

    def set(self, text: ConfigText, /) -> None:
        self._line._live()
        self._line.set(text)


@final
class Parameter(_Variable, api.Parameter):
    __slots__ = ("_detached", "_line", "_token")

    _line: SnippetLine
    _token: int
    """Its VARIABLE token index in the current parse."""
    _detached: bool

    def __init__(self, line: SnippetLine) -> None:
        """Made by its snippet line only."""
        self._line = line
        self._token = 0
        self._detached = False

    def __repr__(self) -> str:
        if self._detached or self._line._detached:
            return "Parameter(detached)"
        return f"Parameter({self.name!r})"

    def _owner(self) -> SnippetLine:
        """Its line, live. Raises DetachedError."""
        if self._detached:
            raise _detached("parameter")
        self._line._live()
        return self._line

    def _graph_of(self) -> DocumentGraph:
        return self._owner()._doc._graph

    @property
    def kind(self) -> Literal[VariableKind.PARAMETER]:
        return VariableKind.PARAMETER

    @property
    def name(self) -> str:
        return self._owner()._doc._syntax.tokens[self._token].text[1:]

    @property
    def place(self) -> Place:
        from villanelle.written import _document

        line = self._owner()
        return _document.place(line._doc, (self._token, self._token + 1))

    @property
    def line(self) -> SnippetLine:
        return self._owner()

    def rename(self, name: str, /) -> None:
        from villanelle.written import _document

        line = self._owner()
        given = require_text(name, member="rename", parameter="name")
        _document.rename_variable(line, self._token, given)


@final
class OverrideVariable(_Variable, api.OverrideVariable):
    __slots__ = ("_graph", "_name")

    _graph: DocumentGraph
    _name: str

    def __init__(self, name: str, graph: DocumentGraph) -> None:
        """Made by the graph only."""
        self._name = name
        self._graph = graph

    def __repr__(self) -> str:
        return f"OverrideVariable({self._name!r})"

    def _graph_of(self) -> DocumentGraph:
        return self._graph

    @property
    def kind(self) -> Literal[VariableKind.OVERRIDE]:
        return VariableKind.OVERRIDE

    @property
    def name(self) -> str:
        return self._name

    def references(self) -> tuple[Reference, ...]:
        return ()


Variable: TypeAlias = SetVariable | Parameter | OverrideVariable
"""A variable, by kind. Match it by class: ``case SetVariable(name):``."""

# --- The expansion (spec 6.10): the records are generated (``Expansion``, ``DirectiveExpansion``,
# ``UnreadableExpansion``); its block is this one ---


@final
class ExpansionBlock(BlockBase[DirectiveExpansion, DirectiveExpansion], api.ExpansionBlock):
    __slots__ = ("_items",)

    def __init__(self, items: tuple[DirectiveExpansion, ...]) -> None:
        """Made by the expansion only."""
        self._items = items

    def _members(self) -> tuple[DirectiveExpansion, ...]:
        return self._items

    def _directive(self, item: DirectiveExpansion, /) -> DirectiveExpansion:
        return item

    def _name(self, directive: DirectiveExpansion, /) -> str:
        return directive.written.name

    def _inner(self, item: DirectiveExpansion, /) -> ExpansionBlock | None:
        block = item.block
        assert block is None or isinstance(block, ExpansionBlock)
        return block
