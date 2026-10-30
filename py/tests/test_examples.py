"""The user guide's samples (examples/samples.json; .claude/design/cpp/frozen-docs.md).

Every py/examples/<id>.py runs as a program, in a fresh copy of its fixture folder, and what it prints must be
examples/expected/<id>.txt byte for byte. The same table drives ts/examples/examples.test.ts and
cpp/examples/CMakeLists.txt, so the three bindings' samples print the same text. The run folder is cut from the output
before comparing, as the TypeScript runner does (Python's file source keeps paths relative, so it is a no-op here).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TABLE: dict[str, dict[str, str | None]] = json.loads((REPO / "examples" / "samples.json").read_text("utf-8"))["samples"]
FILES = sorted((REPO / "py" / "examples").glob("*.py"))


@pytest.mark.parametrize("sample", FILES, ids=lambda f: f.stem)
def test_a_sample_prints_its_expected_output(sample: Path, tmp_path: Path) -> None:
    assert sample.stem in TABLE, f"{sample.name} is not in examples/samples.json"
    fixture = TABLE[sample.stem]["fixture"]
    folder = tmp_path.resolve()
    if fixture is not None:
        shutil.copytree(REPO / fixture, folder, dirs_exist_ok=True)
    run = subprocess.run(
        [sys.executable, str(sample)], cwd=folder, capture_output=True, encoding="utf-8", check=False, timeout=60
    )
    assert run.returncode == 0, run.stderr
    expected = (REPO / "examples" / "expected" / f"{sample.stem}.txt").read_text("utf-8")
    assert run.stdout.replace(f"{folder}/", "") == expected
