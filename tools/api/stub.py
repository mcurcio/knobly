"""A third binding in miniature: the proof that a new binding is an emitter and an adapter, with no schema edit and no
edit to the loader or the docs emitter (spec/codegen.md section 10). ``tools/gen-api.py --check`` builds the model with
this Language beside the real ones, renders one module per layer (every concept the binding keeps, each member's
signature and every type through a trivial type printer, the free functions, the error tree), and renders every docs
table with the stub as a third column. It fails if the schema names a language, or holds a fact only the two real
bindings supply, or a docs table spells a binding by hand.

Its facts are made up (a language called Toylang, ``::`` between module parts, classes of its own): they stand for what
a real emitter states about its language. Nothing is written to disk."""

from __future__ import annotations

from typing import Dict, List, Optional

from . import emit_docs
from .loader import IDIOM_FIELDS, TRAITS, Concept, Language, Model, Type, pascal, snake, upper_snake


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    return "value"


LANGUAGE = Language(
    key="toy",
    name="Toylang",
    sep="::",
    function_case=snake,
    code_case=upper_snake,
    public_kind=_public_kind,
    enum_form="enum",
    generic=lambda name, params: f"{name}{{{', '.join(params)}}}",
    construct=lambda name: f"make {name}(...)",
    extends_word="is a",
    cause_field="reason",
    error_roots={
        "knobly error": {"base": "Failure"},
        "detached error": {"base": "Failure"},
        "misuse error": {"base": "Failure"},
        "argument type error": {"builtin": "TypeFailure"},  # a group with no message of its own is the language's class
        "index out of range": {"builtin": "RangeFailure"},
    },
    argument_type_message="{member}: {parameter} wants text, got {got}",
    modules={"files": "disk"},  # no fetch or include adapter: their functions and concepts are left out
    trait_forms={t: f"toy {t}" for t in (*TRAITS, *IDIOM_FIELDS)},
)


def toy_type(model: Model, t: Type) -> str:
    """Every type form the grammar has, printed: a form the stub cannot print is one a new binding would trip on."""
    if t.form == "name":
        if t.name in model.concept and model.concept[t.name].is_ == "native":
            return LANGUAGE.native[t.name]
        known = t.name in model.concept or t.name in model.kind or t.name in model.group
        base = pascal(t.name) if known else t.name
        return LANGUAGE.generic(base, [toy_type(model, a) for a in t.args]) if t.args else base
    if t.form == "list":
        return f"list{{{toy_type(model, t.item)}}}"
    if t.form == "union":
        return " | ".join(toy_type(model, a) for a in t.args)
    if t.form == "map":
        return f"map{{{toy_type(model, t.args[0])}, {toy_type(model, t.args[1])}}}"
    if t.form == "function":
        *params, result = t.args
        return f"fn({', '.join(toy_type(model, p) for p in params)}) {toy_type(model, result)}"
    raise AssertionError(t)


def layer_module(model: Model, layer: str) -> str:
    out: List[str] = []
    for c in model.concepts:
        if c.layer != layer or LANGUAGE.key not in c.languages:
            continue
        out.append(f"type {pascal(c.name)} ({c.nature}) in {model.concept_module(c, LANGUAGE.key)}")
        for t in [c.extends, c.callback]:
            if t is not None:
                out.append(f"  = {toy_type(model, t)}")
        for m in model.all_members(c):
            params = ", ".join(f"{snake(p.name)} {toy_type(model, p.type)}" for p in m.params)
            out.append(f"  {snake(m.name)}({params}) {toy_type(model, m.type)}")
    for f in model.functions:
        mod = model.function_module(f, LANGUAGE.key)
        if f.layer == layer and mod is not None:
            params = ", ".join(f"{snake(p.name)} {toy_type(model, p.type)}" for p in f.params)
            out.append(f"fn {mod}{LANGUAGE.sep}{snake(f.name)}({params}) {toy_type(model, f.returns)}")
    return "".join(f"{line}\n" for line in out)


def render(model: Model) -> Dict[str, str]:
    """The binding's public names, one module per layer, its error tree and every docs table with it as a column."""
    files = {"names.txt": "".join(f"{module} {name}\n" for module, name, _ in model.public(LANGUAGE.key))}
    for layer in model.layers:
        files[f"{layer.name}.toy"] = layer_module(model, layer.name)
    files["errors.toy"] = "".join(
        f"error {g.builtin(LANGUAGE.key) or pascal(g.name)} {LANGUAGE.extends_word} "
        f"{pascal(g.parent) if g.parent else g.base[LANGUAGE.key].get('base', '-')}\n" for g in model.groups)
    for name, table in emit_docs.render_all(model).items():
        files[f"docs/{name}.md"] = table
    return files
