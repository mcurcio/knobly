"""The low level's documents, handles, edits, save and reads (slices.md S3: C4, C7; and the units S1's and S2's
criteria name: identity, detaching, comment ownership, refused edits, save, read, set_override, written)."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import assert_never

import pytest
from conftest import REPO

import villanelle as vl
from villanelle import written
from villanelle.include import include


def load(files: Mapping[str, str], overrides: Mapping[str, vl.ConfigText] | None = None) -> vl.DocumentGraph:
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

    def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        return self.inner.read(resolved_path)


def directive(statement: vl.Statement) -> vl.WrittenDirective:
    assert isinstance(statement, vl.WrittenDirective)
    return statement


# --- documents and handles ---


def test_keeps_one_handle_per_statement_and_value_across_an_edit_elsewhere_in_the_file() -> None:
    graph = load({"main.conf": "@set $a 1;\nb 2 3;\nc { d 4; }\n"})
    body = graph.root.block
    set_line, b, c = body
    assert isinstance(set_line, vl.SetLine)
    two, three = directive(b).values
    c_block = directive(c).block
    assert c_block is not None
    d = c_block[0]
    set_line.set(vl.text("100 200"))
    assert graph.root.text == "@set $a 100 200;\nb 2 3;\nc { d 4; }\n"
    assert body[0] is set_line and body[1] is b
    assert directive(b).values[0] is two and directive(b).values[1] is three
    assert c_block[0] is d
    assert [b.text, two.text, three.text, d.text, set_line.text] == ["b 2 3;", "2", "3", "d 4;", "@set $a 100 200;"]
    assert set_line.variable is graph.variables("a")[0]
    assert b.place.span.start == vl.SourcePosition(17, 1, 0)


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
    [made] = value.replace_with_text(vl.text("2"))
    assert made.text == "2"
    assert value.kind == "word"
    with pytest.raises(vl.DetachedError):
        _ = value.text
    with pytest.raises(vl.DetachedError):
        value.replace_with_text(vl.text("3"))


def test_owns_the_comment_lines_directly_above_a_statement_and_its_trailing_comment() -> None:
    graph = load({"main.conf": "# far\n\n# near\n  b 2; # end\nc;\n"})
    b = graph.root.block[0]
    assert b.text == "# near\n  b 2; # end"
    assert (b.place.span.start.line, b.place.span.start.column) == (2, 0)
    b.remove()
    assert graph.root.text == "# far\n\nc;\n"


def test_changes_nothing_when_an_edit_is_refused() -> None:
    graph = load({"main.conf": "@set $a 1;\nx [1];\n"})
    set_line = graph.root.block[0]
    assert isinstance(set_line, vl.SetLine)
    for text in ["1; x", "{", "", '"open']:
        with pytest.raises(vl.BadTextError):
            set_line.set(vl.text(text))
        assert graph.root.text == "@set $a 1;\nx [1];\n"
    assert set_line.text == "@set $a 1;"
    with pytest.raises(IndexError):
        graph.root.block.insert_statements(3, vl.text("y;"))
    with pytest.raises(vl.BadTextError):
        graph.root.block.add_statements(vl.text("@set $a 2;"))  # E5002: a second `set` of $a in one block
    assert graph.root.text == "@set $a 1;\nx [1];\n"


ABSENT: dict[type, tuple[str, ...]] = {
    vl.WrittenDirective: ("variable", "parameters", "snippet_name", "snippet", "snippets"),
    vl.ExtensionLine: ("rename", "variable", "parameters", "snippet_name", "snippet", "snippets"),
    vl.SetLine: ("name", "block", "rename", "parameters", "snippet_name", "snippet", "snippets"),
    vl.SnippetLine: ("values", "rename", "set", "variable", "snippet_name", "snippet", "snippets"),
    vl.UseLine: ("name", "block", "rename", "variable", "parameters"),
    vl.UnreadableLine: ("name", "values", "block", "rename", "set", "variable", "parameters", "snippet_name"),
    vl.SetVariable: (),
    vl.Parameter: ("set",),
    vl.OverrideVariable: ("place", "line", "rename", "set"),
    written.Word: ("items", "name", "start", "end", "index", "declaration", "resolutions"),
    written.String: ("items", "name", "start", "end", "index", "declaration", "resolutions"),
    written.List: ("name", "start", "end", "index", "declaration", "resolutions"),
    written.Slice: ("items", "index", "declaration", "resolutions"),
    written.Index: ("items", "start", "end", "declaration", "resolutions"),
    written.Reference: ("items", "start", "end", "index"),
}
"""frozen-m2.md section 2: the members each variant does not have (a call is an AttributeError, like any missing
attribute; nothing raises a villanelle error for it)."""


@pytest.mark.parametrize("cls", list(ABSENT), ids=lambda cls: cls.__name__)
def test_an_operation_exists_only_on_the_variants_where_it_can_succeed(cls: type) -> None:
    assert [name for name in ABSENT[cls] if hasattr(cls, name)] == []


def test_set_and_rename_on_a_parameter_or_an_override_are_attribute_errors() -> None:
    graph = load({"main.conf": "@snippet s $p { x $p; }\n@use s 1;\n"}, {"h": vl.text("1")})
    parameter, override = graph.variables()
    assert isinstance(parameter, vl.Parameter) and isinstance(override, vl.OverrideVariable)
    assert (parameter.kind, override.kind) == (vl.VariableKind.PARAMETER, vl.VariableKind.OVERRIDE)
    with pytest.raises(AttributeError):
        parameter.set("2")  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        override.rename("g")  # type: ignore[attr-defined]
    assert graph.root.text == "@snippet s $p { x $p; }\n@use s 1;\n"


def test_an_include_line_is_an_extension_line_without_rename() -> None:
    graph = load({"main.conf": '@include "p.conf";\nx 1;\n', "p.conf": ""})
    line, x = graph.root.block
    assert isinstance(line, vl.ExtensionLine) and not isinstance(line, vl.WrittenDirective)
    assert (line.kind, line.name, [v.text for v in line.values]) == ("extension", "include", ['"p.conf"'])
    assert graph.root.block.directives() == (x,)
    line.set(vl.text('"q.conf"'))
    assert graph.root.text == '@include "q.conf";\nx 1;\n'


# --- Python idioms (C4) ---


def describe(statement: vl.Statement) -> str:
    match statement:
        case vl.WrittenDirective(name, values, block):
            return f"directive {name} {len(values)} {block is not None}"
        case vl.ExtensionLine(name, values, _):
            return f"extension {name} {values[0].text}"
        case vl.SetLine(variable, values):
            return f"set ${variable.name} {len(values)}"
        case vl.SnippetLine(name, parameters, block):
            return f"snippet {name} {len(parameters)} {len(block)}"
        case vl.UseLine(snippet_name, values):
            return f"use {snippet_name} {len(values)}"
        case vl.UnreadableLine(text):
            return f"unreadable {text}"
        case _:
            assert_never(statement)


def value_kind(value: vl.WrittenValue) -> str:
    match value:
        case written.Word(text) | written.String(text):
            return f"{value.kind} {text}"
        case written.List(items):
            return f"list of {len(items)}"
        case written.Slice(name, start, end):
            return f"slice {name.text} {start is not None} {end is not None}"
        case written.Index(name, index):
            return f"index {name.text}[{index.text}]"
        case written.Reference(name):
            return f"reference {name}"
        case _:
            assert_never(value)


def test_match_narrows_every_kind_and_a_block_is_a_sequence_of_the_same_handles() -> None:
    text = '@include "p.conf";\n@set $a 1;\n@snippet s { y; }\n@use s;\nx w "s" [1, 2] c[1~2] c[0] $a;\nz x"y";\n'
    graph = load({"main.conf": text, "p.conf": ""})
    body = graph.root.block
    assert [describe(s) for s in body] == [
        'extension include "p.conf"',
        "set $a 1",
        "snippet s 0 1",
        "use s 0",
        "directive x 6 False",
        'unreadable z x"y";',
    ]
    x = directive(body[4])
    assert [value_kind(v) for v in x.values] == [
        "word w",
        'string "s"',
        "list of 2",
        "slice c True True",
        "index c[0]",
        "reference a",
    ]
    assert isinstance(body[0], vl.Statement) and isinstance(x.values[0], vl.WrittenValue)
    assert all(isinstance(v, vl.Variable) for v in graph.variables())
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
    text = "@snippet s $a {\n    x {\n        @set $a 1;\n        y $a;\n    }\n    z $a;\n}\n@use s 2;\n@use s 3;\n"
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
    graph.root.replace_with_text(vl.text("b 2;\n"))
    assert graph.root.saved_text == "a 1;\n"
    with pytest.raises(vl.DetachedError):
        _ = a.text
    writer = Recorder()
    assert graph.save(writer) == ["main.conf"]
    assert writer.batches == [[vl.FileWrite("main.conf", "b 2;\n", "a 1;\n")]]


def test_save_hands_only_changed_files_to_the_writer_in_one_call_then_updates_saved_text() -> None:
    graph = load({"main.conf": '@include "p.conf";\nx 1;\n', "p.conf": "y 2;\n"})
    writer = Recorder()
    assert graph.save(writer) == []
    assert writer.batches == []
    p = graph.documents["p.conf"]
    directive(p.block[0]).values[0].replace_with_text(vl.text("3"))
    assert graph.save(writer) == ["p.conf"]
    assert writer.batches == [[vl.FileWrite("p.conf", "y 3;\n", "y 2;\n")]]
    assert p.saved_text == "y 3;\n"
    assert graph.save(writer) == []
    assert len(writer.batches) == 1


def test_save_raises_save_error_from_the_writers_error_and_changes_no_saved_text() -> None:
    graph = load({"main.conf": "x 1;\n"})
    directive(graph.root.block[0]).values[0].replace_with_text(vl.text("2"))
    cause = OSError("disk full")

    class Failing:
        def write(self, files: Sequence[vl.FileWrite], /) -> None:
            raise cause

    with pytest.raises(vl.SaveError) as raised:
        graph.save(Failing())
    assert raised.value.paths == ("main.conf",)
    assert raised.value.__cause__ is cause
    assert graph.root.saved_text == "x 1;\n"
    assert graph.root.text != graph.root.saved_text


def test_the_readme_example_sets_values_from_program_data_as_text() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "host a;\nport 80;\n"})).load("main.conf")
    host, port = graph.root.block
    host.set(vl.quote("10.0.60.31"))  # type: ignore[union-attr]
    port.set(vl.text(str(8080)))  # type: ignore[union-attr]
    assert graph.root.text == 'host "10.0.60.31";\nport 8080;\n'


def test_quote_writes_a_plain_string_as_the_canonical_villanelle_string() -> None:
    assert vl.quote('10.0.60.31 "x"\n') == '"10.0.60.31 \\"x\\"\\n"'


# --- reads, overrides, the rendered tree's written handles ---


def test_an_added_include_stays_unread_until_read_which_reads_it_once_and_keeps_every_other_text() -> None:
    source = Counting({"main.conf": "a 1;\n", "part.conf": "p 1;\n"})
    graph = vl.Processor(source=source, extensions=[include()]).load("main.conf")
    directive(graph.root.block[0]).values[0].replace_with_text(vl.text("2"))
    [added] = graph.root.block.add_statements(vl.text('@include "part.conf";'))
    assert [e.copy.statement for e in graph.unread()] == [added]
    unread = vl.render(graph)
    assert [d.name for d in unread.block] == ["a"]
    match unread.unreadable:
        case (vl.UnreadableExpansion(vl.UnreadableReason.UNREAD, line),):
            assert line is added
        case _:
            pytest.fail("no unread copy")
    assert [(str(d.code), str(d.place)) for d in graph.diagnostics] == [("E3007", "main.conf:2:1")]
    assert unread.diagnostics == graph.diagnostics
    assert graph.read() == ["part.conf"]
    assert graph.read() == []
    assert source.reads == ["main.conf", "part.conf"]
    assert graph.unread() == ()
    assert graph.diagnostics == ()
    assert graph.root.text == 'a 2;\n@include "part.conf";\n'
    assert [(d.name, d.values[0].text) for d in vl.render(graph).block] == [("a", "2"), ("p", "1")]


def test_set_override_changes_the_render_without_a_reload() -> None:
    source = Counting({"main.conf": "@set $a 1;\nx $a;\n"})
    graph = vl.Processor(source=source).load("main.conf")
    graph.set_override("a", vl.text("2 3"))
    override = graph.variables("a")[1]
    assert [a.text for a in vl.render(graph).block[0].values] == ["2", "3"]
    graph.set_override("a", None)
    assert [a.text for a in vl.render(graph).block[0].values] == ["1"]
    graph.set_override("a", vl.text("4"))
    assert graph.variables("a")[1] is override  # D28: one variable per name for the graph's life
    assert dict(graph.overrides) == {"a": "4"}
    with pytest.raises(vl.BadTextError) as raised:
        graph.set_override("a", vl.text('"\\q"'))
    assert [d.code for d in raised.value.diagnostics] == ["E1005"]
    with pytest.raises(ValueError, match="letters, digits"):
        graph.set_override("a-b", vl.text("1"))
    assert source.reads == ["main.conf"]


def test_a_rendered_directive_is_a_copy_of_one_written_directive_handle() -> None:
    files = {"main.conf": 'a { @include "p.conf"; }\nb { @include "p.conf"; }\n', "p.conf": "x 1;\n"}
    graph = vl.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf")
    rendered = vl.render(graph)
    x1, x2 = (d for d in rendered.walk() if d.name == "x")
    assert x1.written is x2.written is graph.documents["p.conf"].block[0]
    assert len(x1.written.copies()) == 2


def test_an_unreadable_names_the_statement_that_could_not_be_read() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "a $nope;\n"})).load("main.conf")
    [unreadable] = vl.render(graph).unreadable
    assert unreadable.written is graph.root.block[0]


def test_load_of_an_unreadable_root_raises_read_error_with_its_path_and_no_diagnostic() -> None:
    with pytest.raises(vl.ReadError) as raised:
        vl.Processor(source=vl.memory_source({})).load("missing.conf")
    assert not isinstance(raised.value, vl.DiagnosticError)
    assert raised.value.paths == ("missing.conf",)
    assert not hasattr(raised.value, "diagnostic")


def test_format_diagnostic_prints_the_documents_current_text() -> None:
    graph = vl.Processor(source=vl.memory_source({"main.conf": "a $x;\n"})).load("main.conf")
    graph.root.block.insert_statements(0, vl.text("b;"))
    [d] = vl.render(graph).diagnostics
    assert vl.format_diagnostic(d, graph).split("\n")[1:] == ["a $x;", "  ^^"]


def test_an_expanded_value_links_its_line_its_definition_and_its_chain() -> None:
    graph = load({"main.conf": "@set $l [1, 2];\nx $l 3;\ny $h;\n"}, {"h": vl.text("4")})
    x, y = vl.render(graph).block
    listed, three = x.values
    reference = directive(graph.root.block[1]).values[0]
    assert listed.written is reference and listed.chain[0].reference is reference
    assert listed.definition is graph.root.block[0].values[0]  # type: ignore[union-attr]
    assert [item.written for item in listed.list()] == [reference, reference]  # items share their list's $name
    assert three.written is three.definition is directive(graph.root.block[1]).values[1] and three.chain == ()
    [four] = y.values
    assert four.definition is None and four.written is directive(graph.root.block[2]).values[0]


# --- one check of an override (spec 6.3) ---


@pytest.mark.parametrize(
    ("text", "code", "column"),
    [("1;", "E2001", 1), ("", "E2001", 0), ("$x", "E2001", 0), ("1 # c", "E2001", 5), ('"\\q"', "E1005", 0)],
)
def test_load_and_set_override_refuse_an_override_text_alike(text: str, code: str, column: int) -> None:
    with pytest.raises(vl.BadTextError) as by_load:
        load({"main.conf": "x $a;\n"}, {"a": vl.text(text)})
    graph = load({"main.conf": "x $a;\n"})
    with pytest.raises(vl.BadTextError) as by_setter:
        graph.set_override("a", vl.text(text))
    found = [[(d.code, d.span.start) for d in e.value.diagnostics] for e in (by_load, by_setter)]
    assert found[0] == found[1]
    assert [(c, start.column) for c, start in found[0]] == [(code, column)]
    assert graph.overrides == {}


def test_load_refuses_an_override_text_followed_by_a_semicolon() -> None:
    with pytest.raises(vl.BadTextError) as raised:
        load({"main.conf": "x $a;\n"}, {"a": vl.text("1;")})
    [d] = raised.value.diagnostics
    assert (d.code, d.span.start.line, d.span.start.column) == ("E2001", 0, 1)


# --- edits take text only (spec 6.9) ---

NOT_TEXT = [2400, None, ["1"]]


@pytest.mark.parametrize("value", NOT_TEXT, ids=["number", "none", "list"])
def test_every_edit_that_takes_text_raises_type_error_for_anything_else_and_changes_nothing(value: object) -> None:
    graph = load({"main.conf": "@set $a 1;\nx 1 { y; }\n@use s 1;\n"})
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
                "villanelle edits take config text: quote() a program string, text() one already written as villanelle "
                "text, str() a number first"
            )
    assert graph.root.text == "@set $a 1;\nx 1 { y; }\n@use s 1;\n"


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


# --- a line break in a values text is whitespace (vil-umh.1) ---


def test_set_writes_a_values_text_with_a_line_break_as_one_statement() -> None:
    graph = load({"main.conf": "port 80;\n"})
    port = directive(graph.root.block[0])
    port.set(vl.text("1\n2"))
    assert graph.root.text == "port 1\n2;\n"
    assert [v.text for v in directive(graph.root.block[0]).values] == ["1", "2"]


def test_an_override_with_a_line_break_is_two_values() -> None:
    graph = load({"main.conf": "x $a;\n"}, {"a": vl.text("1\n2")})
    assert [v.text for v in vl.render(graph).block[0].values] == ["1", "2"]


# --- the error classes (spec/contract.md 4) ---


@pytest.mark.parametrize(
    ("cls", "bases"),
    [
        (vl.DiagnosticError, (vl.VillanelleError,)),
        (vl.ReadError, (vl.VillanelleError,)),
        (vl.BadTextError, (vl.VillanelleError,)),
        (vl.SaveError, (vl.VillanelleError,)),
        (vl.LostUpdateError, (vl.SaveError,)),
        (vl.DetachedError, (ReferenceError,)),
        (vl.VillanelleError, (Exception,)),
    ],
)
def test_the_error_classes_sit_on_the_two_sorts_as_the_contract_draws_the_tree(
    cls: type, bases: tuple[type, ...]
) -> None:
    assert cls.__bases__ == bases


def test_villanelle_error_catches_every_expected_outcome_and_no_program_bug() -> None:
    assert not issubclass(vl.DetachedError, vl.VillanelleError)
    assert not issubclass(vl.BadTextError, ValueError)
    assert not hasattr(vl, "EditError")


def test_a_detached_error_is_a_program_bug_and_reading_a_property_raises_it() -> None:
    graph = load({"main.conf": "x 1;\n"})
    x = directive(graph.root.block[0])
    x.remove()
    with pytest.raises(vl.DetachedError) as raised:
        _ = x.name
    assert isinstance(raised.value, ReferenceError)
    assert not isinstance(raised.value, vl.VillanelleError | ValueError)
    assert x.kind is vl.StatementKind.DIRECTIVE


def test_a_bad_text_errors_message_is_built_from_its_diagnostics() -> None:
    graph = load({"main.conf": "port 80;\n"})
    with pytest.raises(vl.BadTextError) as raised:
        directive(graph.root.block[0]).set(vl.text("1;"))
    [d] = raised.value.diagnostics
    assert str(raised.value) == f"bad text: 1:2: E2001: {d.message}"
    assert d.message == 'unexpected token: ";"'


# --- every bad name is a misuse error, through one check per kind of name (vil-umh.7) ---


@pytest.mark.parametrize("name", ["a-b", "", "$a", "a b"])
def test_every_bad_variable_name_is_a_value_error_from_load_set_override_and_rename(name: str) -> None:
    graph = load({"main.conf": "@set $a 1;\n@snippet s $p { x $p; }\nx $a;\n"})
    set_line, snippet = graph.root.block[0], graph.root.block[1]
    assert isinstance(set_line, vl.SetLine) and isinstance(snippet, vl.SnippetLine)
    calls: list[Callable[[], object]] = [
        lambda: load({"main.conf": "x $a;\n"}, {name: vl.text("1")}),
        lambda: graph.set_override(name, vl.text("1")),
        lambda: graph.set_override(name, None),
        lambda: set_line.variable.rename(name),
        lambda: snippet.parameters[0].rename(name),
    ]
    for call in calls:
        with pytest.raises(ValueError, match="letters, digits and _"):
            call()
    assert graph.root.text == "@set $a 1;\n@snippet s $p { x $p; }\nx $a;\n"


@pytest.mark.parametrize("name", ["0x", "-x", "a b", "", "@set", "@include", "@x", "x;"])
def test_every_bad_directive_name_is_a_value_error(name: str) -> None:
    graph = load({"main.conf": "rate 20;\n"})
    with pytest.raises(ValueError) as raised:
        directive(graph.root.block[0]).rename(name)
    assert not isinstance(raised.value, vl.VillanelleError)
    assert graph.root.text == "rate 20;\n"


@pytest.mark.parametrize("name", ["set", "snippet", "use", "include"])
def test_no_directive_name_is_reserved_so_a_rename_to_a_keyword_word_keeps_it_a_directive(name: str) -> None:
    graph = load({"main.conf": "rate 20;\n"})
    rate = directive(graph.root.block[0])
    rate.rename(name)
    assert graph.root.text == f"{name} 20;\n"
    assert graph.root.block[0] is rate and isinstance(rate, vl.WrittenDirective)


def test_a_variable_rename_that_collides_with_a_set_stays_a_bad_text_error() -> None:
    graph = load({"main.conf": "@set $a 1;\n@set $b 2;\n"})
    second = graph.root.block[1]
    assert isinstance(second, vl.SetLine)
    with pytest.raises(vl.BadTextError) as raised:
        second.variable.rename("a")
    assert [d.code for d in raised.value.diagnostics] == ["E5002"]


@pytest.mark.parametrize("writer", [lambda files: None, object(), None])
def test_save_raises_type_error_for_anything_but_a_document_writer_before_anything(writer: object) -> None:
    graph = load({"main.conf": "x 1;\n"})
    directive(graph.root.block[0]).set(vl.text("2"))
    got = type(writer).__name__
    message = f"save() argument 'writer' must be a document writer (an object with a write method), not {got}"
    with pytest.raises(TypeError) as raised:
        graph.save(writer)  # type: ignore[arg-type]
    assert str(raised.value) == message
    assert graph.root.saved_text == "x 1;\n"


# --- the memory adapters (spec/contract.md 5) ---


def test_a_memory_writer_saves_into_the_map_a_memory_source_reads() -> None:
    files = {"main.conf": "x 1;\n"}
    processor = vl.Processor(source=vl.memory_source(files))
    graph = processor.load("main.conf")
    directive(graph.root.block[0]).set(vl.text("2"))
    assert graph.save(vl.memory_writer(files)) == ["main.conf"]
    assert files == {"main.conf": "x 2;\n"}
    assert graph.root.saved_text == "x 2;\n"
    assert processor.load("main.conf").root.text == "x 2;\n"


def test_a_memory_writer_refuses_a_lost_update_and_writes_nothing() -> None:
    files = {"main.conf": '@include "a.conf";\n', "a.conf": "y 1;\n"}
    graph = load(files)
    graph.root.replace_with_text(vl.text('@include "a.conf";\nz;\n'))
    directive(graph.documents["a.conf"].block[0]).set(vl.text("2"))
    files["a.conf"] = "y 9;\n"  # changed by someone else since the load
    with pytest.raises(vl.LostUpdateError) as raised:
        graph.save(vl.memory_writer(files))
    assert raised.value.paths == ("a.conf",)  # only the conflicting file
    assert raised.value.__cause__ is None
    assert str(raised.value) == "lost update: changed since read: a.conf"
    assert files == {"main.conf": '@include "a.conf";\n', "a.conf": "y 9;\n"}
    assert graph.root.saved_text == '@include "a.conf";\n'


def test_check_lost_updates_reads_an_absent_file_as_empty_and_names_each_conflict_in_batch_order() -> None:
    batch = [vl.FileWrite("a", "1", "old"), vl.FileWrite("b", "2", ""), vl.FileWrite("c", "3", "c")]
    vl.check_lost_updates(batch, ["old", None, "c"])
    with pytest.raises(vl.LostUpdateError) as raised:
        vl.check_lost_updates(batch, ["new", "x", None])
    assert raised.value.paths == ("a", "b", "c")


def test_check_lost_updates_refuses_a_current_list_not_as_long_as_the_batch_as_misuse() -> None:
    with pytest.raises(ValueError, match="1 files but 0 current texts"):
        vl.check_lost_updates([vl.FileWrite("a", "1", "")], [])


def test_save_raises_a_program_writers_lost_update_error_as_it_is() -> None:
    graph = load({"main.conf": "x 1;\n"})
    directive(graph.root.block[0]).set(vl.text("2"))
    lost = vl.LostUpdateError(["main.conf"])

    class Checking:
        def write(self, files: Sequence[vl.FileWrite], /) -> None:
            raise lost

    with pytest.raises(vl.LostUpdateError) as raised:
        graph.save(Checking())
    assert raised.value is lost


def test_a_memory_source_reads_its_map_at_every_call() -> None:
    files = {"main.conf": "x 1;\n"}
    processor = vl.Processor(source=vl.memory_source(files))
    files["main.conf"] = "x 2;\n"
    assert processor.load("main.conf").root.text == "x 2;\n"


# --- insert before and after ---


def test_insert_before_and_after_go_into_the_statements_own_block() -> None:
    graph = load({"main.conf": "a 1;\nblk {\n    b 2;\n}\n"})
    a, blk = graph.root.block
    inner = directive(blk).block
    assert inner is not None
    [b] = inner
    assert [s.text for s in b.insert_after(vl.text("c 3;"))] == ["c 3;"]
    assert [s.text for s in a.insert_before(vl.text("z;"))] == ["z;"]
    assert graph.root.text == "z;\na 1;\nblk {\n    b 2;\n    c 3;\n}\n"
    with pytest.raises(TypeError, match=r"^insert_before\(\) argument 'text' must be str, not int"):
        a.insert_before(1)  # type: ignore[arg-type]


# --- the expansion the rendered layer builds on (spec 6.10) ---


def test_expand_gives_every_copy_with_its_values_links_and_what_could_not_be_read() -> None:
    graph = load({"main.conf": "@set $l [1, 2];\nx $l { y 3; $bad; }\nz $nope;\n"})
    expansion = graph.expand()
    [x] = expansion.block
    match x:
        case vl.DirectiveExpansion(statement, [value], block):
            assert statement is graph.root.block[1]
            assert value.text == "[1, 2]" and isinstance(value, vl.ExpandedList)
            assert [i.text for i in value.items] == ["1", "2"]
            assert value.written.text == "$l" and value.definition is not None and value.definition.text == "[1, 2]"
            assert [r.reference.text for r in value.chain] == ["$l"]
            assert block is not None and [d.written.name for d in block] == ["y"]
        case _:
            pytest.fail("no match")
    assert [(u.reason, u.written.text) for u in x.unreadable] == [("syntax", "$bad;")]
    match expansion.unreadable:
        case (vl.UnreadableExpansion(reason, line),):
            assert (reason, line.text) == ("expansion", "z $nope;")
        case _:
            pytest.fail("no match")
    assert expansion.diagnostics == vl.render(graph).diagnostics == graph.diagnostics
    assert "E5001" in [str(d.code) for d in graph.diagnostics]


def test_a_rendered_directive_holds_its_expansions_own_values_and_unreadables() -> None:
    graph = load({"main.conf": "x 1 [2] { $bad; }\n"})
    [expanded] = graph.expand().block
    [rendered] = vl.render(graph).block
    assert rendered.written is expanded.written
    assert [v.text for v in rendered.values] == [v.text for v in expanded.values]
    assert [type(v) for v in rendered.values] == [vl.ExpandedWord, vl.ExpandedList]
    assert [(u.reason, u.written) for u in rendered.unreadable] == [(u.reason, u.written) for u in expanded.unreadable]
    assert all(isinstance(u, vl.UnreadableExpansion) for u in rendered.unreadable)


def test_expanded_values_are_equal_by_text_across_renders_and_written_values_by_identity() -> None:
    files = {"main.conf": 'port 8080;\nhost 8080;\nname "8080";\n'}
    graph = load(files)
    first, second = vl.render(graph), vl.render(load(files))
    a, b = first.block[0].values[0], second.block[0].values[0]
    assert a is not b and a == b and hash(a) == hash(b)
    assert first.block[1].values[0] == a  # the same text from another line
    assert first.block[2].values[0] != a  # "8080" is a string: its text has the quotes
    assert len({a, b}) == 1
    assert a != "8080"  # an expanded value is never equal to a str
    w1, w2 = (directive(s).values[0] for s in graph.root.block[:2])
    assert w1 != w2 and w1.text == w2.text


def test_list_items_have_one_shape_in_both_layers() -> None:
    graph = load({"main.conf": "x [1, [2]];\n"})
    written_list = directive(graph.root.block[0]).values[0]
    expanded = vl.render(graph).block[0].values[0]
    assert isinstance(written_list, written.List) and isinstance(expanded, vl.ExpandedList)
    assert isinstance(written_list.items, tuple) and isinstance(expanded.items, tuple)
    assert [i.text for i in written_list.items] == [i.text for i in expanded.items] == ["1", "[2]"]
    assert expanded.list() == expanded.items
    assert [type(i) for i in expanded.items] == [vl.ExpandedWord, vl.ExpandedList]


# --- kinds, match and the union aliases (frozen-m2.md 1, 13) ---


def test_match_works_on_every_variable_variant_and_each_union_alias_is_an_isinstance_check() -> None:
    graph = load({"main.conf": "@set $a 1;\n@snippet s $p { x $p; }\n@use s $a;\n"}, {"h": vl.text("2")})
    names = []
    for variable in graph.variables():
        match variable:
            case vl.SetVariable(name) | vl.Parameter(name) | vl.OverrideVariable(name):
                names.append((variable.kind.value, name))
    assert names == [("set", "a"), ("parameter", "p"), ("override", "h")]
    rendered = vl.render(graph)
    value = rendered.block[0].values[0]
    assert isinstance(value, vl.ExpandedWord)
    assert isinstance(value.origin.place, vl.Place) and value.origin.place.kind is vl.PlaceKind.FILE
    assert vl.Override("h").kind is vl.PlaceKind.OVERRIDE
    after = vl.render(load({"main.conf": "@set $a 1;\n@snippet s $p { x $p; y; }\n@use s $a;\n"}))
    [change] = rendered.diff(after)
    assert isinstance(change, vl.Change) and change.kind is vl.ChangeKind.ADDED
    match change:
        case vl.Added(address, directive_after):
            assert (str(address), directive_after.name) == ("y", "y")
        case _:
            pytest.fail("no match")


def test_a_diagnostic_prints_its_people_form() -> None:
    [d] = vl.parse("x ]\n").diagnostics
    assert str(d) == f"1:3: E2004: {d.message}"


# --- a written value's set keeps its handle (milestone 5, vil-umh.12; spec 6.1) ---


def test_a_value_set_keeps_the_handle_and_reassigns_its_class_to_the_new_kind() -> None:
    graph = load({"main.conf": "port 80 [1, 2] c[1~2];\n"})
    port = directive(graph.root.block[0])
    eighty, items, sliced = port.values
    assert isinstance(items, written.List) and isinstance(sliced, written.Slice)
    old_items = items.items
    old_bounds = (sliced.name, sliced.start, sliced.end)
    eighty.set(vl.text("8080"))
    assert isinstance(eighty, written.Word) and eighty.text == "8080"
    eighty.set(vl.text("[3, 4]"))
    assert isinstance(eighty, written.List) and eighty.kind == "list"
    match eighty:
        case written.List([written.Word("3"), written.Word("4")]):
            pass
        case _:
            pytest.fail("no match")
    items.set(vl.text("$x"))
    assert isinstance(items, written.Reference) and items.name == "x"
    assert all(item._detached for item in old_items)
    sliced.set(vl.text('"s"'))
    assert isinstance(sliced, written.String)
    assert all(part is not None and part._detached for part in old_bounds)
    assert port.values == (eighty, items, sliced)
    assert graph.root.text == 'port [3, 4] $x "s";\n'


def test_a_value_set_takes_exactly_one_value_and_each_part_its_entry_rule() -> None:
    graph = load({"main.conf": "x [1, 2] $s[$i~3];\n"})
    x = directive(graph.root.block[0])
    items, sliced = x.values
    assert isinstance(items, written.List) and isinstance(sliced, written.Slice)
    one = items.items[0]
    for bad, column in [("1 2", 2), ("", 0), ("1;", 1), ("1 # c", 5)]:
        with pytest.raises(vl.BadTextError) as raised:
            one.set(vl.text(bad))
        assert [(d.code, d.span.start.column) for d in raised.value.diagnostics] == [("E2001", column)]
    name, end = sliced.name, sliced.end
    assert isinstance(name, written.Reference) and end is not None
    with pytest.raises(vl.BadTextError):
        end.set(vl.text("x"))  # a bound takes boundText: an integer word or a $name
    with pytest.raises(vl.BadTextError):
        name.set(vl.text("[1]"))  # a slice's name takes sliceNameText: a word or a $name
    name.set(vl.text("leds"))
    end.set(vl.text("$n"))
    assert isinstance(name, written.Word) and isinstance(end, written.Reference)
    assert sliced.name is name and sliced.end is end
    assert graph.root.text == "x [1, 2] leds[$i~$n];\n"


def test_two_rendered_copies_of_one_line_share_the_written_value_and_both_can_set_it() -> None:
    files = {"main.conf": 'a { @include "p.conf"; }\nb { @include "p.conf"; }\n', "p.conf": "@set $v 1;\nn $v;\n"}
    graph = load(files)
    values = [d.values[0] for d in vl.render(graph).walk() if d.name == "n"]
    assert len(values) == 2 and values[0].written is values[1].written
    for value in values:
        value.written.set(vl.text("2"))
    assert graph.documents["p.conf"].text == "@set $v 1;\nn 2;\n"


def test_a_slice_name_is_a_written_value_and_a_variable_reference() -> None:
    graph = load({"main.conf": "@set $s leds;\nx $s[0~3] b[$s];\n"})
    x = directive(graph.root.block[1])
    sliced, index = x.values
    match sliced:
        case written.Slice(written.Reference("s"), written.Word("0"), written.Word("3")):
            pass
        case _:
            pytest.fail("no match")
    assert isinstance(index, written.Index) and isinstance(index.name, written.Word)
    [variable] = graph.variables("s")
    assert [r.place.span.start.column for r in variable.references()] == [2, 12]
    name = sliced.name
    assert isinstance(name, written.Reference) and name.declaration is variable
    assert x.values[0] is sliced  # the slice keeps its start; its name is reached as slice.name


# --- config text, its own type (milestone 5, vil-umh.6; spec 6.9) ---


def test_config_text_is_made_by_quote_or_text_and_a_plain_str_is_a_type_error() -> None:
    graph = load({"main.conf": "port 80;\n"})
    port = directive(graph.root.block[0])
    # mypy strict (warn_unused_ignores) fails the build if a plain str stops being a type error here.
    port.set("8080")  # type: ignore[arg-type]
    port.set(vl.text("8081"))
    port.set(vl.quote("h"))
    assert graph.root.text == 'port "h";\n'
    assert vl.text("1 2") == "1 2" and vl.quote('a"b') == '"a\\"b"'
    with pytest.raises(TypeError, match=r"^text\(\) argument 'raw' must be str, not int; villanelle edits take config"):
        vl.text(1)  # type: ignore[arg-type]


# --- the milestone 4 leftovers (spec 2.8, 7.0) ---


@pytest.mark.parametrize("text", ["# c\n", "\n", "  "])
def test_a_statement_set_with_a_text_that_holds_no_value_must_be_given_empty_text(text: str) -> None:
    graph = load({"main.conf": "a 1;\n@set $v 2;\n"})
    a, set_line = graph.root.block
    assert isinstance(set_line, vl.SetLine)
    for statement in (directive(a), set_line):
        with pytest.raises(vl.BadTextError) as raised:
            statement.set(vl.text(text))
        assert [(d.code, d.span.start.line, d.span.start.column) for d in raised.value.diagnostics] == [("E2001", 0, 0)]
    with pytest.raises(vl.BadTextError) as raised:
        set_line.set(vl.text(""))
    assert [d.code for d in raised.value.diagnostics] == ["E5009"]
    directive(a).set(vl.text(""))
    assert graph.root.text == "a;\n@set $v 2;\n"


def test_render_of_anything_but_a_document_graph_is_the_argument_type_error() -> None:
    graph = load({"main.conf": "a 1;\n"})
    for given, got in [(graph.root, "Document"), (graph.root.block[0], "WrittenDirective"), (None, "NoneType")]:
        with pytest.raises(TypeError) as raised:
            vl.render(given)  # type: ignore[arg-type]
        assert str(raised.value) == (
            f"render() argument 'graph' must be a document graph (an object with an expand method), not {got}"
        )
