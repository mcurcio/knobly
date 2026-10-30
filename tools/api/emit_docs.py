"""The docs emitter: the Markdown tables read on GitHub, rewritten between markers from the same model.

Each table sits between `<!-- generated: NAME (tools/gen-api.py docs) -->` and `<!-- end generated -->`. These are the
one generated output that is committed: the spec and READMEs are read on GitHub as they are, and the user guide's
pages (docs/site/pages/) are built as written, so the tables must be in the repository (spec/codegen.md section 6). `tools/gen-api.py --check` (run by tools/check.sh) fails when a committed table differs
from what the schema gives, so a table cannot drift from its source.

Nothing here knows a target language: each binding is a column, in the order of the model's languages, and every cell
is spelled through that binding's ``Language`` (its casing, ``enum_form``, ``generic``, ``construct``,
``extends_word``, ``cause_field``, ``omitted_as``, ``type_case``, its constants' names, its module paths and its error
roots). A new binding is a new
column with no edit here.

The hand-written pages' tables with a column per binding (the members tables, ``<!-- generated: members: NAME ... -->``)
keep their rows in docs/tables.json: each row names a schema thing (``ref``) that every binding's column spells through
its ``Language`` (``member_spelling``, ``property_form``, ``call_params``, ``trait_forms``), so those tables gain a
binding's column with no edit too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from .loader import (
    MODULES,
    REPO,
    Concept,
    ErrorGroup,
    Function,
    Language,
    Member,
    Model,
    Param,
    SchemaError,
    Type,
    constant_name,
    pascal,
    pattern_body,
    upper_snake,
)

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
                cells.append(f"`{lang.type_case(g.name)}`, {lang.extends_word} `{g.base[lang.key]['base']}`")
            else:
                cells.append(f"`{lang.type_case(g.name)}`")
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
        case = language.type_case
        lines: List[str] = []

        def fields(g: object) -> str:
            names = [f for f, _ in g.fields]  # type: ignore[attr-defined]
            if g.cause == "chained" or g.sort == "base":  # type: ignore[attr-defined]
                names.append(language.cause_field)
            return f"  ({', '.join(names)})" if names and g.sort != "base" else ""  # type: ignore[attr-defined]

        def down(parent: str, depth: int) -> None:
            kids = [g for g in model.groups if g.parent == parent]
            for i, g in enumerate(kids):
                lines.append("   " * depth + ("└─ " if i == len(kids) - 1 else "├─ ") + case(g.name) + fields(g))
                down(g.name, depth + 1)

        for g in model.groups:
            if g.parent is None and g.sort == "base":
                lines += [g.base[lang]["base"], f"└─ {case(g.name)}  (expected outcomes)"]
                down(g.name, 1)
        lines += ["", "program bugs, not under " + case(next(g.name for g in model.groups if g.sort == "base")) + ":"]
        for g in model.groups:
            if g.sort == "program bug":
                if g.builtin(lang):
                    lines.append(f"{g.builtin(lang)}  ({g.name})")
                else:
                    lines.append(f"{case(g.name)} {language.extends_word} {g.base[lang]['base']}  ({g.name})")
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
    name = language.type_case(c.name)
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
        name = language.construct(language.type_case(f.factory["of"]))  # type: ignore[index]
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
                    f"`{lang.type_case(k.name)}` ({lang.enum_form})" if lang.key in k.languages else lang.omitted_as(k.name, "kind list"))))
        if layer == model.registry_layer:
            rows.append(row("`diagnostic code`", lambda lang: f"`{lang.type_case('diagnostic code')}` ({lang.enum_form})"))
            for g in model.groups:
                rows.append(row(f"`{g.name}` (error group)", lambda lang, g=g: f"`{g.builtin(lang.key) or lang.type_case(g.name)}`"))  # type: ignore[misc]
        for f in model.functions:
            if f.layer == layer:
                rows.append(row(f"`{f.name}` (free function)", lambda lang, f=f: function_cell(model, f, lang)))  # type: ignore[misc]
        for c in model.constants:
            if c.layer == layer:
                rows.append(row(f"`{c.name}` (constant)", lambda lang, c=c: f"`{constant_name(lang, c)}`"))  # type: ignore[misc]
        return "\n".join(rows)

    return make


# --- members tables: rows from docs/tables.json, a column per binding ----------------------------------------------------

TABLES = REPO / "docs" / "tables.json"
ROW_KEYS = {"what", "ref", "receiver", "names", "last", "cells"}


def member_name(language: Language, c: Concept, m: Member) -> str:
    spell = language.member_spelling
    return spell(c.name, m.name) if spell is not None else language.function_case(m.name)


def call_params(language: Language, params: List[Param]) -> str:
    return language.call_params([(language.function_case(p.name), p.passed, p.optional) for p in params])


def member_ref(model: Model, c: Concept, m: Member, language: Language, receiver: str) -> str:
    """A member in one binding: a trait's documentation form, a property's read, or a method's call with its
    parameters; after ``receiver.`` when the row names one."""
    if language.key not in c.languages:
        return language.omitted_as(c.name, c.nature)
    if m.trait is not None:
        return language.trait_forms[m.trait]
    name = member_name(language, c, m)
    text = language.property_form(name) if m.member == "property" else f"{name}({call_params(language, m.params)})"
    return f"`{receiver}.{text}`" if receiver else f"`{text}`"


def call_ref(model: Model, f: Function, language: Language) -> str:
    """A free function's call with its parameters, and where it is imported from; none where the binding lacks it."""
    mod = model.function_module(f, language.key)
    if mod is None:
        return "none"
    fac = (f.factory or {}).get(language.key)
    params = call_params(language, f.params)
    if fac == "package function":
        name = f"{model.package}({params})"
    elif fac == "constructor":
        name = language.construct(language.type_case(f.factory["of"])).replace("(...)", f"({params})")  # type: ignore[index]
    else:
        name = f"{language.function_case(f.name)}({params})"
    return f"`{name}` from `{mod}`"


