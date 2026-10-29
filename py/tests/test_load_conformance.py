"""The load conformance runner (conformance/load/format.md): every case, byte for byte with the expected output,
through the public API only: ``render(load(...))``, the key rule passed to ``addresses()`` and ``diff`` (C2)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO

import villanelle as vl
from villanelle.include import include

LOAD = REPO / "conformance" / "load"
EXPECTED = LOAD / "expected"
CASES: list[dict[str, Any]] = json.loads((LOAD / "cases.json").read_text(encoding="utf-8"))


def rasl_key(d: vl.Directive) -> str | None:
    """The "rasl" key rule of format.md."""
    if d.name == "node" and d.parent is not None and d.parent.name == "graph":
        return d.values[1].text if len(d.values) > 1 else None
    if d.name == "connect":
        return " ".join(a.text for a in d.values)
    if d.name == "fill":
        return d.values[0].text if d.values else None
    return None


def place(where: vl.Place) -> str:
    return f"{where.resolved_path}:{where.span.start.line}:{where.span.start.column}"


def origin(where: vl.Place | vl.Override, via: Sequence[vl.Step]) -> str:
    head = f"override {where.variable}" if isinstance(where, vl.Override) else place(where)
    return head + "".join(f" < {step.kind} {step.name} {place(step.place)}" for step in via)


def fmt(rendered: vl.Rendered, key: vl.KeyRule | None, changes: list[list[str]] | None) -> bytes:
    directives: list[Any] = []
    unreadable: list[Any] = [["", u.reason.value, origin(u.origin.place, u.origin.via)] for u in rendered.unreadable]
    addresses = rendered.addresses(key=key)
    for d in rendered.walk():
        address = str(addresses[d])
        args = [[a.text, origin(a.origin.place, a.origin.via)] for a in d.values]
        directives.append([address, d.block is not None, origin(d.origin.place, d.origin.via), args])
        unreadable.extend([address, u.reason.value, origin(u.origin.place, u.origin.via)] for u in d.unreadable)
    value: dict[str, Any] = {
        "files": list(rendered.graph.documents),
        "directives": directives,
        "unreadable": unreadable,
        "diagnostics": [[str(d.code), origin(d.place, d.via)] for d in rendered.diagnostics],
    }
    if changes is not None:
        value["changes"] = changes
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (re.sub(r"[\u0080-\U0010ffff]", _escape, text) + "\n").encode("ascii")


def _escape(match: re.Match[str]) -> str:
    units = match.group().encode("utf-16-le", "surrogatepass")
    return "".join(f"\\u{int.from_bytes(units[i : i + 2], 'little'):04x}" for i in range(0, len(units), 2))


class _Files:
    """One processor's source for both loads: it serves whatever ``files`` holds at each call."""

    def __init__(self, files: Mapping[str, str]) -> None:
        self.files = files

    def resolve(self, spec: str, context: vl.LoadContext, /) -> Sequence[str]:
        return vl.memory_source(self.files).resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        return vl.memory_source(self.files).read(resolved_path)


@pytest.mark.parametrize("case", [pytest.param(c, id=c["name"]) for c in CASES])
def test_load_case_matches_expected_bytes(case: dict[str, Any]) -> None:
    source = _Files(case["files"])
    processor = vl.Processor(source=source, extensions=[include()] if "include" in case.get("extensions", ()) else ())
    key = rasl_key if case.get("key") == "rasl" else None
    overrides = case.get("overrides")
    first = vl.render(processor.load(case["root"], overrides=overrides))
    changes = None
    if "after" in case:
        source.files = {**case["files"], **case["after"]}
        second = vl.render(processor.load(case["root"], overrides=overrides))
        changes = [[change_kind(c), str(c.address)] for c in first.diff(second, key=key)]
    assert fmt(first, key, changes).decode() == (EXPECTED / f"{case['name']}.json").read_text(encoding="utf-8")


def change_kind(change: vl.Change) -> str:
    match change:
        case vl.Added():
            return "added"
        case vl.Removed():
            return "removed"
        case vl.Changed():
            return "changed"
        case vl.Unknown():
            return "unknown"
