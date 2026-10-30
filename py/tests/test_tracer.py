"""The round 12 tracer (design.md §1 and §14; slices.md S3 C3): fixtures/rasl/split through ``memory_source`` and a
recording writer, the whole flow through the public API, written as design.md §1's Python: load, (1)'s table, (2)
through ``chain[0]``, save, render; (3) from a fresh load; (4) an edit inside the included file and its undo."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from conftest import REPO

import villanelle as vl
from villanelle import rendered, written
from villanelle.include import include

SPLIT = REPO / "fixtures" / "rasl" / "split"
FILES = {name: (SPLIT / name).read_text(encoding="utf-8") for name in ("main.conf", "sink.conf")}


def line_of(place: vl.Place) -> str:
    """1-based ``file:line``, as design.md §1 prints it."""
    return f"{place.resolved_path}:{place.span.start.line + 1}"


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[vl.FileWrite]] = []

    def write(self, files: Sequence[vl.FileWrite], /) -> None:
        self.batches.append(list(files))


def open_split() -> written.DocumentGraph:
    config = written.Processor(source=vl.memory_source(FILES), extensions=[include()])
    return config.load("main.conf", overrides={"leds_host": vl.quote("10.0.70.1")})


def node_named(tree: rendered.Rendered, name: str) -> rendered.Directive:
    return next(d for d in tree.block.walk() if d.name == "node" and len(d.values) > 1 and d.values[1].text == name)


def max_counts(tree: rendered.Rendered) -> list[tuple[str, str | None, int]]:
    out: list[tuple[str, str | None, int]] = []
    for d in tree.block.walk():
        if d.name == "max_count":
            arg = d.values[0]
            definition = (
                None
                if arg.definition is None
                else f"{line_of(arg.definition.place)}:{arg.definition.place.span.start.column + 1}"
            )
            out.append((arg.text, definition, len(arg.chain)))
    return out


def test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf() -> None:
    graph = open_split()
    files = [
        (doc.resolved_path, [line_of(e.copy.statement.place) for e in doc.included_by()])
        for doc in graph.documents.values()
    ]
    assert files == [("main.conf", []), ("sink.conf", ["main.conf:19", "main.conf:24"])]
    table = [
        (
            v.name,
            v.kind,
            "override" if isinstance(v, written.OverrideVariable) else line_of(v.place),
            [line_of(r.reference.place) for r in v.wins()],
            [(line_of(r.reference.place), None if r.winner is None else r.winner.kind) for r in v.shadowed_at()],
        )
        for v in graph.variables()
    ]
    assert table == [
        ("pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []),
        ("leds_host", "set", "main.conf:5", [], [("main.conf:21", "override")]),
        ("name", "set", "main.conf:20", ["sink.conf:2"], []),
        ("host", "set", "main.conf:21", ["sink.conf:3"], []),
        ("name", "set", "main.conf:25", ["sink.conf:2"], []),
        ("host", "set", "main.conf:26", ["sink.conf:3"], []),
        ("leds_host", "override", "override", ["main.conf:21"], []),
    ]

    tree = rendered.render(graph)
    leds = node_named(tree, "leds")
    max_count = next(d for d in leds.block or () if d.name == "max_count").values[0]
    read = max_count.chain[0]
    assert isinstance(read.winner, written.SetVariable)
    read.winner.set(vl.text("2400"))  # (2)
    writer = Recorder()
    assert graph.save(writer) == ("main.conf",)
    [[saved]] = writer.batches
    assert saved.text == FILES["main.conf"].replace("@set $pixels 2284;", "@set $pixels 2400;")
    assert graph.save(writer) == ()  # (5): saving twice writes once
    assert len(writer.batches) == 1
    assert max_counts(rendered.render(graph)) == [("2400", "main.conf:4:14", 1), ("2400", "main.conf:4:14", 1)]
    # The render from before the edit is a snapshot: it still reads 2284.
    assert max_count.text == "2284"


def test_changes_max_count_to_no_longer_use_the_variable_only_sink_conf_and_pixels_wins_nothing() -> None:
    graph = open_split()
    leds = node_named(rendered.render(graph), "leds")
    read = next(d for d in leds.block or () if d.name == "max_count").values[0].chain[0]
    assert read.reference.text == "$pixels"
    read.reference.replace_with_text(vl.text("2400"))  # (3)
    writer = Recorder()
    assert graph.save(writer) == ("sink.conf",)
    assert writer.batches[0][0].text == FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;")
    assert graph.variables("pixels")[0].wins() == ()
    assert max_counts(rendered.render(graph)) == [("2400", "sink.conf:6:15", 0), ("2400", "sink.conf:6:15", 0)]


def test_edits_a_directive_inside_the_included_file_and_undoes_it() -> None:
    graph = open_split()
    node = node_named(rendered.render(graph), "porch").written  # (4): `node DdpSink $name {` in sink.conf
    assert node is node_named(rendered.render(graph), "leds").written
    assert len(node.copies()) == 2
    doc = node.document
    kept = doc.text
    block = node.block
    assert block is not None
    [fps] = block.directives("fps")
    fps.set(vl.text("30hz"))
    block.insert_statements(list(block).index(fps) + 1, vl.text("brightness 0.8;"))
    assert "    fps 30hz;\n    brightness 0.8;\n    input_port pixels;" in doc.text
    porch = node_named(rendered.render(graph), "porch")
    assert [(d.name, [a.text for a in d.values]) for d in porch.block or ()][1:3] == [
        ("fps", ["30hz"]),
        ("brightness", ["0.8"]),
    ]
    doc.replace_with_text(vl.text(kept))  # undo: `saved_text` is untouched; every handle into it detaches
    assert doc.text == doc.saved_text
    with pytest.raises(vl.DetachedError):
        _ = node.text
    assert graph.save(Recorder()) == ()
