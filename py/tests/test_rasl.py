"""rasl acceptance (S3 criterion 9): rasl's real configs (fixtures/rasl/) load through the file source and the
include extension, with the "rasl" key rule and a handed-in variable, and a reload diffs as expected."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO

import villanelle as vl
from villanelle.files import file_source
from villanelle.include import include

FIXTURES = REPO / "fixtures" / "rasl"
EXPECTED: dict[str, dict[str, Any]] = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def rasl_key(d: vl.KeyInput) -> str | None:
    """The "rasl" key rule of conformance/load/format.md."""
    if d.name == "node" and d.parent is not None and d.parent.name == "graph":
        return d.args[1].text if len(d.args) > 1 else None
    if d.name == "connect":
        return " ".join(a.text for a in d.args)
    if d.name == "fill":
        return d.args[0].text if d.args else None
    return None


def node_ids(loaded: vl.Loaded) -> list[str]:
    graph = next(d for d in loaded.body if d.name == "graph")
    return [d.args[1].text for d in graph.body or () if d.name == "node"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
@pytest.mark.parametrize("handed", [False, True])
def test_a_rasl_fixture_loads_and_reloads_as_expected(name: str, handed: bool, tmp_path: Path) -> None:
    shutil.copytree(FIXTURES, tmp_path / "rasl")
    root = tmp_path / "rasl" / name
    processor = vl.Processor(source=file_source(), extensions=[include()], key=rasl_key)
    variables = {"leds_host": '"10.0.0.9"'} if handed else None
    first = processor.load(str(root), variables=variables)
    expected = EXPECTED[name]
    assert expected["diagnostics"] == []
    assert first.diagnostics == ()
    assert node_ids(first) == expected["nodes"]
    text = root.read_text(encoding="utf-8")
    assert text.count("set $pixels 2284;") == 1
    root.write_text(text.replace("set $pixels 2284;", "set $pixels 2400;"), encoding="utf-8")
    second = processor.load(str(root), variables=variables)
    assert [[type(c).__name__.lower(), str(c.address)] for c in processor.diff(first, second)] == expected["changes"]


def test_the_split_fixtures_sinks_take_their_include_blocks_values_and_the_handed_host_wins() -> None:
    processor = vl.Processor(source=file_source(), extensions=[include()], key=rasl_key)
    root = str(FIXTURES / "split" / "main.conf")

    def targets(loaded: vl.Loaded) -> dict[str, str]:
        return {d.address.steps[1].key or "": d.args[0].text for d in vl.walk(loaded) if d.name == "target"}

    assert targets(processor.load(root)) == {"leds": '"10.0.60.30"', "porch": '"10.0.60.31"'}
    handed = processor.load(root, variables={"leds_host": '"10.0.0.9"'})
    assert targets(handed) == {"leds": '"10.0.0.9"', "porch": '"10.0.60.31"'}
    assert list(handed.graph.nodes) == [root, str(FIXTURES / "split" / "sink.conf")]
    assert len(handed.graph.edges) == 2
    leds_target = next(d for d in vl.walk(handed) if d.name == "target")
    assert leds_target.args[0].origin.written == vl.Handed("leds_host")
    assert [(s.kind, s.name) for s in leds_target.args[0].origin.via] == [
        ("variable", "leds_host"),
        ("variable", "host"),
        ("extension", "include"),
    ]
