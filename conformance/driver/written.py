"""The written corpus (conformance/written/format.md): steps on one loaded graph. The driver finds every target in
the adapter's dumps and sends the edit to that handle's id; the adapter only applies it."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from adapter import Thrown
from common import CaseError, Session, Texts
from encode import to_bytes
from rendered import projection, walk
from units import line_column

# The corpus's op tokens (format.md "Tokens"): each is a spec member name and its parameters, in order.
OPS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "set": ("set", ("text",)),
    "replaceWithText": ("replace with text", ("text",)),
    "remove": ("remove", ()),
    "rename": ("rename", ("name",)),
    "insertStatements": ("insert statements", ("index", "text")),
    "addStatements": ("add statements", ("text",)),
    "insertBefore": ("insert before", ("text",)),
    "insertAfter": ("insert after", ("text",)),
    "setOverride": ("set override", ("name", "text")),
}
# The corpus's error tokens (format.md "Tokens") by error group spec name.
ERRORS = {
    "bad text error": "BadTextError",
    "detached error": "DetachedError",
    "misuse error": "MisuseError",
    "lost update error": "LostUpdateError",
    "argument type error": "TypeError",
}
SKIP = ("COMMENT", "SPACE", "NEWLINE")


def statements(block: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Every statement of a block, depth first in text order."""
    for s in block["statements"]:
        yield s
        if s.get("block") is not None:
            yield from statements(s["block"])


