"""One file as written (round 12 slices.md 2.1-2.4): the tree of handles over a document's current parse, and every
edit. An edit computes the new text, checks it (2.3), re-parses the whole document and reconciles the handles (2.1).
Private; a port of ts/src/written/document.ts (and S2's edits, by the same rules).

Offsets here are ``str`` indices (code points): ``Document._starts`` maps each token to its index; places and
diagnostics count in the same unit (spec/contract.md 1)."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from villanelle._anatomy import anatomy_of, items_of, values_of
from villanelle._api.kinds import StatementKind
from villanelle.diagnostics import Diagnostic, DiagnosticCode
from villanelle.errors import BadTextError
from villanelle.origin import Place
from villanelle.span import SourcePosition, SourceSpan
from villanelle.syntax._recovery import message_of
from villanelle.syntax.cst import Node, NodeKind, Syntax, ValueRef, span_of
from villanelle.syntax.parse import EntryRule, parse, parse_entry
from villanelle.syntax.tokens import TokenKind
from villanelle.written import _names
from villanelle.written._shape import Shape, ShapeKind, block_shapes, parameter_tokens, statement_nodes
from villanelle.written.model import (
    Document,
    ExtensionLine,
    Index,
    List,
    Parameter,
    Reference,
    SetLine,
    SetVariable,
    Slice,
    SnippetLine,
    Statement,
    String,
    UnreadableLine,
    UseLine,
    Variable,
    Word,
    WrittenBlock,
    WrittenDirective,
    WrittenValue,
)

Handle: TypeAlias = "Statement | WrittenValue | Parameter"
"""Anything a reconcile keeps or detaches."""

_TRIVIA = frozenset({TokenKind.SPACE, TokenKind.NEWLINE})
_LIST_GAP = frozenset({TokenKind.SPACE, TokenKind.NEWLINE, TokenKind.COMMENT})

Piece: TypeAlias = "str | tuple[int, int]"
"""A piece of an insert: text the edit adds, or the range ``[from, to)`` of the caller's text it copies."""


@dataclass(frozen=True, slots=True)
class _Insert:
    """What an edit splices in: its text, the caller's text, and for each ``str`` index its index there (-1: added)."""

    text: str
    given: str
    origin: tuple[int, ...]


def _insert_of(given: str, pieces: Sequence[Piece]) -> _Insert:
    text: list[str] = []
    origin: list[int] = []
    for piece in pieces:
        if isinstance(piece, str):
            text.append(piece)
            origin.extend([-1] * len(piece))
        else:
            text.append(given[piece[0] : piece[1]])
            origin.extend(range(piece[0], piece[1]))
    return _Insert("".join(text), given, tuple(origin))


@dataclass(frozen=True, slots=True)
class _Range:
    start: int
    end: int


def starts_of(syntax: Syntax) -> list[int]:
    """Each token's start as a ``str`` index, then the text's length."""
    out = [0]
    for token in syntax.tokens:
        out.append(out[-1] + len(token.text))
    return out


# --- Ranges, places, text ---


def ref_range(ref: ValueRef) -> tuple[int, int]:
    return (ref, ref + 1) if isinstance(ref, int) else (ref.start, ref.end)


def place_of_span(doc: Document, span: SourceSpan) -> Place:
    return Place(doc._path, span)


def place(doc: Document, rng: tuple[int, int]) -> Place:
    return Place(doc._path, span_of(doc._syntax, _Range(*rng)))


def text_of_range(doc: Document, rng: tuple[int, int]) -> str:
    return doc._text[doc._starts[rng[0]] : doc._starts[rng[1]]]


def offsets(doc: Document, rng: tuple[int, int]) -> tuple[int, int]:
    return doc._starts[rng[0]], doc._starts[rng[1]]


def first_arg_token(statement: Statement) -> int:
    """The token index of its first value-position token (a ``set``'s ``$name``, a snippet's or use's name)."""
    args = anatomy_of(statement._doc._syntax.tokens, statement._node).args
    return args[0] if args and isinstance(args[0], int) else statement._node.start


