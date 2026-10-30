"""villanelle's own parser generator (design.md 1.5; frozen-m1.md section 3): reads grammar/Villanelle.g4 and writes a
header-only C++ lexer and recursive-descent parser. Python 3.9+ standard library only, like tools/api/, but for the
pinned clang-format the output goes through (the C++ Language's formatter in tools/api/emit_cpp.py, run by
tools/api/formatter.py, as every generated C++ file is).

    python3 tools/parser/gen.py cpp      -> cpp/include/villanelle/detail/syntax/parser.gen.hpp (never committed)
    python3 tools/parser/gen.py --check  -> the generator accepts grammar/Villanelle.g4, refuses every grammar in
                                            tools/planted-parser/, and the .g4's tree annotations match the .ebnf's;
                                            prints one summary line, exits 1 on any failure

tools/gen.sh cpp runs `cpp` before tools/gen-api.py cpp; tools/check.sh runs `--check`. TypeScript and Python keep
ANTLR (spec/binding-guide.md step 3 names both routes).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List

import cpp
import g4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api.emit_cpp import LANGUAGE  # noqa: E402  (the one home of the clang-format pin)
from api.formatter import FormatterError, format_files  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
GRAMMAR = REPO / "grammar" / "Villanelle.g4"
OUT = REPO / "cpp" / "include" / "villanelle" / "detail" / "syntax" / "parser.gen.hpp"


def write(text: str, out: Path) -> None:
    """Write beside `out`, then move into place: no reader sees a half-written file."""
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp.", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv: List[str]) -> int:
    if argv not in (["cpp"], ["--check"]):
        print("usage: tools/parser/gen.py <cpp|--check>", file=sys.stderr)
        return 2
    try:
        grammar = g4.read(GRAMMAR)
        text = cpp.render(grammar)
    except (g4.GrammarError, ValueError, OSError) as e:
        print(f"gen.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if argv == ["--check"]:
        print(f"grammar read: {len(grammar.tokens)} tokens, {len(grammar.rules)} rules (placeholder generator: no "
              "lexer, lookahead or refusal checks yet)")
        return 0
    try:
        text = format_files(LANGUAGE.formatter, {OUT.name: text})[OUT.name]
    except FormatterError as e:
        print(f"gen.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    write(text, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
