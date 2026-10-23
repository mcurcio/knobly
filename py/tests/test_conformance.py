from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import REPO

from villanelle import Node, Syntax, parse, text_of

CONFORMANCE = REPO / "conformance"
EXPECTED = CONFORMANCE / "expected"


def load(file: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = json.loads((CONFORMANCE / file).read_text(encoding="utf-8"))
    return cases


def cst_json(node: Node) -> list[Any]:
    return [node.kind.value, node.start, node.end, [cst_json(child) for child in node.children]]


def fmt(syntax: Syntax) -> bytes:
    """conformance/format.md, format v0."""
    value = {
        "tokens": [[t.kind.value, t.text] for t in syntax.tokens],
        "cst": cst_json(syntax.root),
        "diagnostics": [[d.code.value, d.span.start.line, d.span.start.column] for d in syntax.diagnostics],
    }
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("ascii")


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(c["src"], id=f"{file}:{c['name']}")
        for file in ("cases.json", "extra.json", "tracer.json")
        for c in load(file)
    ],
)
def test_lossless_cst(src: str) -> None:
    syntax = parse(src)
    assert text_of(syntax, syntax.root) == src
    assert syntax.root.kind == "document"
    assert (syntax.root.start, syntax.root.end) == (0, len(syntax.tokens))
    offset = 0
    for token in syntax.tokens:
        assert token.text != ""
        assert token.span.start.offset == offset
        offset = token.span.end.offset
        assert offset - token.span.start.offset == utf16_length(token.text)
    assert offset == utf16_length(src)


@pytest.mark.parametrize("case", load("tracer.json"), ids=lambda c: c["name"])
def test_expected_output_is_byte_identical(case: dict[str, str]) -> None:
    expected = EXPECTED / f"{case['name']}.json"
    assert expected.is_file(), f"missing {expected}"
    assert fmt(parse(case["src"])) == expected.read_bytes()
