"""The round 12 tracer (design.md §1 and §14; slices.md S3 C3): fixtures/rasl/split through ``memory_source`` and a
recording writer, the whole flow through the public API, written as design.md §1's Python: load, (1)'s table, (2)
through ``resolutions[0]``, save, render; (3) from a fresh load; (4) an edit inside the included file and its undo."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from conftest import REPO

import villanelle as vl
from villanelle.include import include

SPLIT = REPO / "fixtures" / "rasl" / "split"
FILES = {name: (SPLIT / name).read_text(encoding="utf-8") for name in ("main.conf", "sink.conf")}


def line_of(at: vl.Place) -> str:
    """1-based ``file:line``, as design.md §1 prints it."""
    return f"{at.resolved_path}:{at.span.start.line + 1}"


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[vl.FileWrite]] = []

    def write(self, files: Sequence[vl.FileWrite], /) -> None:
        self.batches.append(list(files))


def open_split() -> tuple[vl.Processor, vl.DocumentGraph]:
    config = vl.Processor(source=vl.memory_source(FILES), extensions=[include()])
    return config, config.load("main.conf", variables={"leds_host": '"10.0.70.1"'})


def node_named(rendered: vl.Rendered, name: str) -> vl.Directive:
    return next(d for d in vl.walk(rendered) if d.name == "node" and len(d.args) > 1 and d.args[1].text == name)


def max_counts(rendered: vl.Rendered) -> list[tuple[str, str | None, int]]:
    out: list[tuple[str, str | None, int]] = []
    for d in vl.walk(rendered):
        if d.name == "max_count":
            arg = d.args[0]
            written = (
                None
                if arg.written is None
                else f"{line_of(arg.written.place)}:{arg.written.place.span.start.column + 1}"
            )
            out.append((arg.text, written, len(arg.resolutions)))
    return out


def test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf() -> None:
    config, graph = open_split()
    files = [
        (doc.resolved_path, [line_of(e.copy.statement.place) for e in doc.included_by()])
        for doc in graph.documents.values()
    ]
    assert files == [("main.conf", []), ("sink.conf", ["main.conf:19", "main.conf:24"])]
    table = [
        (
            v.name,
            v.kind,
            "handed in" if v.place is None else line_of(v.place),
            [line_of(r.reference.place) for r in v.reaches()],
            [(line_of(r.reference.place), None if r.winner is None else r.winner.kind) for r in v.overridden()],
        )
        for v in graph.variables()
    ]
    assert table == [
        ("pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []),
        ("leds_host", "set", "main.conf:5", [], [("main.conf:21", "handed")]),
        ("name", "set", "main.conf:20", ["sink.conf:2"], []),
        ("host", "set", "main.conf:21", ["sink.conf:3"], []),
        ("name", "set", "main.conf:25", ["sink.conf:2"], []),
        ("host", "set", "main.conf:26", ["sink.conf:3"], []),
        ("leds_host", "handed", "handed in", ["main.conf:21"], []),
    ]

    rendered = config.render(graph)
    leds = node_named(rendered, "leds")
    max_count = next(d for d in leds.body or () if d.name == "max_count").args[0]
    read = max_count.resolutions[0]
    assert read.winner is not None and read.winner.kind == "set"
    read.winner.set_values("2400")  # (2)
    writer = Recorder()
    assert vl.save(graph, writer) == ["main.conf"]
    [[written]] = writer.batches
    assert written.text == FILES["main.conf"].replace("set $pixels 2284;", "set $pixels 2400;")
    assert vl.save(graph, writer) == []  # (5): saving twice writes once
    assert len(writer.batches) == 1
    assert max_counts(config.render(graph)) == [("2400", "main.conf:4:13", 1), ("2400", "main.conf:4:13", 1)]
    # The render from before the edit is a snapshot: it still reads 2284.
    assert max_count.text == "2284"


def test_changes_max_count_to_no_longer_use_the_variable_only_sink_conf_and_pixels_reaches_nothing() -> None:
    config, graph = open_split()
    leds = node_named(config.render(graph), "leds")
    read = next(d for d in leds.body or () if d.name == "max_count").args[0].resolutions[0]
    assert read.reference.text == "$pixels"
    read.reference.replace_with_text("2400")  # (3)
    writer = Recorder()
    assert vl.save(graph, writer) == ["sink.conf"]
    assert writer.batches[0][0].text == FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;")
    assert graph.variables("pixels")[0].reaches() == ()
    assert max_counts(config.render(graph)) == [("2400", "sink.conf:6:15", 0), ("2400", "sink.conf:6:15", 0)]


def test_edits_a_directive_inside_the_included_file_and_undoes_it() -> None:
    config, graph = open_split()
    node = node_named(config.render(graph), "porch").written  # (4): `node DdpSink $name {` in sink.conf
    assert node is node_named(config.render(graph), "leds").written
    assert len(node.copies()) == 2
    doc = node.document
    kept = doc.text
    block = node.block
    assert block is not None
    [fps] = block.directives("fps")
    fps.set_values("30hz")
    block.insert_statements(list(block).index(fps) + 1, "brightness 0.8;")
    assert "    fps 30hz;\n    brightness 0.8;\n    input_port pixels;" in doc.text
    porch = node_named(config.render(graph), "porch")
    assert [(d.name, [a.text for a in d.args]) for d in porch.body or ()][1:3] == [
        ("fps", ["30hz"]),
        ("brightness", ["0.8"]),
    ]
    doc.replace_with_text(kept)  # undo: `source` is untouched; every handle into it detaches
    assert doc.text == doc.source
    with pytest.raises(vl.DetachedError):
        _ = node.text
    assert vl.save(graph, Recorder()) == []
