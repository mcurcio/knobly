"""Generate each binding's API declarations from spec/schema/ (spec/codegen.md).

    python3 tools/gen-api.py ts       -> ts/src/gen/api/*.ts and ts/conformance/shapes.ts
    python3 tools/gen-api.py py       -> py/src/villanelle/_api/*.py, py/conformance/shapes.py and py/tests/api_contract.py
    python3 tools/gen-api.py docs     -> rewrites the generated tables in spec/ (committed: they are read on GitHub)
    python3 tools/gen-api.py --check  -> checks the schema (and that each check bites), renders both bindings into a temp
                                         dir, renders a third binding's stub (tools/api/stub.py) to prove a binding needs
                                         no schema edit, and fails when a committed generated table is stale

tools/gen.sh runs `ts` or `py` after the parser, so every TypeScript package script and py/tests/conftest.py regenerate
the code. Generated code is never committed (owner, 2026-10-23: "Don't commit the generated code, just the source").

The work is split as a compiler is: tools/api/loader.py reads and checks the schema into one language-neutral model;
one emitter per language renders it (tools/api/emit_ts.py, emit_py.py), and emit_docs.py renders the Markdown tables.
Each emitter hands the loader its Language (EMITTERS below); spec/codegen.md section 10 lists what else a new binding
touches. Python 3.9+ standard library only.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import emit_docs, emit_py, emit_ts, stub  # noqa: E402
from api.loader import REPO, Model, SchemaError, planted, read_schema  # noqa: E402

# Each emitter's outputs: the folder the binding's code is generated into (all generated), and further folders that
# also hold hand-written files (the adapter's shapes; Python's test contract, spec/codegen.md section 4).
OUT = {
    "ts": (REPO / "ts" / "src" / "gen" / "api", {"shapes": REPO / "ts" / "conformance"}),
    "py": (REPO / "py" / "src" / "villanelle" / "_api", {"shapes": REPO / "py" / "conformance", "contract": REPO / "py" / "tests"}),
}
EMITTERS = {"ts": emit_ts, "py": emit_py}
LANGUAGES = [e.LANGUAGE for e in EMITTERS.values()]


def extra(emitter: object) -> Dict[str, Dict[str, str]]:
    """An emitter's outputs beside its code folder, by OUT's key: render_shapes, and render_contract where it has one."""
    out = {"shapes": emitter.render_shapes}  # type: ignore[attr-defined]
    if hasattr(emitter, "render_contract"):
        out["contract"] = emitter.render_contract  # type: ignore[attr-defined]
    return out  # type: ignore[return-value]


def check_stub(schema: tuple) -> int:
    """A third binding is an emitter with no schema edit: the stub's Language loads beside the real ones and renders."""
    names = stub.render(Model(*schema, [*LANGUAGES, stub.LANGUAGE]))["names.txt"]
    if "villanelle::rendered render\n" not in names or "villanelle::fetch" in names:
        raise SchemaError(f"the third-binding stub rendered an unexpected names list:\n{names}")
    return names.count("\n")


def write(files: Dict[str, str], out: Path, owned: bool = True) -> None:
    """Write into a temp dir inside `out`, then move each file into place: no reader sees a half-written file. When
    `owned` (the folder is all generated), a file the emitter no longer writes is removed, so a dropped module cannot
    linger and keep stale imports compiling."""
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".tmp.", dir=out))
    try:
        for name, text in files.items():
            (tmp / name).write_text(text, encoding="utf-8")
        for name in files:
            os.replace(tmp / name, out / name)
        if owned:
            for old in out.iterdir():
                if old.is_file() and old.name not in files and old.name != ".gitignore":
                    old.unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: List[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("ts", "py", "docs", "--check"):
        print("usage: tools/gen-api.py <ts|py|docs|--check>", file=sys.stderr)
        return 2
    try:
        schema = read_schema()
        model = Model(*schema, LANGUAGES)
        if argv[0] == "--check":
            caught = planted(*schema, LANGUAGES)
            with tempfile.TemporaryDirectory() as tmp:
                for lang, emitter in EMITTERS.items():
                    write(emitter.render(model), Path(tmp) / lang)
                    for key, render in extra(emitter).items():
                        write(render(model), Path(tmp) / lang / key)
            stub_names = check_stub(schema)
            stale = emit_docs.stale(model)
            if stale:
                print(f"gen-api.py: generated tables are stale (run python3 tools/gen-api.py docs): {', '.join(stale)}", file=sys.stderr)
                return 1
            print(f"schema checked; {len(caught)} planted breakages caught; ts and py rendered; a third binding's stub "
                  f"rendered {stub_names} names with no schema edit; docs tables current")
            return 0
        if argv[0] == "docs":
            for path in emit_docs.write(model):
                print(f"wrote {path.relative_to(REPO)}")
            return 0
        api_out, beside = OUT[argv[0]]
        emitter = EMITTERS[argv[0]]
        write(emitter.render(model), api_out)
        for key, render in extra(emitter).items():
            write(render(model), beside[key], owned=False)  # these folders hold hand-written files too
    except (SchemaError, KeyError, TypeError, ValueError, OSError) as e:
        print(f"gen-api.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
