"""rasl acceptance (S3 criterion 9): rasl's real configs (fixtures/rasl/) load through the file source and the
include extension, with the "rasl" key rule and an override, and a reload diffs as expected."""

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


def rasl_key(d: vl.Directive) -> str | None:
    """The "rasl" key rule of conformance/keys.json."""
    if d.name == "node" and d.parent is not None and d.parent.name == "graph":
        return d.values[1].text if len(d.values) > 1 else None
    if d.name == "connect":
        return " ".join(a.text for a in d.values)
    if d.name == "fill":
        return d.values[0].text if d.values else None
    return None


def node_ids(loaded: vl.Rendered) -> list[str]:
    graph = next(d for d in loaded.block if d.name == "graph")
    return [d.values[1].text for d in graph.block or () if d.name == "node"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
@pytest.mark.parametrize("override", [False, True])
def test_a_rasl_fixture_loads_and_reloads_as_expected(name: str, override: bool, tmp_path: Path) -> None:
    shutil.copytree(FIXTURES, tmp_path / "rasl")
    root = tmp_path / "rasl" / name
    processor = vl.Processor(source=file_source(), extensions=[include()])
    overrides = {"leds_host": vl.quote("10.0.0.9")} if override else None
    first = vl.render(processor.load(str(root), overrides=overrides))
    expected = EXPECTED[name]
    assert expected["diagnostics"] == []
    assert first.diagnostics == ()
    assert node_ids(first) == expected["nodes"]
    text = root.read_text(encoding="utf-8")
    assert text.count("@set $pixels 2284;") == 1
    root.write_text(text.replace("@set $pixels 2284;", "@set $pixels 2400;"), encoding="utf-8")
    second = vl.render(processor.load(str(root), overrides=overrides))
    changes = first.diff(second, key=rasl_key)
    assert [[type(c).__name__.lower(), str(c.address)] for c in changes] == expected["changes"]


def test_the_split_fixtures_sinks_take_their_include_blocks_values_and_the_override_host_wins() -> None:
    processor = vl.Processor(source=file_source(), extensions=[include()])
    root = str(FIXTURES / "split" / "main.conf")

    def targets(loaded: vl.Rendered) -> dict[str, str]:
        addresses = loaded.addresses(key=rasl_key)
        return {addresses[d].steps[1].key or "": d.values[0].text for d in loaded.walk() if d.name == "target"}

    assert targets(vl.render(processor.load(root))) == {"leds": '"10.0.60.30"', "porch": '"10.0.60.31"'}
    overridden_host = vl.render(processor.load(root, overrides={"leds_host": vl.quote("10.0.0.9")}))
    assert targets(overridden_host) == {"leds": '"10.0.0.9"', "porch": '"10.0.60.31"'}
    assert list(overridden_host.graph.documents) == [root, str(FIXTURES / "split" / "sink.conf")]
    assert len(overridden_host.graph.edges()) == 2
    leds_target = next(d for d in overridden_host.walk() if d.name == "target")
    assert leds_target.values[0].origin.place == vl.Override("leds_host")
    assert [(s.kind, s.name) for s in leds_target.values[0].origin.via] == [
        ("variable", "leds_host"),
        ("variable", "host"),
        ("extension", "include"),
    ]


def test_an_edit_loop_sets_every_max_count_through_the_render_with_no_skip_list() -> None:
    graph = vl.Processor(source=file_source(), extensions=[include()]).load(str(FIXTURES / "split" / "main.conf"))
    # sink.conf is included twice: both rendered max_counts share the one written value of its line. A value's set
    # keeps its handle (spec 6.1), so setting it through each copy writes the same line twice.
    shared = []
    for d in vl.render(graph).walk():
        match d:
            case vl.Directive("max_count", [value]):
                value.written.set(vl.text("2400"))
                shared.append(value.written)
    assert len(shared) == 2 and shared[0] is shared[1]
    assert "    max_count 2400;\n" in graph.documents[str(FIXTURES / "split" / "sink.conf")].text