def owned_range(doc: Document, node: Node) -> tuple[int, int]:
    """A statement's owned token range (2.2): from a comment line above it to its trailing comment."""
    tokens = doc._syntax.tokens
    n = len(tokens)

    def kind(i: int) -> TokenKind | None:
        return tokens[i].kind if 0 <= i < n else None

    first = node.start
    last = node.end - 1
    while last > first and kind(last) in _TRIVIA:
        last -= 1
    j = last + 1
    while kind(j) is TokenKind.SPACE:
        j += 1
    if kind(j) is TokenKind.COMMENT:
        last = j
    # Comment lines directly above, only when the statement starts its line (D-S1-4).
    k = first - 1
    while kind(k) is TokenKind.SPACE:
        k -= 1
    if k < 0 or kind(k) in (TokenKind.NEWLINE, TokenKind.BOM):
        while kind(k) is TokenKind.NEWLINE:
            m = k - 1
            while kind(m) is TokenKind.SPACE:
                m -= 1
            if kind(m) is not TokenKind.COMMENT:
                break
            comment = m
            m -= 1
            while kind(m) is TokenKind.SPACE:
                m -= 1
            if not (m < 0 or kind(m) in (TokenKind.NEWLINE, TokenKind.BOM)):
                break
            first = comment
            k = m
    return first, last + 1


def _trimmed(doc: Document, node: Node) -> tuple[int, int]:
    """A node's range without trailing spaces and line breaks."""
    tokens = doc._syntax.tokens
    end = node.end
    while end > node.start + 1 and tokens[end - 1].kind in _TRIVIA:
        end -= 1
    return node.start, end


# --- The reconcile (2.1) ---


class _Reconcile:
    """Matches the handles of a new parse to the old ones."""

    __slots__ = ("created", "keep", "old", "range")

    def __init__(
        self,
        old: dict[tuple[str, int], tuple[Handle, int, int]],
        rng: tuple[int, int, int] | None,
        keep: Handle | None = None,
    ) -> None:
        self.old = old
        self.range = rng
        """The replaced range in old offsets, and the length of what replaced it; None: keep nothing."""
        self.keep = keep
        """The handle an edit was called on that keeps its identity although its own tokens are replaced."""
        self.created: list[Handle] = []

    def take(self, key: str, new_start: int) -> Handle | None:
        if self.range is None:
            return None
        start, end, inserted = self.range
        delta = inserted - (end - start)
        old: int | None = None
        if new_start < start:
            old = new_start
        elif new_start >= start + inserted:
            old = new_start - delta
        if old is not None:
            found = self._match(key, old, strict=False)
            if found is not None:
                return found
        # Something starting where the splice starts: only a handle spanning the replaced tokens (a renamed
        # directive) or the one the edit was called on keeps its identity.
        return self._match(key, start, strict=True) if new_start == start and end > start else None

    def _match(self, key: str, old: int, *, strict: bool) -> Handle | None:
        assert self.range is not None
        start, end, _ = self.range
        entry = self.old.get((key, old))
        if entry is None:
            return None
        handle, entry_start, entry_end = entry
        contains = entry_start <= start and entry_end >= end and (entry_start < start or entry_end > end)
        if strict:
            ok = entry_start == start and (contains or handle is self.keep)
        else:
            ok = entry_end <= start or entry_start >= end or contains
        if not ok:
            return None
        del self.old[(key, old)]
        return handle

    def leftovers(self) -> list[Handle]:
        """Handles left over: their tokens were replaced."""
        return [entry[0] for entry in self.old.values()]


def _entries(doc: Document) -> dict[tuple[str, int], tuple[Handle, int, int]]:
    """The handles currently in the tree, by reconcile key."""
    out: dict[tuple[str, int], tuple[Handle, int, int]] = {}

    def add(key: str, handle: Handle, rng: tuple[int, int]) -> None:
        start, end = offsets(doc, rng)
        out[(key, start)] = (handle, start, end)

    def value(v: WrittenValue) -> None:
        add(f"v:{v.kind}", v, ref_range(v._ref))
        for inner in v._inner():
            value(inner)

    def statement(s: Statement) -> None:
        add(f"s:{s.kind}", s, _trimmed(doc, s._node))
        for v in s._value_list:
            value(v)
        if isinstance(s, SnippetLine):
            for p in s._parameters:
                add("p", p, (p._token, p._token + 1))
        if s._block is not None:
            for child in s._block._items:
                statement(child)

    for s in doc._block._items:
        statement(s)
    return out


def _detach(handles: Sequence[Handle]) -> None:
    for handle in handles:
        handle._detached = True


# --- Building the handle tree ---


def start(doc: Document, text: str) -> None:
    """A new document's first parse and handles."""
    _install(doc, text, parse(text), _Reconcile({}, None))


