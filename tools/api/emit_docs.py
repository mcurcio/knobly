"""The docs emitter: the Markdown tables read on GitHub, rewritten between markers from the same model.

Each table sits between `<!-- generated: NAME (tools/gen-api.py docs) -->` and `<!-- end generated -->`. These are the
one generated output that is committed: nothing builds the docs, so the text GitHub shows must be in the repository
(spec/codegen.md section 6). `tools/gen-api.py --check` (run by tools/check.sh) fails when a committed table differs
from what the schema gives, so a table cannot drift from its source.

Nothing here knows a target language: each binding is a column, in the order of the model's languages, and every cell
is spelled through that binding's ``Language`` (its casing, ``enum_form``, ``generic``, ``construct``,
``extends_word``, ``cause_field``, ``omitted_as``, its module paths and its error roots). A new binding is a new
column with no edit here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from .loader import REPO, Concept, Function, Language, Model, SchemaError, Type, pascal, pattern_body, upper_snake

BEGIN = "<!-- generated: {name} (tools/gen-api.py docs) -->"
END = "<!-- end generated -->"


def spec_codes(model: Model) -> str:
    rows = ["| Code | Spec name | Found by | Unreadable reason | Meaning |", "|---|---|---|---|---|"]
    for c in model.codes:
        rows.append(f"| {c.code} | `{c.name}` | {', '.join(c.found_by)} | {c.reason or 'none'} | {c.meaning} |")
    return "\n".join(rows)


def langs(model: Model) -> List[Language]:
    return list(model.languages.values())


def header(first: List[str], model: Model, last: List[str] = (), suffix: str = "") -> List[str]:  # type: ignore[assignment]
    cols = [*first, *(f"{lang.name}{suffix}" for lang in langs(model)), *last]
    return [f"| {' | '.join(cols)} |", "|" + "---|" * len(cols)]


def guide_codes(model: Model) -> str:
    rows = header(["Code"], model, ["Meaning", "At"], " name")
    for c in model.codes:
        cells = " | ".join(f"`{lang.code_case(c.name)}`" for lang in langs(model))
        rows.append(f"| {c.code} | {cells} | {c.summary} | {c.placed_at} |")
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
        if sh.doc:
            body += f" ({sh.doc})"
        rows.append(f"| {sh.name} | {body} |")
    return "\n".join(rows)


def protocol_requests(model: Model) -> str:
    rows = ["| `op` | Parameters | `ok` result | Level |", "|---|---|---|---|"]
    for r in model.protocol.requests:
        rows.append(f"| `{r.op}` | {r.params_doc} | {r.doc} | {r.level} |")
    return "\n".join(rows)


def error_groups(model: Model) -> str:
    """Spec 2.8's table: each group, its sort, when it is raised, and its class in each binding."""
    rows = header(["Group", "Sort", "Raised when"], model)
    for g in model.groups:
        sort = g.sort if g.parent is None else f"{g.sort}, under `{g.parent}`"
        cells = []
        for lang in langs(model):
            if g.builtin(lang.key):
                cells.append(f"`{g.builtin(lang.key)}`")
            elif g.parent is None:
                cells.append(f"`{pascal(g.name)}`, {lang.extends_word} `{g.base[lang.key]['base']}`")
            else:
                cells.append(f"`{pascal(g.name)}`")
        rows.append(f"| `{g.name}` | {sort} | {g.raised_when} | {' | '.join(cells)} |")
    return "\n".join(rows)


def argument_type_messages(model: Model) -> str:
    """Spec 6.9's table: each binding's argument type error sentence, from its emitter's Language."""
    rows = ["| Binding | Message |", "|---|---|"]
    for lang in langs(model):
        rows.append(f"| {lang.name} | `{model.argument_type_message[lang.key]}` |")
    return "\n".join(rows)


def adapters(model: Model) -> str:
    """Contract 5's table: each adapter (a free function of the adapter layer returning a port) with its port and its
    call in each binding, from the import path that binding's Language gives it."""
    ports = {c.name for c in model.concepts if c.nature == "port"}
    rows = header(["Spec name", "Port"], model)
    for f in model.functions:
        if f.layer != model.adapter_layer or f.returns.form != "name" or f.returns.name not in ports:
            continue
        cells = [function_cell(model, f, lang, call=True) for lang in langs(model)]
        rows.append(f"| `{f.name}` | {f.returns.name} | {' | '.join(cells)} |")
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
            shown = "^" + pattern_body(str(c.value), lambda cp: f"\\u{cp:04x}") + "$"
            out.append(f"- `{upper_snake(c.name)}` ({c.about} pattern; the {c.layer} layer): `{shown}`, {c.means}.")
    return "\n".join(out)


def class_tree(model: Model) -> str:
    """Contract 4.2: each binding's error class tree, the expected outcomes under the base, then the program bugs."""

    def tree(language: Language) -> List[str]:
        lang = language.key
        lines: List[str] = []

        def fields(g: object) -> str:
            names = [f for f, _ in g.fields]  # type: ignore[attr-defined]
            if g.cause == "chained" or g.sort == "base":  # type: ignore[attr-defined]
                names.append(language.cause_field)
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
                    lines.append(f"{pascal(g.name)} {language.extends_word} {g.base[lang]['base']}  ({g.name})")
        return lines

    out = []
    for language in langs(model):
        out += [f"{language.name}:", "", "```text", *tree(language), "```", ""]
    return "\n".join(out).rstrip("\n")


