"""The syntax corpus (conformance/format.md): ``parse`` each text, check the tree is lossless, print format v0."""

from __future__ import annotations

from typing import Any, List, Mapping

from common import Session
from encode import to_bytes
from units import line_column, native_length


def lossless(src: str, dump: Mapping[str, Any], unit: str) -> List[str]:
    """Spec 3: the tokens are the text, in order, each non-empty, their native spans contiguous; the tree covers
    every token once, children in order inside their parent; an error node has no children."""
    problems: List[str] = []
    tokens = dump["tokens"]
    if "".join(t[1] for t in tokens) != src:
        problems.append("the tokens' texts joined are not the input")
    offset = 0
    for i, (_kind, text, start, end) in enumerate(tokens):
        if text == "":
            problems.append(f"token {i} is empty")
        if start[2] != offset or end[2] - start[2] != native_length(text, unit):
            problems.append(
                f"token {i} spans {start[2]}..{end[2]}, expected {offset}..{offset + native_length(text, unit)}"
            )
            break
        offset = end[2]
    if offset != native_length(src, unit):
        problems.append(f"the tokens end at {offset}, the input at {native_length(src, unit)}")
    root = dump["root"]
    if root[0] != "document" or root[1] != 0 or root[2] != len(tokens):
        problems.append(f"the root is {root[:3]}, expected ['document', 0, {len(tokens)}]")

    def cover(node: List[Any]) -> None:
        at = node[1]
        for child in node[3]:
            if child[1] < at or child[2] < child[1] or child[2] > node[2]:
                problems.append(f"{child[0]} child {child[1]}..{child[2]} is not inside {node[0]} after {at}")
            if child[0] == "error" and child[3]:
                problems.append("an error node has children")
            cover(child)
            at = child[2]

    cover(root)
    return problems


def run(session: Session, case: Mapping[str, Any]) -> str:
    src = case["src"]
    dump = session.request("parse", text=src)
    problems = lossless(src, dump, session.unit)
    if problems:
        return "not lossless: " + "; ".join(problems[:5]) + "\n"
    conv = session.convert(src)
    return to_bytes(
        {
            "tokens": [[t[0], t[1]] for t in dump["tokens"]],
            "cst": dump["root"],
            "diagnostics": [[d["code"], *line_column(conv, d["start"])] for d in dump["diagnostics"]],
        }
    )
