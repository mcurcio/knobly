"""The written-layer conformance runner (conformance/written/format.md): every case, byte for byte with its expected
output, none skipped (C1). Through the public API only."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from conftest import REPO, utf16_column
from test_load_conformance import _escape, origin, place

import villanelle as vl
from villanelle import written
from villanelle.include import include

WRITTEN = REPO / "conformance" / "written"
EXPECTED = WRITTEN / "expected"
FIXTURES = REPO / "fixtures"
CASES: list[dict[str, Any]] = json.loads((WRITTEN / "cases.json").read_text(encoding="utf-8"))

FEATURES = frozenset(
    {
        "include",
        "snippet",
        "values",
        "statements",
        "save",
        "quote",
        "directive-values",
        "blocks",
        "rename",
        "document",
        "override",
    }
)
"""Every ``needs`` token of format.md: this runner implements all of them."""

_OPS = {
    "set": "set",
    "replaceWithText": "replace_with_text",
    "remove": "remove",
    "rename": "rename",
    "insertStatements": "insert_statements",
    "addStatements": "add_statements",
    "setOverride": "set_override",
    "insertBefore": "insert_before",
    "insertAfter": "insert_after",
}


def fixture_files(directory: str) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((FIXTURES / directory).iterdir())
        if path.suffix == ".conf"
    }


def to_bytes(value: Any) -> str:
    return re.sub(r"[\u0080-\U0010ffff]", _escape, json.dumps(value, ensure_ascii=False, separators=(",", ":"))) + "\n"


def variable_text(variable: vl.Variable | None, graph: vl.DocumentGraph) -> str | None:
    match variable:
        case None:
            return None
        case vl.OverrideVariable(name):
            return f"override {name}"
        case vl.SetVariable() | vl.Parameter():
            return place(variable.place, graph)


def statements_of(block: vl.WrittenBlock) -> list[vl.Statement]:
    out: list[vl.Statement] = []
    for s in block:
        out.append(s)
        inner = s.block if isinstance(s, vl.WrittenDirective | vl.ExtensionLine | vl.SnippetLine) else None
        if inner is not None:
            out.extend(statements_of(inner))
    return out


def values_of(statement: vl.Statement) -> list[vl.WrittenValue]:
    out: list[vl.WrittenValue] = []

    def add(v: vl.WrittenValue) -> None:
        out.append(v)
        match v:
            case written.List():
                for item in v.items:
                    add(item)
            case written.Slice():
                for bound in (v.start, v.end):
                    if bound is not None:
                        add(bound)
            case written.Index():
                add(v.index)
            case _:
                pass

    if isinstance(statement, vl.WrittenDirective | vl.ExtensionLine | vl.SetLine | vl.UseLine):
        for v in statement.values:
            add(v)
    return out


def name_at(doc: vl.Document, statement: vl.Statement) -> tuple[int, int]:
    """Where the statement's name token starts: the first token of its place that is not a comment or space."""
    offset = statement.place.span.start.offset
    skip = (vl.TokenKind.COMMENT, vl.TokenKind.SPACE, vl.TokenKind.NEWLINE)
    token = next((t for t in doc.syntax.tokens if t.span.start.offset >= offset and t.kind not in skip), None)
    return (-1, -1) if token is None else (token.span.start.line, token.span.start.column)


def starts_at(place: vl.Place, line: int, col: int) -> bool:
    return place.span.start.line == line and place.span.start.column == col


