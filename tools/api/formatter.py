"""Runs a language's standard formatter on its generated files (spec/codegen.md section 4).

The emitters write plain, deterministic code and leave its layout to each language's own formatter, pinned to an exact
version: Prettier for TypeScript (ts/package.json), ruff for Python (py/pyproject.toml). Each emitter's ``Language``
names its ``Formatter``; this module only runs it. The files are written into a fresh temporary folder (under the
names they will have, folders included), each command runs once over all of them from the repository root, and the
formatted text is read back, so ``tools/gen-api.py`` still moves each finished file into place in one step.

Invoking a pinned formatter's executable is the one exception to tools/' standard-library-only rule (spec/codegen.md
sections 3 and 11); the rest of this module is the standard library.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

from .loader import REPO, Formatter


class FormatterError(Exception):
    """A formatter refused the generated code or could not run: a generator bug, or the formatter is not installed."""


def format_files(formatter: Optional[Formatter], files: Dict[str, str]) -> Dict[str, str]:
    """``files`` (name to text; a name may hold folders) with every file the formatter takes formatted."""
    if formatter is None:
        return dict(files)
    picked = sorted(name for name in files if name.endswith(formatter.suffix))
    if not picked:
        return dict(files)
    with tempfile.TemporaryDirectory(prefix="knobly-format.") as tmp:
        root = Path(tmp)
        for name in picked:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(files[name], encoding="utf-8")
        paths = [str(root / name) for name in picked]
        for command in formatter.commands:
            try:
                done = subprocess.run([*command, *paths], cwd=REPO, capture_output=True, text=True, check=False)
            except FileNotFoundError as e:
                raise FormatterError(f"{command[0]} not found ({e.strerror}); see spec/codegen.md section 4") from e
            if done.returncode != 0:
                out = (done.stderr + done.stdout).replace(tmp + "/", "").strip()
                raise FormatterError(f"{' '.join(command)} exited {done.returncode}:\n{out}")
        return {name: (root / name).read_text(encoding="utf-8") if name in picked else text for name, text in files.items()}
