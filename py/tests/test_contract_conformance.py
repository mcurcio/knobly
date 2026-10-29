"""The contract conformance runner (conformance/contract/format.md): every case of conformance/contract/cases.json
(spec/contract.md: number readers, positions in Python's own unit, people forms, ``format_diagnostic``), none
skipped. Through the public API only."""

from __future__ import annotations

import json
import math
from typing import Any

import pytest
from conftest import REPO, utf16_column

import villanelle as vl

CASES: list[dict[str, Any]] = json.loads((REPO / "conformance" / "contract" / "cases.json").read_text(encoding="utf-8"))

UNIT = "code point"
"""This binding's string unit, as a ``print`` case's ``expect`` names it (spec/contract.md 1)."""

READERS = ("word", "string", "number", "integer", "boolean", "list", "slice", "plain")


def ecmascript(number: float) -> str:
    """ECMAScript's ``Number::toString`` of a finite double (the number rule of format.md): the shortest digits that
    round-trip (``repr``'s), written plain from 10^-6 up to 10^21 and in exponent form outside."""
    assert math.isfinite(number)
    if number == 0:
        assert math.copysign(1.0, number) > 0, "no reader returns negative zero (spec/contract.md 3)"
        return "0"
    if number < 0:
        return "-" + ecmascript(-number)
    mantissa, _, exponent = repr(number).partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    point = len(whole) + (int(exponent) if exponent else 0)
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    s = stripped.rstrip("0")
    k, n = len(s), point
    if k <= n <= 21:
        return s + "0" * (n - k)
    if 0 < n <= 21:
        return s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return "0." + "0" * -n + s
    e = n - 1
    sign = "+" if e >= 0 else "-"
    return (s if k == 1 else s[0] + "." + s[1:]) + f"e{sign}{abs(e)}"


def number_text(value: object) -> str:
    """An integer the binding holds as an int, in decimal; a float by the ECMAScript rule."""
    if isinstance(value, bool):
        raise AssertionError(f"not a number: {value!r}")
    if isinstance(value, int):
        return str(value)
    assert isinstance(value, float), f"not a number: {value!r}"
    return ecmascript(value)


def read(case: dict[str, Any]) -> list[str]:
    graph = vl.Processor(source=vl.memory_source({"main.conf": f"x {case['value']};\n"})).load("main.conf")
    value = vl.render(graph).block[0].values[0]
    reader = case["reader"]
    assert reader in READERS
    try:
        result = getattr(value, reader)()
    except vl.DiagnosticError as error:
        return ["error", str(error.diagnostic.code)]
    if reader == "integer":
        assert type(result) is int
        return ["integer", str(result)]
    if isinstance(result, bool):
        return ["boolean", "true" if result else "false"]
    if isinstance(result, str):
        return ["text", result]
    return ["number", number_text(result)]


def loaded(case: dict[str, Any]) -> tuple[vl.DocumentGraph, vl.Rendered]:
    source = vl.memory_source(case["files"])
    graph = vl.Processor(source=source).load(case["root"], overrides=case.get("overrides"))
    return graph, vl.render(graph)


def target(case: dict[str, Any], graph: vl.DocumentGraph, rendered: vl.Rendered) -> object:
    kind, *rest = case["target"]
    if kind == "argument":
        d, v, what, *index = rest
        origin = rendered.block[d].values[v].origin
        return origin.place if what == "place" else origin.via[index[0]]
    if kind == "diagnostic":
        return rendered.diagnostics[rest[0]]
    if kind == "syntax diagnostic":
        return graph.documents[rest[0]].syntax.diagnostics[rest[1]]
    raise AssertionError(f"unknown target {kind}")


def with_message(expected: str, found: object) -> str:
    message = getattr(found, "message", None)
    return expected if message is None else expected.replace("{message}", message)


def check(case: dict[str, Any]) -> None:
    kind = case["kind"]
    if kind == "reader":
        assert read(case) == case["expect"]
        return
    graph, rendered = loaded(case)
    found = target(case, graph, rendered)
    if kind == "position":
        assert isinstance(found, vl.Place)
        text = graph.documents[found.resolved_path].text
        start, end = found.span.start, found.span.end
        span = [start.line, utf16_column(text, start.offset, start.column), end.line]
        span.append(utf16_column(text, end.offset, end.column))
        assert {"span": span, "slice": text[start.offset : end.offset]} == case["expect"]
        return
    if kind == "print":
        expect = case["expect"]
        expected = expect[UNIT] if isinstance(expect, dict) else expect
        assert str(found) == with_message(expected, found)
        return
    if kind == "format":
        assert isinstance(found, vl.LocatedDiagnostic)
        expected_lines = [with_message(line, found) for line in case["expect"]]
        assert vl.format_diagnostic(found, graph).split("\n") == expected_lines
        return
    raise AssertionError(f"unknown case kind {kind}")


def test_every_case_kind_is_implemented() -> None:
    assert {c["kind"] for c in CASES} <= {"reader", "position", "print", "format"}
    assert len({c["name"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", [pytest.param(c, id=c["name"]) for c in CASES])
def test_contract_case(case: dict[str, Any]) -> None:
    check(case)


@pytest.mark.parametrize(
    ("number", "text"),
    [
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (1e-7, "1e-7"),
        (1e-6, "0.000001"),
        (0.5, "0.5"),
        (1.5e300, "1.5e+300"),
        (123.0, "123"),
        (-2.5e-8, "-2.5e-8"),
    ],
)
def test_the_number_rule_writes_ecmascripts_form(number: float, text: str) -> None:
    assert ecmascript(number) == text