def group_ref(model: Model, g: ErrorGroup, language: Language) -> str:
    """An error class with the fields a program reads from it (its chained cause's among them)."""
    builtin = g.builtin(language.key)
    if builtin:
        return f"`{builtin}`"
    fields = [f"`{language.property_form(language.function_case(f))}`" for f, _ in g.fields]
    if g.cause == "chained":
        fields.append(f"`{language.cause_field}`")
    return f"`{language.type_case(g.name)}`" + (f" ({', '.join(fields)})" if fields else "")


def trait_ref(model: Model, trait: str, language: Language) -> str:
    """codegen.md's trait table: a trait's or typed field's form (Language.trait_forms), or what the binding's own facts
    say: its factories, native types, adapter modules, what it leaves out, the names its traits add, its root error
    classes and its argument type sentence."""
    if trait == "factory":
        return ", ".join(function_cell(model, f, language) for f in model.functions if f.factory is not None)
    if trait == "native":
        kept = [c for c in model.concepts if c.is_ == "native" and language.key in c.languages]
        return "; ".join(f"`{c.name}`: `{language.native[c.name]}`" for c in kept) or "none"
    if trait == "module":
        return ", ".join(f"`{mod}`: " + (f"`{model.package}{language.sep}{language.modules[mod]}`" if mod in language.modules else "none")
                         for mod in MODULES)
    if trait == "omit":
        gone = [f"`{c.name}`" for c in model.concepts if language.key not in c.languages and c.module is None]
        gone += [f"`{k.name}`" for k in model.kinds if language.key not in k.languages]
        gone += [f"the `{mod}` module" for mod in MODULES if mod not in language.modules]
        return ", ".join(gone) or "nothing"
    if trait == "names":
        return ", ".join(f"`{name}`" for _, name, _ in language.trait_names(model)) or "none"
    if trait == "error roots":
        return ", ".join(f"`{g}`: `{form.get('base') or form.get('builtin')}`" for g, form in language.error_roots.items())
    if trait == "argument type message":
        return f"`{model.argument_type_message[language.key]}`"
    if trait not in language.trait_forms:
        raise SchemaError(f"docs/tables.json: 'trait: {trait}' is no trait, typed field or binding fact")
    return language.trait_forms[trait]


def resolve(model: Model, ref: str) -> Callable[[Language, str], str]:
    """What a row's ``ref`` names, as a cell maker (language, receiver) -> text; a ref naming nothing, or two things,
    fails the docs build so a renamed schema name cannot leave a stale row."""
    if ref.startswith("trait: "):
        trait = ref[len("trait: "):]
        for language in langs(model):
            trait_ref(model, trait, language)  # an unknown trait fails here, whatever the row's cells
        return lambda language, receiver: trait_ref(model, trait, language)
    if "." in ref:
        cname, mname = ref.split(".", 1)
        c = model.concept.get(cname)
        m = next((m for m in model.all_members(c) if m.name == mname), None) if c is not None else None
        if c is None or m is None:
            raise SchemaError(f"docs/tables.json: ref {ref!r} names no member of a concept")
        return lambda language, receiver: member_ref(model, c, m, language, receiver)  # type: ignore[arg-type]
    prefix, _, rest = ref.rpartition(": ")
    if prefix not in ("", "layer", "module"):
        raise SchemaError(f"docs/tables.json: ref {ref!r}: a prefix is 'trait', 'layer' or 'module'")
    found: List[Callable[[Language, str], str]] = []
    if not prefix and rest in model.concept:
        found.append(lambda language, receiver: concept_cell(model, model.concept[rest], language))
    if not prefix:
        found += [lambda language, receiver, f=f: call_ref(model, f, language) for f in model.functions if f.name == rest]  # type: ignore[misc]
    if not prefix and rest in model.group:
        found.append(lambda language, receiver: group_ref(model, model.group[rest], language))
    if not prefix and rest in model.kind:
        found.append(lambda language, receiver: (f"`{language.type_case(rest)}`" if language.key in model.kind[rest].languages
                                                 else language.omitted_as(rest, "kind list")))
    if prefix in ("", "layer") and rest in model.layer:
        found.append(lambda language, receiver: f"`{model.module(rest, language.sep)}`")
    if prefix in ("", "module") and rest in MODULES:
        found.append(lambda language, receiver: (f"`{model.package}{language.sep}{language.modules[rest]}`"
                                                 if rest in language.modules else "none"))
    if not found:
        raise SchemaError(f"docs/tables.json: ref {ref!r} names nothing the schema defines")
    if len(found) > 1:
        raise SchemaError(f"docs/tables.json: ref {ref!r} names {len(found)} things; write 'module: {rest}' or 'layer: {rest}'")
    return found[0]