class Runner:
    def __init__(self, graph: vl.DocumentGraph) -> None:
        self.graph = graph
        self.previous: object = None
        self.returned: object = None
        self.batches: list[list[vl.FileWrite]] = []

    def write(self, files: Any, /) -> None:
        self.batches.append(list(files))

    def doc(self, path: str) -> vl.Document:
        return self.graph.documents[path]

    def statement(self, path: str, line: int, col: int) -> vl.Statement:
        doc = self.doc(path)
        return next(s for s in statements_of(doc.block) if name_at(doc, s) == (line, col))

    def target(self, target: list[Any]) -> object:
        kind, *rest = target
        if kind == "document":
            return self.doc(rest[0])
        if kind == "statement":
            return self.statement(*rest)
        if kind == "block":
            if len(rest) == 1:
                return self.doc(rest[0]).block
            found = self.statement(*rest)
            assert isinstance(found, vl.WrittenDirective | vl.ExtensionLine | vl.SnippetLine)
            return found.block
        if kind == "value":
            doc = self.doc(rest[0])
            values = (v for s in statements_of(doc.block) for v in values_of(s))
            return next(v for v in values if starts_at(v.place, rest[1], rest[2]))
        if kind == "variable":
            return next(
                v
                for v in self.graph.variables()
                if isinstance(v, vl.SetVariable | vl.Parameter)
                and v.place.resolved_path == rest[0]
                and starts_at(v.place, rest[1], rest[2])
            )
        if kind == "override":
            return next(v for v in self.graph.variables() if v.kind == "override" and v.name == rest[0])
        if kind == "graph":
            return self.graph
        if kind == "previous":
            return self.previous
        if kind == "returned":
            return self.returned
        if kind == "rendered":
            address, arg, step, which = rest
            rendered = vl.render(self.graph)
            addresses = rendered.addresses()
            directive = next(d for d in rendered.walk() if str(addresses[d]) == address)
            resolution = directive.values[arg].chain[step]
            return resolution.winner if which == "winner" else resolution.reference
        raise AssertionError(f"unknown target {kind}")

    def edit(self, target: list[Any], op: str, args: list[Any]) -> Any:
        handle = self.target(target)
        self.previous = handle
        try:
            result = getattr(handle, _OPS[op])(*args)
        except (vl.EditError, vl.DetachedError) as error:
            # A bad text error is located in the text the edit was given: its columns are converted with that text.
            given = next((a for a in reversed(args) if isinstance(a, str)), "")
            diagnostics = (
                [
                    [d.code, d.span.start.line, utf16_column(given, d.span.start.offset, d.span.start.column)]
                    for d in error.diagnostics
                ]
                if isinstance(error, vl.BadTextError)
                else []
            )
            return ["error", type(error).__name__, diagnostics]
        if isinstance(result, tuple):
            self.returned = result[0] if result else None
            return ["ok", [h.text for h in result]]
        return ["ok"]

    def listing(self) -> Any:
        g = self.graph
        return {
            "files": [
                [d.resolved_path, [origin(e.copy.statement.place, e.copy.via, g) for e in d.included_by()]]
                for d in g.documents.values()
            ],
            "edges": [
                [origin(e.copy.statement.place, e.copy.via, g), list(e.specs), list(e.targets)] for e in g.edges()
            ],
            "variables": [
                [
                    v.name,
                    v.kind,
                    "override" if isinstance(v, vl.OverrideVariable) else place(v.place, g),
                    [origin(r.reference.place, r.copy.via, g) for r in v.wins()],
                    [[origin(r.reference.place, r.copy.via, g), variable_text(r.winner, g)] for r in v.shadowed_at()],
                ]
                for v in g.variables()
            ],
            "diagnostics": [[str(d.code), origin(d.place, d.via, g)] for d in g.diagnostics],
        }

    def references(self) -> Any:
        g = self.graph
        return [
            [
                place(r.place, g),
                variable_text(r.declaration, g),
                [
                    [
                        origin(r.place, x.copy.via, g),
                        variable_text(x.winner, g),
                        [variable_text(o, g) for o in x.shadowed],
                    ]
                    for x in r.resolutions()
                ],
            ]
            for doc in self.graph.documents.values()
            for s in statements_of(doc.block)
            for r in values_of(s)
            if isinstance(r, written.Reference)
        ]

    def render(self) -> Any:
        g = self.graph
        rendered = vl.render(g)
        addresses = rendered.addresses()
        directives: list[Any] = []
        unreadable: list[Any] = [
            ["", u.reason.value, origin(u.origin.place, u.origin.via, g)] for u in rendered.unreadable
        ]
        for d in rendered.walk():
            address = str(addresses[d])
            args = [
                [
                    a.text,
                    origin(a.origin.place, a.origin.via, g),
                    None if a.definition is None else place(a.definition.place, g),
                    [[origin(r.reference.place, r.copy.via, g), variable_text(r.winner, g)] for r in a.chain],
                ]
                for a in d.values
            ]
            directives.append([address, d.block is not None, origin(d.origin.place, d.origin.via, g), args])
            unreadable.extend([address, u.reason.value, origin(u.origin.place, u.origin.via, g)] for u in d.unreadable)
        diagnostics = [[str(d.code), origin(d.place, d.via, g)] for d in rendered.diagnostics]
        return {"directives": directives, "unreadable": unreadable, "diagnostics": diagnostics}

    def step(self, step: list[Any]) -> Any:
        kind, *args = step
        if kind == "list":
            return self.listing()
        if kind == "references":
            return self.references()
        if kind == "render":
            return self.render()
        if kind == "texts":
            return [[d.resolved_path, d.text] for d in self.graph.documents.values() if d.text != d.saved_text]
        if kind == "save":
            before = len(self.batches)
            self.graph.save(self)
            return [[f.resolved_path, f.text] for f in self.batches[-1]] if len(self.batches) > before else []
        if kind == "edit":
            return self.edit(args[0], args[1], args[2:])
        if kind == "quote":
            return vl.quote(args[0])
        raise AssertionError(f"unknown step {kind}")


def test_every_case_has_an_expected_file_and_every_need_is_implemented() -> None:
    expected = sorted(p.stem for p in EXPECTED.glob("*.json"))
    assert expected == sorted(c["name"] for c in CASES)
    assert {need for c in CASES for need in c["needs"]} <= FEATURES


@pytest.mark.parametrize("case", [pytest.param(c, id=c["name"]) for c in CASES])
def test_written_case_matches_expected_bytes(case: dict[str, Any]) -> None:
    if not set(case["needs"]) <= FEATURES:
        pytest.skip(f"needs {sorted(set(case['needs']) - FEATURES)}")
    files = fixture_files(case["fixture"]) if "fixture" in case else case.get("files", {})
    extensions = [include()] if "include" in case.get("extensions", ()) else []
    processor = vl.Processor(source=vl.memory_source(files), extensions=extensions)
    graph = processor.load(case["root"], overrides=case.get("overrides"))
    runner = Runner(graph)
    out = [runner.step(step) for step in case["steps"]]
    assert to_bytes(out) == (EXPECTED / f"{case['name']}.json").read_text(encoding="utf-8")
