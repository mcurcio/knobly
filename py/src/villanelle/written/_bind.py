"""The binding (design rule 3; slices.md 2.5): one derivation of the graph's current texts, overrides and read
ledger. It walks the copies (the root, then each include and ``use`` spliced in place), decides per copy what each
``$name`` and ``use`` reads (spec/expansion.md), and expands written values into the low level's expanded values,
with their links, for the extension lines (an include's path) and for the expansion. It is the one home of the
name-lookup rule: ``_expand`` turns its ``items`` into the public expansion (``DocumentGraph.expand()``), which the
rendered layer builds on, so nothing above it looks a name up. It names no rendered type. Private; pure (no I/O); a
port of ts/src/written/bind.ts.

The walk is PR 3's expander (cb08803) moved here, unchanged in what it decides and reports, with the read ledger in
place of reading files during the walk."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol, TypeAlias

from villanelle import _values
from villanelle._anatomy import Anatomy, anatomy_of, items_of, values_of
from villanelle._api import shared
from villanelle._api import written as api
from villanelle._api.codes import DiagnosticCode, describe
from villanelle._api.errors import DiagnosticError
from villanelle._api.kinds import (
    NodeKind,
    StatementKind,
    StepKind,
    TokenKind,
    UnreadableReason,
    ValueKind,
    statement_of_keyword,
)
from villanelle._api.limits import MAX_DEPTH, MAX_DIRECTIVES
from villanelle._api.shared import DirectiveOrigin, Origin, SourceSpan
from villanelle._api.syntax import Node, Syntax, Token, TokenRange
from villanelle._api.written import Copy, DocumentEdge, ExtensionUse, ReferenceResolution, Resolution
from villanelle._origin import Override, Place, Step
from villanelle._report import LocatedDiagnostic
from villanelle._text import port_texts
from villanelle.syntax._cst import ValueRef, span_of
from villanelle.syntax._parse import parse_entry
from villanelle.written._model import (
    Document,
    Index,
    Reference,
    SetLine,
    Slice,
    SnippetLine,
    Statement,
    UseLine,
    Variable,
    WrittenValue,
    own,
)
from villanelle.written._shape import shape_of_anatomy
from villanelle.written._value import (
    ExpandedIndex,
    ExpandedList,
    ExpandedSlice,
    ExpandedString,
    ExpandedValue,
    ExpandedWord,
)

if TYPE_CHECKING:
    from villanelle._api.written import Extension


def _names_a_slice(word: str) -> bool:
    """Whether a word may name a slice: what the grammar's ``sliceNameText`` entry rule takes (spec/expansion.md 8)."""
    return not parse_entry(word, "sliceNameText").diagnostics


@dataclass(frozen=True, slots=True, eq=False)
class BoundDirective:
    """One copy of a directive statement (kind "directive"), with its block's items at that copy."""

    copy: Copy
    children: list[BoundItem] | None
    """None when written without a block."""


@dataclass(frozen=True, slots=True, eq=False)
class BoundUnreadable:
    """One copy of a statement that cannot be read there."""

    copy: Copy
    reason: UnreadableReason
    diagnostic: shared.LocatedDiagnostic | None
    """None when the problem is already one of a document's syntax diagnostics."""


BoundItem: TypeAlias = BoundDirective | BoundUnreadable


