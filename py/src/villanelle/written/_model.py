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
        """Every file read, by resolved path, root first, then in first-read order. Never shrinks."""
        return MappingProxyType(self._documents)

    @property
    def overrides(self) -> Mapping[str, ConfigText]:
        """The overrides by name (without ``$``), each the config text the program gave, in order; a read-only view
        (change it with ``set_override``). Never saved."""
        return MappingProxyType(self._override_texts)

    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]:
        """The one list (spec 6.3): each document's syntax diagnostics (documents in order), then every problem the
        low level finds, in walk order. The expansion's and the render's ``diagnostics`` are this same list."""
        from villanelle.written import _graph

        return _graph.diagnostics(self)

    def set_override(self, name: str, text: ConfigText | None, /) -> None:
        """Add, change or (None) remove one override without a reload; which ``set`` lines it wins over is
        spec/expansion.md 5. Raises TypeError for a name or text that is not a str (``quote()`` a program string,
        ``text()`` one already written as villanelle text);
        ValueError (misuse) for a name that is not letters, digits and ``_``; BadTextError for a text the
        ``valuesText`` entry rule refuses or that is not one or more values without a ``$name``, located in that
        text."""
        from villanelle.written import _graph

        _graph.set_override(self, name, text)

    def read(self) -> tuple[str, ...]:
        """Resolve and read what ``unread()`` names through the graph's document source, repeating until nothing new
        is named; keeps every text and every kept rejection (D12). Returns the resolved paths read, in read order."""
        from villanelle.written import _read

        return tuple(_read.read_unread(self))

    def save(self, writer: DocumentWriter, /) -> tuple[str, ...]:
        """Hand every document whose ``text`` differs from its ``saved_text`` to ``writer`` in one batch, in
        ``documents`` order; with none, the writer is not called. When the writer returns, each written document's
        ``saved_text`` becomes the text given to it; when it raises, nothing changes: a ``LostUpdateError`` (the
        writer's ``check_lost_updates``) is raised as it is, anything else as a ``SaveError`` (its ``paths`` the
        batch's resolved paths) from it. Returns the resolved paths given to the writer. Raises TypeError first when
        ``writer`` is not a document writer (no callable ``write``)."""
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
        """Every copy of every extension line, in walk order."""
        return self._binding().edges

    def unread(self) -> tuple[DocumentEdge, ...]:
        """The edges naming a spec not resolved or a file not read yet; each such copy expands to an unreadable
        with reason ``unread`` and E3007 in ``diagnostics`` (spec 6.10)."""
        return self._binding().unread

    def variables(self, name: str | None = None) -> tuple[Variable, ...]:
        """``set`` lines and parameters in document order, then overrides."""
        from villanelle.written import _document

        found: list[Variable] = [v for doc in self._documents.values() for v in _document.variables(doc)]
        found.extend(self._override_variables[n] for n in self._override_texts)
        return tuple(v for v in found if name is None or v.name == name)

    def expand(self) -> Expansion:
        """The current texts and overrides after expansion (spec 6.10): every copy of every directive as read, its
        values with their links to the written text, and what could not be read. What ``render`` builds the rendered
        tree from. A snapshot of the graph's one derivation (a new one after any change); pure: reads no file."""
        from villanelle.written import _expand

        return _expand.expand(self)

    def _binding(self) -> Binding:
        from villanelle.written import _graph

        return _graph.binding(self)


@final
class Document(api.Document):
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

    def replace_with_text(self, text: ConfigText, /) -> None:
        """Replace the whole text; every handle into it detaches; ``saved_text`` is untouched. TypeError for a
        ``text`` that is not a str."""
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
        """The statement whose block holds it; None at a document's top level."""
        self._live()
        return cast("WrittenDirective | ExtensionLine | SnippetLine | None", self._parent)

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

    def replace_with_text(self, text: ConfigText, /) -> tuple[Statement, ...]:
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

    def insert_before(self, text: ConfigText, /) -> tuple[Statement, ...]:
        """Statements inserted just before this one in its block: its block's ``insert_statements`` at this one's
        index. TypeError for a ``text`` that is not a str; BadTextError for one that is not statements."""
        return self._insert(text, "insert_before", 0)

    def insert_after(self, text: ConfigText, /) -> tuple[Statement, ...]:
        """Statements inserted just after this one in its block: its block's ``insert_statements`` at this one's
        index plus one. TypeError for a ``text`` that is not a str; BadTextError for one that is not statements."""
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
        """Read-only: a written directive changes it with ``rename``."""
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
        """Replace this statement's values with ``text`` (config text: ``stmt.set(quote(host))``,
        ``stmt.set(text(str(port)))``); the empty text removes them. Not the language's ``@set`` line: this edits any
        statement's values. TypeError for a ``text`` that is not a str; BadTextError for one the ``valuesText``
        entry rule refuses (spec 2.8: a ``;``, a block, a comment the text ends in), and E2001 at 0:0 for a text that
        holds no value and is not empty (``"# c\n"``, ``"  "``); a line break is whitespace."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(cast("Statement", self), self._node.start, given)


@final
class WrittenDirective(_NamedLine, api.WrittenDirective):
    """A directive as written (``port 8080;``, ``node { ... }``, ``use epoll;``): a statement headed by a word, whatever
    its text; ``@set``, ``@snippet``, ``@use`` and extension lines are headed by ``@`` (spec 2.5)."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.DIRECTIVE]:
        return StatementKind.DIRECTIVE

    def rename(self, name: str, /) -> None:
        """Change its name. TypeError for a ``name`` that is not a str; ValueError (misuse, spec 2.8) for a name the
        grammar's ``nameText`` entry rule refuses (not one word: starting with a digit, ``-`` or ``@``), and for
        nothing else: no name is reserved (``use``, ``include`` are directive names like any other)."""
        from villanelle.written import _document

        self._live()
        _document.rename_directive(self, require_text(name, member="rename", parameter="name"))


