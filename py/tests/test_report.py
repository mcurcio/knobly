"""The diagnostics sink, program codes and the printer (S3 criterion 8)."""

from __future__ import annotations

import pytest

import villanelle as vl
from villanelle.include import include


def _render(processor: vl.Processor, overrides: dict[str, str] | None = None) -> vl.Rendered:
    """``render(load("main.conf"))``."""
    return vl.render(processor.load("main.conf", overrides=overrides))


MAIN = "set $pixels 2284;\ngraph {\n  node DdpSink leds { max_count $pixels; }\n}\n"


def loaded(text: str = MAIN, overrides: dict[str, str] | None = None) -> vl.Rendered:
    return _render(vl.Processor(source=vl.memory_source({"main.conf": text})), overrides=overrides)


def max_count(load: vl.Rendered) -> vl.Directive:
    return next(d for d in load.walk() if d.name == "max_count")


def test_report_and_add_record_in_order_after_the_initial_ones() -> None:
    load = loaded("a $x;\nb 1;\n")
    problems = vl.Diagnostics(load.diagnostics)
    b = load.block[0]
    problems.report(b, "b is not wanted", code="rasl/unwanted")
    problems.add(load.error("no graph", code="rasl/no-graph").diagnostic)
    assert len(problems) == 3
    assert [str(d.code) for d in problems] == ["E5001", "rasl/unwanted", "rasl/no-graph"]
    reported = list(problems)[1]
    assert (reported.place, reported.via, reported.message) == (b.origin.place, (), "b is not wanted")
    assert list(problems)[2].place == load.origin.place


def test_collecting_records_a_diagnostic_error_and_ends_the_block() -> None:
    load = loaded("a word;\n")
    problems = vl.Diagnostics()
    reached = []
    with problems.collecting():
        load.block[0].values[0].integer()
        reached.append(True)
    assert reached == []
    assert [str(d.code) for d in problems] == ["E4005"]


def test_collecting_lets_any_other_exception_through() -> None:
    problems = vl.Diagnostics()
    with pytest.raises(KeyError), problems.collecting():
        raise KeyError("not a diagnostic")
    assert len(problems) == 0


@pytest.mark.parametrize("code", ["E5001", "unknown-node", "/x", "rasl/", "", "a b/c", "a/b c", "rasl/ bad name"])
def test_a_program_code_needs_a_namespace(code: str) -> None:
    load = loaded()
    directive = max_count(load)
    with pytest.raises(ValueError, match="namespace"):
        directive.error("m", code=code)
    with pytest.raises(ValueError, match="namespace"):
        directive.values[0].error("m", code=code)
    with pytest.raises(ValueError, match="namespace"):
        load.error("m", code=code)
    with pytest.raises(ValueError, match="namespace"):
        vl.Diagnostics().report(directive, "m", code=code)


def test_a_located_diagnostic_made_directly_checks_its_code() -> None:
    place = loaded().origin.place
    assert vl.LocatedDiagnostic("rasl/x", "m", place, ()).code == "rasl/x"
    made = vl.LocatedDiagnostic("E5001", "m", place, ())
    assert made.code is vl.DiagnosticCode.UNKNOWN_VARIABLE
    with pytest.raises(ValueError, match="namespace"):
        vl.LocatedDiagnostic("E9999", "m", place, ())


def test_an_error_on_an_override_value_is_placed_on_the_name_that_used_it() -> None:
    load = loaded("blk { target $host; }\n", overrides={"host": "h"})
    [blk] = load.block
    [target] = blk.block or ()
    d = target.values[0].error("unreachable host", code="rasl/host").diagnostic
    start = d.place.span.start
    assert (d.place.resolved_path, start.line, start.column, d.via) == ("main.conf", 0, 13, ())
    assert "host" in d.message


def test_format_diagnostic_prints_place_code_message_source_caret_and_via() -> None:
    files = {"main.conf": "snippet s $v {\n  value $v;\n}\nuse s 1;\n", "x.conf": ""}
    load = _render(vl.Processor(source=vl.memory_source(files), extensions=[include()]))
    d = load.block[0].values[0].error("too small", code="rasl/small").diagnostic
    assert vl.format_diagnostic(d, load.graph) == (
        "main.conf:4:7: rasl/small: too small\n"
        "use s 1;\n"
        "      ^\n"
        "  via variable v at main.conf:2:9\n"
        "  via use s at main.conf:4:1"
    )


@pytest.mark.parametrize(
    ("text", "caret"),
    [
        ("\ta\t$y;\n", "\t \t^^"),
        ('a "\U0001f600" $y;\n', "      ^^"),
    ],
)
def test_format_diagnostic_keeps_tabs_and_counts_columns_in_code_points(text: str, caret: str) -> None:
    load = loaded(text)
    [d] = load.diagnostics
    assert vl.format_diagnostic(d, load.graph).split("\n")[1:] == [text.removesuffix("\n"), caret]


def test_format_diagnostic_without_the_file_prints_the_first_line_only() -> None:
    load = loaded("a $nope;\n")
    [d] = load.diagnostics
    assert vl.format_diagnostic(d) == "main.conf:1:3: E5001: unknown variable: $nope"
    assert vl.format_diagnostic(d, load.graph) == "main.conf:1:3: E5001: unknown variable: $nope\na $nope;\n  ^^^^^"