def concept_cell(model: Model, c: Concept, language: Language) -> str:
    lang = language.key
    if lang not in c.languages:
        return language.omitted_as(c.name, c.nature)
    if c.is_ == "native":
        return "the platform's own"
    name = pascal(c.name)
    if c.type_parameters:
        tps = ["T"] if len(c.type_parameters) == 1 else [pascal(t) for t in c.type_parameters]
        name = language.generic(name, tps)
    note = " (union)" if c.is_union else ""
    if c.module is not None:
        note += f" (`{model.concept_module(c, lang)}`)"
    return f"`{name}`{note}"


def function_cell(model: Model, f: Function, language: Language, call: bool = False) -> str:
    """A free function's spelling in one binding; ``call``: with its parameters and always with its import path."""
    lang = language.key
    mod = model.function_module(f, lang)
    if mod is None:
        return "none"
    fac = (f.factory or {}).get(lang)
    if fac == "package function":
        name = f"{model.package}(...)"
    elif fac == "constructor":
        name = language.construct(pascal(f.factory["of"]))  # type: ignore[index]
    else:
        name = language.function_case(f.name)
        if call:
            name += f"({', '.join(language.function_case(p.name) for p in f.params)})"
    if call:
        return f"`{name}` from `{mod}`"
    return f"`{name}`" + (f" (`{mod}`)" if f.module else "")


def layer_names(layer: str) -> Callable[[Model], str]:
    """The glossary's table of one layer: every concept, kind list, free function, constant (and, in the shared layer,
    error class) with its spelling in each binding, from the casing rule."""

    def make(model: Model) -> str:
        def row(spec: str, cell: Callable[[Language], str]) -> str:
            return f"| {spec} | {' | '.join(cell(lang) for lang in langs(model))} |"

        rows = header(["Spec name"], model)
        for c in model.concepts:
            if c.layer == layer:
                rows.append(row(f"`{c.name}`", lambda lang, c=c: concept_cell(model, c, lang)))  # type: ignore[misc]
        for k in model.kinds:
            if k.layer == layer:
                rows.append(row(f"`{k.name}` (kind list)", lambda lang, k=k: (  # type: ignore[misc]
                    f"`{pascal(k.name)}` ({lang.enum_form})" if lang.key in k.languages else lang.omitted_as(k.name, "kind list"))))
        if layer == model.registry_layer:
            rows.append(row("`diagnostic code`", lambda lang: f"`{pascal('diagnostic code')}` ({lang.enum_form})"))
            for g in model.groups:
                rows.append(row(f"`{g.name}` (error group)", lambda lang, g=g: f"`{g.builtin(lang.key) or pascal(g.name)}`"))  # type: ignore[misc]
        for f in model.functions:
            if f.layer == layer:
                rows.append(row(f"`{f.name}` (free function)", lambda lang, f=f: function_cell(model, f, lang)))  # type: ignore[misc]
        for c in model.constants:
            if c.layer == layer:
                rows.append(row(f"`{c.name}` (constant)", lambda lang, c=c: f"`{upper_snake(c.name)}`"))  # type: ignore[misc]
        return "\n".join(rows)

    return make


def tables(model: Model) -> Dict[str, Tuple[Path, Callable[[Model], str]]]:
    """Every generated table, by its marker name: one glossary table per layer the schema lists."""
    return {
        "diagnostic codes": (REPO / "spec" / "spec.md", spec_codes),
        "error codes": (REPO / "docs" / "rendered-tree.md", guide_codes),
        "adapter requests": (REPO / "spec" / "conformance.md", protocol_requests),
        "adapter dumps": (REPO / "spec" / "conformance.md", protocol_dumps),
        "error groups": (REPO / "spec" / "spec.md", error_groups),
        "argument type messages": (REPO / "spec" / "spec.md", argument_type_messages),
        "limits": (REPO / "spec" / "spec.md", limits),
        "class tree": (REPO / "spec" / "contract.md", class_tree),
        "adapters": (REPO / "spec" / "contract.md", adapters),
        **{f"names: {layer.name}": (REPO / "spec" / "glossary.md", layer_names(layer.name)) for layer in model.layers},
    }


def render_all(model: Model) -> Dict[str, str]:
    """Every table's text, written nowhere: the third-binding stub renders them to prove a binding is a column."""
    return {name: make(model) for name, (_, make) in tables(model).items()}


def _apply(text: str, name: str, table: str, path: Path) -> str:
    begin = BEGIN.format(name=name)
    pattern = re.compile(re.escape(begin) + r"\n.*?\n" + re.escape(END), re.S)
    if not pattern.search(text):
        raise SchemaError(f"{path.relative_to(REPO)}: no '{begin}' ... '{END}' region")
    return pattern.sub(lambda _: f"{begin}\n{table}\n{END}", text, count=1)


def rendered(model: Model) -> Dict[Path, Tuple[str, str]]:
    """Each file's current text and its text with every table regenerated."""
    out: Dict[Path, Tuple[str, str]] = {}
    for name, (path, make) in tables(model).items():
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
