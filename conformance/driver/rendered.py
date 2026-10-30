"""The load corpus (conformance/load/format.md) and the rendered corpus (conformance/rendered/format.md): load,
render, diff; and the render projection the written corpus's ``["render"]`` step prints too."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from common import Session, Texts, key_rules
from encode import to_bytes


def walk(block: List[Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    """Every directive, depth-first in written order (spec 7.5), from the render dump's tree."""
    for directive in block:
        yield directive
        if directive["block"] is not None:
            yield from walk(directive["block"])


def projection(texts: Texts, render: Mapping[str, Any], links: bool) -> Dict[str, Any]:
    """``directives``, ``unreadable`` and ``diagnostics`` of a render; with ``links``, each argument also has its
    ``definition`` and ``chain`` (conformance/written/format.md ``["render"]``)."""
    directives: List[Any] = []
    unreadable: List[Any] = [["", u["reason"], texts.origin(**u["origin"])] for u in render["unreadable"]]
    for d in walk(render["block"]):
        address = d["address"]["people"]
        values: List[Any] = []
        for a in d["values"]:
            value: List[Any] = [a["text"], texts.origin(**a["origin"])]
            if links:
                value.append(None if a["definition"] is None else texts.place(a["definition"]))
                value.append([[texts.resolution(r), texts.variable(r["winner"])] for r in a["chain"]])
            values.append(value)
        directives.append([address, d["block"] is not None, texts.origin(**d["origin"]), values])
        unreadable.extend([address, u["reason"], texts.origin(**u["origin"])] for u in d["unreadable"])
    diagnostics = [[x["code"], texts.origin(x["place"], x["via"])] for x in render["diagnostics"]]
    return {"directives": directives, "unreadable": unreadable, "diagnostics": diagnostics}


def _renders(
    session: Session, case: Mapping[str, Any]
) -> Tuple[Texts, Dict[str, Any], Mapping[str, Any], Optional[List[Mapping[str, Any]]]]:
    """Load and render the case; with ``after``, load and render again and diff the two."""
    key: Optional[str] = case.get("key")
    graph = session.load(case)
    dump = session.graph(graph)
    first = session.render(graph, key)
    changes = None
    if "after" in case:
        second = session.render(session.load(case, {**case["files"], **case["after"]}), key)
        params: Dict[str, Any] = {"before": first["id"], "after": second["id"]}
        if key is not None:
            params["key"] = key_rules(key)
        changes = session.request("diff", **params)
    return Texts(session, dump), dump, first, changes


def run_load(session: Session, case: Mapping[str, Any]) -> str:
    texts, dump, first, changes = _renders(session, case)
    value: Dict[str, Any] = {"files": [d["path"] for d in dump["documents"]], **projection(texts, first, links=False)}
    if changes is not None:
        value["changes"] = [[c["kind"], c["address"]["people"]] for c in changes]
    return to_bytes(value)


def run_rendered(session: Session, case: Mapping[str, Any]) -> str:
    _texts, _dump, first, changes = _renders(session, case)
    value: Dict[str, Any] = {
        "addresses": [[d["address"]["text"], d["address"]["people"]] for d in walk(first["block"])]
    }
    if changes is not None:
        value["changes"] = [[c["kind"], c["address"]["text"], c["address"]["people"]] for c in changes]
    return to_bytes(value)
