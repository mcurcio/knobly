"""The syntax corpus (conformance/format.md): ``parse`` each text, check the tree is lossless, print format v0."""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from common import Session
from encode import to_bytes
from units import line_column, native_length


SYNTAX_MEMBERS = frozenset({"tokens", "root", "diagnostics"})
DIAGNOSTIC_MEMBERS = frozenset({"id", "code", "message", "start", "end"})


def native_position(src: str, native: int, unit: str) -> List[int]:
    """``[line, column, offset]`` of the native offset ``native`` in ``src``, all in ``unit``."""
    at = 0
    for i, ch in enumerate(src):
        if at >= native:
            prefix = src[:i]
            break
        at += native_length(ch, unit)
    else:
        prefix = src
    line_start = prefix.rfind("\n") + 1
    return [prefix.count("\n"), native_length(prefix[line_start:], unit), native]


def shape(src: str, dump: Mapping[str, Any], unit: str) -> List[str]:
    """Spec/conformance.md 4.2: the syntax dump and its diagnostics have exactly their members, and every position's
    line and column agree with its offset in the input."""
    problems: List[str] = []
    if set(dump) != SYNTAX_MEMBERS:
        return [f"the syntax dump has members {sorted(dump)}, expected {sorted(SYNTAX_MEMBERS)}"]

    def check(what: str, pos: Sequence[int]) -> None:
        if list(pos) != native_position(src, pos[2], unit):
            problems.append(f"{what} is at {list(pos)}, expected {native_position(src, pos[2], unit)}")

    for i, token in enumerate(dump["tokens"]):
        if len(token) != 4:
            problems.append(f"token {i} has {len(token)} members, expected 4")
            continue
        check(f"token {i}'s start", token[2])
        check(f"token {i}'s end", token[3])
    for i, d in enumerate(dump["diagnostics"]):
        if set(d) != DIAGNOSTIC_MEMBERS:
            problems.append(f"diagnostic {i} has members {sorted(d)}, expected {sorted(DIAGNOSTIC_MEMBERS)}")
            continue
        if not isinstance(d["id"], str) or not isinstance(d["message"], str):
            problems.append(f"diagnostic {i}'s id and message must be text")
        check(f"diagnostic {i}'s start", d["start"])
        check(f"diagnostic {i}'s end", d["end"])
    return problems


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
    problems = shape(src, dump, session.unit)
    if problems:
        return "not the syntax dump's shape: " + "; ".join(problems[:5]) + "\n"
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
