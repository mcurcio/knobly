"""Expansion (round 11 slices.md §1.2): files' tier-1 trees in, readable directives and unreadable statements out.
Private to the load layer; the same rules as ts/src/load/expand.ts, held to them by conformance/load/.

Rules by number: reserved names (1), ``set`` (2), handed-in values win (3), ``$name`` (4), ``snippet`` (5), ``use``
(6), extension directives (7) and their blocks (8), limits and cycles (9), value rules checked at load (10),
unreadable statements (11), diagnostics order (12, with the processor)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from villanelle import _values
from villanelle._anatomy import Anatomy, anatomy_of, items_of
from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.directives import (
    Address,
    AddressStep,
    Argument,
    Directive,
    KeyInput,
    KeyRule,
    Unreadable,
    UnreadableKind,
)
from villanelle.graph import DocumentEdge, DocumentNode
from villanelle.origin import DirectiveOrigin, Handed, Origin, Place, Step, StepKind
from villanelle.processor import Extension, ExtensionUse
from villanelle.report import LocatedDiagnostic
from villanelle.source import DocumentSource, LoadContext
from villanelle.span import SourceSpan
from villanelle.syntax._recovery import message_of
from villanelle.syntax.cst import Node, NodeKind, Syntax, ValueRef, span_of
from villanelle.syntax.parse import parse
from villanelle.syntax.tokens import Token, TokenKind
from villanelle.value import IndexValue, SliceValue, ValueKind

MAX_DEPTH = 16
"""``use`` and extension directives may nest this many places; one more is E5007."""
MAX_DIRECTIVES = 100_000
"""Directives after expansion; one more is E5008 and expansion stops."""


@dataclass(frozen=True, slots=True)
class Text:
    """One text being expanded: a file, or a value handed in by the program (``handed`` is its variable's name)."""

    syntax: Syntax
    path: str
    handed: str | None = None

    def written(self, span: SourceSpan) -> Place | Handed:
        """Where a span of this text was written, for origins."""
        return Place(self.path, span) if self.handed is None else Handed(self.handed)

    def place(self, span: SourceSpan) -> Place:
        """The file place of a span, for diagnostics (a handed-in text never reports: its problems are ValueErrors)."""
        return Place(self.path, span)


class Problem(Exception):
    """A statement that cannot be read: raised inside a statement, caught where the statement is kept unreadable.
    ``diagnostic`` is None for a syntax error already reported by the parse."""

    def __init__(self, kind: UnreadableKind, diagnostic: LocatedDiagnostic | None, *, stop: bool = False) -> None:
        super().__init__(kind if diagnostic is None else diagnostic.message)
        self.kind = kind
        self.diagnostic = diagnostic
        self.stop = stop


class Stopped(Exception):
    """Expansion stopped (E5008); everything read so far stays."""


@dataclass(eq=False, slots=True)
class Snippet:
    """One ``snippet`` definition. Compared by identity: two definitions of one name in two blocks differ."""

    name: str
    params: tuple[str, ...]
    block: Node
    text: Text
    scope: Scope
    """Where it was written: its body sees what is visible there (lexical), plus its parameters."""


class Scope:
    """What one block can see: its own ``set`` and ``snippet`` lines so far, then the enclosing block's. ``forced``
    holds an extension block's ``set`` values, which win over every ``set`` in the files it splices (rule 8)."""

    __slots__ = ("bound", "claimed", "forced", "outer", "snippets")

    def __init__(self, outer: Scope | None) -> None:
        self.outer = outer
        self.bound: dict[str, tuple[Argument, ...]] = {}
        self.claimed: set[str] = set()
        self.snippets: dict[str, Snippet] = {}
        self.forced: Mapping[str, tuple[Argument, ...]] = {}

    def splice(self, forced: Mapping[str, tuple[Argument, ...]]) -> Scope:
        """The scope an extension's files are read in: this block's own bindings (shared, so a file's top-level
        ``set`` and ``snippet`` stay visible after the extension line, L2), with ``forced`` winning inside."""
        view = Scope(self.outer)
        view.bound, view.claimed, view.snippets = self.bound, self.claimed, self.snippets
        view.forced = {**self.forced, **forced}
        return view

    def lookup(self, name: str) -> tuple[Argument, ...] | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.forced:
                return scope.forced[name]
            scope = scope.outer
        scope = self
        while scope is not None:
            if name in scope.bound:
                return scope.bound[name]
            scope = scope.outer
        return None

    def snippet(self, name: str) -> Snippet | None:
        scope: Scope | None = self
        while scope is not None:
            if name in scope.snippets:
                return scope.snippets[name]
            scope = scope.outer
        return None


@dataclass(frozen=True, slots=True)
class At:
    """Where expansion stands: the text, what is visible, the steps that brought it here (innermost first), and the
    snippets and files being expanded (the root file first), for cycles and depth."""

    text: Text
    scope: Scope
    via: tuple[Step, ...]
    active: tuple[object, ...]

    def place(self, span: SourceSpan) -> Place:
        return self.text.place(span)

    def inner(self, scope: Scope) -> At:
        return At(self.text, scope, self.via, self.active)


@dataclass(slots=True)
class Container:
    """What one container (the top level or a block) holds after expansion; spliced statements land in it too."""

    body: list[Directive]
    unreadable: list[Unreadable]
    parent: Directive | None
    occurrences: dict[tuple[str, str | None], int] = field(default_factory=dict)


class Expander:
    def __init__(
        self,
        *,
        source: DocumentSource,
        extensions: Mapping[str, Extension],
        handed: Mapping[str, tuple[Argument, ...]],
        key: KeyRule | None,
        nodes: dict[str, DocumentNode],
    ) -> None:
        self._source = source
        self._extensions = extensions
        self._handed = handed
        self._key = key
        self.nodes = nodes
        """Every file read, by resolved path, in first-read order (the root first)."""
        self._failed: dict[str, Exception] = {}
        self.diagnostics: list[LocatedDiagnostic] = []
        """Load diagnostics in the order expansion meets them."""
        self.edges: list[DocumentEdge] = []
        self.directives: list[Directive] = []

    # --- statements ---------------------------------------------------------------------------------------------

    def statements(self, at: At, scope_node: Node, into: Container) -> None:
        """Expand the statements of ``scope_node`` (a document or block node) into ``into``."""
        for node in scope_node.children:
            if node.kind is NodeKind.ERROR:
                into.unreadable.append(self._unreadable(at, node, UnreadableKind.SYNTAX))
                continue
            if node.kind is not NodeKind.DIRECTIVE:
                continue
            try:
                self._statement(at, node, into)
            except Problem as problem:
                if problem.diagnostic is not None:
                    self.diagnostics.append(problem.diagnostic)
                into.unreadable.append(self._unreadable(at, node, problem.kind))
                if problem.stop:
                    raise Stopped from None

    def _statement(self, at: At, node: Node, into: Container) -> None:
        tokens = at.text.syntax.tokens
        anatomy = anatomy_of(tokens, node)
        name_token = tokens[anatomy.name]
        name = name_token.text
        if name == "set":
            self._set(at, anatomy)
            return
        if name == "snippet":
            self._snippet(at, anatomy)
            return
        if name == "use":
            self._use(at, anatomy, into)
            return
        extension = self._extensions.get(name)
        if extension is not None:
            self._extension(at, extension, anatomy, into)
            return
        self._directive(at, node, anatomy, into)

    def _directive(self, at: At, node: Node, anatomy: Anatomy, into: Container) -> None:
        name_token = at.text.syntax.tokens[anatomy.name]
        name = name_token.text
        args = self._values(at, anatomy.args)
        if len(self.directives) >= MAX_DIRECTIVES:
            problem = self._problem(UnreadableKind.EXPANSION, DiagnosticCode.TOO_MANY_DIRECTIVES, at, name_token.span)
            raise Problem(problem.kind, problem.diagnostic, stop=True)
        parent = into.parent
        has_block = anatomy.block is not None
        key_input = KeyInput(name, args, has_block, None if parent is None else parent._key_input)
        key = None if self._key is None else self._key(key_input)
        slot = (name, key)
        occurrence = into.occurrences.get(slot, 0)
        into.occurrences[slot] = occurrence + 1
        steps = (() if parent is None else parent.address.steps) + (AddressStep(name, key, occurrence),)
        origin = DirectiveOrigin(at.place(name_token.span), at.via)
        directive = Directive(name, args, has_block, parent, Address(steps), origin, node, key_input)
        self.directives.append(directive)
        into.body.append(directive)
        if anatomy.block is not None:
            body, unreadable = directive._contents()
            self.statements(at.inner(Scope(at.scope)), anatomy.block, Container(body, unreadable, directive))

    # --- set, snippet, use ----------------------------------------------------------------------------------------

    def _set(self, at: At, anatomy: Anatomy) -> None:
        """``set $name value...;`` (rule 2): binds in ``at.scope`` from this line to the end of its block."""
        tokens = at.text.syntax.tokens
        args = anatomy.args
        first = args[0] if args else None
        variable = tokens[first] if isinstance(first, int) else None
        if variable is None or variable.kind is not TokenKind.VARIABLE or len(args) < 2 or anatomy.block is not None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_SET, at, tokens[anatomy.name].span)
        name = variable.text[1:]
        if name in at.scope.claimed:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.VARIABLE_SET_TWICE, at, variable.span, variable.text
            )
        at.scope.claimed.add(name)
        values = self._values(at, args[1:])
        # Stored without this line's own steps; a reader adds the variable step and its own (Argument.rebase).
        at.scope.bound[name] = tuple(value._rebase(len(at.via), ()) for value in values)

    def _snippet(self, at: At, anatomy: Anatomy) -> None:
        """``snippet name $param... { body }`` (rule 5): defined from this line to the end of its block."""
        tokens = at.text.syntax.tokens
        refs = anatomy.args
        name_ref = refs[0] if refs else None
        params = [tokens[r] if isinstance(r, int) else None for r in refs[1:]]
        names = [p.text[1:] for p in params if p is not None and p.kind is TokenKind.VARIABLE]
        if (
            not isinstance(name_ref, int)
            or tokens[name_ref].kind is not TokenKind.WORD
            or len(names) != len(params)
            or len(set(names)) != len(names)
            or anatomy.block is None
        ):
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_SNIPPET, at, tokens[anatomy.name].span)
        name_token = tokens[name_ref]
        if name_token.text in at.scope.snippets:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.SNIPPET_DEFINED_TWICE, at, name_token.span, name_token.text
            )
        at.scope.snippets[name_token.text] = Snippet(name_token.text, tuple(names), anatomy.block, at.text, at.scope)

    def _use(self, at: At, anatomy: Anatomy, into: Container) -> None:
        """``use name value...;`` (rule 6): splices the snippet's body in place."""
        tokens = at.text.syntax.tokens
        use_token = tokens[anatomy.name]
        refs = anatomy.args
        name_ref = refs[0] if refs else None
        if not isinstance(name_ref, int) or tokens[name_ref].kind is not TokenKind.WORD or anatomy.block is not None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.BAD_USE, at, use_token.span)
        name_token = tokens[name_ref]
        snippet = at.scope.snippet(name_token.text)
        if snippet is None:
            raise self._problem(
                UnreadableKind.EXPANSION, DiagnosticCode.UNKNOWN_SNIPPET, at, name_token.span, name_token.text
            )
        values = self._values(at, refs[1:])
        if len(values) != len(snippet.params):
            detail = f"{snippet.name} takes {len(snippet.params)}, given {len(values)}"
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.SNIPPET_ARITY, at, use_token.span, detail)
        self._enter(at, snippet, use_token, snippet.name)
        body = Scope(snippet.scope)
        for param, value in zip(snippet.params, values, strict=True):
            body.claimed.add(param)
            body.bound[param] = (value._rebase(len(at.via), ()),)
        step = Step(StepKind.USE, snippet.name, at.place(use_token.span))
        self.statements(At(snippet.text, body, (step, *at.via), (*at.active, snippet)), snippet.block, into)

    def _enter(self, at: At, what: object, token: Token, name: str) -> None:
        """Rule 9: E5006 when ``what`` (a snippet or a file) is already being expanded; E5007 past the depth."""
        if what in at.active:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.EXPANSION_CYCLE, at, token.span, name)
        if len(at.active) > MAX_DEPTH:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.EXPANSION_TOO_DEEP, at, token.span, name)

    # --- extensions -----------------------------------------------------------------------------------------------

    def _extension(self, at: At, extension: Extension, anatomy: Anatomy, into: Container) -> None:
        """An extension directive (rules 7 and 8): its specs' files spliced in place."""
        tokens = at.text.syntax.tokens
        name_token = tokens[anatomy.name]
        name = name_token.text
        name_place = at.place(name_token.span)
        args = self._values(at, anatomy.args)
        forced = self._extension_block(at, anatomy.block)
        origin = DirectiveOrigin(name_place, at.via)
        try:
            specs = tuple(extension.specs(ExtensionUse(args, origin)))
        except DiagnosticError as error:
            raise Problem(UnreadableKind.EXTENSION, error.diagnostic) from None
        except Exception as error:
            raise self._problem(
                UnreadableKind.EXTENSION, DiagnosticCode.EXTENSION_FAILED, at, name_token.span, f"{name}: {error}"
            ) from None
        targets: list[str] = []
        try:
            for spec in specs:
                targets.extend(sorted(self._resolve(at, name_token, spec)))
            for target in targets:
                self._enter(at, target, name_token, target)
            documents = [self._read(at, name_token, target) for target in targets]
        except Problem:
            self.edges.append(DocumentEdge(name, origin, specs, ()))
            raise
        self.edges.append(DocumentEdge(name, origin, specs, tuple(targets)))
        via = (Step(StepKind.EXTENSION, name, name_place), *at.via)
        scope = at.scope.splice(forced)
        for document in documents:
            text = Text(document.syntax, document.resolved_path)
            self.statements(At(text, scope, via, (*at.active, document.resolved_path)), document.syntax.root, into)

    def _extension_block(self, at: At, block: Node | None) -> Mapping[str, tuple[Argument, ...]]:
        """Rule 8: an extension directive's block holds only ``set`` lines (E5012); they bind for the spliced files."""
        if block is None:
            return {}
        tokens = at.text.syntax.tokens
        scope = Scope(at.scope)
        for child in block.children:
            if child.kind is NodeKind.ERROR:
                # Already reported by the parse; a broken line here could be a value the files need.
                raise Problem(UnreadableKind.SYNTAX, None)
            if child.kind is not NodeKind.DIRECTIVE:
                continue
            anatomy = anatomy_of(tokens, child)
            if tokens[anatomy.name].text != "set":
                raise self._problem(
                    UnreadableKind.EXTENSION, DiagnosticCode.EXTENSION_BLOCK_NOT_SET, at, tokens[anatomy.name].span
                )
            self._set(at.inner(scope), anatomy)
        return scope.bound

    def _resolve(self, at: At, name_token: Token, spec: str) -> Sequence[str]:
        try:
            paths = self._source.resolve(spec, LoadContext(at.text.path))
        except Exception as error:
            raise self._problem(
                UnreadableKind.EXTENSION,
                DiagnosticCode.INCLUDE_RESOLVER_FAILED,
                at,
                name_token.span,
                f"{spec}: {error}",
            ) from None
        if not paths:
            raise self._problem(UnreadableKind.EXTENSION, DiagnosticCode.INCLUDE_NOT_FOUND, at, name_token.span, spec)
        return paths

    def _read(self, at: At, name_token: Token, path: str) -> DocumentNode:
        """Each path is read and parsed once per load (R21), however many places splice it."""
        document = self.nodes.get(path)
        if document is not None:
            return document
        failure = self._failed.get(path)
        if failure is None:
            try:
                text = self._source.read(path)
            except Exception as error:
                failure = self._failed[path] = error
            else:
                document = self.nodes[path] = DocumentNode(path, text, parse(text))
                return document
        raise self._problem(
            UnreadableKind.EXTENSION, DiagnosticCode.INCLUDE_RESOLVER_FAILED, at, name_token.span, f"{path}: {failure}"
        )

    # --- values ---------------------------------------------------------------------------------------------------

    def _values(self, at: At, refs: Sequence[ValueRef]) -> tuple[Argument, ...]:
        return tuple(argument for ref in refs for argument in self.value(at, ref))

    def value(self, at: At, ref: ValueRef) -> list[Argument]:
        """One written value, expanded: a ``$name`` becomes all its values (rule 4); a list's items the same way."""
        syntax = at.text.syntax
        if isinstance(ref, Node):
            origin = Origin(at.text.written(span_of(syntax, ref)), at.via)
            if ref.kind is NodeKind.LIST:
                items = self._values(at, items_of(syntax.tokens, ref))
                return [Argument(ValueKind.LIST, items, origin)]
            return [self._slice(at, ref, origin)]
        token = syntax.tokens[ref]
        origin = Origin(at.text.written(token.span), at.via)
        if token.kind is TokenKind.WORD:
            return [Argument(ValueKind.WORD, token.text, origin)]
        if token.kind is TokenKind.STRING:
            if not _values.has_only_known_escapes(token.text):
                raise self._problem(UnreadableKind.VALUE, DiagnosticCode.BAD_ESCAPE, at, token.span, token.text)
            return [Argument(ValueKind.STRING, _values.decode_string(token.text), origin)]
        if token.kind is TokenKind.VARIABLE:
            return self._variable(at, token)
        raise TypeError(f"not a value token: {token.kind}")

    def _variable(self, at: At, token: Token) -> list[Argument]:
        """``$name``'s values as read at ``token``: each with the variable step, then the reading place's steps."""
        name = token.text[1:]
        values = self._handed.get(name)
        if values is None:
            values = at.scope.lookup(name)
        if values is None:
            raise self._problem(UnreadableKind.EXPANSION, DiagnosticCode.UNKNOWN_VARIABLE, at, token.span, token.text)
        step = Step(StepKind.VARIABLE, name, at.place(token.span))
        return [value._rebase(0, (step, *at.via)) for value in values]

    def _slice(self, at: At, node: Node, origin: Origin) -> Argument:
        """``name[bounds]``: each bound a literal IntegerText or a variable holding exactly one (rules 4 and 10)."""
        tokens = at.text.syntax.tokens
        name = tokens[node.start].text
        inner = tokens[node.start + 2 : node.end - 1]
        colon = next((i for i, t in enumerate(inner) if t.kind is TokenKind.COLON), None)
        if colon is None:
            return Argument(ValueKind.INDEX, IndexValue(name, self._bound(at, inner[0])), origin)
        start = None if colon == 0 else self._bound(at, inner[0])
        end = self._bound(at, inner[colon + 1]) if colon + 1 < len(inner) else None
        return Argument(ValueKind.SLICE, SliceValue(name, start, end), origin)

    def _bound(self, at: At, token: Token) -> int:
        """One bound's integer. E4001 at the bound, or for a variable at its value's place via the variable."""
        if token.kind is TokenKind.WORD:
            value = _values.integer_of(token.text)
            if value is None:
                raise self._problem(UnreadableKind.VALUE, DiagnosticCode.NON_INTEGER_BOUND, at, token.span, token.text)
            return value
        values = self._variable(at, token)
        only = values[0] if values else None
        if len(values) == 1 and only is not None and only.kind is ValueKind.WORD:
            value = _values.integer_of(only.text)
            if value is not None:
                return value
        written = None if only is None else only.origin.written
        if only is None or not isinstance(written, Place):
            # A handed-in value is written in no file: the problem is placed on the `$name` that used it.
            raise self._problem(UnreadableKind.VALUE, DiagnosticCode.NON_INTEGER_BOUND, at, token.span, token.text)
        code = DiagnosticCode.NON_INTEGER_BOUND
        message = f"{message_of(code)}: {token.text} is {only.text}"
        raise Problem(UnreadableKind.VALUE, LocatedDiagnostic(code, message, written, only.origin.via))

    # --- helpers --------------------------------------------------------------------------------------------------

    def _problem(
        self, kind: UnreadableKind, code: DiagnosticCode, at: At, span: SourceSpan, detail: str = ""
    ) -> Problem:
        message = message_of(code) if detail == "" else f"{message_of(code)}: {detail}"
        return Problem(kind, LocatedDiagnostic(code, message, at.place(span), at.via))

    def _unreadable(self, at: At, node: Node, kind: UnreadableKind) -> Unreadable:
        span = span_of(at.text.syntax, node)
        return Unreadable(kind, DirectiveOrigin(at.place(span), at.via), node)