def short_name(model: Model, ref: str, language: Language) -> str:
    """A name a row lists after its cell (an entry point's exports): the identifier only, no parameters or module."""
    if ref in model.concept:
        return f"`{language.type_case(ref)}`" if language.key in model.concept[ref].languages else ""
    if ref in model.kind:
        return f"`{language.type_case(ref)}`" if language.key in model.kind[ref].languages else ""
    if ref in model.group:
        return f"`{model.group[ref].builtin(language.key) or language.type_case(ref)}`"
    f = next((f for f in model.functions if f.name == ref), None)
    if f is not None:
        if model.function_module(f, language.key) is None:
            return ""
        fac = (f.factory or {}).get(language.key)
        if fac == "package function":
            return f"`{model.package}`"
        return f"`{language.type_case(f.factory['of']) if fac == 'constructor' else language.function_case(f.name)}`"  # type: ignore[index]
    raise SchemaError(f"docs/tables.json: name {ref!r} is no concept, kind list, error group or free function")


def read_tables() -> Dict[str, dict]:
    return json.loads(TABLES.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def members(name: str) -> Callable[[Model], str]:
    """A hand-written page's table with a column per binding: its rows from docs/tables.json, each language cell
    spelled from the row's ``ref`` through that binding's Language; a row's ``cells`` replace a language's cell only
    where the schema cannot spell the text (spec/codegen.md section 6)."""

    def make(model: Model) -> str:
        spec = read_tables()[name]
        first, last = list(spec["first"]), list(spec.get("last", []))
        if len(first) != 1:
            raise SchemaError(f"docs/tables.json: table {name!r}: 'first' is one column (the row's 'what')")
        rows = header(first, model, last)
        keys = set(model.languages)
        for i, row in enumerate(spec["rows"]):
            where = f"docs/tables.json: table {name!r}, row {i + 1}"
            if set(row) - ROW_KEYS or "ref" not in row or "what" not in row:
                raise SchemaError(f"{where}: a row has 'what' and 'ref', and may have only {sorted(ROW_KEYS)}")
            if len(row.get("last", [])) != len(last):
                raise SchemaError(f"{where}: {len(row.get('last', []))} 'last' cells for {len(last)} columns")
            cells = dict(row.get("cells", {}))
            if set(cells) - keys:
                raise SchemaError(f"{where}: cells for {sorted(set(cells) - keys)}, which is no binding")
            refs = row["ref"] if isinstance(row["ref"], list) else [row["ref"]]
            makers = [resolve(model, r) for r in refs]
            names = row.get("names", [])
            out = []
            for language in langs(model):
                if language.key in cells:
                    out.append(cells[language.key])
                    continue
                text = ", ".join(make_(language, row.get("receiver", "")) for make_ in makers)
                listed = [n for n in (short_name(model, r, language) for r in names) if n]
                if listed and text != "none":
                    text += ": " + ", ".join(listed) + ", ..."
                out.append(text)
            rows.append(f"| {' | '.join([row['what'], *out, *row.get('last', [])])} |")
        return "\n".join(rows)

    return make


def tables(model: Model) -> Dict[str, Tuple[Path, Callable[[Model], str]]]:
    """Every generated table, by its marker name: one glossary table per layer the schema lists, and one members table
    per entry in docs/tables.json."""
    return {
        "diagnostic codes": (REPO / "spec" / "spec.md", spec_codes),
        "error codes": (REPO / "docs" / "site" / "pages" / "diagnostics.md", guide_codes),
        "adapter requests": (REPO / "spec" / "conformance.md", protocol_requests),
        "adapter dumps": (REPO / "spec" / "conformance.md", protocol_dumps),
        "error groups": (REPO / "spec" / "spec.md", error_groups),
        "argument type messages": (REPO / "spec" / "spec.md", argument_type_messages),
        "limits": (REPO / "spec" / "spec.md", limits),
        "class tree": (REPO / "spec" / "contract.md", class_tree),
        "adapters": (REPO / "spec" / "contract.md", adapters),
        **{f"names: {layer.name}": (REPO / "spec" / "glossary.md", layer_names(layer.name)) for layer in model.layers},
        **{f"members: {name}": (REPO / spec["file"], members(name)) for name, spec in read_tables().items()},
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
