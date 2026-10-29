"""The docs emitter: the Markdown tables read on GitHub, rewritten between markers from the same model.

Each table sits between `<!-- generated: NAME (tools/gen-api.py docs) -->` and `<!-- end generated -->`. These are the
one generated output that is committed: nothing builds the docs, so the text GitHub shows must be in the repository
(spec/codegen.md section 6). `tools/gen-api.py --check` (run by tools/check.sh) fails when a committed table differs
from what the schema gives, so a table cannot drift from its source.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from .loader import REPO, Model, Type, pascal, upper_snake

BEGIN = "<!-- generated: {name} (tools/gen-api.py docs) -->"
END = "<!-- end generated -->"


def spec_codes(model: Model) -> str:
    rows = ["| Code | Spec name | Found by | Unreadable reason | Meaning |", "|---|---|---|---|---|"]
    for c in model.codes:
        rows.append(f"| {c.code} | `{c.name}` | {', '.join(c.found_by)} | {c.reason or 'none'} | {c.meaning} |")
    return "\n".join(rows)


def guide_codes(model: Model) -> str:
    rows = ["| Code | TypeScript name | Python name | Meaning | At |", "|---|---|---|---|---|"]
    for c in model.codes:
        rows.append(f"| {c.code} | `{pascal(c.name)}` | `{upper_snake(c.name)}` | {c.summary} | {c.placed_at} |")
    return "\n".join(rows)


def wire(t: Type) -> str:
    if t.form == "name":
        return {"id": "id", "null": "null"}.get(t.name, t.name)
    if t.form == "literal":
        return f'"{t.name}"'
    if t.form == "list":
        return f"[{wire(t.item)}, ...]"
    if t.form == "union":
        return " \\| ".join(wire(a) for a in t.args)
    if t.form == "map":
        return f"{{name: {wire(t.args[1])}}}"
    if t.form == "tuple":
        return "[" + ", ".join(wire(a) for a in t.args) + "]"
    raise AssertionError(t)


def fields_text(fields: Dict[str, Type], optional: List[str]) -> str:
    parts = []
    for k, t in fields.items():
        q = "?" if k in optional else ""
        parts.append(f'"{k}"{q}' if t.form == "name" and t.name == "id" else f'"{k}"{q}: {wire(t)}')
    return "{" + ", ".join(parts) + "}"


def protocol_dumps(model: Model) -> str:
    rows = ["| Shape | Members |", "|---|---|"]
    for sh in model.protocol.shapes:
        if sh.tuple_ is not None:
            body = "`[" + ", ".join(wire(t) for t in sh.tuple_) + "]`"
        elif sh.one_of:
            body = "exactly one of " + ", ".join(f'`{{"{k}": {wire(t)}}}`' for k, t in sh.one_of.items())
        else:
            body = f"`{fields_text(sh.fields, sh.optional)}`"
            if sh.by_kind:
                body += "; by `kind`: " + "; ".join(f"`{k}` `{fields_text(v, [])}`" for k, v in sh.by_kind.items())
        if sh.note:
            body += f" ({sh.note})"
        rows.append(f"| {sh.name} | {body} |")
    return "\n".join(rows)


def protocol_requests(model: Model) -> str:
    rows = ["| `op` | Parameters | `ok` result | Level |", "|---|---|---|---|"]
    for r in model.protocol.requests:
        rows.append(f"| `{r.op}` | {r.params_note} | {r.note} | {r.level} |")
    return "\n".join(rows)


TABLES: Dict[str, Tuple[Path, Callable[[Model], str]]] = {
    "diagnostic codes": (REPO / "spec" / "spec.md", spec_codes),
    "error codes": (REPO / "docs" / "rendered-tree.md", guide_codes),
    "adapter requests": (REPO / "spec" / "conformance.md", protocol_requests),
    "adapter dumps": (REPO / "spec" / "conformance.md", protocol_dumps),
}


def _apply(text: str, name: str, table: str, path: Path) -> str:
    begin = BEGIN.format(name=name)
    pattern = re.compile(re.escape(begin) + r"\n.*?\n" + re.escape(END), re.S)
    if not pattern.search(text):
        raise ValueError(f"{path.relative_to(REPO)}: no '{begin}' ... '{END}' region")
    return pattern.sub(lambda _: f"{begin}\n{table}\n{END}", text, count=1)


def rendered(model: Model) -> Dict[Path, Tuple[str, str]]:
    """Each file's current text and its text with every table regenerated."""
    out: Dict[Path, Tuple[str, str]] = {}
    for name, (path, make) in TABLES.items():
        before, after = out.get(path, (path.read_text(encoding="utf-8"),) * 2)
        out[path] = (before, _apply(after, name, make(model), path))
    return out


def stale(model: Model) -> List[str]:
    return [str(p.relative_to(REPO)) for p, (before, after) in rendered(model).items() if before != after]


def write(model: Model) -> List[Path]:
    written = []
    for path, (before, after) in rendered(model).items():
        if before != after:
            path.write_text(after, encoding="utf-8")
            written.append(path)
    return written
