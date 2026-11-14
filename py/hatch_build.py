"""Build hook: generate the parser and the API declarations before a build from a checkout.

Generated code is never committed, so a build from the repository (``uv build``, or a consumer's
``knobly @ git+https://github.com/mcurcio/knobly#subdirectory=py``) has to make it first:
``tools/gen.sh py`` writes ``src/knobly/_gen/`` and ``src/knobly/_api/``, which ``pyproject.toml`` then forces into
the wheel and sdist. An sdist carries the generated files and not ``tools/``, so a build from one uses what it holds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# One file of each generated folder: enough to tell "generated" from "not".
GENERATED = ("src/knobly/_gen/KnoblyParser.py", "src/knobly/_api/__init__.py")


class GenerateHook(BuildHookInterface[Any]):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version == "editable":
            # A development install (`uv run`, `pip install -e`): gen.sh itself runs ruff through `uv run`, which
            # makes one, so generating here would never end. The tests and gen.sh generate for a checkout.
            return
        root = Path(self.root)
        gen = root.parent / "tools" / "gen.sh"
        if gen.is_file():
            try:
                subprocess.run(["bash", str(gen), "py"], check=True)
            except (OSError, subprocess.CalledProcessError) as error:
                raise RuntimeError(
                    "knobly: tools/gen.sh py failed, so the parser could not be generated. A build from the "
                    "repository needs bash, Java 11+, curl and uv (see py/README.md)."
                ) from error
        missing = [path for path in GENERATED if not (root / path).is_file()]
        if missing:
            raise RuntimeError(
                f"knobly: generated files missing, and no tools/gen.sh to make them: {', '.join(missing)}"
            )
