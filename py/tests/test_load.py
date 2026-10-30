"""The load and render layers through their public API (round 11 slices.md §1.2, S3 criteria 2, 3, 6, 7, 8; round
12: ``render(load(...))``, the key rule at ``addresses()`` and ``diff``): every test loads text through ``Processor``
and ``memory_source``."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import cast

import pytest

import villanelle as vl
from villanelle import rendered, written
from villanelle.include import include as include_extension


def processor(files: Mapping[str, str], *, include: bool = False) -> written.Processor:
    extensions = [include_extension()] if include else []
    return written.Processor(source=vl.memory_source(files), extensions=extensions)


def load_and_render(
    p: written.Processor, path: str = "main.conf", *, overrides: Mapping[str, vl.ConfigText] | None = None
) -> rendered.Rendered:
    """``render(load(path))``: the mechanical form of a PR 3 load (D8)."""
    return rendered.render(p.load(path, overrides=overrides))


def load(text: str, *, overrides: Mapping[str, vl.ConfigText] | None = None) -> rendered.Rendered:
    return load_and_render(processor({"main.conf": text}), overrides=overrides)


def inner(loaded: rendered.Rendered) -> rendered.Directive:
    """The first directive inside the first top-level directive's block."""
    body = loaded.block[0].block
    assert body
    return body[0]


def codes(loaded: rendered.Rendered) -> list[str]:
    return [str(d.code) for d in loaded.diagnostics]


def at(d: vl.LocatedDiagnostic) -> tuple[int, int]:
    return d.place.span.start.line, d.place.span.start.column


def names(loaded: rendered.Rendered) -> list[str]:
    addresses = loaded.addresses()
    return [str(addresses[d]) for d in loaded.block.walk()]


def texts(directive: rendered.Directive) -> list[str]:
    return [a.text for a in directive.values]


# --- the directive tree ------------------------------------------------------------------------------------------


def test_gives_args_in_written_order_without_spaces_comments_or_punctuation() -> None:
    loaded = load('listen 80 "a b" c[1~2] [x, # note\n  y];\nend;\n')
    assert codes(loaded) == []
    listen, end = loaded.block
    assert texts(listen) == ["80", '"a b"', "c[1~2]", "[x, y]"]
    assert [a.kind for a in listen.values] == ["word", "string", "slice", "list"]
    assert end.name == "end"
    assert end.values == ()


def test_body_is_none_without_a_block_and_a_list_value_is_not_a_body() -> None:
    loaded = load("a [1, 2];\nb {}\nc { d; }\n")
    a, b, c = loaded.block
    assert a.block is None
    assert b.block is not None and list(b.block) == []
    assert c.block is not None
    assert [d.name for d in c.block] == ["d"]
    assert c.block[0].parent is c
    assert a.parent is None


def test_walk_is_depth_first_in_written_order_and_descend_false_passes_over_a_block() -> None:
    loaded = load("http {\n  server { listen 80; location { root x; } }\n  server { listen 443; }\n}\nevents;\n")
    assert names(loaded) == [
        "http",
        "http > server",
        "http > server > listen",
        "http > server > location",
        "http > server > location > root",
        "http > server #1",
        "http > server #1 > listen",
        "events",
    ]
    skipped = [d.name for d in loaded.block.walk(descend=lambda d: d.name != "server")]
    assert skipped == ["http", "server", "server", "events"]
    http = loaded.block[0]
    assert http.block is not None
    assert [d.name for d in http.block.walk()] == ["server", "listen", "location", "root", "server", "listen"]


def test_directive_matches_by_name_values_and_block() -> None:
    loaded = load("graph { node DdpSink leds 1 { max_count 4; } }\n")
    graph = loaded.block[0]
    assert graph.block is not None
    match graph.block[0]:
        case rendered.Directive("node", [kind, node_id, *rest], block):
            assert (kind.text, node_id.text, [r.text for r in rest]) == ("DdpSink", "leds", ["1"])
            assert block is not None
            assert [d.name for d in block] == ["max_count"]
        case _:
            pytest.fail("no match")
    match graph.block[0].values[0]:
        case written.ExpandedWord("DdpSink"):
            pass
        case _:
            pytest.fail("no match")


def test_closest_finds_this_or_the_nearest_enclosing_match() -> None:
    loaded = load("graph { node a { connect b { x; } } }\n")
    x = next(d for d in loaded.block.walk() if d.name == "x")
    node = x.closest(lambda d: d.name == "node")
    assert node is not None
    assert node.name == "node"
    assert x.closest(lambda d: d.name == "x") is x
    assert x.closest(lambda d: d.name == "nothing") is None


