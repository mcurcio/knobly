"""The kind lint (spec 2.10; owner, 2026-10-29: "Yes, generate both"; bead kno-umh.11): no ``.kind``, ``.reason`` or
``.code`` of the package or its adapter is compared with a string literal, only with an enum member. It runs
tools/lint/kind_lint.py (its own planted cases run in tools/check.sh) under this interpreter, Python 3.11, so a
``match`` statement is read too."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PY = Path(__file__).resolve().parents[1]
LINT = PY.parent / "tools" / "lint" / "kind_lint.py"


def test_no_kind_reason_or_code_is_compared_with_a_string() -> None:
    run = subprocess.run(
        [sys.executable, str(LINT), str(PY / "src"), str(PY / "conformance")], capture_output=True, text=True
    )
    assert (run.returncode, run.stdout, run.stderr) == (0, "", "")


def test_the_lint_bites_on_a_planted_comparison(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text('def f(s):\n    match s.kind:\n        case "set":\n            return s.reason == "value"\n')
    run = subprocess.run([sys.executable, str(LINT), str(planted)], capture_output=True, text=True)
    assert run.returncode == 1
    assert run.stdout.count("planted.py:") == 2
