"""Regenerates the parser (tools/gen.sh py) before any test imports villanelle, as the TypeScript test script does:
generated code is never committed (owner, 2026-10-23), and a stale copy would hide a grammar change."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

subprocess.run(["bash", str(REPO / "tools" / "gen.sh"), "py"], check=True)


def utf16_length(text: str) -> int:
    """How many UTF-16 code units ``text`` is: a character above U+FFFF counts two."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def utf16_column(text: str, offset: int, column: int) -> int:
    """A position's column in UTF-16 units (the conformance corpus's unit, spec/contract.md 1), from its code-point
    ``offset`` and ``column`` in ``text``, the text it counts in."""
    return utf16_length(text[offset - column : offset])