def _install(doc: Document, text: str, syntax: Syntax, reconcile: _Reconcile) -> None:
    doc._text = text
    doc._syntax = syntax
    doc._starts = starts_of(syntax)
    doc._statements = {}
    doc._values = {}
    doc._block._items = _build_block(doc, syntax.root, None, (), reconcile)


def _build_block(
    doc: Document, container: Node, owner: Statement | None, claimed: Sequence[str], reconcile: _Reconcile
) -> list[Statement]:
    nodes = statement_nodes(container)
    shapes = block_shapes(doc._syntax.tokens, nodes, doc._graph._extension_names, claimed)
    return [_build_statement(doc, node, shape, owner, reconcile) for node, shape in zip(nodes, shapes, strict=True)]


def _new_statement(doc: Document, kind: ShapeKind) -> Statement:
    match kind:
        case StatementKind.DIRECTIVE:
            return WrittenDirective(doc)
        case StatementKind.EXTENSION:
            return ExtensionLine(doc)
        case StatementKind.SET:
            return SetLine(doc)
        case StatementKind.SNIPPET:
            return SnippetLine(doc)
        case StatementKind.USE:
            return UseLine(doc)
        case StatementKind.UNREADABLE:
            return UnreadableLine(doc)


_STATEMENT_CLASS: dict[
    ShapeKind, type[WrittenDirective | ExtensionLine | SetLine | SnippetLine | UseLine | UnreadableLine]
] = {
    StatementKind.DIRECTIVE: WrittenDirective,
    StatementKind.EXTENSION: ExtensionLine,
    StatementKind.SET: SetLine,
    StatementKind.SNIPPET: SnippetLine,
    StatementKind.USE: UseLine,
    StatementKind.UNREADABLE: UnreadableLine,
}


def _build_statement(
    doc: Document, node: Node, shape: Shape, owner: Statement | None, reconcile: _Reconcile
) -> Statement:
    tokens = doc._syntax.tokens
    kept = reconcile.take(f"s:{shape.kind}", doc._starts[node.start])
    handle: Statement
    if isinstance(kept, _STATEMENT_CLASS[shape.kind]):
        handle = kept
    else:
        handle = _new_statement(doc, shape.kind)
        reconcile.created.append(handle)
    handle._node = node
    handle._parent = owner
    handle._detached = False
    doc._statements[node.start] = handle
    anatomy = anatomy_of(tokens, node) if node.kind is NodeKind.DIRECTIVE else None
    args = anatomy.args if anatomy is not None else ()

    def values(refs: Sequence[ValueRef]) -> list[WrittenValue]:
        return [_build_value(doc, ref, handle, None, False, reconcile) for ref in refs]

    def block(claimed: Sequence[str]) -> None:
        if anatomy is None or anatomy.block is None:
            handle._block = None
            return
        if handle._block is None:
            handle._block = WrittenBlock(doc, handle)
        handle._block._items = _build_block(doc, anatomy.block, handle, claimed, reconcile)

    if isinstance(handle, WrittenDirective | ExtensionLine):
        handle._value_list = values(args)
        block(())
    elif isinstance(handle, SetLine | UseLine):
        handle._value_list = values(args[1:])
        handle._block = None
    elif isinstance(handle, SnippetLine):
        handle._value_list = []
        parameters: list[Parameter] = []
        for token in parameter_tokens(tokens, node):
            kept_parameter = reconcile.take("p", doc._starts[token])
            if isinstance(kept_parameter, Parameter):
                parameter = kept_parameter
            else:
                parameter = Parameter(handle)
                reconcile.created.append(parameter)
            parameter._token = token
            parameter._detached = False
            parameters.append(parameter)
        handle._parameters = parameters
        block([tokens[p._token].text[1:] for p in parameters])
    else:
        handle._value_list = []
        handle._block = None
    return handle


def _value_kind(syntax: Syntax, ref: ValueRef) -> str:
    tokens = syntax.tokens
    if isinstance(ref, Node):
        if ref.kind is NodeKind.LIST:
            return "list"
        if any(tokens[i].kind is TokenKind.COLON for i in range(ref.start + 2, ref.end - 1)):
            return "slice"
        return "index" if ref.end - ref.start > 3 else "slice"
    kind = tokens[ref].kind
    return "string" if kind is TokenKind.STRING else "reference" if kind is TokenKind.VARIABLE else "word"


