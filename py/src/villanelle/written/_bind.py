"""The binding (design rule 3; slices.md 2.5): one derivation of the graph's current texts, handed-in values and read
ledger. It walks the copies (the root, then each include and ``use`` spliced in place), decides per copy what each
``$name`` and ``use`` reads, and expands written values for the extension lines (an include's path) and for
``render``. It is the one home of the name-lookup rule: ``render`` walks ``items`` and calls ``arguments_at``, and
never looks a name up. Private; pure (no I/O); a port of ts/src/written/bind.ts.

The walk is PR 3's expander (cb08803) moved here, unchanged in what it decides and reports, with the read ledger in
place of reading files during the walk."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias

from villanelle import _values
from villanelle import processor as _processor
from villanelle._anatomy import Anatomy, anatomy_of, items_of
from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.directives import Argument, UnreadableKind
from villanelle.origin import DirectiveOrigin, Handed, Origin, Place, Step, StepKind
from villanelle.report import LocatedDiagnostic
from villanelle.span import SourceSpan
from villanelle.syntax._recovery import message_of
from villanelle.syntax.cst import Node, NodeKind, Syntax, ValueRef, span_of
from villanelle.syntax.parse import parse
from villanelle.syntax.tokens import Token, TokenKind
from villanelle.value import IndexValue, SliceValue, ValueKind
from villanelle.written.model import (
    Copy,
    Document,
    DocumentEdge,
    Reference,
    ReferenceResolution,
    Resolution,
    SetLine,
    SnippetLine,
    Statement,
    UseLine,
    Variable,
    WrittenValue,
)

if TYPE_CHECKING:
    from villanelle.processor import Extension

MAX_DEPTH = 16
"""``use`` and extension directives may nest this many places deep (E5007 beyond)."""
MAX_DIRECTIVES = 100_000
"""At most this many directives after expansion (E5008 beyond, and expansion stops)."""
RESERVED = frozenset({"set", "snippet", "use"})
"""The names reserved at a statement's start in every block, besides each registered extension's (L6)."""


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
    reason: UnreadableKind
    diagnostic: LocatedDiagnostic | None
    """None when the problem is already one of a document's syntax diagnostics."""


BoundItem: TypeAlias = BoundDirective | BoundUnreadable


class BindingProblem(Exception):
    """A written value that cannot be expanded at a copy (E5001, E4001, E4003): the statement is unreadable there."""

    def __init__(self, kind: UnreadableKind, diagnostic: LocatedDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.kind = kind
        self.diagnostic = diagnostic


class ReadLedger(Protocol):
    """Which files were read: the one piece of state besides the texts (design rule 1)."""

    def resolved(self, parent_path: str, spec: str, /) -> tuple[str, ...] | Exception | None: ...

    def read(self, resolved_path: str, /) -> Document | Exception | None: ...


@dataclass(frozen=True, slots=True)
class HandedInput:
    """A handed-in value: its variable handle and its values, already read."""

    variable: Variable
    values: tuple[Argument, ...]


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
    handed: Mapping[str, HandedInput],
    reads: ReadLedger,
) -> Binding:
    """Derive the binding of these inputs. Pure and synchronous."""
    binding = Binding(extensions, handed, reads)
    binding._run(root)
    return binding


_VARIABLE_NAME = re.compile(r"[A-Za-z0-9_]+")