class BindingProblem(Exception):
    """A written value that cannot be expanded at a copy (E5001, E4001): the statement is unreadable there."""

    def __init__(self, reason: UnreadableReason, diagnostic: shared.LocatedDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.reason = reason
        self.diagnostic = diagnostic


class ReadLedger(Protocol):
    """Which files were read: the one piece of state besides the texts (design rule 1)."""

    def resolved(self, parent_path: str, spec: str, /) -> tuple[str, ...] | Exception | None: ...

    def read(self, resolved_path: str, /) -> Document | Exception | None: ...


@dataclass(frozen=True, slots=True)
class OverrideValues:
    """An override's text, read once as values. ``long_bound``: the text holds a literal slice or index bound beyond
    ±(2**53 - 1) (the grammar cannot check the range), so every ``$name`` that reads the override is E4001 there, as
    for a bad bound through a variable."""

    values: tuple[ExpandedValue, ...]
    long_bound: bool


@dataclass(frozen=True, slots=True)
class OverrideInput:
    """An override: its variable handle and its values, already read."""

    variable: Variable
    values: OverrideValues


@dataclass(frozen=True, slots=True)
class ResolveNeed:
    parent_path: str
    specs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadNeed:
    paths: tuple[str, ...]


Need: TypeAlias = ResolveNeed | ReadNeed
"""What an unread edge still needs from the source: specs to resolve, or paths to read."""


def bind(
    root: Document,
    extensions: Mapping[str, Extension],
    overrides: Mapping[str, OverrideInput],
    reads: ReadLedger,
) -> Binding:
    """Derive the binding of these inputs. Pure and synchronous."""
    binding = Binding(extensions, overrides, reads)
    binding._run(root)
    return binding


def override_values(name: str, text: str) -> OverrideValues:
    """An override's values: the text, already checked (``_graph.check_override``), parsed with the ``valuesText``
    entry rule and read as values (never through a probe document)."""
    syntax = parse_entry(text, "valuesText")
    reader = Binding({}, {}, None)
    given = _Text(None, syntax, "", name)
    try:
        values = tuple(
            value
            for ref in values_of(syntax.tokens, syntax.root)
            for value in reader.value(given, ref, _Scope(None), (), None)
        )
    except _Problem:
        return OverrideValues((), True)
    return OverrideValues(values, False)


# --- The walk ---


@dataclass(frozen=True, slots=True)
class _Text:
    """One text being walked: a document, or an override's text (``override`` is its name)."""

    doc: Document | None
    syntax: Syntax
    resolved_path: str
    override: str | None = None

    def written(self, span: SourceSpan) -> Place | Override:
        return Place(self.resolved_path, span) if self.override is None else Override(self.override)

    def place(self, span: SourceSpan) -> Place:
        return Place(self.resolved_path, span)


def _document_text(doc: Document) -> _Text:
    return _Text(doc, doc._syntax, doc._path)


class _Problem(Exception):
    """A statement that cannot be read: raised inside a statement, caught where it is kept unreadable."""

    def __init__(self, reason: UnreadableReason, diagnostic: shared.LocatedDiagnostic | None) -> None:
        super().__init__(reason if diagnostic is None else diagnostic.message)
        self.reason = reason
        self.diagnostic = diagnostic


class _ValueProblem(_Problem):
    """A problem with one of a directive's values: the directive is unreadable there, and arguments_at raises it."""


@dataclass(frozen=True, slots=True, eq=False)
class _Definition:
    """One definition of a name: its variable, the values a reader gets (without the definer's steps), as written."""

    variable: Variable
    values: tuple[ExpandedValue, ...]
    written: tuple[WrittenValue, ...]
    long_bound: bool = False
    """An override's literal bound beyond the integer range (``OverrideValues``): reading it is E4001."""


class _Precedence(Enum):
    """What kind of definition an entry is, for ``_pick``: a snippet parameter, a ``set``, or an include block's
    ``set`` (forced: it wins over every ``set`` of the spliced files)."""

    PARAMETER = "parameter"
    SET = "set"
    FORCED = "forced"


@dataclass(frozen=True, slots=True)
class _Entry:
    """One visible definition of a name, and its precedence."""

    kind: _Precedence
    definition: _Definition


@dataclass(frozen=True, slots=True, eq=False)
class _Snippet:
    """A snippet definition: its parameters, its body and the scope it was written in (lexical, rule 6)."""

    name: str
    params: tuple[str, ...]
    body: Node
    text: _Text
    scope: _ScopeView
    line: SnippetLine


class _ScopeView(Protocol):
    def entries(self, name: str, out: list[_Entry]) -> None:
        """Every definition of ``name`` visible here, innermost first."""
        ...

    def snippets(self, name: str, out: list[_Snippet]) -> None:
        """Every snippet of ``name`` visible here, innermost first."""
        ...


class _BlockScope(_ScopeView, Protocol):
    def claim(self, name: str) -> bool: ...

    def bind(self, name: str, definition: _Definition) -> None: ...

    def define(self, snippet: _Snippet) -> bool: ...


class _Scope:
    """The variables and snippets of one block: its own lines so far, then the enclosing view's."""

    __slots__ = ("_claimed", "_defined", "_outer", "_params", "_vars")

    def __init__(self, outer: _ScopeView | None) -> None:
        self._outer = outer
        self._vars: dict[str, _Definition] = {}
        self._params: dict[str, _Definition] = {}
        self._claimed: set[str] = set()
        self._defined: dict[str, _Snippet] = {}

    def entries(self, name: str, out: list[_Entry]) -> None:
        if name in self._params:
            out.append(_Entry(_Precedence.PARAMETER, self._params[name]))
        if name in self._vars:
            out.append(_Entry(_Precedence.SET, self._vars[name]))
        if self._outer is not None:
            self._outer.entries(name, out)

    def snippets(self, name: str, out: list[_Snippet]) -> None:
        if name in self._defined:
            out.append(self._defined[name])
        if self._outer is not None:
            self._outer.snippets(name, out)

    def claim(self, name: str) -> bool:
        if name in self._claimed:
            return False
        self._claimed.add(name)
        return True

    def bind(self, name: str, definition: _Definition) -> None:
        self._vars[name] = definition

    def param(self, name: str, definition: _Definition) -> None:
        """Bind a snippet parameter: the body block's own binding of that name (S3-03)."""
        self._claimed.add(name)
        self._params[name] = definition

    def define(self, snippet: _Snippet) -> bool:
        if snippet.name in self._defined:
            return False
        self._defined[snippet.name] = snippet
        return True

    def own(self) -> Mapping[str, _Definition]:
        """The variables this block bound itself (an extension block's ``set`` lines)."""
        return self._vars


class _SpliceScope:
    """The including block's scope as a spliced file sees it (the rules: spec/expansion.md 4 and 7): the file's
    top-level ``set`` and ``snippet`` lines bind in the including block, and the extension block's ``set`` lines are
    "forced" entries for ``_pick``."""

    __slots__ = ("_overrides", "_target")

    def __init__(self, target: _BlockScope, overrides: Mapping[str, _Definition]) -> None:
        self._target = target
        self._overrides = overrides

    def entries(self, name: str, out: list[_Entry]) -> None:
        if name in self._overrides:
            out.append(_Entry(_Precedence.FORCED, self._overrides[name]))
        self._target.entries(name, out)

    def snippets(self, name: str, out: list[_Snippet]) -> None:
        self._target.snippets(name, out)

    def claim(self, name: str) -> bool:
        return self._target.claim(name)

    def bind(self, name: str, definition: _Definition) -> None:
        self._target.bind(name, definition)

    def define(self, snippet: _Snippet) -> bool:
        return self._target.define(snippet)


def _pick(entries: Sequence[_Entry], override: _Definition | None) -> _Definition | None:
    """The winner among ``entries`` (innermost first) and an override: the precedence table of spec/expansion.md
    (the one statement of the rule; this is its code)."""
    found: _Entry | None = None
    for entry in entries:
        if entry.kind is _Precedence.PARAMETER and found is None:
            return entry.definition
        if entry.kind is _Precedence.SET and found is None:
            found = entry
        if entry.kind is _Precedence.FORCED:
            found = entry
            break
    if override is not None:
        return override
    return None if found is None else found.definition


def _ordered(entries: Sequence[_Entry], override: _Definition | None) -> list[_Definition]:
    """Every visible definition in the order the rule picks them, each as if those before it were removed."""
    out: list[_Definition] = []
    left = list(entries)
    passed_in = override
    while True:
        chosen = _pick(left, passed_in)
        if chosen is None:
            return out
        out.append(chosen)
        if chosen is passed_in:
            passed_in = None
        else:
            left = [entry for entry in left if entry.definition is not chosen]


@dataclass(frozen=True, slots=True)
class _Context:
    """One place statements are walked into."""

    text: _Text
    scope: _BlockScope
    via: tuple[Step, ...]
    """The steps that brought this text here, innermost first."""
    open: tuple[_Snippet | str, ...]
    """The snippets and files being walked around this place, outermost first; the root file first."""
    into: list[BoundItem]


@dataclass(slots=True, eq=False)
class _EdgeDraft:
    copy: Copy
    specs: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    need: Need | None = None


def _span_of_ref(syntax: Syntax, ref: ValueRef) -> SourceSpan:
    return span_of(syntax, ref if isinstance(ref, Node) else TokenRange(ref, ref + 1))


class Binding:
    """One derivation. Immutable once made; the graph makes a new one after any edit, ``set_override`` or read."""

    def __init__(
        self, extensions: Mapping[str, Extension], overrides: Mapping[str, OverrideInput], reads: ReadLedger | None
    ) -> None:
        self._extensions = extensions
        self._reads = reads
        self._overrides = {
            name: _Definition(o.variable, o.values.values, (), o.values.long_bound) for name, o in overrides.items()
        }
        self.items: list[BoundItem] = []
        """The root document's top level at the root copy, includes and uses spliced in place."""
        self.edges: tuple[DocumentEdge, ...] = ()
        """Every copy of every extension line, in walk order (a failed or unread one included)."""
        self.unread: tuple[DocumentEdge, ...] = ()
        self.diagnostics: list[shared.LocatedDiagnostic] = []
        """Every diagnostic the walk found, in walk order: the second half of the graph's one list."""
        self.resolutions: list[ReferenceResolution] = []
        """Every resolution, in walk order."""
        self._drafts: list[_EdgeDraft] = []
        self._needs: dict[DocumentEdge, Need] = {}
        self._copies: dict[Statement, list[Copy]] = {}
        self._by_reference: dict[Reference, list[ReferenceResolution]] = {}
        self._by_use: dict[UseLine, list[Resolution[api.SnippetLine]]] = {}
        self._args: dict[Copy, dict[WrittenValue, tuple[ExpandedValue, ...]] | BindingProblem] = {}
        self._count = 0
        self._stopped = False

    # --- What the graph, the documents and the rendered layer ask ---

    def need_of(self, edge: DocumentEdge) -> Need | None:
        return self._needs.get(edge)

    def copies_of(self, statement: Statement) -> tuple[Copy, ...]:
        return tuple(self._copies.get(statement, ()))

    def resolutions_of(self, reference: Reference) -> tuple[ReferenceResolution, ...]:
        return tuple(self._by_reference.get(reference, ()))

    def snippets_of(self, use: UseLine) -> tuple[Resolution[api.SnippetLine], ...]:
        return tuple(self._by_use.get(use, ()))

    def arguments_at(self, value: WrittenValue, copy: Copy) -> tuple[ExpandedValue, ...]:
        """One written value at one copy of its statement, expanded with PR 3's origins. Raises BindingProblem
        (E5001, E4001)."""
        found = self._args.get(copy)
        if isinstance(found, BindingProblem):
            raise found
        if found is None or value not in found:
            raise LookupError("arguments_at: the value is not read at that copy")
        return found[value]

    # --- The walk (PR 3's expander) ---

    def _run(self, root: Document) -> None:
        self._statements(root._syntax.root, _Context(_document_text(root), _Scope(None), (), (root._path,), self.items))
        edges: list[DocumentEdge] = []
        unread: list[DocumentEdge] = []
        for draft in self._drafts:
            edge = DocumentEdge(draft.copy, tuple(draft.specs), tuple(draft.targets))
            edges.append(edge)
            if draft.need is not None:
                self._needs[edge] = draft.need
                unread.append(edge)
        self.edges = tuple(edges)
        self.unread = tuple(unread)

    def _copy_of(self, statement: Statement, via: tuple[Step, ...]) -> Copy:
        copy = Copy(statement, via)
        self._copies.setdefault(statement, []).append(copy)
        return copy

    def _statements(self, scope_node: Node, context: _Context) -> None:
        doc = context.text.doc
        assert doc is not None, "an override's text has no statements"
        for node in scope_node.children:
            if self._stopped:
                return
            if node.kind not in (NodeKind.DIRECTIVE, NodeKind.ERROR):
                continue
            copy = self._copy_of(doc._statements[node.start], context.via)
            if node.kind is NodeKind.ERROR:
                context.into.append(BoundUnreadable(copy, UnreadableReason.SYNTAX, None))
                continue
            try:
                self._statement(node, copy, context)
            except _Problem as problem:
                if problem.diagnostic is not None:
                    self.diagnostics.append(problem.diagnostic)
                    if isinstance(problem, _ValueProblem):
                        self._args[copy] = BindingProblem(problem.reason, problem.diagnostic)
                context.into.append(BoundUnreadable(copy, problem.reason, problem.diagnostic))

    def _statement(self, node: Node, copy: Copy, context: _Context) -> None:
        """One directive node, by its head token's kind (spec 2.5): an AT_WORD heads a language statement, which does
        its work, or an extension line; an ``@name`` no extension owns is unreadable (E3008 at it); a WORD heads a
        directive, its block walked."""
        text, scope, via = context.text, context.scope, context.via
        tokens = text.syntax.tokens
        anatomy = anatomy_of(tokens, node)
        name = tokens[anatomy.name]
        if name.kind is TokenKind.AT_WORD:
            keyword = statement_of_keyword(name.text[1:])
            if keyword is StatementKind.SET:
                self._set(anatomy, copy, text, scope, via)
            elif keyword is StatementKind.SNIPPET:
                self._snippet(anatomy, copy, context)
            elif keyword is StatementKind.USE:
                self._use(anatomy, name, copy, context)
            elif (extension := self._extensions.get(name.text[1:])) is not None:
                self._extension(extension, anatomy, name, copy, context)
            else:
                code = DiagnosticCode.UNKNOWN_EXTENSION
                raise self._problem(code, text, name.span, via, name.text)
            return
        statement = own(copy.statement)
        values: dict[WrittenValue, tuple[ExpandedValue, ...]] = {}
        for value in statement._value_list:
            try:
                values[value] = tuple(self.value(text, value._ref, scope, via, copy))
            except _ValueProblem:
                raise
            except _Problem as problem:
                raise _ValueProblem(problem.reason, problem.diagnostic) from None
        self._args[copy] = values
        self._count += 1
        if self._count > MAX_DIRECTIVES:
            self._stopped = True
            raise self._problem(
                DiagnosticCode.TOO_MANY_DIRECTIVES,
                text,
                name.span,
                via,
                f"more than {MAX_DIRECTIVES}",
            )
        children: list[BoundItem] | None = None if anatomy.block is None else []
        context.into.append(BoundDirective(copy, children))
        if anatomy.block is not None and children is not None:
            self._statements(anatomy.block, _Context(text, _Scope(scope), via, context.open, children))

    def _well_formed(self, anatomy: Anatomy, text: _Text, via: tuple[Step, ...]) -> None:
        """A ``@set``, ``@snippet`` or ``@use`` line's text-alone shape (``_shape``, the one home of those rules), or
        its problem."""
        fault = shape_of_anatomy(text.syntax.tokens, anatomy, frozenset()).fault
        if fault is not None:
            span = text.syntax.tokens[fault.token].span
            raise self._problem(fault.code, text, span, via)

    def _set(self, anatomy: Anatomy, copy: Copy, text: _Text, scope: _BlockScope, via: tuple[Step, ...]) -> None:
        """``@set $name value...;`` (rule 2): binds from this line to the end of the enclosing block."""
        self._well_formed(anatomy, text, via)
        tokens = text.syntax.tokens
        args = anatomy.args
        assert isinstance(args[0], int)
        variable = tokens[args[0]]
        variable_name = variable.text[1:]
        if not scope.claim(variable_name):
            raise self._problem(DiagnosticCode.VARIABLE_SET_TWICE, text, variable.span, via, variable.text)
        line = copy.statement
        assert isinstance(line, SetLine), "a set line that claims its name is kind set"
        bound = [argument for ref in args[1:] for argument in self.value(text, ref, scope, via, copy)]
        # Stored without this line's own steps; a reader adds the variable step and its own (``_moved``).
        scope.bind(
            variable_name,
            _Definition(line._variable, tuple(v._moved(len(via), (), None) for v in bound), tuple(line._value_list)),
        )

    def _snippet(self, anatomy: Anatomy, copy: Copy, context: _Context) -> None:
        """``@snippet name $param... { body }`` (rule 5): visible from this line to the end of its block."""
        text, scope, via = context.text, context.scope, context.via
        self._well_formed(anatomy, text, via)
        tokens = text.syntax.tokens
        args = anatomy.args
        assert isinstance(args[0], int) and anatomy.block is not None
        name = tokens[args[0]]
        params = [tokens[ref].text[1:] for ref in args[1:] if isinstance(ref, int)]
        line = copy.statement
        defined = isinstance(line, SnippetLine) and scope.define(
            _Snippet(name.text, tuple(params), anatomy.block, text, scope, line)
        )
        if not defined:
            raise self._problem(DiagnosticCode.SNIPPET_DEFINED_TWICE, text, name.span, via, name.text)

    def _use(self, anatomy: Anatomy, keyword: Token, copy: Copy, context: _Context) -> None:
        """``@use name value...;`` (rule 6): the snippet's body, spliced in place with its parameters bound."""
        text, scope, via, open_ = context.text, context.scope, context.via, context.open
        self._well_formed(anatomy, text, via)
        tokens = text.syntax.tokens
        args = anatomy.args
        assert isinstance(args[0], int)
        name = tokens[args[0]]
        visible: list[_Snippet] = []
        scope.snippets(name.text, visible)
        use = copy.statement
        assert isinstance(use, UseLine)
        resolution: Resolution[api.SnippetLine] = Resolution(
            copy, visible[0].line if visible else None, tuple(s.line for s in visible[1:])
        )
        self._by_use.setdefault(use, []).append(resolution)
        if not visible:
            raise self._problem(DiagnosticCode.UNKNOWN_SNIPPET, text, name.span, via, name.text)
        snippet = visible[0]
        written: list[WrittenValue] = []
        values: list[ExpandedValue] = []
        doc = text.doc
        for ref in args[1:]:
            expanded = self.value(text, ref, scope, via, copy)
            if doc is not None:
                handle = doc._values[ref if isinstance(ref, int) else ref.start]
                written.extend(handle for _ in expanded)
            values.extend(expanded)
        if len(values) != len(snippet.params):
            detail = f"{name.text} takes {len(snippet.params)}, given {len(values)}"
            code = DiagnosticCode.SNIPPET_ARITY
            raise self._problem(code, text, keyword.span, via, detail)
        if snippet in open_:
            raise self._problem(DiagnosticCode.EXPANSION_CYCLE, text, keyword.span, via, name.text)
        self._check_depth(open_, text, keyword, via)
        # Parameters are the body block's own bindings (a `set` of one there is E5002, S3-03), stored without the
        # use line's steps, as a `set` stores its values.
        body = _Scope(snippet.scope)
        for i, param in enumerate(snippet.params):
            if i < len(snippet.line._parameters):
                body.param(
                    param,
                    _Definition(
                        snippet.line._parameters[i],
                        (values[i]._moved(len(via), (), None),),
                        (written[i],) if i < len(written) else (),
                    ),
                )
        step = Step(StepKind.USE, name.text, text.place(keyword.span))
        self._statements(snippet.body, _Context(snippet.text, body, (step, *via), (*open_, snippet), context.into))

    def _extension(self, extension: Extension, anatomy: Anatomy, name: Token, copy: Copy, context: _Context) -> None:
        """An extension line (rules 7 and 8): the files its specs name, spliced in place. Its step is named without
        ``@`` and placed on the ``@name`` token."""
        text, scope, via, open_ = context.text, context.scope, context.via, context.open
        draft = _EdgeDraft(copy)
        self._drafts.append(draft)
        args = tuple(argument for ref in anatomy.args for argument in self.value(text, ref, scope, via, copy))
        overrides = self._extension_block(anatomy.block, text, scope, via)
        origin = DirectiveOrigin(text.place(name.span), via)

        def fail(code: DiagnosticCode, detail: str) -> _Problem:
            return self._problem(code, text, name.span, via, detail)

        try:
            draft.specs.extend(port_texts(extension.specs(ExtensionUse(args, origin)), port="specs()"))
        except DiagnosticError as error:
            draft.specs.clear()
            raise _Problem(UnreadableReason.EXTENSION, error.diagnostic) from None
        except Exception as error:
            draft.specs.clear()
            raise fail(DiagnosticCode.EXTENSION_FAILED, f"{name.text[1:]}: {error}") from None
        reads = self._reads
        assert reads is not None, "no read ledger"
        found: list[str] = []
        for spec in draft.specs:
            paths = reads.resolved(text.resolved_path, spec)
            if paths is None:
                draft.need = ResolveNeed(text.resolved_path, tuple(draft.specs))
                raise self._unread(text, name, via)
            if isinstance(paths, Exception):
                raise fail(DiagnosticCode.INCLUDE_RESOLVER_FAILED, f"{spec}: {paths}")
            if not paths:
                raise fail(DiagnosticCode.INCLUDE_NOT_FOUND, spec)
            found.extend(sorted(paths))
        cycle = next((path for path in found if path in open_), None)
        if cycle is not None:
            raise self._problem(DiagnosticCode.EXPANSION_CYCLE, text, name.span, via, cycle)
        self._check_depth(open_, text, name, via)
        files: list[Document] = []
        for path in found:
            doc = reads.read(path)
            if doc is None:
                draft.need = ReadNeed(tuple(found))
                raise self._unread(text, name, via)
            if isinstance(doc, Exception):
                raise fail(DiagnosticCode.INCLUDE_RESOLVER_FAILED, f"{path}: {doc}")
            files.append(doc)
        draft.targets.extend(found)
        step = Step(StepKind.EXTENSION, name.text[1:], text.place(name.span))
        spliced = _SpliceScope(scope, overrides)
        for file in files:
            self._statements(
                file._syntax.root,
                _Context(_document_text(file), spliced, (step, *via), (*open_, file._path), context.into),
            )

    def _unread(self, text: _Text, name: Token, via: tuple[Step, ...]) -> _Problem:
        """An extension copy not read yet (its edge is in ``unread()``): unreadable with reason ``unread``, and E3007
        on the extension line's name (spec 6.10), so a render shows it and ``diff`` reports what it held as unknown."""
        return self._problem(DiagnosticCode.UNREAD_COPY, text, name.span, via)

    def _extension_block(
        self, block: Node | None, text: _Text, scope: _BlockScope, via: tuple[Step, ...]
    ) -> Mapping[str, _Definition]:
        """An extension directive's block: only ``@set`` lines (E5012), bound for the spliced files."""
        if block is None:
            return {}
        own = _Scope(scope)
        tokens = text.syntax.tokens
        doc = text.doc
        for node in block.children:
            # Already reported by the parse; the broken line may be a `set` the files need: the include is unreadable.
            if node.kind is NodeKind.ERROR:
                raise _Problem(UnreadableReason.SYNTAX, None)
            if node.kind is not NodeKind.DIRECTIVE or doc is None:
                continue
            anatomy = anatomy_of(tokens, node)
            name = tokens[anatomy.name]
            if name.kind is not TokenKind.AT_WORD or statement_of_keyword(name.text[1:]) is not StatementKind.SET:
                raise self._problem(DiagnosticCode.EXTENSION_BLOCK_NOT_SET, text, name.span, via)
            self._set(anatomy, self._copy_of(doc._statements[node.start], via), text, own, via)
        return own.own()

    def _check_depth(self, open_: tuple[_Snippet | str, ...], text: _Text, name: Token, via: tuple[Step, ...]) -> None:
        """Rule 9's depth, after the cycle check (S3-10): a ``use`` or extension directive 17 places deep is E5007."""
        if len(open_) > MAX_DEPTH:
            raise self._problem(
                DiagnosticCode.EXPANSION_TOO_DEEP,
                text,
                name.span,
                via,
                f"more than {MAX_DEPTH}",
            )

    def value(
        self, text: _Text, ref: ValueRef, scope: _ScopeView, via: tuple[Step, ...], copy: Copy | None
    ) -> list[ExpandedValue]:
        """One written value, expanded: a ``$name`` becomes all its values (rule 4); a list's items the same way.
        Read where it is written, its ``definition`` is its own handle (None in an override's text)."""
        syntax = text.syntax
        doc = text.doc
        written = None if doc is None else doc._values.get(ref if isinstance(ref, int) else ref.start)
        if isinstance(ref, Node):
            origin = Origin(text.written(span_of(syntax, ref)), via)
            if ref.kind is NodeKind.LIST:
                items = tuple(
                    argument
                    for item in items_of(syntax.tokens, ref)
                    for argument in self.value(text, item, scope, via, copy)
                )
                return [ExpandedList(items, origin, written, ())]
            return [self._slice(text, ref, scope, via, copy, origin, written)]
        token = syntax.tokens[ref]
        origin = Origin(text.written(token.span), via)
        if token.kind in (TokenKind.WORD, TokenKind.AT_WORD, TokenKind.INTEGER, TokenKind.DIGIT_WORD):
            return [ExpandedWord(token.text, origin, written, ())]
        if token.kind is TokenKind.STRING:
            return [ExpandedString(_values.decode_string(token.text), origin, written, ())]
        if token.kind is TokenKind.VARIABLE:
            return self._variable(text, ref, token, scope, via, copy)
        raise TypeError(f"not a value token: {token.kind}")

    def _variable(
        self,
        text: _Text,
        ref: int,
        token: Token,
        scope: _ScopeView,
        via: tuple[Step, ...],
        copy: Copy | None,
        reference: WrittenValue | None = None,
    ) -> list[ExpandedValue]:
        """``$name``'s values as read here: each with the variable step, then the reading place's steps.
        ``reference`` is its written handle when the value index at ``ref`` holds another (a slice's name shares the
        slice's start)."""
        name = token.text[1:]
        entries: list[_Entry] = []
        scope.entries(name, entries)
        ordered = _ordered(entries, self._overrides.get(name))
        winner = ordered[0] if ordered else None
        resolution: ReferenceResolution | None = None
        if reference is None and text.doc is not None:
            reference = text.doc._values.get(ref)
        if copy is not None and isinstance(reference, Reference):
            resolution = ReferenceResolution(
                copy,
                None if winner is None else winner.variable,
                tuple(d.variable for d in ordered[1:]),
                reference,
                () if winner is None else winner.written,
            )
            self.resolutions.append(resolution)
            self._by_reference.setdefault(reference, []).append(resolution)
        if winner is None:
            raise self._problem(DiagnosticCode.UNKNOWN_VARIABLE, text, token.span, via, token.text)
        if winner.long_bound:
            code = DiagnosticCode.NON_INTEGER_BOUND
            raise self._problem(code, text, token.span, via, f"{token.text} (override)")
        step = Step(StepKind.VARIABLE, name, text.place(token.span))
        return [value._moved(0, (step, *via), resolution) for value in winner.values]

    def _slice(
        self,
        text: _Text,
        node: Node,
        scope: _ScopeView,
        via: tuple[Step, ...],
        copy: Copy | None,
        origin: Origin,
        written: WrittenValue | None,
    ) -> ExpandedValue:
        """``name[bounds]``: the name a word or a variable holding exactly one word (E4007 otherwise), each bound a
        literal INTEGER or a variable holding exactly one (rules 4 and 10). Read where written, as a word is."""
        tokens = text.syntax.tokens
        name = self._slice_name(text, node.start, scope, via, copy, written)
        inner = list(range(node.start + 2, node.end - 1))

        def bound(position: int) -> int | None:
            if not 0 <= position < len(inner):
                return None
            return self._bound(text, inner[position], tokens[inner[position]], scope, via, copy)

        tilde = next((i for i, t in enumerate(inner) if tokens[t].kind is TokenKind.TILDE), -1)
        if tilde < 0:
            index = bound(0)
            return ExpandedIndex(name, 0 if index is None else index, origin, written, ())
        start = None if tilde == 0 else bound(0)
        end = bound(tilde + 1) if tilde + 1 < len(inner) else None
        return ExpandedSlice(name, start, end, origin, written, ())

    def _slice_name(
        self,
        text: _Text,
        ref: int,
        scope: _ScopeView,
        via: tuple[Step, ...],
        copy: Copy | None,
        written: WrittenValue | None,
    ) -> str:
        """A slice's name: a word's text, or through a ``$name`` the one word it holds, a word that may name a slice
        (the grammar's ``sliceName``: a WORD or an AT_WORD, so never ``5``, ``1.5`` or ``-``). E4007 otherwise, placed
        as E4001 is for a bound through a variable (``_bound``)."""
        token = text.syntax.tokens[ref]
        if token.kind is not TokenKind.VARIABLE:
            return token.text
        reference = written._name if isinstance(written, Slice | Index) else None
        values = self._variable(text, ref, token, scope, via, copy, reference)
        only = values[0] if values else None
        if len(values) == 1 and only is not None and only.kind is ValueKind.WORD and _names_a_slice(only.text):
            return only.text
        raise self._through(DiagnosticCode.BAD_SLICE_NAME, text, token, via, only)

    def _bound(
        self, text: _Text, ref: int, token: Token, scope: _ScopeView, via: tuple[Step, ...], copy: Copy | None
    ) -> int:
        """One bound's integer. A literal is an INTEGER (the grammar's rule): E4001 at it beyond ±(2**53 - 1). For a
        variable, E4001 at its value's place via the variable unless it holds exactly one integer word."""
        if token.kind is TokenKind.INTEGER:
            value = _values.integer_of(token.text)
            if value is None:
                raise self._problem(DiagnosticCode.NON_INTEGER_BOUND, text, token.span, via, token.text)
            return value
        values = self._variable(text, ref, token, scope, via, copy)
        only = values[0] if values else None
        if len(values) == 1 and only is not None and only.kind is ValueKind.WORD:
            integer = _values.integer_of(only.text)
            if integer is not None:
                return integer
        raise self._through(DiagnosticCode.NON_INTEGER_BOUND, text, token, via, only)

    def _through(
        self, code: DiagnosticCode, text: _Text, token: Token, via: tuple[Step, ...], only: ExpandedValue | None
    ) -> _Problem:
        """A value problem of a ``$name`` read as a slice's name or bound (E4007, E4001): at its first value's place,
        via the variable, when that value is written in a file; else at the ``$name``."""
        at = None if only is None else only.origin.place
        if only is None or not isinstance(at, Place):
            # An override is written in no file: the problem is placed on the `$name` that used it.
            return self._problem(code, text, token.span, via, token.text)
        described = describe(code, f"{token.text} is {only.text}")
        assert described.reason is not None
        return _Problem(described.reason, LocatedDiagnostic(code, described.message, at, only.origin.via))

    def _problem(
        self, code: DiagnosticCode, text: _Text, span: SourceSpan, via: tuple[Step, ...], detail: str | None = None
    ) -> _Problem:
        """A statement this copy cannot read, for ``code`` at ``span``: its message and its unreadable reason come
        from the registry (``describe``), so they cannot disagree with it."""
        described = describe(code, detail)
        assert described.reason is not None, f"{code} makes a statement unreadable"
        return _Problem(described.reason, LocatedDiagnostic(code, described.message, text.place(span), via))
