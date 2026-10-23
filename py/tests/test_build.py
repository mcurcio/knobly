"""The wheel and sdist ship the generated parser although git ignores it (tool.hatch artifacts in pyproject.toml)."""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path

PY = Path(__file__).resolve().parents[1]
GENERATED = {"VillanelleLexer.py", "VillanelleParser.py", "__init__.py"}


def test_wheel_and_sdist_contain_the_generated_parser(tmp_path: Path) -> None:
    subprocess.run(["uv", "build", "--quiet", "--out-dir", str(tmp_path), str(PY)], check=True)
    [wheel] = tmp_path.glob("*.whl")
    [sdist] = tmp_path.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as zf:
        in_wheel = {Path(n).name for n in zf.namelist() if n.startswith("villanelle/_gen/")}
    with tarfile.open(sdist) as tf:
        in_sdist = {Path(n).name for n in tf.getnames() if "/src/villanelle/_gen/" in n}
    assert in_wheel >= GENERATED
    assert in_sdist >= GENERATED
