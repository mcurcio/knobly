"""The contract corpus (conformance/contract/format.md): readers, positions in the binding's own unit, people forms
and ``format diagnostic``. Expected results are inline in each case; the driver compares them as JSON text."""

from __future__ import annotations

import json
import math
from typing import Any, List, Mapping, Tuple

from adapter import Thrown
from common import CaseError, Session, Texts


def ecmascript(number: float) -> str:
    """ECMAScript's ``Number::toString`` of a finite double: shortest round-trip digits (``repr``'s), plain from
    10^-6 up to 10^21, exponent form outside."""
    if not math.isfinite(number):
        raise CaseError(f"a reader returned {number!r}")
    if number == 0:
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
    return (s if k == 1 else s[0] + "." + s[1:]) + f"e{'+' if e >= 0 else '-'}{abs(e)}"


def number_text(value: Any) -> str:
    """The number rule: an integer in decimal, a double as ECMAScript writes it; negative zero has no spelling."""
    if value == "-0" or (isinstance(value, float) and value == 0 and math.copysign(1.0, value) < 0):
        raise CaseError("a reader returned negative zero (spec/contract.md 3)")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CaseError(f"not a number: {value!r}")
    return str(value) if isinstance(value, int) else ecmascript(value)


def result(reader: str, value: Mapping[str, Any]) -> List[Any]:
    """A reader's neutral result (spec/conformance.md, ``read``) as the corpus writes it."""
    if "text" in value:
        return ["text", value["text"]]
    if "boolean" in value:
        return ["boolean", "true" if value["boolean"] else "false"]
    if "number" in value:
        return ["integer" if reader == "integer" else "number", number_text(value["number"])]
    if "slice" in value:
        return ["slice", *value["slice"]]
    if "index" in value:
        return ["index", *value["index"]]
    if "list" in value:
        if reader == "list":
            return ["values", [item["value"] for item in value["list"]]]
        return ["list", [result(reader, item) for item in value["list"]]]
    raise CaseError(f"not a reader result: {value!r}")


def _target(
    session: Session, case: Mapping[str, Any], graph: Mapping[str, Any], render: Mapping[str, Any]
) -> Mapping[str, Any]:
    kind, *rest = case["target"]
    try:
        if kind == "argument":
            d, v, what, *index = rest
            origin = render["block"][d]["values"][v]["origin"]
            return dict(origin["place"] if what == "place" else origin["via"][index[0]])
        if kind == "diagnostic":
            return dict(render["diagnostics"][rest[0]])
        if kind == "syntax diagnostic":
            doc = next(x for x in graph["documents"] if x["path"] == rest[0])
            return dict(doc["syntax"]["diagnostics"][rest[1]])
    except (IndexError, KeyError, StopIteration) as error:
        raise CaseError(f"no target {case['target']}") from error
    raise CaseError(f"unknown target {kind}")


def _message(text: str, target: Mapping[str, Any]) -> str:
    return text.replace("{message}", str(target.get("message", "")))


def run(session: Session, case: Mapping[str, Any]) -> Tuple[str, str]:
    """``(actual, expected)``, each as JSON text."""
    kind = case["kind"]
    if kind == "reader":
        graph = session.load({"files": {"main.conf": f"x {case['value']};\n"}, "root": "main.conf"})
        render = session.render(graph)
        value = render["block"][0]["values"][0]["id"]
        try:
            actual: Any = result(case["reader"], session.request("read", value=value, reader=case["reader"]))
        except Thrown as thrown:
            actual = ["error", thrown.error.get("code")]
        return _json(actual), _json(case["expect"])
    graph_id = session.load(case)
    graph = session.graph(graph_id)
    render = session.render(graph_id)
    target = _target(session, case, graph, render)
    expect: Any = case["expect"]
    if kind == "position":
        texts = Texts(session, graph)
        text = texts.by_path[target["path"]]
        span = texts.line_column(target["path"], target["start"]) + texts.line_column(target["path"], target["end"])
        cut = session.request("cut", text=text, start=target["start"][2], end=target["end"][2])
        return _json({"span": span, "slice": cut}), _json(expect)
    if kind == "print":
        expected = expect if isinstance(expect, str) else expect.get(session.unit)
        if expected is None:
            raise CaseError(f"no expectation for the unit {session.unit}")
        return _json(session.request("print", target=target["id"])), _json(_message(expected, target))
    if kind == "format":
        params = {"diagnostic": target["id"]}
        if case.get("graph", True):
            params["graph"] = graph_id
        lines = expect if isinstance(expect, list) else expect.get(session.unit)
        if lines is None:
            raise CaseError(f"no expectation for the unit {session.unit}")
        text = session.request("format", **params)
        return _json(text.split("\n")), _json([_message(line, target) for line in lines])
    raise CaseError(f"unknown case kind {kind}")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
