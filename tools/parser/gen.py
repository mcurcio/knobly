"""knobly's own parser generator (design.md 1.5; frozen-m1.md section 3): reads grammar/Knobly.g4 and writes a
header-only C++ lexer and recursive-descent parser. Python 3.9+ standard library only, like tools/api/, but for the
pinned clang-format the output goes through (the C++ Language's formatter in tools/api/emit_cpp.py, run by
tools/api/formatter.py, as every generated C++ file is).

    python3 tools/parser/gen.py cpp      -> cpp/include/knobly/detail/syntax/parser.gen.hpp (never committed)
    python3 tools/parser/gen.py --check  -> the generator accepts grammar/Knobly.g4, refuses every grammar in
                                            tools/planted-parser/ for the reason its first line names, the .g4's tree
                                            annotations match the .ebnf's, and test_parser.py passes; prints one
                                            summary line, exits 1 on any failure

The steps: g4.py reads the grammar, lexer.py builds the lexer DFA, lookahead.py analyses every choice point (LL(*)),
cpp.py writes the header. tools/gen.sh cpp runs `cpp` before tools/gen-api.py cpp; tools/check.sh runs `--check`.
TypeScript and Python keep ANTLR (spec/binding-guide.md step 3 names both routes).
"""

from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

import cpp
import g4
import lexer
import lookahead

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GRAMMAR = REPO / "grammar" / "Knobly.g4"
EBNF = REPO / "grammar" / "knobly.ebnf"
PLANTED = REPO / "tools" / "planted-parser"
OUT = REPO / "cpp" / "include" / "knobly" / "detail" / "syntax" / "parser.gen.hpp"
REFUSED = re.compile(r"^// refused: (.+)$", re.M)  # a planted grammar's first line: what its refusal must say


def build(grammar: g4.Grammar) -> Tuple[lookahead.Plan, lexer.Dfa]:
    """Every check the generator makes: raises g4.GrammarError on a refusal."""
    return lookahead.analyse(grammar), lexer.build(grammar)


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


def planted() -> int:
    """Each planted grammar must be refused, and for the reason its `// refused:` line names."""
    files = sorted(PLANTED.glob("*.g4"))
    if not files:
        raise ValueError(f"no planted grammars in {PLANTED}")
    for path in files:
        src = path.read_text(encoding="utf-8")
        want = REFUSED.search(src)
        if not want:
            raise ValueError(f"{path.name}: no '// refused: <reason>' line")
        try:
            build(g4.parse(src, path.name))
        except g4.GrammarError as e:
            if want.group(1) not in str(e):
                raise ValueError(f"{path.name}: refused for the wrong reason: {e}") from None
            continue
        raise ValueError(f"{path.name}: accepted (want refused: {want.group(1)})")
    return len(files)


def annotations(grammar: g4.Grammar) -> None:
    ebnf = g4.ebnf_annotations(EBNF.read_text(encoding="utf-8"))
    if dict(grammar.cst) != dict(ebnf):
        raise ValueError(f"tree annotations differ: {GRAMMAR.name} has {dict(grammar.cst)}, {EBNF.name} has {ebnf}")


def unit_tests() -> None:
    import test_parser

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromModule(test_parser))
    if not result.wasSuccessful():
        raise ValueError("test_parser.py failed:\n" + stream.getvalue().strip())


def main(argv: List[str]) -> int:
    if argv not in (["cpp"], ["--check"]):
        print("usage: tools/parser/gen.py <cpp|--check>", file=sys.stderr)
        return 2
    try:
        grammar = g4.read(GRAMMAR)
        plan, dfa = build(grammar)
        text = cpp.render(plan, dfa)
        if argv == ["--check"]:
            annotations(grammar)
            refused = planted()
            unit_tests()
    except (g4.GrammarError, ValueError, OSError) as e:
        print(f"gen.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if argv == ["--check"]:
        print(f"grammar accepted: lexer {len(dfa.accept)} states; {plan.one_token} one-token choice points, "
              f"{plan.longer} longer ({plan.longer_states} lookahead states); {refused} planted grammars refused; "
              f"tree annotations agree with {EBNF.name}")
        return 0
    sys.path.insert(0, str(HERE.parent))
    from api.emit_cpp import LANGUAGE  # the one home of the clang-format pin
    from api.formatter import FormatterError, format_files

    try:
        text = format_files(LANGUAGE.formatter, {OUT.name: text})[OUT.name]
    except FormatterError as e:
        print(f"gen.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    write(text, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
