"""Regenerates the parser (tools/gen.sh py) before any test imports villanelle, as the TypeScript test script does:
generated code is never committed (owner, 2026-10-23), and a stale copy would hide a grammar change."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

subprocess.run(["bash", str(REPO / "tools" / "gen.sh"), "py"], check=True)
