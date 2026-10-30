"""The Python binding's conformance adapter (spec/conformance.md): the shared driver runs every corpus through it.
From py/:

    python3 ../conformance/driver/run.py -- uv run --locked python conformance/adapter.py

It speaks the adapter protocol on standard input and output: one JSON request per line, one JSON response per line.
Every object it dumps gets an id; a later request names the object by that id. It finds no target and compares
nothing: the driver does both. Its dumps are typed by the generated message shapes (``shapes.py``, from
spec/schema/protocol.json), members are spelled through the generated ``SPELLING`` and error groups named through the
generated ``ERROR_GROUP_OF_CLASS``. Parameters are typed with the binding's public classes, the types the generated
records' fields carry."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from typing import Any

from shapes import (
    ERROR_GROUP_OF_CLASS,
    PROTOCOL,
    SPELLING,
    AddressDump,
    BlockDump,
    ChangeDump,
    CopyDump,
    DirectiveDump,
    EditedDump,
    ExpandedValueDump,
    GraphDump,
    HelloResultDump,
    KeyRuleDump,
    LoadedDump,
    LocatedDiagnosticDump,
    OriginDump,
    OverrideDump,
    PlaceDump,
    Position,
    ReaderResultDump,
    RenderDump,
    ResolutionDump,
    SavedDump,
    StatementDump,
    StepDump,
    SyntaxDiagnosticDump,
    SyntaxDump,
    UnreadableDump,
    VariableReferenceDump,
    WrittenValueDump,
)

import villanelle as vl
from villanelle import rendered, syntax, written
from villanelle.include import include

handles: list[object] = []


def ref(obj: object) -> str:
    handles.append(obj)
    return str(len(handles) - 1)


def get(id_: str) -> Any:
    return handles[int(id_)]


def pos(p: vl.SourcePosition) -> Position:
    return (p.line, p.column, p.offset)


def file_place(p: vl.Place) -> PlaceDump:
    return {"id": ref(p), "path": p.resolved_path, "start": pos(p.span.start), "end": pos(p.span.end)}


def place(p: vl.Place | vl.Override) -> PlaceDump | OverrideDump:
    if p.kind is vl.PlaceKind.OVERRIDE:
        return {"id": ref(p), "override": p.variable}
    return file_place(p)


def steps(via: Sequence[vl.Step]) -> list[StepDump]:
    return [{"id": ref(s), "kind": str(s.kind), "name": s.name, "place": file_place(s.place)} for s in via]


def origin(o: vl.Origin | vl.DirectiveOrigin) -> OriginDump:
    return {"place": place(o.place), "via": steps(o.via)}


def diagnostic(d: vl.Diagnostic) -> SyntaxDiagnosticDump:
    return {"id": ref(d), "code": str(d.code), "message": d.message, "start": pos(d.span.start), "end": pos(d.span.end)}


def located(d: vl.LocatedDiagnostic) -> LocatedDiagnosticDump:
    return {"id": ref(d), "code": str(d.code), "message": d.message, "place": file_place(d.place), "via": steps(d.via)}


def syntax_dump(s: syntax.Syntax) -> SyntaxDump:
    def node(n: syntax.Node) -> Any:
        return (str(n.kind), n.start, n.end, [node(c) for c in n.children])

    return {
        "tokens": [(str(t.kind), t.text, pos(t.span.start), pos(t.span.end)) for t in s.tokens],
        "root": node(s.root),
        "diagnostics": [diagnostic(d) for d in s.diagnostics],
    }


def variable(v: written.Variable) -> VariableReferenceDump:
    where = None if v.kind is written.VariableKind.OVERRIDE else file_place(v.place)
    return {"id": ref(v), "name": v.name, "kind": str(v.kind), "place": where}


def resolution(r: written.ReferenceResolution) -> ResolutionDump:
    return {
        "reference": {"id": ref(r.reference), "place": file_place(r.reference.place)},
        "via": steps(r.copy.via),
        "winner": None if r.winner is None else variable(r.winner),
        "shadowed": [variable(v) for v in r.shadowed],
    }


def value(v: written.WrittenValue) -> WrittenValueDump:
    """The dump of one value: a discriminated union on the wire's kind, so each kind's own fields are checked."""
    i, at, text = ref(v), file_place(v.place), v.text
    match v:
        case written.List():
            return {"id": i, "kind": "list", "place": at, "text": text, "items": [value(x) for x in v.items]}
        case written.Slice():
            start = None if v.start is None else value(v.start)
            end = None if v.end is None else value(v.end)
            return {
                "id": i,
                "kind": "slice",
                "place": at,
                "text": text,
                "name": value(v.name),
                "start": start,
                "end": end,
            }
        case written.Index():
            return {"id": i, "kind": "index", "place": at, "text": text, "name": value(v.name), "index": value(v.index)}
        case written.Reference():
            declaration = None if v.declaration is None else variable(v.declaration)
            resolutions = [resolution(r) for r in v.resolutions()]
            return {
                "id": i,
                "kind": "reference",
                "place": at,
                "text": text,
                "declaration": declaration,
                "resolutions": resolutions,
            }
        case written.Word():
            return {"id": i, "kind": "word", "place": at, "text": text}
        case _:
            return {"id": i, "kind": "string", "place": at, "text": text}


def statement(s: written.Statement) -> StatementDump:
    """The dump of one statement, one alternative per kind (as value above)."""
    i, at, text = ref(s), file_place(s.place), s.text

    def inner(b: written.WrittenBlock | None) -> BlockDump | None:
        return None if b is None else block(b)

    match s:
        case written.WrittenDirective():
            return {
                "id": i,
                "kind": "directive",
                "place": at,
                "text": text,
                "values": [value(v) for v in s.values],
                "block": inner(s.block),
            }
        case written.ExtensionLine():
            return {
                "id": i,
                "kind": "extension",
                "place": at,
                "text": text,
                "values": [value(v) for v in s.values],
                "block": inner(s.block),
            }
        case written.SetLine():
            return {"id": i, "kind": "set", "place": at, "text": text, "values": [value(v) for v in s.values]}
        case written.UseLine():
            return {"id": i, "kind": "use", "place": at, "text": text, "values": [value(v) for v in s.values]}
        case written.SnippetLine():
            return {"id": i, "kind": "snippet", "place": at, "text": text, "block": inner(s.block)}
        case _:
            return {"id": i, "kind": "unreadable", "place": at, "text": text}


def block(b: written.WrittenBlock) -> BlockDump:
    return {"id": ref(b), "statements": [statement(s) for s in b]}


def copy(c: written.Copy) -> CopyDump:
    return {"place": file_place(c.statement.place), "via": steps(c.via)}


def graph_dump(g: written.DocumentGraph) -> GraphDump:
    return {
        "id": ref(g),
        "documents": [
            {
                "id": ref(d),
                "path": d.resolved_path,
                "text": d.text,
                "savedText": d.saved_text,
                "syntax": syntax_dump(d.syntax),
                "block": block(d.block),
                "includedBy": [copy(e.copy) for e in d.included_by()],
            }
            for d in g.documents.values()
        ],
        "edges": [{"copy": copy(e.copy), "specs": list(e.specs), "targets": list(e.targets)} for e in g.edges()],
        "variables": [
            {
                **variable(v),
                "wins": [resolution(r) for r in v.wins()],
                "shadowedAt": [resolution(r) for r in v.shadowed_at()],
            }
            for v in g.variables()
        ],
        "diagnostics": [located(d) for d in g.diagnostics],
    }


def key_rule(rules: Sequence[KeyRuleDump] | None) -> rendered.KeyRule | None:
    """A key rule from its data (spec/conformance.md section 3)."""
    if rules is None:
        return None

    def key(d: rendered.Directive) -> str | None:
        for rule in rules:
            parent = rule.get("parent")
            if rule["directive"] == d.name and (parent is None or (d.parent is not None and d.parent.name == parent)):
                how, arg = rule["key"]
                if how == "value":
                    return d.values[int(arg)].text if len(d.values) > int(arg) else None
                return str(arg).join(a.text for a in d.values)
        return None

    return key


def address(a: rendered.Address) -> AddressDump:
    return {"text": a.text, "people": str(a)}


def render_dump(r: rendered.Rendered, rules: Sequence[KeyRuleDump] | None) -> RenderDump:
    addresses = r.addresses(key=key_rule(rules))

    def unreadable(u: written.UnreadableExpansion) -> UnreadableDump:
        return {"reason": str(u.reason), "origin": origin(u.origin)}

    def expanded(a: written.ExpandedValue) -> ExpandedValueDump:
        return {
            "id": ref(a),
            "kind": str(a.kind),
            "text": a.text,
            "origin": origin(a.origin),
            "definition": None if a.definition is None else file_place(a.definition.place),
            "chain": [resolution(x) for x in a.chain],
        }

    def directive(d: rendered.Directive) -> DirectiveDump:
        return {
            "id": ref(d),
            "name": d.name,
            "address": address(addresses[d]),
            "origin": origin(d.origin),
            "values": [expanded(a) for a in d.values],
            "block": None if d.block is None else [directive(x) for x in d.block],
            "unreadable": [unreadable(u) for u in d.unreadable],
        }

    return {
        "id": ref(r),
        "block": [directive(d) for d in r.block],
        "unreadable": [unreadable(u) for u in r.unreadable],
        "diagnostics": [located(d) for d in r.diagnostics],
    }


def result(x: Any) -> ReaderResultDump:
    """A reader's result, neutral (spec/conformance.md, ``read``)."""
    if isinstance(x, bool):
        return {"boolean": x}
    if isinstance(x, str):
        return {"text": x}
    if isinstance(x, int | float):
        return {"number": "-0" if x == 0 and str(x).startswith("-") else x}
    if isinstance(x, written.SliceValue):
        return {"slice": (x.name, x.start, x.end)}
    if isinstance(x, written.IndexValue):
        return {"index": (x.name, x.index)}
    if isinstance(x, tuple):  # the list reader's items
        return {"list": [{"value": item.text} for item in x]}
    raise TypeError(f"not a reader result: {x!r}")


