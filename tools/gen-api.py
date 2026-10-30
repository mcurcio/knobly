"""Generate each binding's API declarations from spec/schema/ (spec/codegen.md).

    python3 tools/gen-api.py ts       -> ts/src/gen/api/*.ts, ts/conformance/shapes.ts and ts/test/api-contract.ts
    python3 tools/gen-api.py py       -> py/src/villanelle/_api/*.py, py/conformance/shapes.py and py/tests/api_contract.py
    python3 tools/gen-api.py docs     -> rewrites the generated tables in spec/ (committed: they are read on GitHub)
    python3 tools/gen-api.py --check  -> checks the schema and every emitter's Language (and that each check bites),
                                         renders both bindings into a temp dir, renders a schema copy with one more
                                         layer to prove every layer gets a module, renders a third binding's stub
                                         (tools/api/stub.py) to prove a binding needs no schema edit and is a docs
                                         column, and fails when a committed generated table is stale

tools/gen.sh runs `ts` or `py` after the parser, so every TypeScript package script and py/tests/conftest.py regenerate
the code. Generated code is never committed (owner, 2026-10-23: "Don't commit the generated code, just the source").

The work is split as a compiler is: tools/api/loader.py reads and checks the schema into one language-neutral model;
one emitter per language renders it (tools/api/emit_ts.py, emit_py.py), and emit_docs.py renders the Markdown tables.
Each emitter hands the loader its Language (EMITTERS below); spec/codegen.md section 10 lists what else a new binding
touches. Building one binding loads only its own Language, so a broken fact in one emitter never blocks another
binding's build; --check and docs load them all. Python 3.9+ standard library only.
"""

from __future__ import annotations

import json
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
    "ts": (REPO / "ts" / "src" / "gen" / "api", {"shapes": REPO / "ts" / "conformance", "contract": REPO / "ts" / "test"}),
    "py": (REPO / "py" / "src" / "villanelle" / "_api", {"shapes": REPO / "py" / "conformance", "contract": REPO / "py" / "tests"}),
}
EMITTERS = {"ts": emit_ts, "py": emit_py}
LANGUAGES = [e.LANGUAGE for e in EMITTERS.values()]


def extra(emitter: object) -> Dict[str, Dict[str, str]]:
    """An emitter's outputs beside its code folder, by OUT's key: its adapter shapes and its test contract."""
    return {"shapes": emitter.render_shapes, "contract": emitter.render_contract}  # type: ignore[attr-defined]


def check_stub(schema: tuple) -> int:
    """A third binding is an emitter with no schema edit: the stub's Language loads beside the real ones and renders a
    module per layer, its error tree and every docs table (where it is a third column)."""
    model = Model(*schema, [*LANGUAGES, stub.LANGUAGE])
    files = stub.render(model)
    names = files["names.txt"]
    if "villanelle::rendered render\n" not in names or "villanelle::fetch" in names:
        raise SchemaError(f"the third-binding stub rendered an unexpected names list:\n{names}")
    for layer in model.layers:
        if any(c.layer == layer.name for c in model.concepts) and not files.get(f"{layer.name}.toy"):
            raise SchemaError(f"the third-binding stub rendered nothing for the {layer.name} layer")
    if stub.LANGUAGE.name not in files["docs/error groups.md"]:
        raise SchemaError("the docs tables have no column for the third-binding stub")
    return names.count("\n")


def check_layers(schema: tuple) -> None:
    """Every layer the schema lists gets a module in every binding: a copy with one more layer, holding one record, must
    render that record in each emitter and in the stub (a layer list kept by hand in an emitter would drop it)."""
    api, diagnostics, protocol = (json.loads(json.dumps(x)) for x in schema)
    api["layers"].append({"name": "planted", "holds": "a planted layer", "may import": [api["registry layer"]], "namespace": "own"})
    api["concepts"].append({"name": "widget", "layer": "planted", "nature": "record",
                            "members": [{"name": "size", "member": "property", "type": "integer"}]})
    model = Model(api, diagnostics, protocol, [*LANGUAGES, stub.LANGUAGE])
    for key, emitter in [*EMITTERS.items(), ("stub", stub)]:
        files = emitter.render(model)  # type: ignore[attr-defined]
        if not any(name.startswith("planted.") and "Widget" in text for name, text in files.items()):
            raise SchemaError(f"the {key} emitter rendered no module for a layer added to the schema")


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
    # Only the schema's own refusals and a missing file are reported in one line; any other exception is a generator
    # bug and keeps its traceback.
    try:
        schema = read_schema()
        if argv[0] == "--check":
            model = Model(*schema, LANGUAGES)
            caught = planted(*schema, LANGUAGES)
            with tempfile.TemporaryDirectory() as tmp:
                for lang, emitter in EMITTERS.items():
                    own = Model(*schema, [emitter.LANGUAGE])  # as `gen-api.py <lang>` builds it
                    write(emitter.render(own), Path(tmp) / lang)
                    for key, render in extra(emitter).items():
                        write(render(own), Path(tmp) / lang / key)
            check_layers(schema)
            stub_names = check_stub(schema)
            stale = emit_docs.stale(model)
            if stale:
                print(f"gen-api.py: generated tables are stale (run python3 tools/gen-api.py docs): {', '.join(stale)}", file=sys.stderr)
                return 1
            print(f"schema checked; {len(caught)} planted breakages caught; ts and py rendered; a planted layer rendered in "
                  f"every emitter; a third binding's stub rendered {stub_names} names, every layer and every docs table "
                  "with no schema edit; docs tables current")
            return 0
        if argv[0] == "docs":
            for path in emit_docs.write(Model(*schema, LANGUAGES)):
                print(f"wrote {path.relative_to(REPO)}")
            return 0
        api_out, beside = OUT[argv[0]]
        emitter = EMITTERS[argv[0]]
        model = Model(*schema, [emitter.LANGUAGE])
        write(emitter.render(model), api_out)
        for key, render in extra(emitter).items():
            write(render(model), beside[key], owned=False)  # these folders hold hand-written files too
    except (SchemaError, OSError) as e:
        print(f"gen-api.py: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