def read_handed(name: str, written: str) -> tuple[Argument, ...]:
    """A handed-in value's values, read as PR 3's ``read_handed`` read them: the text as the values of one directive.
    ValueError for a name that is not letters, digits and ``_``, or a text that is not one or more values (a syntax
    error, a block, a variable, an unknown escape, a non-integer bound)."""
    if not _VARIABLE_NAME.fullmatch(name):
        raise ValueError(f"handed-in variable name must be letters, digits and _: {name!r}")

    def bad(why: str) -> ValueError:
        return ValueError(f"handed-in variable {name}: {why}: {written!r}")

    if not isinstance(written, str):
        raise bad("not a string")
    syntax = parse(f"x {written}")
    nodes = syntax.root.children
    if syntax.diagnostics or len(nodes) != 1 or nodes[0].kind is not NodeKind.DIRECTIVE:
        raise bad("not a run of values")
    if any(token.kind is TokenKind.VARIABLE for token in syntax.tokens):
        raise bad("a handed-in value may not use a variable")
    anatomy = anatomy_of(syntax.tokens, nodes[0])
    if anatomy.block is not None:
        raise bad("not a run of values")
    if not anatomy.args:
        raise bad("no value")
    reader = Binding({}, {}, None)
    text = _Text(None, syntax, "", name)
    try:
        return tuple(argument for ref in anatomy.args for argument in reader.value(text, ref, _Scope(None), (), None))
    except _Problem as problem:
        raise bad(problem.diagnostic.message if problem.diagnostic else str(problem.kind)) from None


def handed_value_problem(written: str) -> tuple[DiagnosticCode, SourceSpan] | None:
    """What the handed-in reader refuses in a text already checked as values (an unknown escape, a non-integer
    bound): its code and span in ``x <written>``, for ``set_handed``'s BadTextError."""
    syntax = parse(f"x {written}")
    if syntax.diagnostics or not syntax.root.children or syntax.root.children[0].kind is not NodeKind.DIRECTIVE:
        return None
    reader = Binding({}, {}, None)
    text = _Text(None, syntax, "", "")
    try:
        for ref in anatomy_of(syntax.tokens, syntax.root.children[0]).args:
            reader.value(text, ref, _Scope(None), (), None)
    except _Problem as problem:
        if problem.diagnostic is not None:
            return DiagnosticCode(problem.diagnostic.code), problem.diagnostic.at.span
    return None


# --- The walk ---


@dataclass(frozen=True, slots=True)
class _Text:
    """One text being walked: a document, or a value handed in by the program (``handed`` is its name)."""

    doc: Document | None
    syntax: Syntax
    resolved_path: str
    handed: str | None = None

    def written(self, span: SourceSpan) -> Place | Handed:
        return Place(self.resolved_path, span) if self.handed is None else Handed(self.handed)

    def place(self, span: SourceSpan) -> Place:
        return Place(self.resolved_path, span)


def _document_text(doc: Document) -> _Text:
    return _Text(doc, doc._syntax, doc._path)


class _Problem(Exception):
    """A statement that cannot be read: raised inside a statement, caught where it is kept unreadable."""

    def __init__(self, kind: UnreadableKind, diagnostic: LocatedDiagnostic | None) -> None:
        super().__init__(kind if diagnostic is None else diagnostic.message)
        self.kind = kind
        self.diagnostic = diagnostic


class _ValueProblem(_Problem):
    """A problem with one of a directive's values: the directive is unreadable there, and arguments_at raises it."""


@dataclass(frozen=True, slots=True, eq=False)
class _Definition:
    """One definition of a name: its variable, the values a reader gets (without the definer's steps), as written."""

    variable: Variable
    values: tuple[Argument, ...]
    written: tuple[WrittenValue, ...]


@dataclass(frozen=True, slots=True)
class _Entry:
    """A snippet parameter, a ``set``, or an include block's ``set`` ("forced": it wins over every ``set`` of the
    spliced files)."""

    kind: Literal["parameter", "set", "forced"]
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
            out.append(_Entry("parameter", self._params[name]))
        if name in self._vars:
            out.append(_Entry("set", self._vars[name]))
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
    """The including block's scope as a spliced file sees it: the file's top-level ``set`` and ``snippet`` lines
    claim, bind and define in the including block (L2), and inside the spliced files the extension block's ``set``
    lines win over every ``set`` of the files, at any depth, but not over a parameter (rule 8, F1-01)."""

    __slots__ = ("_overrides", "_target")

    def __init__(self, target: _BlockScope, overrides: Mapping[str, _Definition]) -> None:
        self._target = target
        self._overrides = overrides

    def entries(self, name: str, out: list[_Entry]) -> None:
        if name in self._overrides:
            out.append(_Entry("forced", self._overrides[name]))
        self._target.entries(name, out)

    def snippets(self, name: str, out: list[_Snippet]) -> None:
        self._target.snippets(name, out)

    def claim(self, name: str) -> bool:
        return self._target.claim(name)

    def bind(self, name: str, definition: _Definition) -> None:
        self._target.bind(name, definition)

    def define(self, snippet: _Snippet) -> bool:
        return self._target.define(snippet)


