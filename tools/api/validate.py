"""Check spec/schema/{api,diagnostics,protocol}.json against spec/schema/api.schema.json (JSON Schema 2020-12), then
check that the meta-schema bites: a planted copy with a per-language spelling, a per-language error base, a language
list, a note in place of doc and rationale, a free-text type, an unknown trait and an unknown 'found by' must each be
refused (the schema names no language: spec/codegen.md section 10). Run by tools/check.sh as `uv run --with jsonschema python tools/api/validate.py`
(the one third-party package tools/ uses, for the shape check only; the generator itself needs none)."""

import copy
import json
import sys
from pathlib import Path

import jsonschema

SCHEMA = Path(__file__).resolve().parent.parent.parent / "spec" / "schema"


def main() -> int:
    meta = json.loads((SCHEMA / "api.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(meta)
    validator = jsonschema.Draft202012Validator(meta)
    files = {name: json.loads((SCHEMA / name).read_text(encoding="utf-8")) for name in ("api.json", "diagnostics.json", "protocol.json")}
    failed = False
    for name, data in files.items():
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        for e in errors[:5]:
            print(f"{name}: {'/'.join(map(str, e.absolute_path))}: {e.message[:300]}", file=sys.stderr)
        failed |= bool(errors)

    def concept(a, n):
        return next(c for c in a["concepts"] if c["name"] == n)

    plants = {
        "per-language spelling": ("api.json", lambda a: concept(a, "document").__setitem__("ts", "IDocument")),
        "per-language error base": ("api.json", lambda a: a["error groups"][0].__setitem__("py", {"base": "Exception"})),
        "language list": ("api.json", lambda a: concept(a, "document").__setitem__("languages", ["ts"])),
        "note for doc": ("api.json", lambda a: concept(a, "document").__setitem__("note", "a file (milestone 5)")),
        "free-text type": ("api.json", lambda a: concept(a, "copy")["members"][1].__setitem__("type", "the steps, innermost first")),
        "unknown trait": ("api.json", lambda a: concept(a, "place")["members"][-1].__setitem__("trait", "display")),
        "spell note": ("api.json", lambda a: concept(a, "place")["members"][-1].__setitem__("spell", {"ts": "toString()"})),
        "unknown found by": ("diagnostics.json", lambda d: d["codes"][0].__setitem__("found by", ["render"])),
    }
    for plant, (name, change) in plants.items():
        broken = copy.deepcopy(files[name])
        change(broken)
        if validator.is_valid(broken):
            print(f"planted {plant}: not caught", file=sys.stderr)
            failed = True
    if not failed:
        print(f"3 files match api.schema.json; {len(plants)} planted breakages caught")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