_VALUE_CLASS: dict[str, type[WrittenValue]] = {
    "word": Word,
    "string": String,
    "list": List,
    "slice": Slice,
    "index": Index,
    "reference": Reference,
}


def _build_value(
    doc: Document, ref: ValueRef, statement: Statement, in_list: List | None, bound: bool, reconcile: _Reconcile
) -> WrittenValue:
    tokens = doc._syntax.tokens
    index = ref if isinstance(ref, int) else ref.start
    kind = _value_kind(doc._syntax, ref)
    cls = _VALUE_CLASS[kind]
    kept = reconcile.take(f"v:{kind}", doc._starts[index])
    handle: WrittenValue
    if kept is not None and isinstance(kept, cls):
        handle = kept
    else:
        handle = cls(doc)
        reconcile.created.append(handle)
    handle._ref = ref
    handle._statement = statement
    handle._list = in_list
    handle._bound = bound
    handle._detached = False
    doc._values[index] = handle
    if isinstance(handle, List) and isinstance(ref, Node):
        handle._items = [_build_value(doc, item, statement, handle, False, reconcile) for item in items_of(tokens, ref)]
    elif isinstance(handle, Slice | Index) and isinstance(ref, Node):
        inner = list(range(ref.start + 2, ref.end - 1))
        colon = next((i for i, t in enumerate(inner) if tokens[t].kind is TokenKind.COLON), -1)

        def bound_at(position: int) -> Word | Reference | None:
            if not 0 <= position < len(inner):
                return None
            at = inner[position]
            if tokens[at].kind not in (TokenKind.WORD, TokenKind.INTEGER, TokenKind.DIGIT_WORD, TokenKind.VARIABLE):
                return None
            made = _build_value(doc, at, statement, None, True, reconcile)
            assert isinstance(made, Word | Reference)
            return made

        if isinstance(handle, Index):
            handle._index = bound_at(0)
        else:
            handle._start = None if colon == 0 else bound_at(0)
            handle._end = bound_at(colon + 1) if colon + 1 < len(inner) else None
    return handle


# --- Edits (2.3, 2.4) ---


def _splice(
    doc: Document, start: int, end: int, insert: str | _Insert, given: Sequence[Diagnostic], keep: Handle | None = None
) -> list[Handle]:
    """Replace ``doc._text[start:end]`` with ``insert``, after ``given`` (the given text's own problems) and the
    text-alone rules found nothing wrong; then re-parse, reconcile and tell the graph. Raises BadTextError, changing
    nothing. Returns the handles made for the inserted text."""
    if given:
        raise BadTextError(given)
    spliced = _insert_of(insert, [(0, len(insert))]) if isinstance(insert, str) else insert
    text = doc._text[:start] + spliced.text + doc._text[end:]
    syntax = parse(text)
    rules = _rule_problems(syntax, starts_of(syntax), doc._graph._extension_names, start, spliced)
    if rules:
        raise BadTextError(rules)
    reconcile = _Reconcile(_entries(doc), (start, end, len(spliced.text)), keep)
    _install(doc, text, syntax, reconcile)
    _detach(reconcile.leftovers())
    doc._graph._version += 1
    return reconcile.created


def replace_document(doc: Document, text: str) -> None:
    reconcile = _Reconcile(_entries(doc), None)
    _install(doc, text, parse(text), reconcile)
    _detach(reconcile.leftovers())
    doc._graph._version += 1


def line_break(doc: Document) -> str:
    """The line break this document uses: its first, else ``\\n``."""
    found = re.search(r"\r\n|\n", doc._text)
    return "\n" if found is None else found.group()


def indentation_at(doc: Document, offset: int) -> str:
    """The leading whitespace of the line holding ``offset``."""
    line_start = doc._text.rfind("\n", 0, offset) + 1
    found = re.match(r"[ \t]*", doc._text[line_start:])
    return "" if found is None else found.group()


def _indentation_unit(doc: Document) -> str:
    """The leading whitespace of the document's first indented line, else four spaces (D14)."""
    found = re.search(r"^([ \t]+)\S", doc._text, re.MULTILINE)
    return "    " if found is None else found.group(1)


def remove_statement(statement: Statement) -> None:
    """``remove()`` of a statement (2.2): its owned span, and its lines when nothing else is on them."""
    doc = statement._doc
    start, end = offsets(doc, owned_range(doc, statement._node))
    first, last = _removal_range(doc._text, start, end)
    _splice(doc, first, last, "", [])