def _pick(entries: Sequence[_Entry], handed: _Definition | None) -> _Definition | None:
    """The winner among ``entries`` (innermost first) and a handed-in value, by PR 3's rule: the nearest ``set`` or
    parameter; an include block's ``set`` wins over every ``set`` nearer than it, but a nearer parameter wins over
    it; a handed-in value wins over every ``set`` and include-block ``set``, never over a parameter."""
    found: _Entry | None = None
    for entry in entries:
        if entry.kind == "parameter" and found is None:
            return entry.definition
        if entry.kind == "set" and found is None:
            found = entry
        if entry.kind == "forced":
            found = entry
            break
    if handed is not None:
        return handed
    return None if found is None else found.definition


def _ordered(entries: Sequence[_Entry], handed: _Definition | None) -> list[_Definition]:
    """Every visible definition in the order the rule picks them, each as if those before it were removed."""
    out: list[_Definition] = []
    left = list(entries)
    hand = handed
    while True:
        chosen = _pick(left, hand)
        if chosen is None:
            return out
        out.append(chosen)
        if chosen is hand:
            hand = None
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
    return span_of(syntax, ref if isinstance(ref, Node) else _TokenRange(ref, ref + 1))


@dataclass(frozen=True, slots=True)
class _TokenRange:
    start: int
    end: int


