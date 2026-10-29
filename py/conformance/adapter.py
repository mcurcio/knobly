"""The Python binding's conformance adapter (spec/conformance.md): the shared driver runs every corpus through it.
From py/:

    python3 ../conformance/driver/run.py -- uv run --locked python conformance/adapter.py

It speaks the adapter protocol on standard input and output: one JSON request per line, one JSON response per line.
Every object it dumps gets an id; a later request names the object by that id. It finds no target and compares
nothing: the driver does both."""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import villanelle as vl
from villanelle import written
from villanelle.include import include

handles: list[object] = []


def ref(obj: object) -> str:
    handles.append(obj)
    return str(len(handles) - 1)


def get(id_: str) -> Any:
    return handles[int(id_)]


def pos(p: vl.SourcePosition) -> list[int]:
    return [p.line, p.column, p.offset]


def place(p: vl.Place | vl.Override) -> dict[str, Any]:
    if isinstance(p, vl.Override):
        return {"id": ref(p), "override": p.variable}
    return {"id": ref(p), "path": p.resolved_path, "start": pos(p.span.start), "end": pos(p.span.end)}


def steps(via: Sequence[vl.Step]) -> list[dict[str, Any]]:
    return [{"id": ref(s), "kind": str(s.kind), "name": s.name, "place": place(s.place)} for s in via]


def origin(o: Any) -> dict[str, Any]:
    return {"place": place(o.place), "via": steps(o.via)}


def diagnostic(d: vl.Diagnostic) -> dict[str, Any]:
    return {"id": ref(d), "code": str(d.code), "message": d.message, "start": pos(d.span.start), "end": pos(d.span.end)}


def located(d: vl.LocatedDiagnostic) -> dict[str, Any]:
    return {"id": ref(d), "code": str(d.code), "message": d.message, **origin(d)}


def syntax(s: vl.Syntax) -> dict[str, Any]:
    def node(n: vl.Node) -> list[Any]:
        return [str(n.kind), n.start, n.end, [node(c) for c in n.children]]

    return {
        "tokens": [[str(t.kind), t.text, pos(t.span.start), pos(t.span.end)] for t in s.tokens],
        "root": node(s.root),
        "diagnostics": [diagnostic(d) for d in s.diagnostics],
    }


def variable(v: vl.Variable | None) -> dict[str, Any] | None:
    if v is None:
        return None
    where = None if isinstance(v, vl.OverrideVariable) else place(v.place)
    return {"id": ref(v), "name": v.name, "kind": str(v.kind), "place": where}


def resolution(r: vl.ReferenceResolution) -> dict[str, Any]:
    return {
        "reference": {"id": ref(r.reference), "place": place(r.reference.place)},
        "via": steps(r.copy.via),
        "winner": variable(r.winner),
        "shadowed": [variable(v) for v in r.shadowed],
    }


def value(v: vl.WrittenValue) -> dict[str, Any]:
    out: dict[str, Any] = {"id": ref(v), "kind": str(v.kind), "place": place(v.place), "text": v.text}
    if isinstance(v, written.List):
        out["items"] = [value(i) for i in v.items]
    elif isinstance(v, written.Slice):
        out["start"] = None if v.start is None else value(v.start)
        out["end"] = None if v.end is None else value(v.end)
    elif isinstance(v, written.Index):
        out["index"] = value(v.index)
    elif isinstance(v, written.Reference):
        out["declaration"] = variable(v.declaration)
        out["resolutions"] = [resolution(r) for r in v.resolutions()]
    return out


def statement(s: vl.Statement) -> dict[str, Any]:
    out: dict[str, Any] = {"id": ref(s), "kind": str(s.kind), "place": place(s.place), "text": s.text}
    if isinstance(s, vl.WrittenDirective | vl.ExtensionLine | vl.SetLine | vl.UseLine):
        out["values"] = [value(v) for v in s.values]
    if isinstance(s, vl.WrittenDirective | vl.ExtensionLine | vl.SnippetLine):
        out["block"] = None if s.block is None else block(s.block)
    return out


def block(b: vl.WrittenBlock) -> dict[str, Any]:
    return {"id": ref(b), "statements": [statement(s) for s in b]}


def copy(c: vl.Copy) -> dict[str, Any]:
    return {"place": place(c.statement.place), "via": steps(c.via)}


def graph_dump(g: vl.DocumentGraph) -> dict[str, Any]:
    return {
        "id": ref(g),
        "documents": [
            {
                "id": ref(d),
                "path": d.resolved_path,
                "text": d.text,
                "savedText": d.saved_text,
                "syntax": syntax(d.syntax),
                "block": block(d.block),
                "includedBy": [copy(e.copy) for e in d.included_by()],
            }
            for d in g.documents.values()
        ],
        "edges": [{"copy": copy(e.copy), "specs": list(e.specs), "targets": list(e.targets)} for e in g.edges()],
        "variables": [
            {
                **(variable(v) or {}),
                "wins": [resolution(r) for r in v.wins()],
                "shadowedAt": [resolution(r) for r in v.shadowed_at()],
            }
            for v in g.variables()
        ],
        "diagnostics": [located(d) for d in g.diagnostics],
    }