def _removal_range(text: str, start: int, end: int) -> tuple[int, int]:
    """What a removal of ``text[start:end]`` deletes: whole lines when nothing else is on them, else one space more."""
    line_start = text.rfind("\n", 0, start) + 1
    newline = text.find("\n", end)
    line_end = len(text) if newline < 0 else newline
    before = text[line_start:start]
    after = text[end:line_end].removesuffix("\r")
    if re.fullmatch(r"[ \t﻿]*", before) and re.fullmatch(r"[ \t]*", after):
        bomless = 1 if text.startswith("﻿") and line_start == 0 else 0
        return line_start + bomless, len(text) if newline < 0 else newline + 1
    if end < len(text) and text[end] in " \t":
        return start, end + 1
    if start > 0 and text[start - 1] in " \t":
        return start - 1, end
    return start, end


def _statements_text_problems(text: str) -> tuple[Diagnostic, ...]:
    """A statements text's check: its own syntax diagnostics, as a document (2.8)."""
    return parse(text).diagnostics


def replace_statement(statement: Statement, text: str) -> tuple[Statement, ...]:
    """``replace_with_text`` of a statement: zero or more statements, indented as it is."""
    doc = statement._doc
    given = _statements_text_problems(text)
    if text.strip() == "":
        if given:
            raise BadTextError(given)
        remove_statement(statement)
        return ()
    start, end = offsets(doc, owned_range(doc, statement._node))
    insert = _insert_of(text, _reindent(doc, text, indentation_at(doc, start)))
    owner = statement._parent
    created = _splice(doc, start, end, insert, given)
    return _top_statements(created, owner)


def _top_statements(created: Sequence[Handle], owner: Statement | None) -> tuple[Statement, ...]:
    statements = (WrittenDirective, ExtensionLine, SetLine, SnippetLine, UseLine, UnreadableLine)
    return tuple(h for h in created if isinstance(h, statements) and h._parent is owner)


def _reindent(doc: Document, text: str, indentation: str) -> list[Piece]:
    """The given statements text with its common indentation removed, later lines prefixed with ``indentation``, as
    pieces of an insert (each line's text keeps its place in the given text, for 2.3's locations)."""
    lead_match = re.match(r"(?:[ \t]*\r?\n)+", text)
    lead = 0 if lead_match is None else lead_match.end()
    rest = text[lead:]
    trail_match = re.search(r"(?:\r?\n[ \t]*)+$", rest)
    body = rest if trail_match is None else rest[: trail_match.start()]
    lines: list[tuple[str, int]] = []
    start = 0
    for match in re.finditer(r"\r?\n", body):
        lines.append((body[start : match.start()], lead + start))
        start = match.end()
    lines.append((body[start:], lead + start))
    common = min(len(line) - len(line.lstrip(" \t")) for line, _ in lines if line.strip() != "")
    eol = line_break(doc)
    pieces: list[Piece] = []
    for i, (line, at_index) in enumerate(lines):
        if i > 0:
            pieces.append(eol)
            if line.strip() == "":
                continue
            pieces.append(indentation)
        pieces.append((at_index + common, at_index + len(line)))
    return pieces


def replace_values(statement: Statement, after: int, text: str) -> None:
    """``set`` of a statement's values (2.4): first value to last; with none, after token ``after``."""
    doc = statement._doc
    given = entry_problems(text, "valuesText")
    values = statement._value_list
    if not values:
        if text.strip() == "":
            return
        offset = doc._starts[after + 1]
        _splice(doc, offset, offset, _insert_of(text, [" ", (0, len(text))]), given)
        return
    start = offsets(doc, ref_range(values[0]._ref))[0]
    end = offsets(doc, ref_range(values[-1]._ref))[1]
    if text.strip() == "":
        first = ref_range(values[0]._ref)[0]
        tokens = doc._syntax.tokens
        while first > 0 and tokens[first - 1].kind is TokenKind.SPACE:
            first -= 1
        _splice(doc, doc._starts[first], end, "", given)
        return
    _splice(doc, start, end, text, given)


