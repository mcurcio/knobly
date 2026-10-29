"""Per-statement recovery, the error-code classifier and the nesting-depth guard (as ts/src/syntax/recovery.test.ts)."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from villanelle import DiagnosticCode
from villanelle.syntax import MAX_NESTING, Node, NodeKind, parse, text_of


def shape(text: str) -> dict[str, Any]:
    """The tree as [kind, source text, children] and the diagnostics as [code, line, column]."""
    syntax = parse(text)

    def of(node: Node) -> list[Any]:
        return [node.kind.value, text_of(syntax, node), [of(child) for child in node.children]]

    return {
        "tree": of(syntax.root),
        "codes": [[d.code.value, d.span.start.line, d.span.start.column] for d in syntax.diagnostics],
    }


def test_makes_a_bad_statement_inside_a_block_one_error_node_and_keeps_later_siblings() -> None:
    text = "server {\n  listen 80 ];\n  root /x;\n}\nnext 1;\n"
    assert shape(text) == {
        "tree": [
            "document",
            text,
            [
                [
                    "directive",
                    "server {\n  listen 80 ];\n  root /x;\n}",
                    [
                        [
                            "block",
                            "{\n  listen 80 ];\n  root /x;\n}",
                            [
                                ["error", "listen 80 ];", []],
                                ["directive", "root /x;", []],
                            ],
                        ],
                    ],
                ],
                ["directive", "next 1;", []],
            ],
        ],
        "codes": [["E2004", 1, 12]],
    }


def test_reports_the_first_error_of_each_bad_statement_at_its_real_position_and_only_that_one() -> None:
    text = "a ];\nb 1;\nc x ] ];\nd 2;\n"
    assert shape(text) == {
        "tree": [
            "document",
            text,
            [
                ["error", "a ];", []],
                ["directive", "b 1;", []],
                ["error", "c x ] ];", []],
                ["directive", "d 2;", []],
            ],
        ],
        "codes": [["E2004", 0, 2], ["E2004", 2, 4]],
    }


def test_resumes_after_the_bad_statements_semicolon_never_at_a_line_break() -> None:
    # spec 3.2: an unterminated string's statement runs on to the next `;`, hiding the line after it.
    assert [n[:2] for n in shape('c "x;\nd 2;\ne 3;\n')["tree"][2]] == [["error", 'c "x;\nd 2;'], ["directive", "e 3;"]]
    assert shape("a ]\nb 1;\nc;\n")["tree"][2] == [["error", "a ]\nb 1;", []], ["directive", "c;", []]]
    # a stray `}` at the top level ends the bad statement
    assert [n[:2] for n in shape("x 1 }\ny 2;")["tree"][2]] == [["error", "x 1 }"], ["directive", "y 2;"]]


def test_a_missing_semicolon_is_e2001_where_it_was_due_and_mid_block_joins_the_next_line() -> None:
    assert shape("x 1") == {"tree": ["document", "x 1", [["error", "x 1", []]]], "codes": [["E2001", 0, 3]]}
    assert shape("a { x 1 }")["codes"] == [["E2001", 0, 8]]
    result = shape("a 1;\nb 2\nc 3;\nd 4\n")
    assert [n[:2] for n in result["tree"][2]] == [["directive", "a 1;"], ["directive", "b 2\nc 3;"], ["error", "d 4\n"]]
    assert result["codes"] == [["E2001", 4, 0]]


def test_a_line_break_is_whitespace_so_a_wrapped_line_is_one_directive() -> None:
    syntax = parse("ranges 0.0627\n 0.922;\n")
    assert syntax.diagnostics == ()
    [directive] = syntax.root.children
    assert directive.kind is NodeKind.DIRECTIVE and text_of(syntax, directive) == "ranges 0.0627\n 0.922;"


@pytest.mark.parametrize("text", ["0.922;", "-x 1;", "1[0];", "20hz 1;"])
def test_a_directive_name_that_starts_with_a_digit_or_dash_is_e2001_at_it(text: str) -> None:
    assert shape(text) == {"tree": ["document", text, [["error", text, []]]], "codes": [["E2001", 0, 0]]}


def test_reports_where_the_statement_breaks_never_conjuring_or_deleting_a_token() -> None:
    # ANTLR's default inline recovery would conjure the missing '}' and report it as a different error.
    assert shape("a {\n b 1;\n")["codes"] == [["E2003", 2, 0]]
    assert shape("x [a b];\ny 1;\n")["codes"] == [["E2001", 0, 5]]
    assert shape("x a[1 2];\ny 1;\n")["codes"] == [["E2007", 0, 5]]
    assert [n[0] for n in shape("x a[1:2 z];\ny 1;\n")["tree"][2]] == ["error", "directive"]


def test_gives_a_stray_bracket_and_an_unclosed_bracket_one_located_e2004_each() -> None:
    assert shape("x ];\ny 1;\n")["codes"] == [["E2004", 0, 2]]
    assert shape("a {\n x [1\n}\n")["codes"] == [["E2004", 2, 0]]
    assert shape("x [1, 2")["codes"] == [["E2004", 0, 7]]


def test_a_brace_that_starts_its_line_opens_the_block_of_the_directive_before_it() -> None:
    result = shape("a\n  # c\n  {\n b 1;\n}\nc 2;\n")
    assert result["codes"] == []
    assert [[n[0], n[1]] for n in result["tree"][2]] == [
        ["directive", "a\n  # c\n  {\n b 1;\n}"],
        ["directive", "c 2;"],
    ]


def test_gives_touching_values_e2009() -> None:
    assert shape('x "a""b";')["codes"] == [["E2009", 0, 5]]
    assert shape('x a"b";')["codes"] == [["E2009", 0, 3]]
    assert shape("x [a][b];")["codes"] == [["E2009", 0, 5]]
    assert shape("x a[0~1]b;")["codes"] == [["E2009", 0, 8]]
    assert shape("x 1[0];")["codes"] == [["E2009", 0, 3]]  # a slice's name is a word or a $name: 1 and [0] touch
    assert shape('x @a"b";')["codes"] == [["E2009", 0, 4]]  # an AT_WORD is a value
    assert shape("x \"a\"'b';")["codes"] == [["E2009", 0, 5]]  # 'it''s' is two touching raw strings


def test_a_bracket_after_a_variable_or_an_at_word_is_a_slice_bracket() -> None:
    assert shape("x $s[0~3] @a[1];")["codes"] == []
    assert shape("x $s[0~3;\ny;\n")["codes"] == [["E2007", 0, 8]]
    assert shape("x @a[1;\ny;\n")["codes"] == [["E2007", 0, 6]]
    assert shape("x a[1:3];")["codes"] == [["E2007", 0, 4]]  # 1:3 is one word: not a bound


def test_resumes_after_a_long_run_of_bad_statements_in_a_loop_never_overflowing_the_stack() -> None:
    run = 5000
    bad = "a ];\n" * run
    for text, count in (
        (bad, run),
        ("a ];" * run, run),
        (f"a {{\n{bad}}}\n", run),
        ("a ];\nb 1;\n" * (run // 2), run // 2),
    ):
        syntax = parse(text)
        assert len(syntax.diagnostics) == count
        assert text_of(syntax, syntax.root) == text
    top = shape(bad)
    assert top["tree"][2] == [["error", "a ];", []]] * run
    assert top["codes"][run - 1] == ["E2004", run - 1, 2]
    assert shape(f"a {{\n{bad}}}\n")["tree"][2][0][2][0][2] == [["error", "a ];", []]] * run
    assert shape("a ];\nb 1;\n" * (run // 2))["tree"][2][:4] == [
        ["error", "a ];", []],
        ["directive", "b 1;", []],
        ["error", "a ];", []],
        ["directive", "b 1;", []],
    ]


def test_parses_wrong_format_files_and_bad_runs_at_full_nesting_depth_without_raising() -> None:
    deep = "a {" * MAX_NESTING + "x ];\n" * 200 + "}" * MAX_NESTING
    for text in (
        "".join(f"key{i}: [value, {i}]];\n" for i in range(600)),
        "".join(f'"k{i}": "v",\n' for i in range(600)),
        deep,
    ):
        syntax = parse(text)
        assert syntax.diagnostics
        assert text_of(syntax, syntax.root) == text
    assert [d.code for d in parse(deep).diagnostics] == [DiagnosticCode.EXPECTED_CLOSING_BRACKET] * 200


def blocks(n: int) -> str:
    return "a {" * n + "}" * n


def lists(n: int) -> str:
    return "x " + "[" * n + "]" * n + ";"


def test_parses_max_nesting_levels_of_blocks_and_lists_clean_without_touching_the_recursion_limit() -> None:
    assert MAX_NESTING == 100
    limit = sys.getrecursionlimit()
    for text in (blocks(MAX_NESTING), lists(MAX_NESTING), "a {" + "x [" * (MAX_NESTING - 1)):
        syntax = parse(text)
        assert [d for d in syntax.diagnostics if d.code is DiagnosticCode.NESTING_TOO_DEEP] == []
    assert parse(blocks(MAX_NESTING)).diagnostics == ()
    assert parse(lists(MAX_NESTING)).diagnostics == ()
    assert sys.getrecursionlimit() == limit


def test_rejects_one_level_more_with_one_e2010_at_its_opener_and_one_error_node_over_everything() -> None:
    for text, column in (
        (blocks(MAX_NESTING + 1), 3 * MAX_NESTING + 2),
        (lists(MAX_NESTING + 1), 2 + MAX_NESTING),
        ("a {" + "x [" * MAX_NESTING, 3 + 3 * (MAX_NESTING - 1) + 2),
    ):
        syntax = parse(text)
        assert [(d.code, d.span.start.column) for d in syntax.diagnostics] == [
            (DiagnosticCode.NESTING_TOO_DEEP, column)
        ]
        n = len(syntax.tokens)
        assert syntax.root == Node(
            kind=NodeKind.DOCUMENT, start=0, end=n, children=(Node(kind=NodeKind.ERROR, start=0, end=n, children=()),)
        )
        assert text_of(syntax, syntax.root) == text


def test_counts_closers_so_sequential_nesting_never_adds_up_and_never_raises() -> None:
    assert parse(f"{blocks(MAX_NESTING)}\n{blocks(MAX_NESTING)}").diagnostics == ()
    parse("}" * 500 + blocks(MAX_NESTING))
    assert [d.code for d in parse("]" * 500 + "[" * (MAX_NESTING + 1)).diagnostics] == [DiagnosticCode.NESTING_TOO_DEEP]
    parse("{" * 100_000)
