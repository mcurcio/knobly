"""The wheel and sdist ship the generated parser and API lists although git ignores them (tool.hatch artifacts in
pyproject.toml)."""

from __future__ import annotations

import subprocess
import sys
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


CONSUMER = """\
from villanelle import memory_source
from villanelle.include import include
from villanelle.rendered import render
from villanelle.written import Processor

graph = Processor(source=memory_source({"main.conf": "port 80;\\n"}), extensions=[include()]).load("main.conf")
port: int = render(graph).block[0].values[0].integer()
name: int = render(graph).block[0].name  # a str: the error proves villanelle's annotations reach the checker
"""


def test_a_consumer_type_checks_against_the_installed_wheel(tmp_path: Path) -> None:
    """PEP 561: the wheel ships py.typed, so a program's type checker reads villanelle's annotations."""
    subprocess.run(["uv", "build", "--wheel", "--quiet", "--out-dir", str(tmp_path / "dist"), str(PY)], check=True)
    [wheel] = (tmp_path / "dist").glob("*.whl")
    with zipfile.ZipFile(wheel) as zf:
        assert "villanelle/py.typed" in zf.namelist()
    venv = tmp_path / "venv"
    subprocess.run(["uv", "venv", "--quiet", str(venv)], check=True)
    python = venv / "bin" / "python"
    subprocess.run(["uv", "pip", "install", "--quiet", "--python", str(python), str(wheel)], check=True)
    (tmp_path / "consumer.py").write_text(CONSUMER)
    checked = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            "--config-file",
            "",
            "--python-executable",
            str(python),
            "consumer.py",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "import-untyped" not in checked.stdout, checked.stdout
    errors = [line for line in checked.stdout.splitlines() if ": error:" in line]
    assert len(errors) == 1 and "consumer.py:8:" in errors[0] and '"str"' in errors[0], checked.stdout