_VARIABLE_NAME = re.compile(r"[A-Za-z0-9_]+")


def read_handed(variables: Mapping[str, str]) -> dict[str, tuple[Argument, ...]]:
    """The values handed in by the program, each text read as the values of one directive (S1-13). ValueError for a
    bad name, or a text that is not one run of values (a syntax error, a block, a variable, an unknown escape, a
    non-integer bound)."""
    handed: dict[str, tuple[Argument, ...]] = {}
    for name, written in variables.items():
        if not _VARIABLE_NAME.fullmatch(name):
            raise ValueError(f"handed-in variable name must be letters, digits and _: {name!r}")

        def bad(why: str, name: str = name, written: str = written) -> ValueError:
            return ValueError(f"handed-in variable {name}: {why}: {written!r}")

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
        reader = Expander(source=_NO_SOURCE, extensions={}, handed={}, key=None, nodes={})
        at = At(Text(syntax, "", handed=name), Scope(None), (), ())
        try:
            handed[name] = tuple(argument for ref in anatomy.args for argument in reader.value(at, ref))
        except Problem as problem:
            raise bad(problem.diagnostic.message if problem.diagnostic else str(problem.kind)) from None
    return handed


class _NoSource:
    """The source of a handed-in text's reader, which never reads a file."""

    def resolve(self, spec: str, context: LoadContext, /) -> Sequence[str]:
        raise AssertionError("a handed-in value reads no file")

    def read(self, resolved_path: str, /) -> str:
        raise AssertionError("a handed-in value reads no file")


_NO_SOURCE = _NoSource()