class Binding:
    """One derivation. Immutable once made; the graph makes a new one after any edit, ``set_handed`` or read."""

    def __init__(
        self, extensions: Mapping[str, Extension], handed: Mapping[str, HandedInput], reads: ReadLedger | None
    ) -> None:
        self._extensions = extensions
        self._reads = reads
        self._handed = {name: _Definition(h.variable, h.values, ()) for name, h in handed.items()}
        self.items: list[BoundItem] = []
        """The root document's top level at the root copy, includes and uses spliced in place."""
        self.edges: tuple[DocumentEdge, ...] = ()
        """Every copy of every extension line, in walk order (a failed or unread one included)."""
        self.unread: tuple[DocumentEdge, ...] = ()
        self.diagnostics: list[LocatedDiagnostic] = []
        """Every diagnostic the walk found, in walk order, render's codes included (the graph filters them)."""
        self.resolutions: list[ReferenceResolution] = []
        """Every resolution, in walk order."""
        self._drafts: list[_EdgeDraft] = []
        self._needs: dict[DocumentEdge, Need] = {}
        self._copies: dict[Statement, list[Copy]] = {}
        self._by_reference: dict[Reference, list[ReferenceResolution]] = {}
        self._by_use: dict[UseLine, list[Resolution[SnippetLine]]] = {}
        self._args: dict[Copy, dict[WrittenValue, tuple[Argument, ...]] | BindingProblem] = {}
        self._count = 0
        self._stopped = False

    # --- What the graph, the documents and render ask ---

    def need_of(self, edge: DocumentEdge) -> Need | None:
        return self._needs.get(edge)

    def copies_of(self, statement: Statement) -> tuple[Copy, ...]:
        return tuple(self._copies.get(statement, ()))

    def resolutions_of(self, reference: Reference) -> tuple[ReferenceResolution, ...]:
        return tuple(self._by_reference.get(reference, ()))

    def snippets_of(self, use: UseLine) -> tuple[Resolution[SnippetLine], ...]:
        return tuple(self._by_use.get(use, ()))

    def arguments_at(self, value: WrittenValue, copy: Copy) -> tuple[Argument, ...]:
        """One written value at one copy of its statement, expanded with PR 3's origins. Raises BindingProblem
        (E5001, E4001, E4003)."""
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
        assert doc is not None, "a handed-in text has no statements"
        for node in scope_node.children:
            if self._stopped:
                return
            if node.kind not in (NodeKind.DIRECTIVE, NodeKind.ERROR):
                continue
            copy = self._copy_of(doc._statements[node.start], context.via)
            if node.kind is NodeKind.ERROR:
                context.into.append(BoundUnreadable(copy, UnreadableKind.SYNTAX, None))
                continue
            try:
                self._statement(node, copy, context)
            except _Problem as problem:
                if problem.diagnostic is not None:
                    self.diagnostics.append(problem.diagnostic)
                    if isinstance(problem, _ValueProblem):
                        self._args[copy] = BindingProblem(problem.kind, problem.diagnostic)
                context.into.append(BoundUnreadable(copy, problem.kind, problem.diagnostic))

    def _statement(self, node: Node, copy: Copy, context: _Context) -> None:
        """One directive node: a reserved line does its work; any other becomes a directive, its block walked."""
        text, scope, via = context.text, context.scope, context.via
        tokens = text.syntax.tokens
        anatomy = anatomy_of(tokens, node)
        name = tokens[anatomy.name]
        if name.text == "set":
            self._set(anatomy, name, copy, text, scope, via)
            return
        if name.text == "snippet":
            self._snippet(anatomy, name, copy, context)
            return
        if name.text == "use":
            self._use(anatomy, name, copy, context)
            return
        extension = self._extensions.get(name.text)
        if extension is not None:
            self._extension(extension, anatomy, name, copy, context)
            return
        statement = copy.statement
        values: dict[WrittenValue, tuple[Argument, ...]] = {}
        for value in statement._value_list:
            try:
                values[value] = tuple(self.value(text, value._ref, scope, via, copy))
            except _ValueProblem:
                raise
            except _Problem as problem:
                raise _ValueProblem(problem.kind, problem.diagnostic) from None
        self._args[copy] = values
        self._count += 1
        if self._count > MAX_DIRECTIVES:
            self._stopped = True
            raise self._problem(
                UnreadableKind.EXPANSION,
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

    def _set(
        self, anatomy: Anatomy, name: Token, copy: Copy, text: _Text, scope: _BlockScope, via: tuple[Step, ...]
    ) -> None:
        """``set $name value...;`` (rule 2): binds from this line to the end of the enclosing block."""
        tokens = text.syntax.tokens
        args = anatomy.args
        variable = tokens[args[0]] if args and isinstance(args[0], int) else None
        if variable is None or variable.kind is not TokenKind.VARIABLE or len(args) < 2 or anatomy.block is not None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_SET, text, name.span, via)
        variable_name = variable.text[1:]
        if not scope.claim(variable_name):
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.VARIABLE_SET_TWICE, text, variable.span, via, variable.text
            )
        line = copy.statement
        assert isinstance(line, SetLine), "a set line that claims its name is kind set"
        bound = [argument for ref in args[1:] for argument in self.value(text, ref, scope, via, copy)]
        # Stored without this line's own steps; a reader adds the variable step and its own (Argument._rebase).
        scope.bind(
            variable_name,
            _Definition(line._variable, tuple(v._rebase(len(via), ()) for v in bound), tuple(line._value_list)),
        )

    def _snippet(self, anatomy: Anatomy, keyword: Token, copy: Copy, context: _Context) -> None:
        """``snippet name $param... { body }`` (rule 5): visible from this line to the end of its block."""
        text, scope, via = context.text, context.scope, context.via
        tokens = text.syntax.tokens
        args = anatomy.args
        name = tokens[args[0]] if args and isinstance(args[0], int) else None
        params: list[str] = []
        for ref in args[1:]:
            token = tokens[ref] if isinstance(ref, int) else None
            if token is None or token.kind is not TokenKind.VARIABLE or token.text[1:] in params:
                raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_SNIPPET, text, keyword.span, via)
            params.append(token.text[1:])
        if name is None or name.kind is not TokenKind.WORD or anatomy.block is None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_SNIPPET, text, keyword.span, via)
        line = copy.statement
        defined = isinstance(line, SnippetLine) and scope.define(
            _Snippet(name.text, tuple(params), anatomy.block, text, scope, line)
        )
        if not defined:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.SNIPPET_DEFINED_TWICE, text, name.span, via, name.text
            )

    def _use(self, anatomy: Anatomy, keyword: Token, copy: Copy, context: _Context) -> None:
        """``use name value...;`` (rule 6): the snippet's body, spliced in place with its parameters bound."""
        text, scope, via, open_ = context.text, context.scope, context.via, context.open
        tokens = text.syntax.tokens
        args = anatomy.args
        name = tokens[args[0]] if args and isinstance(args[0], int) else None
        if name is None or name.kind is not TokenKind.WORD or anatomy.block is not None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_USE, text, keyword.span, via)
        visible: list[_Snippet] = []
        scope.snippets(name.text, visible)
        use = copy.statement
        assert isinstance(use, UseLine)
        resolution: Resolution[SnippetLine] = Resolution(
            copy, visible[0].line if visible else None, tuple(s.line for s in visible[1:])
        )
        self._by_use.setdefault(use, []).append(resolution)
        if not visible:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.UNKNOWN_SNIPPET, text, name.span, via, name.text
            )
        snippet = visible[0]
        written: list[WrittenValue] = []
        values: list[Argument] = []
        doc = text.doc
        for ref in args[1:]:
            expanded = self.value(text, ref, scope, via, copy)
            if doc is not None:
                handle = doc._values[ref if isinstance(ref, int) else ref.start]
                written.extend(handle for _ in expanded)
            values.extend(expanded)
        if len(values) != len(snippet.params):
            detail = f"{name.text} takes {len(snippet.params)}, given {len(values)}"
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.SNIPPET_ARITY, text, keyword.span, via, detail)
        if snippet in open_:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.EXPANSION_CYCLE, text, keyword.span, via, name.text
            )
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
                        (values[i]._rebase(len(via), ()),),
                        (written[i],) if i < len(written) else (),
                    ),
                )
        step = Step(StepKind.USE, name.text, text.place(keyword.span))
        self._statements(snippet.body, _Context(snippet.text, body, (step, *via), (*open_, snippet), context.into))

    def _extension(self, extension: Extension, anatomy: Anatomy, name: Token, copy: Copy, context: _Context) -> None:
        """An extension directive (rules 7 and 8): the files its specs name, spliced in place."""
        text, scope, via, open_ = context.text, context.scope, context.via, context.open
        draft = _EdgeDraft(copy)
        self._drafts.append(draft)
        args = tuple(argument for ref in anatomy.args for argument in self.value(text, ref, scope, via, copy))
        overrides = self._extension_block(anatomy.block, text, scope, via)
        origin = DirectiveOrigin(text.place(name.span), via)

        def fail(code: DiagnosticCode, detail: str) -> _Problem:
            return self._problem(UnreadableKind.EXTENSION, code, text, name.span, via, detail)

        try:
            draft.specs.extend(extension.specs(_processor.ExtensionUse(args, origin)))
        except DiagnosticError as error:
            draft.specs.clear()
            raise _Problem(UnreadableKind.EXTENSION, error.diagnostic) from None
        except Exception as error:
            draft.specs.clear()
            raise fail(DiagnosticCode.EXTENSION_FAILED, f"{name.text}: {error}") from None
        reads = self._reads
        assert reads is not None, "no read ledger"
        found: list[str] = []
        for spec in draft.specs:
            paths = reads.resolved(text.resolved_path, spec)
            if paths is None:
                draft.need = ResolveNeed(text.resolved_path, tuple(draft.specs))
                return
            if isinstance(paths, Exception):
                raise fail(DiagnosticCode.INCLUDE_RESOLVER_FAILED, f"{spec}: {paths}")
            if not paths:
                raise fail(DiagnosticCode.INCLUDE_NOT_FOUND, spec)
            found.extend(sorted(paths))
        cycle = next((path for path in found if path in open_), None)
        if cycle is not None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.EXPANSION_CYCLE, text, name.span, via, cycle)
        self._check_depth(open_, text, name, via)
        files: list[Document] = []
        for path in found:
            doc = reads.read(path)
            if doc is None:
                draft.need = ReadNeed(tuple(found))
                return
            if isinstance(doc, Exception):
                raise fail(DiagnosticCode.INCLUDE_RESOLVER_FAILED, f"{path}: {doc}")
            files.append(doc)
        draft.targets.extend(found)
        step = Step(StepKind.EXTENSION, name.text, text.place(name.span))
        spliced = _SpliceScope(scope, overrides)
        for file in files:
            self._statements(
                file._syntax.root,
                _Context(_document_text(file), spliced, (step, *via), (*open_, file._path), context.into),
            )

    def _extension_block(
        self, block: Node | None, text: _Text, scope: _BlockScope, via: tuple[Step, ...]
    ) -> Mapping[str, _Definition]:
        """An extension directive's block: only ``set`` lines (E5012), bound for the spliced files."""
        if block is None:
            return {}
        own = _Scope(scope)
        tokens = text.syntax.tokens
        doc = text.doc
        for node in block.children:
            # Already reported by the parse; the broken line may be a `set` the files need: the include is unreadable.
            if node.kind is NodeKind.ERROR:
                raise _Problem(UnreadableKind.SYNTAX, None)
            if node.kind is not NodeKind.DIRECTIVE or doc is None:
                continue
            anatomy = anatomy_of(tokens, node)
            name = tokens[anatomy.name]
            if name.text != "set":
                raise self._problem(
                    UnreadableKind.EXTENSION, DiagnosticCode.EXTENSION_BLOCK_NOT_SET, text, name.span, via
                )
            self._set(anatomy, name, self._copy_of(doc._statements[node.start], via), text, own, via)
        return own.own()

    def _check_depth(self, open_: tuple[_Snippet | str, ...], text: _Text, name: Token, via: tuple[Step, ...]) -> None:
        """Rule 9's depth, after the cycle check (S3-10): a ``use`` or extension directive 17 places deep is E5007."""
        if len(open_) > MAX_DEPTH:
            raise self._problem(
                UnreadableKind.EXPANSION,
                DiagnosticCode.EXPANSION_TOO_DEEP,
                text,
                name.span,
                via,
                f"more than {MAX_DEPTH}",
            )

    def value(
        self, text: _Text, ref: ValueRef, scope: _ScopeView, via: tuple[Step, ...], copy: Copy | None
    ) -> list[Argument]:
        """One written value, expanded: a ``$name`` becomes all its values (rule 4); a list's items the same way."""
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
                return [Argument(ValueKind.LIST, items, origin, written)]
            return [self._slice(text, ref, scope, via, copy, origin, written)]
        token = syntax.tokens[ref]
        origin = Origin(text.written(token.span), via)
        if token.kind is TokenKind.WORD:
            return [Argument(ValueKind.WORD, token.text, origin, written)]
        if token.kind is TokenKind.STRING:
            if not _values.has_only_known_escapes(token.text):
                raise self._problem(UnreadableKind.VALUE, DiagnosticCode.BAD_ESCAPE, text, token.span, via, token.text)
            return [Argument(ValueKind.STRING, _values.decode_string(token.text), origin, written)]
        if token.kind is TokenKind.VARIABLE:
            return self._variable(text, ref, token, scope, via, copy)
        raise TypeError(f"not a value token: {token.kind}")

    def _variable(
        self, text: _Text, ref: int, token: Token, scope: _ScopeView, via: tuple[Step, ...], copy: Copy | None
    ) -> list[Argument]:
        """``$name``'s values as read here: each with the variable step, then the reading place's steps."""
        name = token.text[1:]
        entries: list[_Entry] = []
        scope.entries(name, entries)
        ordered = _ordered(entries, self._handed.get(name))
        winner = ordered[0] if ordered else None
        resolution: ReferenceResolution | None = None
        reference = None if text.doc is None else text.doc._values.get(ref)
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
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.UNKNOWN_VARIABLE, text, token.span, via, token.text
            )
        step = Step(StepKind.VARIABLE, name, text.place(token.span))
        return [value._rebase(0, (step, *via), resolution) for value in winner.values]

    def _slice(
        self,
        text: _Text,
        node: Node,
        scope: _ScopeView,
        via: tuple[Step, ...],
        copy: Copy | None,
        origin: Origin,
        written: WrittenValue | None,
    ) -> Argument:
        """``name[bounds]``: each bound a literal IntegerText or a variable holding exactly one (rules 4 and 10)."""
        tokens = text.syntax.tokens
        name = tokens[node.start].text
        inner = list(range(node.start + 2, node.end - 1))

        def bound(position: int) -> int | None:
            if not 0 <= position < len(inner):
                return None
            return self._bound(text, inner[position], tokens[inner[position]], scope, via, copy)

        colon = next((i for i, t in enumerate(inner) if tokens[t].kind is TokenKind.COLON), -1)
        if colon < 0:
            index = bound(0)
            return Argument(ValueKind.INDEX, IndexValue(name, 0 if index is None else index), origin, written)
        start = None if colon == 0 else bound(0)
        end = bound(colon + 1) if colon + 1 < len(inner) else None
        return Argument(ValueKind.SLICE, SliceValue(name, start, end), origin, written)

    def _bound(
        self, text: _Text, ref: int, token: Token, scope: _ScopeView, via: tuple[Step, ...], copy: Copy | None
    ) -> int:
        """One bound's integer. E4001 at the bound, or for a variable at its value's place via the variable."""
        if token.kind is TokenKind.WORD:
            value = _values.integer_of(token.text)
            if value is None:
                raise self._problem(
                    UnreadableKind.VALUE, DiagnosticCode.NON_INTEGER_BOUND, text, token.span, via, token.text
                )
            return value
        values = self._variable(text, ref, token, scope, via, copy)
        only = values[0] if values else None
        if len(values) == 1 and only is not None and only.kind is ValueKind.WORD:
            integer = _values.integer_of(only.text)
            if integer is not None:
                return integer
        at = None if only is None else only.origin.written
        if only is None or not isinstance(at, Place):
            # A handed-in value is written in no file: the problem is placed on the `$name` that used it.
            raise self._problem(
                UnreadableKind.VALUE, DiagnosticCode.NON_INTEGER_BOUND, text, token.span, via, token.text
            )
        code = DiagnosticCode.NON_INTEGER_BOUND
        message = f"{message_of(code)}: {token.text} is {only.text}"
        raise _Problem(UnreadableKind.VALUE, LocatedDiagnostic(code, message, at, only.origin.via))

    def _problem(
        self,
        kind: UnreadableKind,
        code: DiagnosticCode,
        text: _Text,
        span: SourceSpan,
        via: tuple[Step, ...],
        detail: str = "",
    ) -> _Problem:
        message = message_of(code) if detail == "" else f"{message_of(code)}: {detail}"
        return _Problem(kind, LocatedDiagnostic(code, message, text.place(span), via))