# Where each edit takes config text (the driver's OPS parameters): the adapter wraps the text the driver sends with
# text(), as a program does with a text already written as villanelle text (spec 6.9). Names stay plain text.
TEXT_AT = {
    "set": 0,
    "replace with text": 0,
    "insert statements": 1,
    "add statements": 0,
    "insert before": 0,
    "insert after": 0,
    "set override": 1,
}


def config_text(given: Any) -> Any:
    """``text(given)`` for a str; anything else as given (a case may pass a non-str to see the argument type error)."""
    return vl.text(given) if isinstance(given, str) else given


def edit(target: str, member: str, args: list[Any]) -> EditedDump:
    at = TEXT_AT.get(member)
    if at is not None and at < len(args):
        args = [config_text(a) if i == at else a for i, a in enumerate(args)]
    out = getattr(get(target), SPELLING[member])(*args)
    return {"handles": [{"id": ref(h), "text": h.text} for h in out]} if isinstance(out, tuple) else {}


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[tuple[str, str]]] = []

    def write(self, files: Sequence[vl.FileWrite], /) -> None:
        self.batches.append([(f.resolved_path, f.text) for f in files])


def save(graph: str, disk: dict[str, str] | None = None) -> SavedDump:
    """Without ``disk``, what a recording writer got; with it, a memory writer over a new map holding ``disk`` (so a
    file whose text there differs from its saved text is a lost update), then the map after, sorted by path."""
    if disk is None:
        recorder = Recorder()
        get(graph).save(recorder)
        return {"batches": recorder.batches}
    files = dict(disk)
    get(graph).save(vl.memory_writer(files))
    return {"files": sorted(files.items())}