def key_rule(rules: Sequence[Mapping[str, Any]] | None) -> vl.KeyRule | None:
    """A key rule from its data (spec/conformance.md section 3)."""
    if rules is None:
        return None

    def key(d: vl.Directive) -> str | None:
        for rule in rules:
            parent = rule.get("parent")
            if rule["directive"] == d.name and (parent is None or (d.parent is not None and d.parent.name == parent)):
                how, arg = rule["key"]
                if how == "value":
                    return d.values[arg].text if len(d.values) > arg else None
                return str(arg).join(a.text for a in d.values)
        return None

    return key


def address(a: vl.Address) -> dict[str, Any]:
    return {"text": a.text, "people": str(a)}


def rendered(r: vl.Rendered, rules: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    addresses = r.addresses(key=key_rule(rules))

    def unreadable(u: vl.UnreadableExpansion) -> dict[str, Any]:
        return {"reason": str(u.reason), "origin": origin(u.origin)}

    def expanded(a: vl.ExpandedValue) -> dict[str, Any]:
        return {
            "id": ref(a),
            "kind": str(a.kind),
            "text": a.text,
            "origin": origin(a.origin),
            "definition": None if a.definition is None else place(a.definition.place),
            "chain": [resolution(x) for x in a.chain],
        }

    def directive(d: vl.Directive) -> dict[str, Any]:
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


def result(x: Any) -> dict[str, Any]:
    """A reader's result, neutral (spec/conformance.md, ``read``)."""
    if isinstance(x, bool):
        return {"boolean": x}
    if isinstance(x, str):
        return {"text": x}
    if isinstance(x, int | float):
        return {"number": "-0" if x == 0 and str(x).startswith("-") else x}
    if isinstance(x, vl.SliceValue):
        return {"slice": [x.name, x.start, x.end]}
    if isinstance(x, vl.IndexValue):
        return {"index": [x.name, x.index]}
    if isinstance(x, vl.ExpandedWord | vl.ExpandedString | vl.ExpandedList | vl.ExpandedSlice | vl.ExpandedIndex):
        return {"value": x.text}
    if isinstance(x, tuple | list):
        return {"list": [result(i) for i in x]}
    raise TypeError(f"not a reader result: {x!r}")


def snake(spec_name: str) -> str:
    return spec_name.replace(" ", "_")


def edit(target: str, member: str, args: list[Any]) -> dict[str, Any]:
    out = getattr(get(target), snake(member))(*args)
    return {"handles": [{"id": ref(h), "text": h.text} for h in out]} if isinstance(out, tuple) else {}


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[list[str]]] = []

    def write(self, files: Sequence[vl.FileWrite], /) -> None:
        self.batches.append([[f.resolved_path, f.text] for f in files])


def save(graph: str, disk: dict[str, str] | None = None) -> dict[str, Any]:
    """Without ``disk``, what a recording writer got; with it, a memory writer over a new map holding ``disk`` (so a
    file whose text there differs from its saved text is a lost update), then the map after, sorted by path."""
    if disk is None:
        recorder = Recorder()
        get(graph).save(recorder)
        return {"batches": recorder.batches}
    files = dict(disk)
    get(graph).save(vl.memory_writer(files))
    return {"files": sorted([path, text] for path, text in files.items())}


def load(files: dict[str, str], root: str, extensions: list[str], overrides: dict[str, str] | None = None) -> Any:
    processor = vl.Processor(source=vl.memory_source(files), extensions=[include()] if "include" in extensions else [])
    return {"graph": ref(processor.load(root, overrides=overrides))}


OPS: dict[str, Callable[..., Any]] = {
    "hello": lambda protocol: {"protocol": 1, "binding": "python", "unit": "code point", "level": 3},
    "parse": lambda text: syntax(vl.parse(text)),
    "load": load,
    "graph": lambda graph: graph_dump(get(graph)),
    "render": lambda graph, key=None: rendered(vl.render(get(graph)), key),
    "diff": lambda before, after, key=None: [
        {"kind": str(c.kind), "address": address(c.address)} for c in get(before).diff(get(after), key=key_rule(key))
    ],
    "edit": edit,
    "save": save,
    "quote": lambda text: vl.quote(text),
    "read": lambda value, reader: result(getattr(get(value), reader)()),
    "print": lambda target: str(get(target)),
    "format": lambda diagnostic, graph=None: vl.format_diagnostic(
        get(diagnostic), None if graph is None else get(graph)
    ),
    "cut": lambda text, start, end: text[start:end],
}


# The program-bug groups that raise the language's own classes (spec 2.8), most specific first.
BUGS: tuple[tuple[type[Exception], str], ...] = (
    (TypeError, "argument type error"),
    (IndexError, "index out of range"),
    (ValueError, "misuse error"),
)


def group(error: Exception) -> dict[str, Any] | None:
    """The spec 2.8 group of an error, the most specific its class belongs to (a package class by its name, PascalCase
    back to words), with its code, diagnostics or paths; None for anything else (a fault)."""
    if isinstance(error, vl.VillanelleError | vl.DetachedError):
        name = re.sub(r"(?<!^)(?=[A-Z])", " ", type(error).__name__).lower()
    else:
        name = next((spec for cls, spec in BUGS if isinstance(error, cls)), "")
        if not name:
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
            thrown = group(error)
            fault = f"{type(error).__name__}: {error}"
            response = {"id": id_, "thrown": thrown} if thrown is not None else {"id": id_, "fault": fault}
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