def replace_value(value: WrittenValue, text: str) -> tuple[WrittenValue, ...]:
    """``replace_with_text`` of a value."""
    doc = value._doc
    rule: EntryRule = "boundText" if value._bound else "itemsText" if value._list is not None else "valuesText"
    given = entry_problems(text, rule)
    if text.strip() == "":
        if given:
            raise BadTextError(given)
        remove_value(value)
        return ()
    start, end = offsets(doc, ref_range(value._ref))
    container = value._list
    statement = value._statement
    created = _splice(doc, start, end, text, given)
    return tuple(
        h
        for h in created
        if isinstance(h, Word | String | List | Slice | Index | Reference)
        and h._list is container
        and h._statement is statement
        and h._bound == value._bound
    )


def remove_value(value: WrittenValue) -> None:
    """``remove()`` of a value (2.4): with the space before it; in a list, with its comma."""
    doc = value._doc
    start, end = offsets(doc, ref_range(value._ref))
    tokens = doc._syntax.tokens
    if value._list is not None:
        _remove_item(doc, value, start, end)
        return
    first = ref_range(value._ref)[0]
    while first > 0 and tokens[first - 1].kind is TokenKind.SPACE:
        first -= 1
    _splice(doc, doc._starts[first], end, "", [])


def _remove_item(doc: Document, value: WrittenValue, start: int, end: int) -> None:
    """A list item's ``remove()``: the item and its comma only (the one after it, else the one before it); comments
    and line breaks between them stay, and a line left empty goes (D-F1-3)."""
    tokens = doc._syntax.tokens
    n = len(tokens)
    text = doc._text
    first, last = ref_range(value._ref)
    after = last
    while after < n and tokens[after].kind in _LIST_GAP:
        after += 1
    if after < n and tokens[after].kind is TokenKind.COMMA:
        comma_start, comma_end = doc._starts[after], doc._starts[after + 1]
        between = text[end:comma_start]
        if re.fullmatch(r"[ \t]*", between):
            frm, to = _removal_range(text, start, comma_end)
            _splice(doc, frm, to, "", [])
        else:
            _splice(doc, start, comma_end, between.lstrip(" \t"), [])
        return
    before = first - 1
    while before >= 0 and tokens[before].kind in _LIST_GAP:
        before -= 1
    if before >= 0 and tokens[before].kind is TokenKind.COMMA:
        between = text[doc._starts[before + 1] : start]
        kept = "" if re.fullmatch(r"[ \t]*", between) else between.rstrip(" \t")
        _splice(doc, doc._starts[before], end, kept, [])
        return
    _splice(doc, start, end, "", [])


def insert_statements(block: WrittenBlock, index: int, text: str) -> tuple[Statement, ...]:
    """``insert_statements`` (2.4): indented as the block's statements, line breaks as the document's."""
    items = block._items
    if not 0 <= index <= len(items):
        raise IndexError(f"insert_statements: index {index} is outside 0..{len(items)}")
    doc = block._doc
    given = _statements_text_problems(text)
    if text.strip() == "":
        if given:
            raise BadTextError(given)
        return ()
    eol = line_break(doc)
    owner = block._owner
    parent_indentation = "" if owner is None else indentation_at(doc, doc._starts[owner._node.start])
    if items:
        indentation = indentation_at(doc, offsets(doc, owned_range(doc, items[0]._node))[0])
    else:
        indentation = "" if owner is None else parent_indentation + _indentation_unit(doc)
    lines = [indentation, *_reindent(doc, text, indentation)]
    if index < len(items):
        target = offsets(doc, owned_range(doc, items[index]._node))[0]
        line_start = doc._text.rfind("\n", 0, target) + 1
        if re.fullmatch(r"[ \t\ufeff]*", doc._text[line_start:target]):
            # On lines of their own before the target's line (a BOM stays first).
            at = line_start + (1 if line_start == 0 and doc._text.startswith("\ufeff") else 0)
            pieces = [*lines, eol]
        else:
            # The target shares its line with an earlier statement: the new lines go between them (D-S2-3).
            at = target
            pieces = [*lines[1:], eol, indentation_at(doc, target)]
    elif items:
        at = offsets(doc, owned_range(doc, items[-1]._node))[1]
        pieces = [eol, *lines]
    elif owner is None:
        at = len(doc._text)
        pieces = [eol if doc._text != "" and not doc._text.endswith("\n") else "", *lines, eol]
    else:
        created = _insert_into_empty_block(doc, owner, text, lines, parent_indentation, eol, given)
        return _top_statements(created, owner)
    created = _splice(doc, at, at, _insert_of(text, pieces), given)
    return _top_statements(created, owner)