def load(
    files: dict[str, str], root: str, extensions: list[str], overrides: dict[str, Any] | None = None
) -> LoadedDump:
    source = vl.memory_source(files)
    processor = written.Processor(source=source, extensions=[include()] if "include" in extensions else [])
    given = None if overrides is None else {name: config_text(text) for name, text in overrides.items()}
    return {"graph": ref(processor.load(root, overrides=given))}


def hello(protocol: int) -> HelloResultDump:
    return {"protocol": PROTOCOL, "binding": "python", "unit": "code point", "level": 3}


def diff(before: str, after: str, key: Sequence[KeyRuleDump] | None = None) -> list[ChangeDump]:
    changes = get(before).diff(get(after), key=key_rule(key))
    return [{"kind": str(c.kind), "address": address(c.address)} for c in changes]


OPS: dict[str, Callable[..., Any]] = {
    "hello": hello,
    "parse": lambda text: syntax_dump(syntax.parse(text)),
    "load": load,
    "graph": lambda graph: graph_dump(get(graph)),
    "render": lambda graph, key=None: render_dump(rendered.render(get(graph)), key),
    "diff": diff,
    "edit": edit,
    "save": save,
    "quote": lambda text: vl.quote(text),
    "read": lambda value, reader: result(getattr(get(value), SPELLING[reader])()),
    "print": lambda target: str(get(target)),
    "format": lambda diagnostic, graph=None: written.format_diagnostic(
        get(diagnostic), None if graph is None else get(graph)
    ),
    "cut": lambda text, start, end: text[start:end],
}


def group_of(error: Exception) -> str | None:
    """The spec 2.8 group of an error: the first class of its ``__mro__`` that ``ERROR_GROUP_OF_CLASS`` names, so the
    most specific (a ``LostUpdateError`` before its ``SaveError``; the language's own ``TypeError``, ``ValueError``
    and ``IndexError`` for the program-bug groups)."""
    names = (cls.__name__ for cls in type(error).__mro__)
    return next((ERROR_GROUP_OF_CLASS[name] for name in names if name in ERROR_GROUP_OF_CLASS), None)


def thrown(error: Exception) -> dict[str, Any] | None:
    """The thrown response's body: the group, with its code, diagnostics or paths; None for anything else (a fault)."""
    name = group_of(error)
    if name is None:
        return None
    out: dict[str, Any] = {"group": name}
    if isinstance(error, vl.DiagnosticError):
        out["code"] = str(error.diagnostic.code)
    if isinstance(error, vl.BadTextError):
        out["diagnostics"] = [diagnostic(d) for d in error.diagnostics]
    if isinstance(error, vl.ReadError | vl.SaveError):
        out["paths"] = list(error.paths)
    return out


def main() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        id_, op = request.pop("id"), request.pop("op")
        try:
            response = {"id": id_, "ok": OPS[op](**request)}
        except Exception as error:
            body = thrown(error)
            fault = f"{type(error).__name__}: {error}"
            response = {"id": id_, "thrown": body} if body is not None else {"id": id_, "fault": fault}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
