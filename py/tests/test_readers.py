"""Value readers and canonical text (round 11 slices.md §1.3; S3 criteria 4 and 5), through a load. Replaces the old
``value_of`` tests: slices, indexes, bounds and string escapes are now read by ``Argument``."""

from __future__ import annotations

import pytest

import villanelle as vl


def _render(processor: vl.Processor, overrides: dict[str, str] | None = None) -> vl.Rendered:
    """``render(load("main.conf"))``."""
    return vl.render(processor.load("main.conf", overrides=overrides))


def args(text: str) -> tuple[vl.Argument, ...]:
    loaded = _render(vl.Processor(source=vl.memory_source({"main.conf": f"x {text};\n"})))
    assert loaded.diagnostics == ()
    return loaded.block[0].values


def arg(text: str) -> vl.Argument:
    [only] = args(text)
    return only


def raises(read: object, code: str) -> vl.LocatedDiagnostic:
    assert callable(read)
    with pytest.raises(vl.DiagnosticError) as raised:
        read()
    diagnostic = raised.value.diagnostic
    assert diagnostic.code == code
    return diagnostic


# --- readers -----------------------------------------------------------------------------------------------------


def test_word_and_string() -> None:
    assert arg("listen").word() == "listen"
    assert arg("/*.conf").word() == "/*.conf"
    assert arg("listen").string() == "listen"
    assert arg('"a\\tb"').string() == "a\tb"
    raises(arg('"q"').word, "E4002")
    raises(arg("[1]").string, "E4002")
    raises(arg("c[1:2]").string, "E4002")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("8080", 8080),
        ("-0.0176515", -0.0176515),
        ("1e3", 1000.0),
        ("0", 0),
        ("2.5E-1", 0.25),
        (str(2**53 - 1), 2**53 - 1),
        # Beyond ±(2**53 - 1) the same rounded float TypeScript reads (F1-09).
        ("12345678901234567891", 12345678901234567891.0),
        ("-9007199254740993", -9007199254740992.0),
    ],
)
def test_number_reads_a_number_text(text: str, value: float) -> None:
    number = arg(text).number()
    assert number == value
    assert type(number) is type(value)


@pytest.mark.parametrize(("text", "code"), [("20hz", "E4004"), ("01", "E4004"), (".5", "E4004"), ('"1"', "E4002")])
def test_number_refuses_anything_else(text: str, code: str) -> None:
    raises(arg(text).number, code)


def test_int_needs_an_integer_text_in_the_safe_range() -> None:
    assert arg("-12").integer() == -12
    assert arg(str(2**53 - 1)).integer() == 2**53 - 1
    raises(arg("1.0").integer, "E4005")
    raises(arg(str(2**53)).integer, "E4005")
    raises(arg("[1]").integer, "E4002")


def test_bool_reads_only_true_and_false() -> None:
    assert arg("true").boolean() is True
    assert arg("false").boolean() is False
    raises(arg("yes").boolean, "E4006")
    raises(arg('"true"').boolean, "E4002")


def test_list_gives_items_each_with_its_own_origin() -> None:
    items = arg("[a, [1, 2], 'z']").list()
    assert [i.text for i in items] == ["a", "[1, 2]", '"z"']
    assert [i.origin.place.span.start.column for i in items if isinstance(i.origin.place, vl.Place)] == [3, 6, 14]
    raises(arg("a").list, "E4002")


def test_slice_gives_slices_with_an_absent_side_none_and_indexes() -> None:
    assert arg("hyperhdr_color[144:152]").slice() == vl.SliceValue("hyperhdr_color", 144, 152)
    assert arg("c[144:]").slice() == vl.SliceValue("c", 144, None)
    assert arg("c[:-2]").slice() == vl.SliceValue("c", None, -2)
    assert arg("foo[1]").slice() == vl.IndexValue("foo", 1)
    big = 2**53 - 1
    assert arg(f"c[-{big}:{big}]").slice() == vl.SliceValue("c", -big, big)
    raises(arg("c").slice, "E4002")


def test_plain_reads_by_the_one_rule_quoting_means_text() -> None:
    values = [a.plain() for a in args('8080 "8080" 0.5 true "true" word [1, "a", false] c[1:2] c[3]')]
    assert values == [
        8080,
        "8080",
        0.5,
        True,
        "true",
        "word",
        (1, "a", False),
        vl.SliceValue("c", 1, 2),
        vl.IndexValue("c", 3),
    ]


def test_a_reader_error_is_placed_on_the_value_with_its_steps() -> None:
    loaded = _render(vl.Processor(source=vl.memory_source({"main.conf": "set $v x;\na 1 $v;\n"})))
    d = raises(loaded.block[0].values[1].integer, "E4005")
    assert (d.place.span.start.line, d.place.span.start.column) == (0, 7)
    assert [(s.kind, s.name, s.place.span.start.column) for s in d.via] == [("variable", "v", 4)]


# --- value rules at load -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("literal", "decoded"),
    [('"a\\"b"', 'a"b'), ("'it\\'s'", "it's"), ('"\\\\"', "\\"), ('"\\n\\t\\r"', "\n\t\r"), ('"a😀b"', "a😀b")],
)
def test_strings_decode_the_six_escapes(literal: str, decoded: str) -> None:
    assert arg(literal).string() == decoded


@pytest.mark.parametrize(("text", "column"), [("c[x:2]", 4), ("c[1:x]", 6), ("c[007]", 4), (f"c[{2**53}]", 4)])
def test_a_non_integer_bound_is_e4001_at_the_bound(text: str, column: int) -> None:
    loaded = _render(vl.Processor(source=vl.memory_source({"main.conf": f"x {text};\n"})))
    [d] = loaded.diagnostics
    assert (d.code, d.place.span.start.column) == ("E4001", column)
    assert loaded.block == ()


# --- canonical text ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "text"),
    [
        ("w", "w"),
        ("'single \"q\"'", '"single \\"q\\""'),
        ('"tab\\tnl\\ncr\\rbs\\\\"', '"tab\\tnl\\ncr\\rbs\\\\"'),
        ('"it\\\'s"', '"it\'s"'),
        ("c[1:2]", "c[1:2]"),
        ("c[:2]", "c[:2]"),
        ("c[1:]", "c[1:]"),
        ("c[-0]", "c[0]"),
        ("c[4]", "c[4]"),
        ("[1, # comment\n  'a',\n  [b, c[1]],\n]", '[1, "a", [b, c[1]]]'),
        ("[]", "[]"),
    ],
)
def test_canonical_text(written: str, text: str) -> None:
    assert arg(written).text == text


def test_a_value_from_a_variable_has_the_values_text() -> None:
    loaded = _render(vl.Processor(source=vl.memory_source({"main.conf": "set $v 'x';\na $v;\n"})))
    assert loaded.block[0].values[0].text == '"x"'