def values(statement: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """A statement's written values in text order, list items and a slice's or index's name and bounds included
    (milestone 5: a slice's name is a written value, a word or a reference)."""

    def each(v: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
        yield v
        for child in v.get("items", []):
            yield from each(child)
        for part in ("name", "start", "end", "index"):
            if isinstance(v.get(part), dict):
                yield from each(v[part])

    for v in statement.get("values", []):
        yield from each(v)


class Case:
    def __init__(self, session: Session, case: Mapping[str, Any]) -> None:
        self.s = session
        self.graph = session.load(case)
        self.previous: Optional[str] = None
        self.returned: Optional[str] = None
        self.rendered: Optional[str] = None  # the id of the most recent ["render"] step's render

    # --- targets ---------------------------------------------------------------------------------------------

    def _document(self, dump: Mapping[str, Any], path: str) -> Mapping[str, Any]:
        for d in dump["documents"]:
            if d["path"] == path:
                return d
        raise CaseError(f"no document {path}")

    def _starts(self, texts: Texts, place: Mapping[str, Any], path: str, line: int, col: int) -> bool:
        return place.get("path") == path and texts.line_column(path, place["start"]) == [line, col]

    def _statement(self, dump: Mapping[str, Any], texts: Texts, path: str, line: int, col: int) -> Mapping[str, Any]:
        doc = self._document(dump, path)
        conv = self.s.convert(doc["text"])
        tokens = doc["syntax"]["tokens"]
        for st in statements(doc["block"]):
            offset = st["place"]["start"][2]
            name = next((t for t in tokens if t[2][2] >= offset and t[0] not in SKIP), None)
            if name is not None and line_column(conv, name[2]) == [line, col]:
                return st
        raise CaseError(f"no statement at {path}:{line}:{col}")

    def target(self, target: Sequence[Any]) -> str:
        kind, *rest = target
        if kind == "previous":
            found = self.previous
        elif kind == "returned":
            found = self.returned
        elif kind == "graph":
            found = self.graph
        elif kind == "rendered":
            address, arg, step, which = rest
            render = self.s.render(self.graph)
            directive = next((d for d in walk(render["block"]) if d["address"]["people"] == address), None)
            if directive is None:
                raise CaseError(f"no rendered directive {address}")
            resolution = directive["values"][arg]["chain"][step]
            found = resolution["winner"]["id"] if which == "winner" else resolution["reference"]["id"]
        else:
            dump = self.s.graph(self.graph)
            texts = Texts(self.s, dump)
            found = self._find(dump, texts, kind, rest)
        if found is None:
            raise CaseError(f"no target {list(target)}")
        return str(found)

    def _find(self, dump: Mapping[str, Any], texts: Texts, kind: str, rest: List[Any]) -> Optional[str]:
        if kind == "document":
            return str(self._document(dump, rest[0])["id"])
        if kind == "statement":
            return str(self._statement(dump, texts, *rest)["id"])
        if kind == "block":
            if len(rest) == 1:
                return str(self._document(dump, rest[0])["block"]["id"])
            block = self._statement(dump, texts, *rest).get("block")
            return None if block is None else str(block["id"])
        if kind == "value":
            path, line, col = rest
            doc = self._document(dump, path)
            for st in statements(doc["block"]):
                for v in values(st):
                    if self._starts(texts, v["place"], path, line, col):
                        return str(v["id"])
            return None
        if kind == "variable":
            path, line, col = rest
            for v in dump["variables"]:
                if v["place"] is not None and self._starts(texts, v["place"], path, line, col):
                    return str(v["id"])
            return None
        if kind == "override":
            return next(
                (str(v["id"]) for v in dump["variables"] if v["kind"] == "override" and v["name"] == rest[0]), None
            )
        raise CaseError(f"unknown target kind {kind}")

    # --- steps -----------------------------------------------------------------------------------------------

    def edit(self, target: Sequence[Any], token: str, args: List[Any]) -> List[Any]:
        if token not in OPS:
            raise CaseError(f"unknown op {token}")
        member, params = OPS[token]
        handle = self.target(target)
        self.previous = handle
        try:
            result = self.s.request("edit", target=handle, member=member, args=args)
        except Thrown as thrown:
            error = thrown.error
            group = error.get("group", "")
            given = dict(zip(params, args))
            # A bad text error is located in the text the edit was given (spec 2.8): convert with that text.
            text = given.get("text", given.get("name")) or ""
            conv = self.s.convert(text)
            diagnostics = [[d["code"], *line_column(conv, d["start"])] for d in error.get("diagnostics", [])]
            return ["error", ERRORS.get(group, group), diagnostics]
        if "handles" in result:
            handles = result["handles"]
            self.returned = str(handles[0]["id"]) if handles else None
            return ["ok", [h["text"] for h in handles]]
        return ["ok"]

    def listing(self) -> Dict[str, Any]:
        dump = self.s.graph(self.graph)
        t = Texts(self.s, dump)
        return {
            "files": [
                [d["path"], [t.origin(c["place"], c["via"]) for c in d["includedBy"]]] for d in dump["documents"]
            ],
            "edges": [
                [t.origin(e["copy"]["place"], e["copy"]["via"]), e["specs"], e["targets"]] for e in dump["edges"]
            ],
            "variables": [
                [
                    v["name"],
                    v["kind"],
                    "override" if v["kind"] == "override" else t.place(v["place"]),
                    [t.resolution(r) for r in v["wins"]],
                    [[t.resolution(r), t.variable(r["winner"])] for r in v["shadowedAt"]],
                ]
                for v in dump["variables"]
            ],
            "diagnostics": [[d["code"], t.origin(d["place"], d["via"])] for d in dump["diagnostics"]],
        }

    def references(self) -> List[Any]:
        dump = self.s.graph(self.graph)
        t = Texts(self.s, dump)
        return [
            [
                t.place(v["place"]),
                t.variable(v["declaration"]),
                [
                    [t.resolution(r), t.variable(r["winner"]), [t.variable(o) for o in r["shadowed"]]]
                    for r in v["resolutions"]
                ],
            ]
            for doc in dump["documents"]
            for st in statements(doc["block"])
            for v in values(st)
            if v["kind"] == "reference"
        ]

    def step(self, step: Sequence[Any]) -> Any:
        kind, *args = step
        if kind == "list":
            return self.listing()
        if kind == "references":
            return self.references()
        if kind == "render" and args:
            # Milestone 5: render (x) of something that is not a document graph is an argument type error.
            try:
                self.s.request("render", graph=self.target(args[0]))
            except Thrown as thrown:
                group = thrown.error.get("group", "")
                return ["error", ERRORS.get(group, group)]
            return ["ok"]
        if kind == "render":
            texts = Texts(self.s, self.s.graph(self.graph))
            render = self.s.render(self.graph)
            self.rendered = str(render["id"])
            return projection(texts, render, links=True)
        if kind == "diff":
            if self.rendered is None:
                raise CaseError("a diff step before any render step")
            after = self.s.render(self.graph)
            changes = self.s.request("diff", before=self.rendered, after=after["id"])
            return [[c["kind"], c["address"]["people"]] for c in changes]
        if kind == "texts":
            dump = self.s.graph(self.graph)
            return [[d["path"], d["text"]] for d in dump["documents"] if d["text"] != d["savedText"]]
        if kind == "save":
            batches = self.s.request("save", graph=self.graph)["batches"]
            return [list(f) for f in batches[-1]] if batches else []
        if kind == "saveTo":
            try:
                saved = self.s.request("save", graph=self.graph, disk=args[0])
            except Thrown as thrown:
                group = thrown.error.get("group", "")
                return ["error", ERRORS.get(group, group), list(thrown.error.get("paths", []))]
            return ["ok", [list(f) for f in saved["files"]]]
        if kind == "edit":
            return self.edit(args[0], args[1], list(args[2:]))
        if kind == "quote":
            return self.s.request("quote", text=args[0])
        raise CaseError(f"unknown step {kind}")


def run(session: Session, case: Mapping[str, Any]) -> str:
    runner = Case(session, case)
    return to_bytes([runner.step(step) for step in case["steps"]])
