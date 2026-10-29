"""The driver's own test: position conversion, the byte rule, the number rule, and a run against the stub adapter
(each failure mode reaches the exit status). Python 3.9+ standard library: python3 conformance/driver/test_driver.py"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run  # noqa: E402
from common import CaseError  # noqa: E402
from contract import ecmascript, result  # noqa: E402
from encode import to_bytes  # noqa: E402
from units import Converter  # noqa: E402


class Units(unittest.TestCase):
    TEXT = "a\U0001f600b\néc"

    def test_code_points_to_utf16(self) -> None:
        conv = Converter(self.TEXT, "code point")
        self.assertEqual(conv.position([0, 2, 2]), (0, 3, 3))  # "b" after the emoji
        self.assertEqual(conv.position([1, 1, 5]), (1, 1, 6))  # "c" after "é"

    def test_bytes_to_utf16(self) -> None:
        conv = Converter(self.TEXT, "byte")
        self.assertEqual(conv.position([0, 5, 5]), (0, 3, 3))
        self.assertEqual(conv.position([1, 2, 9]), (1, 1, 6))
        with self.assertRaises(ValueError):
            conv.offset(2)  # inside the emoji's four bytes

    def test_utf16_is_unchanged(self) -> None:
        self.assertEqual(Converter(self.TEXT, "utf-16").position([0, 3, 3]), (0, 3, 3))


class Bytes(unittest.TestCase):
    def test_escapes_above_ascii_as_utf16_units(self) -> None:
        self.assertEqual(
            to_bytes(["\u007f\u0080\U0001f600\ud800<&\b\x01"]), '["\x7f\\u0080\\ud83d\\ude00\\ud800<&\\b\\u0001"]\n'
        )


class Numbers(unittest.TestCase):
    def test_ecmascript_form(self) -> None:
        for number, text in [
            (1e21, "1e+21"),
            (1e20, "100000000000000000000"),
            (1e-7, "1e-7"),
            (0.5, "0.5"),
            (123.0, "123"),
        ]:
            self.assertEqual(ecmascript(number), text)

    def test_negative_zero_fails(self) -> None:
        with self.assertRaises(CaseError):
            result("number", {"number": "-0"})


def drive(mode: str) -> "tuple[int, str]":
    out = io.StringIO()
    with redirect_stdout(out):
        status = run.main(
            ["--corpus", "syntax", "--case", "empty", "--", sys.executable, str(HERE / "stub_adapter.py"), mode]
        )
    return status, out.getvalue()


class Driver(unittest.TestCase):
    def test_a_passing_case(self) -> None:
        status, out = drive("ok")
        self.assertEqual(status, 0, out)
        self.assertIn("ok 2 - syntax/empty # L0", out)
        self.assertIn("claimed L0 syntax: not checked", out)  # --case ran one case only

    def test_an_adapter_that_exits_fails_the_case(self) -> None:
        status, out = drive("crash")
        self.assertNotEqual(status, 0, out)
        self.assertIn("adapter fault", out)

    def test_a_bad_hello_bails_out(self) -> None:
        status, out = drive("bad-hello")
        self.assertEqual(status, 2, out)


if __name__ == "__main__":
    unittest.main()