def _insert_into_empty_block(
    doc: Document,
    owner: Statement,
    given_text: str,
    lines: Sequence[Piece],
    parent_indentation: str,
    eol: str,
    given: Sequence[Diagnostic],
) -> list[Handle]:
    """An empty block: ``{}`` (or only whitespace and line breaks between) becomes ``{``, a line break, the lines, a
    line break, the parent's indentation, ``}`` (D14, D-F1-1); a block holding only comments takes the lines before
    its ``}`` line (D-S2-4)."""
    anatomy = anatomy_of(doc._syntax.tokens, owner._node)
    assert anatomy.block is not None
    brace_open = doc._starts[anatomy.block.start] + 1
    brace_close = doc._starts[anatomy.block.end - 1]
    text = doc._text
    if re.fullmatch(r"[ \t\r\n]*", text[brace_open:brace_close]):
        pieces = [eol, *lines, eol, parent_indentation]
        return _splice(doc, brace_open, brace_close, _insert_of(given_text, pieces), given)
    line_start = text.rfind("\n", 0, brace_close) + 1
    if re.fullmatch(r"[ \t]*", text[line_start:brace_close]):
        return _splice(doc, line_start, line_start, _insert_of(given_text, [*lines, eol]), given)
    pieces = [eol, *lines, eol, parent_indentation]
    return _splice(doc, brace_close, brace_close, _insert_of(given_text, pieces), given)


def rename_directive(statement: WrittenDirective, name: str) -> None:
    """``rename`` (D17, D-S1-10): a name the one directive-name check takes (``_names``: misuse otherwise), never one
    that would change its kind (an extension line has no ``rename``)."""
    doc = statement._doc
    _names.directive_name(name, doc._graph._extension_names, member="rename")
    start, end = offsets(doc, (statement._node.start, statement._node.start + 1))
    _splice(doc, start, end, name, [], statement)


def rename_variable(line: SetLine | SnippetLine, token: int, name: str) -> None:
    """``SetVariable.rename`` and ``Parameter.rename``: its ``$name`` only; the one variable-name check (misuse
    otherwise), then E5002 in its block (a bad text error: the document decides it)."""
    _names.variable_name(name, member="rename")
    doc = line._doc
    keep = next((p for p in line._parameters if p._token == token), None) if isinstance(line, SnippetLine) else None
    start, end = offsets(doc, (token, token + 1))
    _splice(doc, start, end, _insert_of(name, ["$", (0, len(name))]), [], keep)


# --- Declarations by where written (2.6) ---


def declaration_of(reference: Reference) -> SetVariable | Parameter | None:
    """The variable a reference binds to by where it is written; None when free. Nearest first, as the binding picks
    (2.5): block by block outward, the ``set`` lines above in that block, then the parameters of the snippet whose
    body it is (D-F1-8)."""
    name = reference.name
    s: Statement | None = reference._statement
    while s is not None:
        parent = s._parent
        block = parent._block if parent is not None and parent._block is not None else s._doc._block
        items = block._items
        i = next(j for j, item in enumerate(items) if item is s)
        for candidate in reversed(items[:i]):
            if isinstance(candidate, SetLine) and candidate._variable.name == name:
                return candidate._variable
        if isinstance(parent, SnippetLine):
            for parameter in parent._parameters:
                if parameter.name == name:
                    return parameter
        s = parent
    return None


def above(statement: Statement, match: Callable[[Statement], bool]) -> Statement | None:
    """The nearest statement above ``statement`` in its block or an enclosing block that matches."""
    s: Statement | None = statement
    while s is not None:
        parent = s._parent
        block = parent._block if parent is not None and parent._block is not None else s._doc._block
        items = block._items
        i = next(j for j, item in enumerate(items) if item is s)
        for candidate in reversed(items[:i]):
            if match(candidate):
                return candidate
        s = parent
    return None


def references(doc: Document) -> list[Reference]:
    """Every reference value of this document, in text order."""
    out: list[Reference] = []

    def value(v: WrittenValue) -> None:
        if isinstance(v, Reference):
            out.append(v)
        for inner in v._inner():
            value(inner)

    def statement(s: Statement) -> None:
        for v in s._value_list:
            value(v)
        if s._block is not None:
            for child in s._block._items:
                statement(child)

    for s in doc._block._items:
        statement(s)
    return out