@final
class ExtensionLine(_NamedLine, api.ExtensionLine):
    """A line headed by ``@`` and a registered extension's name (``@include "sink.conf";``): its values are the
    extension's, its block holds ``@set`` lines. No ``rename``: a new name would change its kind."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.EXTENSION]:
        return StatementKind.EXTENSION

    @property
    def name(self) -> str:
        """The extension's name, without ``@`` (``include``)."""
        return super().name[1:]


@final
class SetLine(_Statement, api.SetLine):
    """``@set $name values;``."""

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
        """After the ``$name``."""
        self._live()
        return tuple(self._value_list)

    def set(self, text: ConfigText, /) -> None:
        """Replace the values after the ``$name`` with ``text``, as ``WrittenDirective.set`` does."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


@final
class SnippetLine(_Statement, api.SnippetLine):
    """``@snippet name $param... { body }``."""

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
    """``@use name values;``."""

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

    def set(self, text: ConfigText, /) -> None:
        """Replace the values after the snippet name with ``text``, as ``WrittenDirective.set`` does."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.replace_values(self, _document.first_arg_token(self), given)


@final
class UnreadableLine(_Statement, api.UnreadableLine):
    """A statement that cannot be read by its text alone: a syntax error, a malformed ``@set``, ``@snippet`` or
    ``@use`` line, or an ``@name`` no extension owns (E3008)."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[StatementKind.UNREADABLE]:
        return StatementKind.UNREADABLE


Statement: TypeAlias = WrittenDirective | ExtensionLine | SetLine | SnippetLine | UseLine | UnreadableLine
"""One statement of a block, by kind. Match it by class: ``case SetLine(variable, values):``."""


@final
class WrittenBlock(BlockBase["Statement", "WrittenDirective"], api.WrittenBlock):
    """The statements of a document or a block (spec 2.11): iterate, index, ``len``, ``in``, ``directives(name)``
    (written directives only: extension lines are not listed) and ``walk`` (every statement at any depth, through
    written directives', extension lines' and snippet lines' blocks)."""

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
        """Raises TypeError for a ``text`` that is not a str; BadTextError for one that is not statements; IndexError
        for an index outside 0..len."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="insert_statements", parameter="text")
        return _document.insert_statements(self, index, given)

    def add_statements(self, text: ConfigText, /) -> tuple[Statement, ...]:
        """``insert_statements`` at the end."""
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
        """The list it is an item of."""
        self._live()
        return self._list

    def set(self, text: ConfigText, /) -> None:
        """Replace this value with exactly one value and keep the handle (spec 6.1, 6.6): the same object stays where
        it was (its statement's ``values``, its list's ``items``, its slice's bound or name) and now holds the new
        value, of the new value's kind: its class becomes that kind's class (``Word`` set to ``"[1, 2]"`` is a
        ``List``). Its old items, bounds and name detach. Setting it again, through any copy that shares it, writes
        again. TypeError for a ``text`` that is not a str; BadTextError for one its entry rule refuses (spec 2.8):
        ``valueText`` (exactly one value), a bound's ``boundText``, a slice name's ``sliceNameText``."""
        from villanelle.written import _document

        self._live()
        given = require_text(text, member="set", parameter="text")
        _document.set_value(cast("WrittenValue", self), given)

    def replace_with_text(self, text: ConfigText, /) -> tuple[WrittenValue, ...]:
        """Zero or more values in its place. TypeError for a ``text`` that is not a str; BadTextError for one its
        entry rule refuses (spec 2.8): ``valuesText``; a list item's ``itemsText`` (no trailing ``,``); a slice or index
        bound's ``boundText`` (one integer word or ``$name``); a slice or index name's ``sliceNameText``. This handle
        detaches."""
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
    """``name[start~end]``: its name and bounds are written values (a word or a ``$name`` each)."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.SLICE]:
        return ValueKind.SLICE

    @property
    def name(self) -> Word | Reference:
        """The slice name before ``[``: a word, or a ``$name`` holding one (``$src[0~3]``)."""
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
    """``name[index]``: its name and bound are written values (a word or a ``$name`` each)."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.INDEX]:
        return ValueKind.INDEX

    @property
    def name(self) -> Word | Reference:
        """The name before ``[``: a word, or a ``$name`` holding one (``$s[1]``)."""
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
    """One ``$name`` written as a value."""

    __slots__ = ()

    @property
    def kind(self) -> Literal[ValueKind.REFERENCE]:
        return ValueKind.REFERENCE

    @property
    def name(self) -> str:
        return self.text[1:]

    @property
    def declaration(self) -> SetVariable | Parameter | None:
        """The variable it binds to by where it is written; None when free (an override, or nothing)."""
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
        """The ``$name``s written to read it, by where they are written (``Reference.declaration``), in document
        order. Lexical only: a ``$name`` in an included file has no declaration (it is resolved per copy), so it is
        not here; every use, per copy, is in ``wins()`` and ``shadowed_at()``."""
        from villanelle.written import _document

        graph = self._graph_of()
        me: object = self
        return tuple(r for doc in graph._documents.values() for r in _document.references(doc) if r.declaration is me)

    def wins(self) -> tuple[ReferenceResolution, ...]:
        """The resolutions it wins: every ``$name`` at a copy that reads it."""
        me: object = self
        return tuple(r for r in self._graph_of()._binding().resolutions if r.winner is me)

    def shadowed_at(self) -> tuple[ReferenceResolution, ...]:
        """The resolutions where it is visible but another definition wins."""
        me: object = self
        return tuple(r for r in self._graph_of()._binding().resolutions if any(v is me for v in r.shadowed))


@final
class SetVariable(_Variable, api.SetVariable):
    """A ``set`` line's ``$name``. It detaches with its line."""

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
        """Its ``$name``."""
        from villanelle.written import _document

        token = self._token()
        return _document.place(self._line._doc, (token, token + 1))

    @property
    def line(self) -> SetLine:
        self._line._live()
        return self._line

    def rename(self, name: str, /) -> None:
        """Change its ``$name`` (only this one; references keep theirs). TypeError for a ``name`` that is not a str;
        ValueError (misuse) for a name that is not letters, digits and ``_``; BadTextError for one set twice in its
        block (E5002)."""
        from villanelle.written import _document

        token = self._token()
        given = require_text(name, member="rename", parameter="name")
        _document.rename_variable(self._line, token, given)

    def set(self, text: ConfigText, /) -> None:
        """Replace its ``set`` line's values with ``text``, as ``SetLine.set`` does."""
        self._line._live()
        self._line.set(text)


@final
class Parameter(_Variable, api.Parameter):
    """A snippet line's ``$param``: no ``set`` (edit a use line's values instead)."""

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
        """Its ``$name`` in the snippet line."""
        from villanelle.written import _document

        line = self._owner()
        return _document.place(line._doc, (self._token, self._token + 1))

    @property
    def line(self) -> SnippetLine:
        return self._owner()

    def rename(self, name: str, /) -> None:
        """Change its ``$name`` (only this one). TypeError for a ``name`` that is not a str; ValueError (misuse) for a
        name that is not letters, digits and ``_``."""
        from villanelle.written import _document

        line = self._owner()
        given = require_text(name, member="rename", parameter="name")
        _document.rename_variable(line, self._token, given)


@final
class OverrideVariable(_Variable, api.OverrideVariable):
    """An override as a variable: no place, no line, no ``rename``, no ``set`` (``DocumentGraph.set_override``
    changes it). One per name for the graph's life; never detached."""

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
        """None: an override is declared by no written line (its readers are in ``wins()``)."""
        return ()


Variable: TypeAlias = SetVariable | Parameter | OverrideVariable
"""A variable, by kind. Match it by class: ``case SetVariable(name):``."""

# --- The expansion (spec 6.10): the records are generated (``Expansion``, ``DirectiveExpansion``,
# ``UnreadableExpansion``); its block is this one ---


@final
class ExpansionBlock(BlockBase[DirectiveExpansion, DirectiveExpansion], api.ExpansionBlock):
    """The readable directive copies of one block of one copy, in walk order (includes and uses spliced in place):
    the top level's is ``Expansion.block``, a directive expansion's its ``block``. A snapshot."""

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
