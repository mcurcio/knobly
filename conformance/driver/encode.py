"""The byte rule of every expected file (conformance/format.md, "Bytes"), in one place."""

from __future__ import annotations

import json
import re
from typing import Any

_ABOVE_ASCII = re.compile("[\u0080-\U0010ffff]")


def _escape(match: re.Match) -> str:  # type: ignore[type-arg]
    units = match.group().encode("utf-16-le", "surrogatepass")
    return "".join(f"\\u{int.from_bytes(units[i : i + 2], 'little'):04x}" for i in range(0, len(units), 2))


def to_bytes(value: Any) -> str:
    """No insignificant whitespace, every character above U+007F as lowercase ``\\uXXXX`` UTF-16 escapes (a lone
    surrogate as itself), standard short escapes, one trailing newline."""
    return _ABOVE_ASCII.sub(_escape, json.dumps(value, ensure_ascii=False, separators=(",", ":"))) + "\n"