def variables(doc: Document) -> list[Variable]:
    """Every ``set`` and snippet line's variables, in text order."""
    out: list[Variable] = []

    def statement(s: Statement) -> None:
        if isinstance(s, SetLine):
            out.append(s._variable)
        if isinstance(s, SnippetLine):
            out.extend(s._parameters)
        if s._block is not None:
            for child in s._block._items:
                statement(child)

    for s in doc._block._items:
        statement(s)
    return out


# --- The checks (2.3) ---


def position_in(text: str, index: int) -> SourcePosition:
    """The position of ``str`` index ``index`` in ``text`` (0-based line; offset and column in code points)."""
    at = max(0, min(index, len(text)))
    before = text[:at]
    return SourcePosition(at, before.count("\n"), at - before.rfind("\n") - 1)


def at(given: str, index: int, code: DiagnosticCode) -> Diagnostic:
    position = position_in(given, index)
    return Diagnostic(code, message_of(code), SourceSpan(position, position))


def entry_problems(text: str, rule: EntryRule) -> tuple[Diagnostic, ...]:
    """2.8's check of a text that depends only on the text: the grammar's entry rule ``rule`` (``valuesText`` for a
    ``set`` or a value's replace, ``itemsText`` for a list item's, ``boundText`` for a slice or index bound's), its
    first error placed in ``text``. The text-alone rules come after, in ``_splice``."""
    return parse_entry(text, rule).diagnostics


def _rule_problems(
    syntax: Syntax, starts: Sequence[int], extensions: frozenset[str], frm: int, insert: _Insert
) -> list[Diagnostic]:
    """The text-alone rules (E5002, E5005, E5009-E5011) a spliced text would break, on the statements the splice
    touches (D-S1-6; a ``set`` claiming the name of a snippet parameter the splice touches counts too): located in
    the caller's text when the problem lies in what it gave (2.3), else at 0:0 (D-S1-5)."""
    out: list[Diagnostic] = []
    tokens = syntax.tokens
    to = frm + len(insert.text)

    def overlaps(s: int, e: int) -> bool:
        return s < frm < e if frm == to else s < to and e > frm

    def touches(node: Node) -> bool:
        return overlaps(starts[node.start], starts[node.end])

    def visit(container: Node, claimed: Sequence[str], touched_claims: frozenset[str]) -> None:
        nodes = statement_nodes(container)
        shapes = block_shapes(tokens, nodes, extensions, claimed)
        for i, (node, shape) in enumerate(zip(nodes, shapes, strict=True)):
            fault = shape.fault
            if fault is not None:
                involved = touches(node)
                if not involved and fault.code in (
                    DiagnosticCode.VARIABLE_SET_TWICE,
                    DiagnosticCode.SNIPPET_DEFINED_TWICE,
                ):
                    name = fault.detail.removeprefix("$")
                    involved = (fault.code is DiagnosticCode.VARIABLE_SET_TWICE and name in touched_claims) or any(
                        touches(other) and shapes[j].claims == name for j, other in enumerate(nodes[:i])
                    )
                if involved:
                    offset = starts[fault.token]
                    origin = insert.origin[offset - frm] if frm <= offset < to else -1
                    out.append(at(insert.given, max(origin, 0), fault.code))
            if node.kind is not NodeKind.DIRECTIVE:
                continue
            block = anatomy_of(tokens, node).block
            if block is None or shape.kind == "unreadable":
                continue
            params = list(parameter_tokens(tokens, node)) if shape.kind == "snippet" else []
            names = [tokens[t].text[1:] for t in params]
            touched = frozenset(tokens[t].text[1:] for t in params if overlaps(starts[t], starts[t + 1]))
            visit(block, names, touched)

    visit(syntax.root, [], frozenset())
    return out


def override_text_problems(text: str) -> tuple[Diagnostic, ...]:
    """The text half of the check of an override (spec 6.3): the ``valuesText`` entry rule's first error, else E2001
    at the first ``$name`` (an override holds values only), or at 0:0 when the text holds no value."""
    syntax = parse_entry(text, "valuesText")
    if syntax.diagnostics:
        return syntax.diagnostics
    starts = starts_of(syntax)
    variable = next((i for i, t in enumerate(syntax.tokens) if t.kind is TokenKind.VARIABLE), None)
    if variable is not None:
        return (at(text, starts[variable], DiagnosticCode.UNEXPECTED_TOKEN),)
    if not values_of(syntax.tokens, syntax.root):
        return (at(text, 0, DiagnosticCode.UNEXPECTED_TOKEN),)
    return ()
