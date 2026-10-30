#!/usr/bin/env python3
"""Write the C++ binding as one header (design.md 2.5): every public header and what it includes, concatenated in
include order, each file once. The automated release flow attaches it as knobly.hpp (.github/release-cpp.sh);
it is never committed.

    python3 tools/amalgamate.py [--include cpp/include] --output knobly.hpp

Reads the include directory as it is, so the generated headers must exist (bash tools/gen.sh cpp). The single
header is header-only mode only: it stops the compile when KNOBLY_HEADER_ONLY is defined to 0. Standard library
headers stay as #include lines. A knobly #include inside a preprocessor condition is inlined only when the
condition is the file's own include guard, `#if KNOBLY_HEADER_ONLY` (true here) or `#ifndef` of the included
file's guard (true the first time); any other condition stops the script, since inlining the file there would hide
it from every later include. Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INCLUDE = re.compile(r"^\s*#\s*include\s*<(knobly/[^>]+)>")
GUARD = re.compile(r"^\s*#\s*ifndef\s+(\w+)\s*$")
DEFINE = re.compile(r"^\s*#\s*define\s+(\w+)\s*$")
OPEN = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b(.*)$")
ELSE = re.compile(r"^\s*#\s*(elif|elifdef|elifndef|else)\b")
ENDIF = re.compile(r"^\s*#\s*endif\b")
VERSION = re.compile(r"^#define KNOBLY_VERSION_(MAJOR|MINOR|PATCH) (\d+)$", re.M)
HEADER_ONLY = "if KNOBLY_HEADER_ONLY"


class Amalgamation:
    def __init__(self, include: Path) -> None:
        self.include = include
        self.done: set[str] = set()
        self.out: list[str] = []

    def guard(self, name: str) -> str | None:
        """The include guard of a header: its first #ifndef, when the next line defines the same name."""
        path = self.include / name
        if not path.is_file():
            sys.exit(f"amalgamate.py: {name}: not found under {self.include}")
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip() and not line.lstrip().startswith("//"):
                found = GUARD.match(line)
                if found and i + 1 < len(lines):
                    defined = DEFINE.match(lines[i + 1])
                    if defined and defined.group(1) == found.group(1):
                        return found.group(1)
                return None
        return None

    def add(self, name: str) -> None:
        if name in self.done:
            return
        own_guard = self.guard(name)
        path = self.include / name
        self.done.add(name)
        # One entry per open condition: its text after '#', and whether it is known true on this path.
        conditions: list[tuple[str, bool]] = []
        self.out.append(f"// ---- begin {name}")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            opened, other, closed = OPEN.match(line), ELSE.match(line), ENDIF.match(line)
            if opened:
                text = f"{opened.group(1)} {opened.group(2).strip()}"
                conditions.append((text, (not conditions and text == f"ifndef {own_guard}") or text == HEADER_ONLY))
            elif other and conditions:
                conditions[-1] = (conditions[-1][0] + " (else branch)", False)
            elif closed and conditions:
                conditions.pop()
            included = INCLUDE.match(line)
            if not included:
                self.out.append(line)
                continue
            target = included.group(1)
            if target in self.done:
                continue
            target_guard = self.guard(target)
            for text, known in conditions:
                if not known and text != f"ifndef {target_guard}":
                    sys.exit(
                        f"amalgamate.py: {name}:{number}: #include <{target}> under '#{text}', which this "
                        "script cannot prove true; include it unconditionally or extend the script"
                    )
            self.add(target)
        self.out.append(f"// ---- end {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--include", type=Path, default=Path(__file__).resolve().parent.parent / "cpp" / "include")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.include / "knobly"
    if not (root / "knobly.hpp").is_file():
        sys.exit(f"amalgamate.py: {root}/knobly.hpp is missing: generate the headers first (bash tools/gen.sh cpp)")
    config = (root / "support" / "config.hpp").read_text(encoding="utf-8")
    version = ".".join(dict(VERSION.findall(config))[part] for part in ("MAJOR", "MINOR", "PATCH"))

    # Every public header but the compiled-mode implementation file; knobly.hpp first, as every layer's includes.
    public = sorted(p.name for p in root.glob("*.hpp") if p.name != "implementation.hpp")
    public.sort(key=lambda name: name != "knobly.hpp")
    amalgamation = Amalgamation(args.include)
    for name in public:
        amalgamation.add(f"knobly/{name}")

    head = [
        f"// knobly {version}: the C++ binding in one header, header-only mode. Generated by tools/amalgamate.py",
        "// from the binding's headers; do not edit. MIT License (the LICENSE file of the release source archive).",
        "#ifndef KNOBLY_SINGLE_HEADER_HPP",
        "#define KNOBLY_SINGLE_HEADER_HPP",
        "",
        "#if defined(KNOBLY_HEADER_ONLY) && !KNOBLY_HEADER_ONLY",
        '#error "the single header is header-only: for compiled mode use the release source archive"',
        "#endif",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(head + amalgamation.out + ["", "#endif  // KNOBLY_SINGLE_HEADER_HPP", ""]), encoding="utf-8"
    )
    print(f"amalgamate.py: {args.output}: knobly {version}, {len(amalgamation.done)} headers")


if __name__ == "__main__":
    main()
