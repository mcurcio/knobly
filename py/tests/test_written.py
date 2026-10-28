"""The low level's documents, handles, edits, save and reads (slices.md S3: C4, C7; and the units S1's and S2's
criteria name: identity, detaching, comment ownership, refused edits, save, read, set_handed, written)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import assert_never

import pytest
from conftest import REPO

import villanelle as vl
from villanelle.include import include


def load(files: Mapping[str, str], variables: Mapping[str, str] | None = None) -> vl.DocumentGraph:
    return vl.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf", variables=variables)


class Recorder:
    def __init__(self) -> None:
        self.batches: list[list[vl.FileWrite]] = []

    def write(self, files: Sequence[vl.FileWrite], /) -> None:
        self.batches.append(list(files))


class Counting:
    """A memory source that counts each read per path."""

    def __init__(self, files: Mapping[str, str]) -> None:
        self.inner = vl.memory_source(files)
        self.reads: list[str] = []

    def resolve(self, spec: str, context: vl.LoadContext, /) -> Sequence[str]:
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        return self.inner.read(resolved_path)


def directive(statement: vl.Statement) -> vl.WrittenDirective:
    assert isinstance(statement, vl.WrittenDirective)
    return statement


# --- documents and handles ---


def test_keeps_one_handle_per_statement_and_value_across_an_edit_elsewhere_in_the_file() -> None:
    graph = load({"main.conf": "set $a 1;\nb 2 3;\nc { d 4; }\n"})
    body = graph.root.body
    set_line, b, c = body
    assert isinstance(set_line, vl.SetLine)
    two, three = directive(b).values
    c_block = directive(c).block
    assert c_block is not None
    d = c_block[0]
    set_line.set_values("100 200")
    assert graph.root.text == "set $a 100 200;\nb 2 3;\nc { d 4; }\n"
    assert body[0] is set_line and body[1] is b
    assert directive(b).values[0] is two and directive(b).values[1] is three
    assert c_block[0] is d
    assert [b.text, two.text, three.text, d.text, set_line.text] == ["b 2 3;", "2", "3", "d 4;", "set $a 100 200;"]
    assert set_line.variable is graph.variables("a")[0]
    assert b.place.span.start == vl.SourcePosition(16, 1, 0)


def test_a_renamed_directive_keeps_its_handle_and_its_values_follow_their_tokens() -> None:
    graph = load({"main.conf": "fps 20;\n"})
    fps = directive(graph.root.body[0])
    [twenty] = fps.values
    fps.rename("rate")
    assert graph.root.body[0] is fps and fps.values[0] is twenty
    assert (fps.name, twenty.text, twenty.place.span.start.column) == ("rate", "20", 5)


def test_a_replaced_value_detaches_and_every_member_but_kind_raises() -> None:
    graph = load({"main.conf": "x 1;\n"})
    [value] = directive(graph.root.body[0]).values
    [made] = value.replace_with_text("2")
    assert made.text == "2"
    assert value.kind == "word"
    with pytest.raises(vl.DetachedError):
        _ = value.text
    with pytest.raises(vl.DetachedError):
        value.replace_with_text("3")


def test_owns_the_comment_lines_directly_above_a_statement_and_its_trailing_comment() -> None:
    graph = load({"main.conf": "# far\n\n# near\n  b 2; # end\nc;\n"})
    b = graph.root.body[0]
    assert b.text == "# near\n  b 2; # end"
    assert (b.place.span.start.line, b.place.span.start.column) == (2, 0)
    b.remove()
    assert graph.root.text == "# far\n\nc;\n"


def test_changes_nothing_when_an_edit_is_refused() -> None:
    graph = load({"main.conf": "set $a 1;\nx [1];\n"})
    set_line = graph.root.body[0]
    assert isinstance(set_line, vl.SetLine)
    for text in ["1; x", "{", "", '"open']:
        with pytest.raises(vl.BadTextError):
            set_line.set_values(text)
        assert graph.root.text == "set $a 1;\nx [1];\n"
    assert set_line.text == "set $a 1;"
    with pytest.raises(IndexError):
        graph.root.body.insert_statements(3, "y;")
    with pytest.raises(vl.BadTextError):
        graph.root.body.add_statements("set $a 2;")  # E5002: a second `set` of $a in one block
    assert graph.root.text == "set $a 1;\nx [1];\n"


def test_a_handed_in_value_and_a_parameter_have_no_set_line() -> None:
    graph = load({"main.conf": "snippet s $p { x $p; }\nuse s 1;\n"}, {"h": "1"})
    parameter, handed = graph.variables()
    assert (parameter.kind, handed.kind) == ("parameter", "handed")
    for variable in (parameter, handed):
        with pytest.raises(vl.NoSetLineError):
            variable.set_values("2")
    with pytest.raises(vl.NoSetLineError):
        handed.rename("g")


# --- Python idioms (C4) ---


def describe(statement: vl.Statement) -> str:
    match statement:
        case vl.WrittenDirective():
            return f"{statement.kind} {statement.name}"
        case vl.SetLine():
            return f"set ${statement.variable.name}"
        case vl.SnippetLine():
            return f"snippet {statement.name}"
        case vl.UseLine():
            return f"use {statement.snippet_name}"
        case vl.UnreadableLine():
            return "unreadable"
        case _:
            assert_never(statement)


def value_kind(value: vl.WrittenValue) -> str:
    match value:
        case vl.Word() | vl.String():
            return value.kind
        case vl.List():
            return f"list of {len(value.items)}"
        case vl.Slice():
            return f"slice {value.name}"
        case vl.Index():
            return f"index {value.name}[{value.index.text}]"
        case vl.Reference():
            return f"reference {value.name}"
        case _:
            assert_never(value)


def test_match_narrows_every_kind_and_a_block_is_a_sequence_of_the_same_handles() -> None:
    text = 'include "p.conf";\nset $a 1;\nsnippet s { y; }\nuse s;\nx w "s" [1, 2] c[1:2] c[0] $a;\nz x"y";\n'
    graph = load({"main.conf": text, "p.conf": ""})
    body = graph.root.body
    assert [describe(s) for s in body] == [
        "extension include",
        "set $a",
        "snippet s",
        "use s",
        "directive x",
        "unreadable",
    ]
    x = directive(body[4])
    assert [value_kind(v) for v in x.values] == [
        "word",
        "string",
        "list of 2",
        "slice c",
        "index c[0]",
        "reference a",
    ]
    assert body[0] is body[0]
    assert len(body) == 6
    assert x in body
    assert list(body[1:3]) == [body[1], body[2]]
    assert body.directives() == (x,)


# --- the lookup rule has one home (C7) ---


def test_no_scope_class_or_lookup_outside_the_binding() -> None:
    package = REPO / "py" / "src" / "villanelle"
    offenders = [
        str(path.relative_to(package))
        for path in package.rglob("*.py")
        if "_gen" not in path.parts
        and path.name != "_bind.py"
        and re.search(r"class \w*Scope\b|\blookup\(", path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# --- save ---


def test_save_hands_only_changed_files_to_the_writer_in_one_call_then_updates_source() -> None:
    graph = load({"main.conf": 'include "p.conf";\nx 1;\n', "p.conf": "y 2;\n"})
    writer = Recorder()
    assert vl.save(graph, writer) == []
    assert writer.batches == []
    p = graph.documents["p.conf"]
    directive(p.body[0]).values[0].replace_with_text("3")
    assert vl.save(graph, writer) == ["p.conf"]
    assert writer.batches == [[vl.FileWrite("p.conf", "y 3;\n", "y 2;\n")]]
    assert p.source == "y 3;\n"
    assert vl.save(graph, writer) == []
    assert len(writer.batches) == 1


def test_save_raises_save_error_from_the_writers_error_and_changes_no_source() -> None:
    graph = load({"main.conf": "x 1;\n"})
    directive(graph.root.body[0]).values[0].replace_with_text("2")
    cause = OSError("disk full")

    class Failing:
        def write(self, files: Sequence[vl.FileWrite], /) -> None:
            raise cause

    with pytest.raises(vl.SaveError) as raised:
        vl.save(graph, Failing())
    assert [f.resolved_path for f in raised.value.files] == ["main.conf"]
    assert raised.value.__cause__ is cause
    assert graph.root.source == "x 1;\n"
    assert graph.root.text != graph.root.source


def test_quote_writes_a_plain_string_as_the_canonical_villanelle_string() -> None:
    assert vl.quote('10.0.60.31 "x"\n') == '"10.0.60.31 \\"x\\"\\n"'


# --- reads, handed-in values, the rendered tree's written handles ---


def test_an_added_include_stays_unread_until_read_which_reads_it_once_and_keeps_every_other_text() -> None:
    source = Counting({"main.conf": "a 1;\n", "part.conf": "p 1;\n"})
    processor = vl.Processor(source=source, extensions=[include()])
    graph = processor.load("main.conf")
    directive(graph.root.body[0]).values[0].replace_with_text("2")
    [added] = graph.root.body.add_statements('include "part.conf";')
    assert [e.copy.statement for e in graph.unread()] == [added]
    assert [d.name for d in processor.render(graph).body] == ["a"]
    assert processor.read(graph) == ["part.conf"]
    assert processor.read(graph) == []
    assert source.reads == ["main.conf", "part.conf"]
    assert graph.unread() == ()
    assert graph.root.text == 'a 2;\ninclude "part.conf";\n'
    assert [(d.name, d.args[0].text) for d in processor.render(graph).body] == [("a", "2"), ("p", "1")]


def test_set_handed_changes_the_render_without_a_reload() -> None:
    source = Counting({"main.conf": "set $a 1;\nx $a;\n"})
    processor = vl.Processor(source=source)
    graph = processor.load("main.conf")
    graph.set_handed("a", "2 3")
    handed = graph.variables("a")[1]
    assert [a.text for a in processor.render(graph).body[0].args] == ["2", "3"]
    graph.set_handed("a", None)
    assert [a.text for a in processor.render(graph).body[0].args] == ["1"]
    graph.set_handed("a", "4")
    assert graph.variables("a")[1] is handed  # D28: one variable per name for the graph's life
    assert dict(graph.handed) == {"a": "4"}
    with pytest.raises(vl.BadTextError) as raised:
        graph.set_handed("a", '"\\q"')
    assert [d.code for d in raised.value.diagnostics] == ["E4003"]
    with pytest.raises(ValueError, match="letters, digits"):
        graph.set_handed("a-b", "1")
    assert source.reads == ["main.conf"]


def test_a_rendered_directive_is_a_copy_of_one_written_directive_handle() -> None:
    files = {"main.conf": 'a { include "p.conf"; }\nb { include "p.conf"; }\n', "p.conf": "x 1;\n"}
    processor = vl.Processor(source=vl.memory_source(files), extensions=[include()])
    graph = processor.load("main.conf")
    rendered = processor.render(graph)
    x1, x2 = (d for d in vl.walk(rendered) if d.name == "x")
    assert x1.written is x2.written is graph.documents["p.conf"].body[0]
    assert len(x1.written.copies()) == 2


def test_an_unreadable_names_the_statement_that_could_not_be_read() -> None:
    processor = vl.Processor(source=vl.memory_source({"main.conf": "a $nope;\n"}))
    graph = processor.load("main.conf")
    [unreadable] = processor.render(graph).unreadable
    assert unreadable.written is graph.root.body[0]


def test_load_of_an_unreadable_root_raises_read_error_a_diagnostic_error() -> None:
    with pytest.raises(vl.ReadError) as raised:
        vl.Processor(source=vl.memory_source({})).load("missing.conf")
    assert isinstance(raised.value, vl.DiagnosticError)
    assert raised.value.diagnostic.code == "E3004"


def test_format_diagnostic_prints_the_documents_current_text() -> None:
    processor = vl.Processor(source=vl.memory_source({"main.conf": "a $x;\n"}))
    graph = processor.load("main.conf")
    graph.root.body.insert_statements(0, "b;")
    [d] = processor.render(graph).diagnostics
    assert vl.format_diagnostic(d, graph).split("\n")[1:] == ["a $x;", "  ^^"]
