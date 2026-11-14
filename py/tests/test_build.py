"""The wheel and sdist ship the generated parser and API lists although git ignores them (tool.hatch artifacts in
pyproject.toml)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

PY = Path(__file__).resolve().parents[1]
GENERATED = {
    "_gen": {"KnoblyLexer.py", "KnoblyParser.py", "__init__.py"},
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
        assert {Path(n).name for n in wheel_names if n.startswith(f"knobly/{folder}/")} >= files
        assert {Path(n).name for n in sdist_names if f"/src/knobly/{folder}/" in n} >= files
    # The page PyPI shows is PYPI.md: its text is the wheel's long description, and no link in it is relative.
    with zipfile.ZipFile(wheel) as zf:
        [metadata_name] = [n for n in wheel_names if n.endswith(".dist-info/METADATA")]
        metadata = zf.read(metadata_name).decode()
    assert "Description-Content-Type: text/markdown" in metadata
    assert (PY / "PYPI.md").read_text() in metadata
    assert re.findall(r"\]\((?!https://)", metadata) == []


CONSUMER = """\
from knobly import memory_source
from knobly.include import include
from knobly.rendered import render
from knobly.written import Processor

graph = Processor(source=memory_source({"main.conf": "port 80;\\n"}), extensions=[include()]).load("main.conf")
port: int = render(graph).block[0].values[0].integer()
name: int = render(graph).block[0].name  # a str: the error proves knobly's annotations reach the checker
"""


def test_a_consumer_type_checks_against_the_installed_wheel(tmp_path: Path) -> None:
    """PEP 561: the wheel ships py.typed, so a program's type checker reads knobly's annotations."""
    subprocess.run(["uv", "build", "--wheel", "--quiet", "--out-dir", str(tmp_path / "dist"), str(PY)], check=True)
    [wheel] = (tmp_path / "dist").glob("*.whl")
    with zipfile.ZipFile(wheel) as zf:
        assert "knobly/py.typed" in zf.namelist()
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


def test_a_checkout_without_generated_code_builds_a_wheel_that_has_it(tmp_path: Path) -> None:
    """hatch_build.py runs tools/gen.sh, so a git dependency (which builds a wheel straight from a clone, where
    nothing generated exists) gets the parser and the API lists."""
    repo = PY.parent
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "grammar", "spec", "tools", "py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    clone = tmp_path / "clone"
    for name in filter(None, tracked):
        if (repo / name).is_file():  # a file deleted but not yet committed is still listed
            (clone / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, clone / name)
    assert not (clone / "py" / "src" / "knobly" / "_gen").exists()
    out = tmp_path / "dist"
    subprocess.run(["uv", "build", "--wheel", "--quiet", "--out-dir", str(out), str(clone / "py")], check=True)
    [wheel] = out.glob("*.whl")
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    for folder, files in GENERATED.items():
        assert {Path(n).name for n in names if n.startswith(f"knobly/{folder}/")} >= files
