"""What every corpus shares: the session one case runs in, and the texts the expected files print for places,
origins and variables (conformance/load/format.md "origin", conformance/written/format.md "copy text")."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from adapter import Adapter
from units import Converters, line_column

REPO = Path(__file__).resolve().parents[2]
CONFORMANCE = REPO / "conformance"
KEYS: Dict[str, List[Dict[str, Any]]] = json.loads((CONFORMANCE / "keys.json").read_text(encoding="utf-8"))["rules"]


class CaseError(Exception):
    """The case cannot go on: a target is missing, or a dump is not what the protocol says."""


def diagnostic_entry(d: Mapping[str, Any], *where: Any) -> List[Any]:
    """One diagnostic as every expected file prints it (conformance/format.md, "Severity"): its code, then where it
    is, then its severity only when that is not ``error``, so an error's entry reads as it did before warnings."""
    if "severity" not in d:
        raise CaseError(f"diagnostic {d.get('code')!r} has no severity (spec/conformance.md 4.2)")
    entry = [d["code"], *where]
    if d["severity"] != "error":
        entry.append(d["severity"])
    return entry


class Session:
    """One case's view of the adapter: requests, the binding's unit, and the key rules as data."""

    def __init__(self, adapter: Adapter) -> None:
        self.adapter = adapter
        self.unit: str = adapter.hello["unit"]
        self.convert = Converters(self.unit)

    def request(self, op: str, **params: Any) -> Any:
        return self.adapter.request(op, **params)

    def load(self, case: Mapping[str, Any], files: Optional[Mapping[str, str]] = None) -> str:
        """``load`` the case's files (or ``files``) and return the graph's id."""
        params: Dict[str, Any] = {
            "files": dict(case_files(case) if files is None else files),
            "root": case["root"],
            "extensions": list(case.get("extensions", [])),
        }
        for optional in ("overrides", "failReads"):
            if optional in case:
                params[optional] = case[optional]
        return str(self.request("load", **params)["graph"])

    def graph(self, graph: str) -> Dict[str, Any]:
        return dict(self.request("graph", graph=graph))

    def render(self, graph: str, key: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"graph": graph}
        if key is not None:
            params["key"] = key_rules(key)
        return dict(self.request("render", **params))


def key_rules(name: str) -> List[Dict[str, Any]]:
    """A key rule by name, as data (conformance/keys.json): the driver sends the rules, never a name."""
    if name not in KEYS:
        raise CaseError(f"no key rule {name!r} in conformance/keys.json")
    return KEYS[name]


def case_files(case: Mapping[str, Any]) -> Dict[str, str]:
    """A case's files: ``files``, or a ``fixture`` directory's ``*.conf`` files by path relative to it."""
    if "fixture" in case:
        directory = REPO / "fixtures" / case["fixture"]
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(directory.iterdir()) if p.suffix == ".conf"}
    return dict(case.get("files", {}))


class Texts:
    """Each document's current text by path, the text a place's position counts in."""

    def __init__(self, session: Session, graph_dump: Mapping[str, Any]) -> None:
        self.session = session
        self.by_path: Dict[str, str] = {d["path"]: d["text"] for d in graph_dump["documents"]}

    def line_column(self, path: str, pos: Sequence[int]) -> List[int]:
        if path not in self.by_path:
            raise CaseError(f"a place in {path!r}, which is not a document of the graph")
        return line_column(self.session.convert(self.by_path[path]), pos)

    def place(self, place: Mapping[str, Any]) -> str:
        """``path:line:col``: 0-based, the span's start, the column in UTF-16 units."""
        line, column = self.line_column(place["path"], place["start"])
        return f"{place['path']}:{line}:{column}"

    def head(self, place: Mapping[str, Any]) -> str:
        """An origin's place: a place, or ``override <name>``."""
        return f"override {place['override']}" if "override" in place else self.place(place)

    def origin(self, place: Mapping[str, Any], via: Sequence[Mapping[str, Any]]) -> str:
        """The origin text: its place, then `` < <kind> <name> <place>`` per step, innermost first."""
        return self.head(place) + "".join(f" < {s['kind']} {s['name']} {self.place(s['place'])}" for s in via)

    def variable(self, variable: Optional[Mapping[str, Any]]) -> Optional[str]:
        """A variable text: its place, ``override <name>``, or null."""
        if variable is None:
            return None
        if variable["kind"] == "override":
            return f"override {variable['name']}"
        return self.place(variable["place"])

    def resolution(self, r: Mapping[str, Any]) -> str:
        """A resolution's copy text: the reference's place with the copy's ``via``."""
        return self.origin(r["reference"]["place"], r["via"])