def test_a_syntax_error_keeps_its_siblings_and_stands_as_an_unreadable_in_place() -> None:
    loaded = load('a 1;\nb x"y";\nc 2;\n')
    assert [d.name for d in loaded.block] == ["a", "c"]
    [bad] = loaded.unreadable
    assert bad.reason is written.UnreadableReason.SYNTAX
    assert bad.written.kind == "unreadable"
    assert bad.written.text == 'b x"y";'
    assert codes(loaded) == ["E2009"]


def test_the_root_origin_is_the_root_file_at_0_0() -> None:
    loaded = load("a;\n")
    assert loaded.origin.place.resolved_path == "main.conf"
    assert loaded.origin.place.span.start == loaded.origin.place.span.end == vl.SourcePosition(0, 0, 0)
    assert loaded.graph.root.resolved_path == "main.conf"


def test_the_root_is_resolved_through_the_source_so_it_has_one_path_and_is_read_once() -> None:
    reads: list[str] = []
    files = {"d/main.conf": 'x 1;\n@include "main.conf";\ny 1;\n'}
    memory = vl.memory_source(files)

    class Counting:
        def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
            return memory.resolve(spec, context)

        def read(self, resolved_path: str, /) -> str:
            reads.append(resolved_path)
            return memory.read(resolved_path)

    loaded = load_and_render(
        written.Processor(source=Counting(), extensions=[include_extension()]), "./d/../d/main.conf"
    )
    assert reads == ["d/main.conf"]
    assert list(loaded.graph.documents) == ["d/main.conf"]
    assert codes(loaded) == ["E5006"]
    assert names(loaded) == ["x", "y"]


def test_a_root_the_source_cannot_resolve_to_one_file_raises_read_error_with_the_path_as_written() -> None:
    glob = processor({"a.conf": "", "b.conf": ""})
    for path in ["*.conf", "missing.conf"]:
        with pytest.raises(vl.ReadError) as raised:
            glob.load(path)
        # No diagnostic and no code (spec/contract.md 4.1): a missing root is not an extension line's E3004.
        assert raised.value.paths == (path,)
        assert raised.value.__cause__ is None
        assert not isinstance(raised.value, vl.DiagnosticError)


def test_a_root_the_source_cannot_read_raises_read_error_from_the_sources_failure() -> None:
    class Failing:
        def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
            return (spec,)

        def read(self, resolved_path: str, /) -> str:
            raise PermissionError(resolved_path)

    with pytest.raises(vl.ReadError) as raised:
        written.Processor(source=Failing()).load("main.conf")
    assert raised.value.paths == ("main.conf",)
    assert isinstance(raised.value.__cause__, PermissionError)


# --- rule 1: extension names (spec 2.5, 5) -----------------------------------------------------------------------


class _Named:
    def __init__(self, directive: str) -> None:
        self.directive = directive

    def specs(self, use: written.ExtensionUse, /) -> tuple[str, ...]:
        return ()


@pytest.mark.parametrize("names", [["set"], ["snippet"], ["use"], ["include", "include"]])
def test_the_processor_refuses_an_extension_named_set_snippet_or_use_or_two_of_one_name(names: list[str]) -> None:
    with pytest.raises(ValueError, match="name taken"):
        written.Processor(source=vl.memory_source({}), extensions=[_Named(name) for name in names])


@pytest.mark.parametrize("name", ["@include", "a b", "1x", "-x", ""])
def test_the_processor_refuses_an_extension_name_the_name_text_entry_rule_refuses(name: str) -> None:
    with pytest.raises(ValueError, match="not a directive name"):
        written.Processor(source=vl.memory_source({}), extensions=[_Named(name)])


