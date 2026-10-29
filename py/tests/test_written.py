"""The low level's documents, handles, edits, save and reads (slices.md S3: C4, C7; and the units S1's and S2's
criteria name: identity, detaching, comment ownership, refused edits, save, read, set_override, written)."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import assert_never

import pytest
from conftest import REPO

import villanelle as vl
from villanelle.include import include


def load(files: Mapping[str, str], overrides: Mapping[str, str] | None = None) -> vl.DocumentGraph:
    return vl.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf", overrides=overrides)


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
    body = graph.root.block
    set_line, b, c = body
    assert isinstance(set_line, vl.SetLine)
    two, three = directive(b).values
    c_block = directive(c).block
    assert c_block is not None
    d = c_block[0]
    set_line.set("100 200")
    assert graph.root.text == "set $a 100 200;\nb 2 3;\nc { d 4; }\n"
    assert body[0] is set_line and body[1] is b
    assert directive(b).values[0] is two and directive(b).values[1] is three
    assert c_block[0] is d
    assert [b.text, two.text, three.text, d.text, set_line.text] == ["b 2 3;", "2", "3", "d 4;", "set $a 100 200;"]
    assert set_line.variable is graph.variables("a")[0]
    assert b.place.span.start == vl.SourcePosition(16, 1, 0)


def test_a_renamed_directive_keeps_its_handle_and_its_values_follow_their_tokens() -> None:
    graph = load({"main.conf": "fps 20;\n"})
    fps = directive(graph.root.block[0])
    [twenty] = fps.values
    fps.rename("rate")
    assert graph.root.block[0] is fps and fps.values[0] is twenty
    assert (fps.name, twenty.text, twenty.place.span.start.column) == ("rate", "20", 5)


def test_a_replaced_value_detaches_and_every_member_but_kind_raises() -> None:
    graph = load({"main.conf": "x 1;\n"})
    [value] = directive(graph.root.block[0]).values
    [made] = value.replace_with_text("2")
    assert made.text == "2"
    assert value.kind == "word"
    with pytest.raises(vl.DetachedError):
        _ = value.text
    with pytest.raises(vl.DetachedError):
        value.replace_with_text("3")


def test_owns_the_comment_lines_directly_above_a_statement_and_its_trailing_comment() -> None:
    graph = load({"main.conf": "# far\n\n# near\n  b 2; # end\nc;\n"})
    b = graph.root.block[0]
    assert b.text == "# near\n  b 2; # end"
    assert (b.place.span.start.line, b.place.span.start.column) == (2, 0)
    b.remove()
    assert graph.root.text == "# far\n\nc;\n"


def test_changes_nothing_when_an_edit_is_refused() -> None:
    graph = load({"main.conf": "set $a 1;\nx [1];\n"})
    set_line = graph.root.block[0]
    assert isinstance(set_line, vl.SetLine)
    for text in ["1; x", "{", "", '"open']:
        with pytest.raises(vl.BadTextError):
            set_line.set(text)
        assert graph.root.text == "set $a 1;\nx [1];\n"
    assert set_line.text == "set $a 1;"
    with pytest.raises(IndexError):
        graph.root.block.insert_statements(3, "y;")
    with pytest.raises(vl.BadTextError):
        graph.root.block.add_statements("set $a 2;")  # E5002: a second `set` of $a in one block
    assert graph.root.text == "set $a 1;\nx [1];\n"


def test_an_override_and_a_parameter_have_no_set_line() -> None:
    graph = load({"main.conf": "snippet s $p { x $p; }\nuse s 1;\n"}, {"h": "1"})
    parameter, override = graph.variables()
    assert (parameter.kind, override.kind) == ("parameter", "override")
    for variable in (parameter, override):
        with pytest.raises(vl.NoSetLineError):
            variable.set("2")
    with pytest.raises(vl.NoSetLineError):
        override.rename("g")


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
    body = graph.root.block
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


def test_a_reference_has_the_declaration_the_binding_picks_at_every_copy() -> None:
    text = "snippet s $a {\n    x {\n        set $a 1;\n        y $a;\n    }\n    z $a;\n}\nuse s 2;\nuse s 3;\n"
    graph = load({"main.conf": text})
    references = {id(r): r for v in graph.variables() for r in v.references()}
    assert len(references) == 2
    for reference in references.values():
        winners = [r.winner for r in reference.resolutions()]
        assert len(winners) == 2
        assert all(winner is reference.declaration for winner in winners)


# --- save ---


def test_replacing_a_documents_text_keeps_saved_text_and_save_writes_the_new_text() -> None:
    graph = load({"main.conf": "a 1;\n"})
    a = graph.root.block[0]
    graph.root.replace_with_text("b 2;\n")
    assert graph.root.saved_text == "a 1;\n"
    with pytest.raises(vl.DetachedError):
        _ = a.text
    writer = Recorder()
    assert graph.save(writer) == ["main.conf"]
    assert writer.batches == [[vl.FileWrite("main.conf", "b 2;\n", "a 1;\n")]]


def test_save_hands_only_changed_files_to_the_writer_in_one_call_then_updates_saved_text() -> None:
    graph = load({"main.conf": 'include "p.conf";\nx 1;\n', "p.conf": "y 2;\n"})
    writer = Recorder()
    assert graph.save(writer) == []
    assert writer.batches == []
    p = graph.documents["p.conf"]
    directive(p.block[0]).values[0].replace_with_text("3")
    assert graph.save(writer) == ["p.conf"]
    assert writer.batches == [[vl.FileWrite("p.conf", "y 3;\n", "y 2;\n")]]
    assert p.saved_text == "y 3;\n"
    assert graph.save(writer) == []
    assert len(writer.batches) == 1


def test_save_raises_save_error_from_the_writers_error_and_changes_no_saved_text() -> None:
    graph = load({"main.conf": "x 1;\n"})
    directive(graph.root.block[0]).values[0].replace_with_text("2")
    cause = OSError("disk full")

    class Failing:
        def write(self, files: Sequence[vl.FileWrite], /) -> None:
            raise cause

    with pytest.raises(vl.SaveError) as raised:
        graph.save(Failing())
    assert [f.resolved_path for f in raised.value.files] == ["main.conf"]
    assert raised.value.__cause__ is cause
    assert graph.root.saved_text == "x 1;\n"
    assert graph.root.text != graph.root.saved_text


def test_the_readme_example_sets_values_from_program_data_as_text() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "host a;\nport 80;\n"})).load("main.conf")
    host, port = graph.root.block
    host.set(vl.quote("10.0.60.31"))  # type: ignore[union-attr]
    port.set(str(8080))  # type: ignore[union-attr]
    assert graph.root.text == 'host "10.0.60.31";\nport 8080;\n'


def test_quote_writes_a_plain_string_as_the_canonical_villanelle_string() -> None:
    assert vl.quote('10.0.60.31 "x"\n') == '"10.0.60.31 \\"x\\"\\n"'


# --- reads, overrides, the rendered tree's written handles ---


def test_an_added_include_stays_unread_until_read_which_reads_it_once_and_keeps_every_other_text() -> None:
    source = Counting({"main.conf": "a 1;\n", "part.conf": "p 1;\n"})
    graph = vl.Processor(source=source, extensions=[include()]).load("main.conf")
    directive(graph.root.block[0]).values[0].replace_with_text("2")
    [added] = graph.root.block.add_statements('include "part.conf";')
    assert [e.copy.statement for e in graph.unread()] == [added]
    assert [d.name for d in vl.render(graph).block] == ["a"]
    assert graph.read() == ["part.conf"]
    assert graph.read() == []
    assert source.reads == ["main.conf", "part.conf"]
    assert graph.unread() == ()
    assert graph.root.text == 'a 2;\ninclude "part.conf";\n'
    assert [(d.name, d.values[0].text) for d in vl.render(graph).block] == [("a", "2"), ("p", "1")]


def test_set_override_changes_the_render_without_a_reload() -> None:
    source = Counting({"main.conf": "set $a 1;\nx $a;\n"})
    graph = vl.Processor(source=source).load("main.conf")
    graph.set_override("a", "2 3")
    override = graph.variables("a")[1]
    assert [a.text for a in vl.render(graph).block[0].values] == ["2", "3"]
    graph.set_override("a", None)
    assert [a.text for a in vl.render(graph).block[0].values] == ["1"]
    graph.set_override("a", "4")
    assert graph.variables("a")[1] is override  # D28: one variable per name for the graph's life
    assert dict(graph.overrides) == {"a": "4"}
    with pytest.raises(vl.BadTextError) as raised:
        graph.set_override("a", '"\\q"')
    assert [d.code for d in raised.value.diagnostics] == ["E4003"]
    with pytest.raises(ValueError, match="letters, digits"):
        graph.set_override("a-b", "1")
    assert source.reads == ["main.conf"]


def test_a_rendered_directive_is_a_copy_of_one_written_directive_handle() -> None:
    files = {"main.conf": 'a { include "p.conf"; }\nb { include "p.conf"; }\n', "p.conf": "x 1;\n"}
    graph = vl.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf")
    rendered = vl.render(graph)
    x1, x2 = (d for d in rendered.walk() if d.name == "x")
    assert x1.written is x2.written is graph.documents["p.conf"].block[0]
    assert len(x1.written.copies()) == 2


def test_an_unreadable_names_the_statement_that_could_not_be_read() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "a $nope;\n"})).load("main.conf")
    [unreadable] = vl.render(graph).unreadable
    assert unreadable.written is graph.root.block[0]


def test_load_of_an_unreadable_root_raises_read_error_a_diagnostic_error() -> None:
    with pytest.raises(vl.ReadError) as raised:
        vl.Processor(source=vl.memory_source({})).load("missing.conf")
    assert isinstance(raised.value, vl.DiagnosticError)
    assert raised.value.diagnostic.code == "E3004"


def test_format_diagnostic_prints_the_documents_current_text() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "a $x;\n"})).load("main.conf")
    graph.root.block.insert_statements(0, "b;")
    [d] = vl.render(graph).diagnostics
    assert vl.format_diagnostic(d, graph).split("\n")[1:] == ["a $x;", "  ^^"]


def test_an_argument_links_its_line_its_definition_and_its_chain() -> None:
    graph = load({"main.conf": "set $l [1, 2];\nx $l 3;\ny $h;\n"}, {"h": "4"})
    x, y = vl.render(graph).block
    listed, three = x.values
    reference = directive(graph.root.block[1]).values[0]
    assert listed.written is reference and listed.chain[0].reference is reference
    assert listed.definition is graph.root.block[0].values[0]  # type: ignore[union-attr]
    assert [item.written for item in listed.as_list()] == [reference, reference]  # items share their list's $name
    assert three.written is three.definition is directive(graph.root.block[1]).values[1] and three.chain == ()
    [four] = y.values
    assert four.definition is None and four.written is directive(graph.root.block[2]).values[0]


# --- one check of an override (spec 6.3) ---


@pytest.mark.parametrize(
    ("text", "code", "column"),
    [("1;", "E2001", 1), ("", "E2001", 0), ("$x", "E2001", 0), ("1\n2", "E2001", 0), ('"\\q"', "E4003", 0)],
)
def test_load_and_set_override_refuse_an_override_text_alike(text: str, code: str, column: int) -> None:
    with pytest.raises(vl.BadTextError) as by_load:
        load({"main.conf": "x $a;\n"}, {"a": text})
    graph = load({"main.conf": "x $a;\n"})
    with pytest.raises(vl.BadTextError) as by_setter:
        graph.set_override("a", text)
    found = [[(d.code, d.span.start) for d in e.value.diagnostics] for e in (by_load, by_setter)]
    assert found[0] == found[1]
    assert [(c, start.column) for c, start in found[0]] == [(code, column)]
    assert graph.overrides == {}


def test_load_refuses_an_override_text_followed_by_a_semicolon() -> None:
    with pytest.raises(vl.BadTextError) as raised:
        load({"main.conf": "x $a;\n"}, {"a": "1;"})
    [d] = raised.value.diagnostics
    assert (d.code, d.span.start.line, d.span.start.column) == ("E2001", 0, 1)


# --- edits take text only (spec 6.9) ---

NOT_TEXT = [2400, None, ["1"]]


@pytest.mark.parametrize("value", NOT_TEXT, ids=["number", "none", "list"])
def test_every_edit_that_takes_text_raises_type_error_for_anything_else_and_changes_nothing(value: object) -> None:
    graph = load({"main.conf": "set $a 1;\nx 1 { y; }\nuse s 1;\n"})
    set_line, x, use = graph.root.block
    assert isinstance(set_line, vl.SetLine) and isinstance(x, vl.WrittenDirective) and isinstance(use, vl.UseLine)
    block = x.block
    assert block is not None
    calls: dict[str, list[Callable[[], object]]] = {
        "set": [lambda: x.set(value), lambda: set_line.set(value), lambda: use.set(value)],  # type: ignore[arg-type]
        "replace_with_text": [
            lambda: x.replace_with_text(value),  # type: ignore[arg-type]
            lambda: x.values[0].replace_with_text(value),  # type: ignore[arg-type]
            lambda: graph.root.replace_with_text(value),  # type: ignore[arg-type]
        ],
        "insert_statements": [lambda: block.insert_statements(0, value)],  # type: ignore[arg-type]
        "add_statements": [lambda: block.add_statements(value)],  # type: ignore[arg-type]
        "rename": [lambda: x.rename(value), lambda: set_line.variable.rename(value)],  # type: ignore[arg-type]
        "quote": [lambda: vl.quote(value)],  # type: ignore[arg-type]
    }
    calls["set"].append(lambda: set_line.variable.set(value))  # type: ignore[arg-type]
    for member, made in calls.items():
        parameter = "name" if member == "rename" else "text"
        for call in made:
            with pytest.raises(TypeError) as raised:
                call()
            got = type(value).__name__
            assert str(raised.value) == (
                f"{member}() argument '{parameter}' must be str, not {got}; "
                "villanelle edits take text: quote() a program string, str() a number"
            )
    assert graph.root.text == "set $a 1;\nx 1 { y; }\nuse s 1;\n"


@pytest.mark.parametrize("value", [2400, ["1"]], ids=["number", "list"])
def test_set_override_and_load_raise_type_error_for_an_override_that_is_not_text(value: object) -> None:
    graph = load({"main.conf": "x $a;\n"})
    with pytest.raises(TypeError, match=r"^set_override\(\) argument 'text' must be str"):
        graph.set_override("a", value)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^set_override\(\) argument 'name' must be str"):
        graph.set_override(value, "1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="^" + re.escape("load() argument 'overrides[\"a\"]' must be str")):
        load({"main.conf": "x $a;\n"}, {"a": value})  # type: ignore[dict-item]


def test_load_raises_type_error_for_an_override_of_none() -> None:
    message = "load() argument 'overrides[\"a\"]' must be str, not NoneType"
    with pytest.raises(TypeError, match="^" + re.escape(message)):
        load({"main.conf": "x $a;\n"}, {"a": None})  # type: ignore[dict-item]


def test_a_detached_handle_raises_detached_error_before_the_type_check() -> None:
    graph = load({"main.conf": "x 1;\n"})
    x = directive(graph.root.block[0])
    x.remove()
    with pytest.raises(vl.DetachedError):
        x.set(2400)  # type: ignore[arg-type]
