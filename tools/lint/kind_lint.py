"""The kind lint for Python (bead vil-umh.11; owner, 2026-10-29, "Yes, generate both"; spec 2.10).

A ``.kind``, ``.reason`` or ``.code`` is compared with an enum member (``StatementKind.SET``), never a string literal:
``s.kind == "sett"`` passes ``mypy --strict`` against a StrEnum and is simply false, so the misspelling is never caught.
Refused, in every module given:

- ``x.kind == "set"``, ``"set" != x.kind`` (any ``==`` / ``!=`` with a ``str`` constant on the other side);
- ``x.kind in ("set", "use")`` (a tuple, list or set holding a ``str`` constant);
- ``match x.kind: case "set": ...`` (a ``str`` constant as a case's value pattern).

    python3 tools/lint/kind_lint.py PATH...   # exits 1 and prints file:line for each, 0 when clean
    python3 tools/lint/kind_lint.py --self-test

Its TypeScript twin is tools/lint/kind-rule.js. Python 3.9 standard library only (``match`` is read only on 3.10+).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterator, List, Tuple

ATTRS = ("kind", "reason", "code")


def _is_attr(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr in ATTRS


def _is_str(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and any(_is_str(e) for e in node.elts)


def findings(source: str, filename: str = "<text>") -> Iterator[Tuple[int, str]]:
    tree = ast.parse(source, filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            for i, op in enumerate(node.ops):
                a, b = sides[i], sides[i + 1]
                if isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) and (
                    (_is_attr(a) and _is_str(b)) or (_is_attr(b) and _is_str(a) and isinstance(op, (ast.Eq, ast.NotEq)))
                ):
                    attr = a if _is_attr(a) else b
                    yield node.lineno, f".{attr.attr} compared with a string literal; compare an enum member"  # type: ignore[attr-defined]
        match_cls = getattr(ast, "Match", None)
        if match_cls is not None and isinstance(node, match_cls) and _is_attr(node.subject):  # type: ignore[attr-defined]
            for case in node.cases:  # type: ignore[attr-defined]
                for pat in ast.walk(case.pattern):
                    if type(pat).__name__ == "MatchValue" and _is_str(pat.value):  # type: ignore[attr-defined]
                        yield pat.lineno, f"match on .{node.subject.attr} with a string case; use an enum member"  # type: ignore[attr-defined]


def scan(paths: List[str]) -> List[str]:
    out = []
    for p in paths:
        files = sorted(Path(p).rglob("*.py")) if Path(p).is_dir() else [Path(p)]
        for f in files:
            if "_gen" in f.parts:
                continue  # the generated parser
            for line, why in findings(f.read_text(encoding="utf-8"), str(f)):
                out.append(f"{f}:{line}: {why}")
    return out


PLANTED = {
    "eq": 'if s.kind == "set": pass',
    "reversed": 'if "set" != s.reason: pass',
    "in": 'ok = s.code in ("E1001", "E1003")',
}
PLANTED_MATCH = 'match s.kind:\n    case "set":\n        pass'
CLEAN = 'if s.kind == StatementKind.SET or s.kind in (StatementKind.USE,): pass\nname == "x"\nd["kind"] == 1'


def self_test() -> int:
    for name, text in PLANTED.items():
        if not list(findings(text)):
            print(f"kind lint: planted {name}: not caught", file=sys.stderr)
            return 1
    if sys.version_info >= (3, 10) and not list(findings(PLANTED_MATCH)):
        print("kind lint: planted match: not caught", file=sys.stderr)
        return 1
    if list(findings(CLEAN)):
        print(f"kind lint: flags clean code: {list(findings(CLEAN))}", file=sys.stderr)
        return 1
    print(f"kind lint: {len(PLANTED) + (1 if sys.version_info >= (3, 10) else 0)} planted comparisons caught, clean code passes")
    return 0


def main(argv: List[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    if not argv:
        print("usage: kind_lint.py PATH... | --self-test", file=sys.stderr)
        return 2
    found = scan(argv)
    for f in found:
        print(f)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