def test_at_statements_never_reach_the_body_and_an_at_name_no_extension_owns_is_e3008() -> None:
    files = {"main.conf": '@set $a 1;\n@snippet s { x $a; }\nblk { @use s; }\n@include "p.conf";\n', "p.conf": "y;\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert codes(loaded) == []
    assert names(loaded) == ["blk", "blk > x", "y"]
    unowned = load_and_render(processor(files), "main.conf")
    assert names(unowned) == ["blk", "blk > x"]
    assert codes(unowned) == ["E3008"]
    assert at(unowned.diagnostics[0]) == (3, 0)
    assert [u.reason for u in unowned.unreadable] == ["extension"]


def test_no_directive_name_is_reserved() -> None:
    loaded = load_and_render(
        processor({"main.conf": "events { use epoll; set x; snippet y; include z; }\n"}, include=True)
    )
    assert codes(loaded) == []
    assert names(loaded) == ["events", "events > use", "events > set", "events > snippet", "events > include"]


@pytest.mark.parametrize(
    ("directive", "error"),
    [(5, TypeError), ("1x", ValueError), ("@x", ValueError), ("a b", ValueError), ("set", ValueError)],
)
def test_make_processor_checks_an_extension_name_type_then_word_then_reserved(directive: object, error: type) -> None:
    with pytest.raises(error):
        written.Processor(source=vl.memory_source({}), extensions=[_Named(cast("str", directive))])


def test_make_processor_refuses_a_non_text_extension_name_with_the_argument_type_error() -> None:
    with pytest.raises(TypeError, match="argument 'directive' must be str, not int"):
        written.Processor(source=vl.memory_source({}), extensions=[_Named(cast("str", 5))])


# --- rule 2: set -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("line", ["@set;", "@set x 1;", "@set $a;", "@set $a 1 { b; }", '@set "$a" 1;', "@set [$a] 1;"])
def test_any_other_set_form_is_e5009_at_set(line: str) -> None:
    loaded = load(f"ok;\n{line}\n")
    assert codes(loaded) == ["E5009"]
    assert at(loaded.diagnostics[0]) == (1, 0)
    assert [u.reason for u in loaded.unreadable] == ["expansion"]
    assert [d.name for d in loaded.block] == ["ok"]


def test_set_binds_from_its_line_to_the_end_of_its_block_and_copies_another_variable() -> None:
    loaded = load("before $a;\n@set $a 1 2;\n@set $b $a x;\nblk { inner $b; }\n")
    assert codes(loaded) == ["E5001"]
    assert [d.name for d in loaded.block] == ["blk"]
    assert texts(inner(loaded)) == ["1", "2", "x"]


def test_values_keep_their_kinds_through_a_variable() -> None:
    loaded = load('@set $v w "s" c[1~2] c[3] [1, 2];\nx $v;\n')
    assert [a.kind for a in loaded.block[0].values] == ["word", "string", "slice", "index", "list"]


# --- rule 3: overrides ------------------------------------------------------------------------------------------


def test_an_override_wins_over_every_set_of_its_name_and_is_visible_everywhere() -> None:
    loaded = load('@set $host "a";\nblk { @set $host "b"; target $host; }\n', overrides={"host": vl.text("h1 h2")})
    assert codes(loaded) == []
    target = inner(loaded)
    assert texts(target) == ["h1", "h2"]
    assert target.values[0].origin.place == vl.Override("host")


@pytest.mark.parametrize("name", ["", "a-b", "$a", "a b", "é"])
def test_a_bad_override_name_raises_value_error(name: str) -> None:
    with pytest.raises(ValueError, match="letters, digits and _"):
        load("x;\n", overrides={name: vl.text("1")})


@pytest.mark.parametrize("text", ["", "   ", 'x"y"', "$other", "1; y 2", "1 { a; }", '"\\q"', "c[a:1]", "1 # c"])
def test_an_override_text_that_is_not_one_run_of_values_raises_bad_text_error(text: str) -> None:
    with pytest.raises(vl.BadTextError, match=r"^bad text: 1:\d+: E\d{4}: "):
        load("x;\n", overrides={"v": vl.text(text)})


# --- rule 4: $name -----------------------------------------------------------------------------------------------


def test_a_variable_becomes_all_its_values_in_a_directive_and_in_a_list() -> None:
    loaded = load("@set $ports 8080 443;\nport $ports dev;\nallow [$ports, 1];\n")
    port, allow = loaded.block
    assert texts(port) == ["8080", "443", "dev"]
    assert [a.text for a in allow.values[0].list()] == ["8080", "443", "1"]


def test_an_override_slice_bound_that_is_not_an_integer_is_e4001_at_the_name_that_used_it() -> None:
    loaded = load("ok 1;\na c[0~$n];\n", overrides={"n": vl.text("x1")})
    assert codes(loaded) == ["E4001"]
    d = loaded.diagnostics[0]
    assert (d.place.resolved_path, at(d), d.via) == ("main.conf", (1, 6), ())
    assert [u.reason for u in loaded.unreadable] == ["value"]


def test_a_variable_slice_bound_must_hold_one_integer_word() -> None:
    loaded = load("@set $n 3;\n@set $two 1 2;\na c[$n~] c[~$n] c[$n];\nb c[$two];\n")
    assert texts(loaded.block[0]) == ["c[3~]", "c[~3]", "c[3]"]
    assert codes(loaded) == ["E4001"]
    assert [u.reason for u in loaded.unreadable] == ["value"]


def test_an_unknown_variable_is_e5001_at_the_name_and_its_directive_is_unreadable() -> None:
    loaded = load("graph {\n  leds { max_count $pixel; }\n}\n")
    [d] = loaded.diagnostics
    assert (d.code, at(d)) == ("E5001", (1, 19))
    leds = inner(loaded)
    assert leds.block is not None and list(leds.block) == []
    assert [u.reason for u in leds.unreadable] == ["expansion"]


def test_a_variable_value_has_its_set_place_and_the_variable_step() -> None:
    loaded = load("@set $pixels 2284;\ngraph {\n  node DdpSink leds { max_count $pixels; }\n}\n")
    value = next(d for d in loaded.block.walk() if d.name == "max_count").values[0]
    assert value.text == "2284"
    assert isinstance(value.origin.place, vl.Place)
    assert value.origin.place.span.start == vl.SourcePosition(13, 0, 13)
    [step] = value.origin.via
    start = step.place.span.start
    assert (step.kind, step.name, start.line, start.column) == ("variable", "pixels", 2, 32)


# --- rules 5 and 6: snippet and use ------------------------------------------------------------------------------


def test_use_splices_the_body_with_parameters_bound_and_a_use_step() -> None:
    loaded = load("@snippet t $src $n {\n  connect $src;\n  count $n;\n}\nnode a { @use t rgb 3; }\n")
    assert codes(loaded) == []
    assert names(loaded) == ["node", "node > connect", "node > count"]
    connect = inner(loaded)
    assert [(s.kind, s.name) for s in connect.origin.via] == [("use", "t")]
    assert [(s.kind, s.name) for s in connect.values[0].origin.via] == [("variable", "src"), ("use", "t")]


def test_a_snippet_body_sees_its_definition_scope_not_the_use_site() -> None:
    loaded = load("@set $c red;\n@snippet s { color $c; }\nblk { @set $c blue; @use s; }\n")
    assert texts(inner(loaded)) == ["red"]


def test_a_snippet_body_exports_nothing_and_snippets_are_their_own_namespace() -> None:
    loaded = load("@snippet universe { @set $x 1; @snippet inner { y; } a $x; }\n@use universe;\nuniverse 2;\nb $x;\n")
    assert [d.name for d in loaded.block] == ["a", "universe"]
    assert codes(loaded) == ["E5001"]


@pytest.mark.parametrize(
    ("text", "code", "where"),
    [
        ("@use nothing;\n", "E5003", (0, 5)),
        ("@snippet s $a { x $a; }\n@use s;\n", "E5004", (1, 0)),
        ("@snippet s $a { x $a; }\n@use s 1 2;\n", "E5004", (1, 0)),
        ("@snippet s { x; }\n@snippet s { y; }\n", "E5005", (1, 9)),
        ("@snippet s $a $a { x; }\n", "E5010", (0, 0)),
        ("@snippet s a { x; }\n", "E5010", (0, 0)),
        ("@snippet s;\n", "E5010", (0, 0)),
        ('@snippet "s" { x; }\n', "E5010", (0, 0)),
        ("@snippet s { x; }\n@use s { y; }\n", "E5011", (1, 0)),
        ("@use;\n", "E5011", (0, 0)),
        ("@snippet s $a { @set $a 2; x $a; }\n@use s 1;\n", "E5002", (0, 21)),
    ],
)
def test_snippet_and_use_errors(text: str, code: str, where: tuple[int, int]) -> None:
    loaded = load(text)
    assert codes(loaded) == [code]
    assert at(loaded.diagnostics[0]) == where


def test_a_snippet_defined_in_an_inner_block_is_not_visible_after_it() -> None:
    loaded = load("blk { @snippet s { x; } @use s; }\n@use s;\n")
    assert names(loaded) == ["blk", "blk > x"]
    assert codes(loaded) == ["E5003"]


# --- rules 7 and 8: extensions -----------------------------------------------------------------------------------


def test_an_included_files_top_level_set_and_snippet_are_visible_after_the_include_line() -> None:
    files = {"main.conf": '@include "lib.conf";\nport $p;\n@use s;\n', "lib.conf": "@set $p 80;\n@snippet s { x; }\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert codes(loaded) == []
    assert names(loaded) == ["port", "x"]


def test_an_extension_block_set_wins_inside_the_spliced_files_only() -> None:
    files = {
        "main.conf": '@include "sink.conf" { @set $host h1; @set $two $host; }\nafter $host;\n',
        "sink.conf": "@set $host h0;\ntarget $host $two;\n",
    }
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert codes(loaded) == []
    target, after = loaded.block
    assert texts(target) == ["h1", "h1"]
    assert texts(after) == ["h0"]


def test_an_include_whose_block_holds_a_syntax_error_is_unreadable_and_reported_once_by_the_parser() -> None:
    files = {"main.conf": '@include "lib.conf" {\n  @set $v x"y";\n}\nz;\n', "lib.conf": "l;\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert codes(loaded) == ["E2009"]
    assert [u.reason for u in loaded.unreadable] == ["syntax"]
    assert names(loaded) == ["z"]


def test_an_extension_block_holds_only_set_lines() -> None:
    files = {"main.conf": '@include "p.conf" {\n  @set $a 1;\n  x 2;\n}\nok;\n', "p.conf": "y;\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert codes(loaded) == ["E5012"]
    assert at(loaded.diagnostics[0]) == (2, 2)
    assert [u.reason for u in loaded.unreadable] == ["extension"]
    assert [d.name for d in loaded.block] == ["ok"]


@pytest.mark.parametrize(
    ("line", "code", "where"),
    [
        ("@include;", "E3005", (0, 0)),
        ("@include p.conf;", "E3005", (0, 9)),
        ('@include "p.conf" "q.conf";', "E3005", (0, 18)),
        ('@include "p.conf" "q.conf" x;', "E3005", (0, 18)),
        ('@include "nope.conf";', "E3001", (0, 0)),
    ],
)
def test_include_errors(line: str, code: str, where: tuple[int, int]) -> None:
    loaded = load_and_render(processor({"main.conf": f"{line}\n", "p.conf": "y;\n"}, include=True), "main.conf")
    assert codes(loaded) == [code]
    assert at(loaded.diagnostics[0]) == where
    assert [u.reason for u in loaded.unreadable] == ["extension"]


def test_memory_source_joins_to_the_parents_directory_and_removes_dot_dot_segments() -> None:
    source = vl.memory_source({"x.conf": "", "../y.conf": ""})
    assert source.resolve("../x.conf", vl.LoadContext("a/b.conf")) == ("x.conf",)
    assert source.resolve("../../y.conf", vl.LoadContext("a/b.conf")) == ("../y.conf",)
    assert source.resolve("./x.conf", vl.LoadContext("")) == ("x.conf",)


def test_an_include_glob_splices_matches_in_code_point_order() -> None:
    files = {"main.conf": '@include "d/*.conf";\n', "d/b.conf": "b;\n", "d/B.conf": "B;\n", "d/a.conf": "a;\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert [d.name for d in loaded.block] == ["B", "a", "b"]
    assert list(loaded.graph.documents) == ["main.conf", "d/B.conf", "d/a.conf", "d/b.conf"]


class _Counting:
    def __init__(self, files: Mapping[str, str], *, resolve_fails: str = "", read_fails: str = "") -> None:
        self.inner = vl.memory_source(files)
        self.reads: list[str] = []
        self.resolve_fails = resolve_fails
        self.read_fails = read_fails

    def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
        if spec == self.resolve_fails:
            raise OSError("resolve failed")
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        if resolved_path == self.read_fails:
            raise OSError("read failed")
        return self.inner.read(resolved_path)


def test_a_file_included_at_two_places_is_read_once_held_once_and_has_two_edges() -> None:
    source = _Counting({"main.conf": 'a { @include "p.conf"; }\nb { @include "p.conf"; }\n', "p.conf": "x;\n"})
    loaded = load_and_render(written.Processor(source=source, extensions=[include_extension()]), "main.conf")
    assert source.reads == ["main.conf", "p.conf"]
    assert list(loaded.graph.documents) == ["main.conf", "p.conf"]
    assert [(e.copy.statement.text, e.specs, e.targets) for e in loaded.graph.edges()] == [
        ('@include "p.conf";', ("p.conf",), ("p.conf",)),
        ('@include "p.conf";', ("p.conf",), ("p.conf",)),
    ]
    assert names(loaded) == ["a", "a > x", "b", "b > x"]


def test_a_source_that_raises_gives_e3004_at_the_extension_directive_and_a_failed_read_is_not_retried() -> None:
    main = '@include "r.conf";\n@include "p.conf";\n@include "p.conf";\nok;\n'
    source = _Counting({"main.conf": main, "p.conf": ""}, resolve_fails="r.conf", read_fails="p.conf")
    loaded = load_and_render(written.Processor(source=source, extensions=[include_extension()]), "main.conf")
    assert codes(loaded) == ["E3004", "E3004", "E3004"]
    assert [at(d) for d in loaded.diagnostics] == [(0, 0), (1, 0), (2, 0)]
    assert source.reads == ["main.conf", "p.conf"]
    assert [d.name for d in loaded.block] == ["ok"]


def test_an_extension_that_raises_something_else_is_e3006() -> None:
    class Broken:
        directive = "broken"

        def specs(self, use: written.ExtensionUse, /) -> tuple[str, ...]:
            raise RuntimeError("boom")

    loaded = load_and_render(
        written.Processor(source=vl.memory_source({"main.conf": "@broken 1;\n"}), extensions=[Broken()])
    )
    assert codes(loaded) == ["E3006"]


@pytest.mark.parametrize("result", ["dark.conf", None, ["a", 1], 3])
def test_an_extension_whose_specs_are_not_a_tuple_of_str_is_e3006_at_the_directive(result: object) -> None:
    class Bare:
        directive = "theme"

        def specs(self, use: written.ExtensionUse, /) -> tuple[str, ...]:
            return result  # type: ignore[return-value]

    files = {"main.conf": "ok;\n@theme 1;\n", "dark.conf": "x;\n"}
    loaded = load_and_render(written.Processor(source=vl.memory_source(files), extensions=[Bare()]))
    assert codes(loaded) == ["E3006"]
    assert at(loaded.diagnostics[0]) == (1, 0)
    assert "specs() must return a tuple of str" in loaded.diagnostics[0].message
    assert [d.name for d in loaded.block] == ["ok"]


class _Bare:
    """A source whose ``resolve`` returns a bare str for one spec (a str is a sequence of one-letter strs)."""

    def __init__(self, files: Mapping[str, str], bare: str) -> None:
        self.inner = vl.memory_source(files)
        self.bare = bare

    def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
        if spec == self.bare:
            return spec  # type: ignore[return-value]
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        return self.inner.read(resolved_path)


def test_a_source_whose_resolve_returns_a_bare_str_is_e3004_or_a_read_error_for_the_root() -> None:
    files = {"main.conf": '@include "p";\nok;\n', "p": "x;\n"}
    loaded = load_and_render(written.Processor(source=_Bare(files, "p"), extensions=[include_extension()]))
    assert codes(loaded) == ["E3004"]
    assert "resolve() must return a tuple of str, not str" in loaded.diagnostics[0].message
    with pytest.raises(vl.ReadError) as raised:
        written.Processor(source=_Bare(files, "main.conf")).load("main.conf")
    assert isinstance(raised.value.__cause__, TypeError)


def test_a_source_whose_read_returns_anything_but_a_str_is_e3004() -> None:
    class Bytes:
        def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
            return (spec,)

        def read(self, resolved_path: str, /) -> str:
            return '@include "p";\n' if resolved_path == "main.conf" else b"x;"  # type: ignore[return-value]

    loaded = load_and_render(written.Processor(source=Bytes(), extensions=[include_extension()]))
    assert codes(loaded) == ["E3004"]
    assert "read() must return a str, not bytes" in loaded.diagnostics[0].message


# --- rule 9: limits and cycles -----------------------------------------------------------------------------------


def nested_snippets(depth: int) -> str:
    """``use s1`` opens ``depth`` snippets, one inside the other."""
    lines = [f"@snippet s{i} {{ @use s{i + 1}; }}" for i in range(1, depth)]
    return "\n".join([*lines, f"@snippet s{depth} {{ leaf; }}", "@use s1;", ""])


def test_sixteen_nested_places_are_allowed_and_the_seventeenth_is_e5007() -> None:
    assert codes(load(nested_snippets(16))) == []
    assert names(load(nested_snippets(16))) == ["leaf"]
    loaded = load(nested_snippets(17))
    assert codes(loaded) == ["E5007"]
    assert len(loaded.diagnostics[0].via) == 16


def test_a_use_that_reaches_itself_is_e5006_at_the_use_that_closes_the_cycle() -> None:
    loaded = load("@snippet a { @use b; }\n@snippet b { @use a; }\n@use a;\nz;\n")
    assert codes(loaded) == ["E5006"]
    assert at(loaded.diagnostics[0]) == (1, 13)
    assert [d.name for d in loaded.block] == ["z"]


def test_more_than_100000_directives_is_e5008_and_expansion_stops() -> None:
    fan = "\n".join(f"@snippet f{i} {{ {' '.join([f'@use f{i - 1};'] * 10)} }}" for i in range(2, 6))
    loaded = load(f"@snippet f1 {{ {'x; ' * 10}}}\n{fan}\n@use f5;\nextra;\nnever;\n")
    assert codes(loaded) == ["E5008"]
    assert at(loaded.diagnostics[0]) == (6, 0)
    assert len(loaded.block) == 100_000
    assert [u.reason for u in loaded.unreadable] == ["expansion"]


# --- rule 10: value rules at load --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["a c[99999999999999999999];", "@set $n x;\na c[$n~2];", "@set $n 1 2;\na c[$n];"], ids=["long", "x", "two"]
)
def test_a_value_rule_broken_at_load_makes_the_directive_unreadable(text: str) -> None:
    loaded = load(f"{text}\nok;\n")
    assert codes(loaded) == ["E4001"]
    assert [u.reason for u in loaded.unreadable] == ["value"]
    assert [d.name for d in loaded.block] == ["ok"]


@pytest.mark.parametrize(
    ("text", "code"), [("a c[x~2];", "E2007"), ("a c[1.5];", "E2007"), ("a c[1:2];", "E2007"), ('a "\\q";', "E1005")]
)
def test_a_literal_bound_that_is_not_an_integer_and_a_bad_escape_are_syntax_errors(text: str, code: str) -> None:
    loaded = load(f"{text}\nok;\n")
    assert codes(loaded) == [code]
    assert [u.reason for u in loaded.unreadable] == ["syntax"]
    assert [d.name for d in loaded.block] == ["ok"]


def test_an_override_with_a_literal_bound_beyond_the_integer_range_is_e4001_where_it_is_read() -> None:
    loaded = load("ok;\nx $n;\n", overrides={"n": vl.text("c[99999999999999999999]")})
    assert codes(loaded) == ["E4001"]
    assert at(loaded.diagnostics[0]) == (1, 2)
    assert [d.name for d in loaded.block] == ["ok"]


# --- rule 12: diagnostics order ----------------------------------------------------------------------------------


def test_syntax_diagnostics_of_every_file_come_first_then_load_diagnostics() -> None:
    files = {"main.conf": 'a $x;\n@include "p.conf";\nb x"y";\n', "p.conf": "c $y;\nd x'z';\n"}
    loaded = load_and_render(processor(files, include=True), "main.conf")
    assert [(str(d.code), d.place.resolved_path) for d in loaded.diagnostics] == [
        ("E2009", "main.conf"),
        ("E2009", "p.conf"),
        ("E5001", "main.conf"),
        ("E5001", "p.conf"),
    ]


# --- addresses and the key rule (criterion 7) --------------------------------------------------------------------


def test_address_text_people_form_and_parent() -> None:
    loaded = load('g {\n  n a;\n  n b;\n  m;\n  n "é";\n}\n')
    addresses = loaded.addresses(key=lambda d: d.values[0].text if d.name == "n" else None)
    g = loaded.block[0]
    assert g.block is not None
    _n_a, n_b, m, n_e = g.block
    assert addresses[n_b].text == '[["g",null,0],["n","b",0]]'
    assert str(addresses[n_b]) == 'g > n "b"'
    assert addresses[n_e].text == '[["g",null,0],["n","\\"é\\"",0]]'
    assert addresses[n_b].parent == addresses[g]
    assert addresses[g].parent is None
    assert str(addresses[m]) == "g > m"
    assert len(set(addresses.values())) == 5
    assert list(addresses) == list(loaded.block.walk())


def test_occurrence_counts_earlier_siblings_with_the_same_name_and_key() -> None:
    loaded = load("a 1;\nb;\na 1;\na 2;\nb;\n")
    addresses = loaded.addresses(key=lambda d: d.values[0].text if d.values else None)
    assert [str(addresses[d]) for d in loaded.block] == ['a "1"', "b", 'a "1" #1', 'a "2"', "b #1"]


def test_without_a_key_rule_a_directive_is_named_by_its_position_among_same_name_siblings() -> None:
    loaded = load("a 1;\nb;\na 2;\n")
    assert [str(a) for a in loaded.addresses().values()] == ["a", "b", "a #1"]


def test_the_key_rule_sees_the_rendered_directive_parents_first() -> None:
    seen: list[tuple[str, list[str], bool, str | None]] = []

    def key(d: rendered.Directive) -> str | None:
        parent = None if d.parent is None else d.parent.name
        seen.append((d.name, [a.text for a in d.values], d.block is not None, parent))
        return None

    load("@set $id leds;\ngraph {\n  node K $id { x; }\n}\n").addresses(key=key)
    assert seen == [("graph", [], True, None), ("node", ["K", "leds"], True, "graph"), ("x", [], False, "node")]


def test_an_exception_from_the_key_rule_propagates_from_addresses_and_diff() -> None:
    def key(d: rendered.Directive) -> str | None:
        raise LookupError("bad key")

    p = processor({"main.conf": "a;\n"})
    first = load_and_render(p)
    with pytest.raises(LookupError, match="bad key"):
        first.addresses(key=key)
    with pytest.raises(LookupError, match="bad key"):
        first.diff(load_and_render(p), key=key)


@pytest.mark.parametrize("returned", [1, b"a", ["a"]])
def test_a_key_rule_returning_anything_but_a_str_or_none_raises_type_error(returned: object) -> None:
    p = processor({"main.conf": "a;\n"})
    first = load_and_render(p)
    key = cast("rendered.KeyRule", lambda d: returned)
    with pytest.raises(TypeError, match="key rule"):
        first.addresses(key=key)
    with pytest.raises(TypeError, match="key rule"):
        first.diff(load_and_render(p), key=key)


# --- diff (criterion 6) ------------------------------------------------------------------------------------------


def kinds(changes: Sequence[rendered.Change]) -> list[tuple[str, str]]:
    return [(type(c).__name__.lower(), str(c.address)) for c in changes]


class _Swap:
    """A source whose text changes between two loads of one processor."""

    def __init__(self, text: str) -> None:
        self.text = text

    def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
        return (spec,)

    def read(self, resolved_path: str, /) -> str:
        return self.text


def changes(
    before: str, after: str, key: Callable[[rendered.Directive], str | None] | None = None
) -> list[tuple[str, str]]:
    source = _Swap(before)
    p = written.Processor(source=source)
    first = load_and_render(p)
    source.text = after
    return kinds(first.diff(load_and_render(p), key=key))


def test_diff_lists_added_removed_and_changed_by_values_and_by_having_a_block() -> None:
    before = "a 1;\nb 1;\nc;\nd { e; }\n"
    after = "a 2;\nc {}\nd { e; f; }\ng;\n"
    assert changes(before, after) == [
        ("removed", "b"),
        ("changed", "a"),
        ("changed", "c"),
        ("added", "d > f"),
        ("added", "g"),
    ]


def test_diff_lists_an_added_or_removed_subtree_once() -> None:
    assert changes("a { b { c; } }\n", "x { y; }\n") == [("removed", "a"), ("added", "x")]


def test_a_directive_missing_beside_an_unreadable_statement_is_unknown_not_removed() -> None:
    assert changes("g {\n  a 1;\n  b 2;\n}\nz;\n", 'g {\n  a 1;\n  b x"y";\n}\n') == [
        ("unknown", "g > b"),
        ("removed", "z"),
    ]
    assert changes("a;\nb;\n", 'a;\nb x"y";\n') == [("unknown", "b")]


def test_diff_compares_canonical_texts_not_the_written_form() -> None:
    assert changes("a 'x' [1, # c\n 2,];\n", 'a "x" [1, 2];\n') == []
    assert changes("a 0.5;\n", "a 0.50;\n") == [("changed", "a")]


def test_diff_names_directives_by_the_key_rule_it_is_given() -> None:
    def key(d: rendered.Directive) -> str | None:
        return d.values[0].text if d.name == "n" else None

    assert changes("n a 1;\nn b 2;\n", "n b 2;\nn a 1;\n", key=key) == []
    assert changes("n a 1;\nn b 2;\n", "n b 2;\nn a 1;\n") == [("changed", "n"), ("changed", "n #1")]


def test_diff_accepts_loads_with_diagnostics() -> None:
    assert changes("a $x;\nb;\n", "a $x;\nb 1;\n") == [("changed", "b")]


def test_render_builds_on_the_graphs_public_members_only() -> None:
    # vil-9fy (spec 7.0): render reads graph.expand() and graph.root.resolved_path, nothing private, so any object
    # with those members renders the same tree.
    graph = processor({"main.conf": "@set $a 1;\nx $a { y; }\n"}).load("main.conf")

    class StandIn:
        root = graph.root

        def expand(self) -> written.Expansion:
            return graph.expand()

    tree = rendered.render(StandIn())  # type: ignore[arg-type]
    assert [(d.name, [a.text for a in d.values]) for d in tree.block.walk()] == [("x", ["1"]), ("y", [])]
    assert tree.origin.place.resolved_path == "main.conf"
