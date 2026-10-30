"""The driver's own test: position conversion, the byte rule, the number rule, and a run against the stub adapter
(each failure mode reaches the exit status). Python 3.9+ standard library: python3 conformance/driver/test_driver.py"""

import io
import os
import subprocess
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
from syntax import shape  # noqa: E402
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


class SyntaxShape(unittest.TestCase):
    SRC = "a\n\u00e9 b"
    TOKENS = [
        ["WORD", "a", [0, 0, 0], [0, 1, 1]],
        ["NEWLINE", "\n", [0, 1, 1], [1, 0, 2]],
        ["WORD", "\u00e9", [1, 0, 2], [1, 2, 4]],
        ["SPACE", " ", [1, 2, 4], [1, 3, 5]],
        ["WORD", "b", [1, 3, 5], [1, 4, 6]],
    ]

    def dump(self, **change: object) -> "dict[str, object]":
        d = {"id": "d1", "code": "E2001", "message": "m", "start": [1, 3, 5], "end": [1, 4, 6]}
        d.update(change)
        return {"tokens": self.TOKENS, "root": ["document", 0, 5, []], "diagnostics": [d]}

    def test_a_right_dump_passes(self) -> None:
        self.assertEqual(shape(self.SRC, self.dump(), "byte"), [])

    def test_a_missing_or_extra_member_fails(self) -> None:
        d = self.dump()
        del d["diagnostics"][0]["message"]  # type: ignore[index]
        self.assertTrue(shape(self.SRC, d, "byte"))
        self.assertTrue(shape(self.SRC, self.dump(extra=1), "byte"))
        self.assertTrue(shape(self.SRC, {**self.dump(), "more": []}, "byte"))

    def test_a_wrong_line_or_column_fails(self) -> None:
        self.assertTrue(shape(self.SRC, self.dump(start=[99, 99, 5]), "byte"))
        bad = [t[:2] + [[0, 2, 2], t[3]] if i == 2 else t for i, t in enumerate(self.TOKENS)]
        self.assertTrue(shape(self.SRC, {**self.dump(), "tokens": bad}, "byte"))

    def test_a_lone_surrogate_is_three_bytes(self) -> None:
        tokens = [["BAD_CHAR", "\ud800", [0, 0, 0], [0, 3, 3]]]
        self.assertEqual(shape("\ud800", {"tokens": tokens, "root": ["document", 0, 1, []], "diagnostics": []}, "byte"), [])


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

    def test_a_stalled_adapter_times_out_as_a_fault(self) -> None:
        # The driver runs in its own process with a 1 s request timeout; the test's own guard (20 s) fails it if the
        # driver blocks instead (kno-p5x).
        command = [sys.executable, str(HERE / "run.py"), "--corpus", "syntax", "--case", "empty", "--"]
        command += [sys.executable, str(HERE / "stub_adapter.py"), "stall"]
        environment = {**os.environ, "KNOBLY_DRIVER_TIMEOUT": "1"}
        try:
            done = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            self.fail("the driver blocked on a stalled adapter instead of timing out")
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertIn("adapter fault: timed out after 1 s waiting for parse", done.stdout)
        self.assertIn("not ok 2 - syntax/empty", done.stdout)


if __name__ == "__main__":
    unittest.main()
