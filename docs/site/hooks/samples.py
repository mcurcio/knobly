"""Fail the build unless every sample of examples/samples.json is shown in all three languages.

A page shows a sample by including its file with pymdownx.snippets (`--8<-- "ts/examples/<id>.ts:main"`); a missing
file or region already fails the build (check_paths). This hook adds the other half: every id in the sample table is
included on some page from ts/examples/<id>.ts, py/examples/<id>.py and cpp/examples/<id>.cpp, so a sample cannot
lose a tab, or never get a page, without the build failing. Run by `hooks:` in mkdocs.yml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mkdocs.exceptions import PluginError

REPO = Path(__file__).resolve().parents[3]
FILES = {"ts": "ts/examples/{}.ts", "py": "py/examples/{}.py", "cpp": "cpp/examples/{}.cpp"}
INCLUDE = re.compile(r'--8<--\s+"(ts/examples/(\w+)\.ts|py/examples/(\w+)\.py|cpp/examples/(\w+)\.cpp)(?::\w+)?"')

_shown: set[tuple[str, str]] = set()


def on_pre_build(config: Any) -> None:
    _shown.clear()


def on_page_markdown(markdown: str, page: Any, config: Any, files: Any) -> str:
    for match in INCLUDE.finditer(markdown):
        ts, py, cpp = match.group(2, 3, 4)
        _shown.add(("ts", ts) if ts else ("py", py) if py else ("cpp", cpp))
    return markdown


def on_env(env: Any, config: Any, files: Any) -> Any:
    table = json.loads((REPO / "examples" / "samples.json").read_text(encoding="utf-8"))
    missing = [
        FILES[language].format(sample)
        for sample in table["samples"]
        for language in FILES
        if (language, sample) not in _shown
    ]
    if missing:
        raise PluginError(
            "samples shown in fewer than three languages (examples/samples.json); no page includes: " + ", ".join(missing)
        )
    return env
