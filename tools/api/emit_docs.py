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

from .loader import REPO, Concept, Function, Model, Type, camel, pascal, snake, upper_snake

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


def error_groups(model: Model) -> str:
    """Spec 2.8's table: each group, its sort, when it is raised, and its class in each binding."""
    rows = ["| Group | Sort | Raised when | TypeScript | Python |", "|---|---|---|---|---|"]
    for g in model.groups:
        sort = g.sort if g.parent is None else f"{g.sort}, under `{g.parent}`"
        cells = []
        for lang, word in (("ts", "extends"), ("py", "subclass of")):
            if g.builtin(lang):
                cells.append(f"`{g.builtin(lang)}`")
            elif g.parent is None:
                cells.append(f"`{pascal(g.name)}`, {word} `{g.base[lang]['base']}`")
            else:
                cells.append(f"`{pascal(g.name)}`")
        rows.append(f"| `{g.name}` | {sort} | {g.raised_when} | {cells[0]} | {cells[1]} |")
    return "\n".join(rows)


def limits(model: Model) -> str:
    """Spec 2.5's list: every constant of the rules module, the layer that exports it, and what it means."""
    out = []
    for c in model.constants:
        if c.sort == "limit":
            value = f"{c.value:,}"
            out.append(f"- `{upper_snake(c.name)}` ({c.about}; the {c.layer} layer): {value}, {c.means} ({c.code}).")
        elif c.sort == "words":
            words_ = ", ".join(f"`{w}`" for w in c.value)  # type: ignore[union-attr]
            out.append(f"- `{upper_snake(c.name)}` ({c.about}; the {c.layer} layer): {words_}: {c.means}.")
        else:
            out.append(f"- `{upper_snake(c.name)}` ({c.about} pattern; the {c.layer} layer): `{c.value}`, {c.means}.")
    return "\n".join(out)


def class_tree(model: Model) -> str:
    """Contract 4.2: each binding's error class tree, the expected outcomes under the base, then the program bugs."""

    def tree(lang: str) -> List[str]:
        lines: List[str] = []

        def fields(g: object) -> str:
            names = [f for f, _ in g.fields]  # type: ignore[attr-defined]
            if g.cause == "chained" or g.sort == "base":  # type: ignore[attr-defined]
                names.append("cause" if lang == "ts" else "__cause__")
            return f"  ({', '.join(names)})" if names and g.sort != "base" else ""  # type: ignore[attr-defined]

        def down(parent: str, depth: int) -> None:
            kids = [g for g in model.groups if g.parent == parent]
            for i, g in enumerate(kids):
                lines.append("   " * depth + ("└─ " if i == len(kids) - 1 else "├─ ") + pascal(g.name) + fields(g))
                down(g.name, depth + 1)

        for g in model.groups:
            if g.parent is None and g.sort == "base":
                lines += [g.base[lang]["base"], f"└─ {pascal(g.name)}  (expected outcomes)"]
                down(g.name, 1)
        lines += ["", "program bugs, not under " + pascal(next(g.name for g in model.groups if g.sort == "base")) + ":"]
        for g in model.groups:
            if g.sort == "program bug":
                if g.builtin(lang):
                    lines.append(f"{g.builtin(lang)}  ({g.name})")
                else:
                    lines.append(f"{pascal(g.name)} {'extends' if lang == 'ts' else 'subclass of'} {g.base[lang]['base']}  ({g.name})")
        return lines

    out = []
    for lang, title in (("ts", "TypeScript"), ("py", "Python")):
        out += [f"{title}:", "", "```text", *tree(lang), "```", ""]
    return "\n".join(out).rstrip("\n")


def concept_cell(model: Model, c: Concept, lang: str) -> str:
    if lang not in c.languages:
        return "none" if c.nature != "options" else "keyword arguments"
    if c.is_ == "native":
        return "the platform's own"
    name = pascal(c.name)
    if c.type_parameters:
        tps = ", ".join("T" for _ in c.type_parameters) if len(c.type_parameters) == 1 else ", ".join(pascal(t) for t in c.type_parameters)
        name += f"<{tps}>" if lang == "ts" else f"[{tps}]"
    note = " (union)" if c.is_union else ""
    if c.module is not None:
        note += f" (`{model.concept_module(c, lang)}`)"
    return f"`{name}`{note}"


def function_cell(model: Model, f: Function, lang: str) -> str:
    mod = model.function_module(f, lang)
    if mod is None:
        return "none"
    fac = (f.factory or {}).get(lang)
    if fac == "package function":
        name = f"{model.package}(...)"
    elif fac == "constructor":
        name = f"{'new ' if lang == 'ts' else ''}{pascal(f.factory['of'])}(...)"  # type: ignore[index]
    else:
        name = camel(f.name) if lang == "ts" else snake(f.name)
    return f"`{name}`" + (f" (`{mod}`)" if f.module else "")


def layer_names(layer: str) -> Callable[[Model], str]:
    """The glossary's table of one layer: every concept, kind list, free function, constant (and, in the shared layer,
    error class) with its spelling in each binding, from the casing rule."""

    def make(model: Model) -> str:
        rows = ["| Spec name | TypeScript | Python |", "|---|---|---|"]
        for c in model.concepts:
            if c.layer == layer:
                rows.append(f"| `{c.name}` | {concept_cell(model, c, 'ts')} | {concept_cell(model, c, 'py')} |")
        for k in model.kinds:
            if k.layer == layer:
                rows.append(f"| `{k.name}` (kind list) | `{pascal(k.name)}` (as-const object and type) | `{pascal(k.name)}` (`StrEnum`) |")
        if layer == "shared":
            rows.append("| `diagnostic code` | `DiagnosticCode` (as-const object and type) | `DiagnosticCode` (`StrEnum`) |")
            for g in model.groups:
                cells = [f"`{g.builtin(lang) or pascal(g.name)}`" for lang in ("ts", "py")]
                rows.append(f"| `{g.name}` (error group) | {cells[0]} | {cells[1]} |")
        for f in model.functions:
            if f.layer == layer:
                rows.append(f"| `{f.name}` (free function) | {function_cell(model, f, 'ts')} | {function_cell(model, f, 'py')} |")
        for c in model.constants:
            if c.layer == layer:
                rows.append(f"| `{c.name}` (constant) | `{upper_snake(c.name)}` | `{upper_snake(c.name)}` |")
        return "\n".join(rows)

    return make


TABLES: Dict[str, Tuple[Path, Callable[[Model], str]]] = {
    "diagnostic codes": (REPO / "spec" / "spec.md", spec_codes),
    "error codes": (REPO / "docs" / "rendered-tree.md", guide_codes),
    "adapter requests": (REPO / "spec" / "conformance.md", protocol_requests),
    "adapter dumps": (REPO / "spec" / "conformance.md", protocol_dumps),
    "error groups": (REPO / "spec" / "spec.md", error_groups),
    "limits": (REPO / "spec" / "spec.md", limits),
    "class tree": (REPO / "spec" / "contract.md", class_tree),
    **{f"names: {layer}": (REPO / "spec" / "glossary.md", layer_names(layer)) for layer in ("shared", "syntax", "io", "written", "rendered")},
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
