"""Generate each binding's API declarations from spec/schema/ (spec/codegen.md).

    python3 tools/gen-api.py ts       -> ts/src/gen/api/*.ts and ts/conformance/shapes.ts
    python3 tools/gen-api.py py       -> py/src/villanelle/_api/*.py and py/conformance/shapes.py
    python3 tools/gen-api.py docs     -> rewrites the generated tables in spec/ (committed: they are read on GitHub)
    python3 tools/gen-api.py --check  -> checks the schema (and that each check bites), renders both bindings into a temp
                                         dir, and fails when a committed generated table is stale

tools/gen.sh runs `ts` or `py` after the parser, so every TypeScript package script and py/tests/conftest.py regenerate
the code. Generated code is never committed (owner, 2026-10-23: "Don't commit the generated code, just the source").

The work is split as a compiler is: tools/api/loader.py reads and checks the schema into one language-neutral model;
one emitter per language renders it (tools/api/emit_ts.py, emit_py.py), and emit_docs.py renders the Markdown tables.
A new binding adds one emitter and one adapter (spec/binding-guide.md section 5). Python 3.9+ standard library only.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import emit_docs, emit_py, emit_ts  # noqa: E402
from api.loader import REPO, Model, SchemaError, planted, read_schema  # noqa: E402

OUT = {
    "ts": (REPO / "ts" / "src" / "gen" / "api", REPO / "ts" / "conformance"),
    "py": (REPO / "py" / "src" / "villanelle" / "_api", REPO / "py" / "conformance"),
}
EMITTERS = {"ts": emit_ts, "py": emit_py}


def write(files: Dict[str, str], out: Path) -> None:
    """Write into a temp dir inside `out`, then move each file into place: no reader sees a half-written file."""
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp.", dir=out))
    try:
        for name, text in files.items():
            (tmp / name).write_text(text, encoding="utf-8")
        for name in files:
            os.replace(tmp / name, out / name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: List[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("ts", "py", "docs", "--check"):
        print("usage: tools/gen-api.py <ts|py|docs|--check>", file=sys.stderr)
        return 2
    try:
        schema = read_schema()
        model = Model(*schema)
        if argv[0] == "--check":
            caught = planted(*schema)
            with tempfile.TemporaryDirectory() as tmp:
                for lang, emitter in EMITTERS.items():
                    write(emitter.render(model), Path(tmp) / lang)
                    write(emitter.render_shapes(model), Path(tmp) / lang / "conformance")
            stale = emit_docs.stale(model)
            if stale:
                print(f"gen-api.py: generated tables are stale (run python3 tools/gen-api.py docs): {', '.join(stale)}", file=sys.stderr)
                return 1
            print(f"schema checked; {len(caught)} planted breakages caught; ts and py rendered; docs tables current")
            return 0
        if argv[0] == "docs":
            for path in emit_docs.write(model):
                print(f"wrote {path.relative_to(REPO)}")
            return 0
        api_out, shapes_out = OUT[argv[0]]
        emitter = EMITTERS[argv[0]]
        write(emitter.render(model), api_out)
        write(emitter.render_shapes(model), shapes_out)
    except (SchemaError, KeyError, TypeError, ValueError) as e:
        print(f"gen-api.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
