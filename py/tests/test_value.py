from __future__ import annotations

import pytest

from villanelle import (
    DiagnosticCode,
    DiagnosticError,
    IndexValue,
    Node,
    NodeKind,
    SliceValue,
    SourcePosition,
    SourceSpan,
    Syntax,
    ValueKind,
    WordValue,
    parse,
    value_of,
)


def slice_of(syntax: Syntax) -> Node:
    """The slice node of the first directive (``connect <value>;``)."""
    node = syntax.root.children[0].children[0]
    assert node.kind is NodeKind.SLICE
    return node


def test_gives_the_tracer_slice() -> None:
    syntax = parse("connect hyperhdr_color[144:152];")
    assert syntax.diagnostics == ()
    value = value_of(syntax, slice_of(syntax))
    assert value == SliceValue(
        "hyperhdr_color", 144, 152, SourceSpan(SourcePosition(8, 0, 8), SourcePosition(31, 0, 31))
    )
    assert value.kind is ValueKind.SLICE


def test_gives_one_sided_slices_the_absent_side_none() -> None:
    open_end = parse("connect hyperhdr_color[144:];")
    assert open_end.diagnostics == ()
    a = value_of(open_end, slice_of(open_end))
    assert isinstance(a, SliceValue)
    assert (a.name, a.start, a.end) == ("hyperhdr_color", 144, None)

    open_start = parse("connect hyperhdr_color[:152];")
    assert open_start.diagnostics == ()
    b = value_of(open_start, slice_of(open_start))
    assert isinstance(b, SliceValue)
    assert (b.name, b.start, b.end) == ("hyperhdr_color", None, 152)


def test_gives_an_index_for_foo_1() -> None:
    syntax = parse("connect foo[1];")
    assert syntax.diagnostics == ()
    value = value_of(syntax, slice_of(syntax))
    assert isinstance(value, IndexValue)
    assert (value.kind, value.name, value.index) == (ValueKind.INDEX, "foo", 1)


def test_accepts_negative_integer_bounds() -> None:
    syntax = parse("connect foo[-3:-1];")
    assert syntax.diagnostics == ()
    value = value_of(syntax, slice_of(syntax))
    assert isinstance(value, SliceValue)
    assert (value.start, value.end) == (-3, -1)


def test_accepts_the_largest_safe_integers() -> None:
    syntax = parse("connect foo[-9007199254740991:9007199254740991];")
    value = value_of(syntax, slice_of(syntax))
    assert isinstance(value, SliceValue)
    assert (value.start, value.end) == (-(2**53 - 1), 2**53 - 1)


def test_raises_e4001_at_a_non_integer_bound_foo_a_b_parses_clean() -> None:
    syntax = parse("connect foo[a:b];")
    assert syntax.diagnostics == ()
    with pytest.raises(DiagnosticError) as raised:
        value_of(syntax, slice_of(syntax))
    assert raised.value.diagnostic.code is DiagnosticCode.NON_INTEGER_BOUND
    assert raised.value.diagnostic.span.start == SourcePosition(12, 0, 12)


@pytest.mark.parametrize(
    "src",
    ["connect foo[1.5];", "connect foo[9007199254740993];", "connect foo[-9007199254740992];", "connect foo[1:-];"],
)
def test_raises_e4001_for_bounds_that_are_not_safe_integers(src: str) -> None:
    syntax = parse(src)
    assert syntax.diagnostics == ()
    with pytest.raises(DiagnosticError) as raised:
        value_of(syntax, slice_of(syntax))
    assert raised.value.diagnostic.code is DiagnosticCode.NON_INTEGER_BOUND


def test_gives_a_word_for_a_word_token_index() -> None:
    syntax = parse("connect foo;")
    value = value_of(syntax, 2)
    assert value == WordValue("foo", syntax.tokens[2].span)
    assert value.kind is ValueKind.WORD


def test_raises_unsupported_value_kind_for_strings_and_lists() -> None:
    string = parse('connect "x";')
    with pytest.raises(NotImplementedError, match=r"^unsupported value kind: string$"):
        value_of(string, 2)
    lst = parse("connect [1, 2];")
    node = lst.root.children[0].children[0]
    assert node.kind is NodeKind.LIST
    with pytest.raises(NotImplementedError, match=r"^unsupported value kind: list$"):
        value_of(lst, node)


def test_raises_type_error_for_a_ref_that_is_not_a_value() -> None:
    syntax = parse("connect foo;")
    for ref in (1, 99, -1, syntax.root.children[0]):  # SPACE, out of range, negative, a directive node
        with pytest.raises(TypeError):
            value_of(syntax, ref)
