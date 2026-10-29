"""The wheel and sdist ship the generated parser and API lists although git ignores them (tool.hatch artifacts in
pyproject.toml)."""

from __future__ import annotations

import subprocess
import tarfile
import zipfile
from pathlib import Path

PY = Path(__file__).resolve().parents[1]
GENERATED = {
    "_gen": {"VillanelleLexer.py", "VillanelleParser.py", "__init__.py"},
    "_api": {"__init__.py", "codes.py", "kinds.py", "limits.py"},
}


def test_wheel_and_sdist_contain_the_generated_parser_and_api_lists(tmp_path: Path) -> None:
    subprocess.run(["uv", "build", "--quiet", "--out-dir", str(tmp_path), str(PY)], check=True)
    [wheel] = tmp_path.glob("*.whl")
    [sdist] = tmp_path.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as zf:
        wheel_names = zf.namelist()
    with tarfile.open(sdist) as tf:
        sdist_names = tf.getnames()
    for folder, files in GENERATED.items():
        assert {Path(n).name for n in wheel_names if n.startswith(f"villanelle/{folder}/")} >= files
        assert {Path(n).name for n in sdist_names if f"/src/villanelle/{folder}/" in n} >= files
