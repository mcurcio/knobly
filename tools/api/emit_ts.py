"""The TypeScript emitter (spec/codegen.md section 4): renders the loader's model as TypeScript modules.

    ts/src/gen/api/kinds.ts      every kind list: an as-const object and the string-literal union derived from it;
                                 the keywords and their dispatch table
    ts/src/gen/api/codes.ts      DiagnosticCode, MESSAGES, CODE_FACTS and describe()
    ts/src/gen/api/limits.ts     the rules: limits, reserved words, patterns
    ts/src/gen/api/errors.ts     the error class tree and argumentTypeMessage()
    ts/src/gen/api/<layer>.ts    one interface per concept, union and callback types, options objects, and the layer's
                                 <Layer>Functions interface (shared, syntax, io, written, rendered)
    ts/src/gen/api/names.ts      every public name per import path, and each error class's group
    ts/conformance/shapes.ts     the adapter protocol's message types and the spec-name spellings an adapter needs

Idiom lives here and only here: readonly properties, readonly arrays, ReadonlyMap results, Readonly<Record> parameters,
options objects, Promise for I/O, toString / Symbol.iterator / length / at / a callback walk for the traits.
"""

from __future__ import annotations

import json
import textwrap
from typing import Dict, List, Optional, Set, Tuple

from .loader import HEADER, PLACEHOLDER, Concept, Member, Model, Param, Type, camel, pascal, upper_snake

LAYER_FILES = ("shared", "syntax", "io", "written", "rendered")


def s(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def doc(text: str, indent: str = "") -> List[str]:
    text = text.replace("*/", "*\\/").strip()
    if not text:
        return []
    lines = textwrap.wrap(text, 114 - len(indent))
    if len(lines) == 1:
        return [f"{indent}/** {lines[0]} */"]
    return [f"{indent}/**", *(f"{indent} * {line}" for line in lines), f"{indent} */"]


def head(source: str) -> List[str]:
    return [f"// {HEADER}", f"// Source: {source}.", ""]


def kind_key(model: Model, list_name: str, value: str) -> str:
    return value if model.kind[list_name].from_grammar else pascal(value)


class Ctx:
    """The names one module uses, so it imports exactly them."""

    def __init__(self, model: Model, here: str, type_params: Dict[str, str]) -> None:
        self.model, self.here, self.type_params = model, here, type_params
        self.imports: Dict[str, Set[str]] = {}

    def use(self, file: str, name: str) -> str:
        if file != self.here:
            self.imports.setdefault(file, set()).add(name)
        return name

    def ref(self, name: str) -> str:
        m = self.model
        if name in self.type_params:
            return self.type_params[name]
        if name in m.kind:
            return self.use("kinds", pascal(name))
        if name == "diagnostic code":
            return self.use("codes", "DiagnosticCode")
        if name in m.group:
            return self.use("errors", pascal(name))
        c = m.concept[name]
        if c.is_ == "native":
            return "typeof globalThis.fetch" if name == "fetch function" else "never"
        return self.use(c.layer, pascal(name))


def ts_type(t: Type, ctx: Ctx, param: bool = False) -> str:
    if t.form == "name":
        b = {"text": "string", "integer": "number", "number": "number", "boolean": "boolean", "nothing": "void", "absent": "undefined"}
        if t.name in b:
            return b[t.name]
        base = ctx.ref(t.name)
        if t.args:
            return f"{base}<{', '.join(ts_type(a, ctx) for a in t.args)}>"
        return base
    if t.form == "list":
        inner = ts_type(t.item, ctx, param)
        if t.item.form in ("union", "function", "list"):
            inner = f"({inner})"
        return f"readonly {inner}[]"
    if t.form == "union":
        return " | ".join(ts_type(a, ctx, param) for a in t.args)
    if t.form == "map":
        key, value = t.args
        v = ts_type(value, ctx, param)
        if key.form == "name" and key.name == "text" and param:
            return f"Record<string, {v}>" if t.writable else f"Readonly<Record<string, {v}>>"
        return f"ReadonlyMap<{ts_type(key, ctx)}, {v}>"
    if t.form == "function":
        *params, result = t.args
        ps = ", ".join(f"{camel(p.name) if p.form == 'name' and p.name not in ctx.type_params else 'value'}: {ts_type(p, ctx)}" for p in params)
        return f"({ps}) => {ts_type(result, ctx)}"
    raise AssertionError(t)


def generic(params: List[str]) -> Tuple[str, Dict[str, str]]:
    names = {p: "T" + pascal(p) for p in params}
    return (f"<{', '.join(names.values())}>" if names else ""), names


# --- members ---------------------------------------------------------------------------------------------------------


def method_params(model: Model, m_params: List[Param], options: Optional[str], ctx: Ctx) -> str:
    out = []
    for p in m_params:
        if p.passed == "option":
            continue
        opt = "?" if p.optional else ""
        t = p.type
        if not p.optional and t.may_be_absent:
            out.append(f"{camel(p.name)}: {ts_type(t, ctx, True)}")
        else:
            out.append(f"{camel(p.name)}{opt}: {ts_type(t.without_absent() if p.optional else t, ctx, True)}")
    if options is not None:
        required = any(p.passed == "option" and not p.optional for p in m_params)
        out.append(f"options{'' if required else '?'}: {ctx.use(model.concept[options].layer, pascal(options))}")
    return ", ".join(out)


def member_lines(model: Model, c: Concept, m: Member, ctx: Ctx) -> List[str]:
    out = doc(m.note, "  ")
    if m.trait == "people form":
        return out + ["  toString(): string;"]
    if m.trait == "iterate":
        return out + [f"  [Symbol.iterator](): Iterator<{ts_type(m.type.item, ctx)}>;"]
    if m.trait == "count":
        return out + ["  readonly length: number;"]
    if m.trait == "index":
        return out + [f"  at(index: number): {ts_type(m.type, ctx)} | undefined;"]
    if m.trait == "walk":
        item = ts_type(m.type.item, ctx)
        return out + [f"  walk(visit: ({camel('item')}: {item}) => {ctx.use('kinds', 'WalkControl')} | void): void;"]
    if m.member == "property":
        if m.name == "kind" and c.kind is not None:
            return out + [f"  readonly kind: {s(c.kind)};"]
        opt = "?" if m.optional else ""
        t = m.type.without_absent() if m.optional else m.type
        return out + [f"  readonly {camel(m.name)}{opt}: {ts_type(t, ctx)};"]
    gen, names = generic(m.type_parameters)
    ctx2 = Ctx(model, ctx.here, {**ctx.type_params, **names})
    ctx2.imports = ctx.imports
    result = ts_type(m.type, ctx2)
    if m.io:
        result = f"Promise<{result}>"
    return out + [f"  {camel(m.name)}{gen}({method_params(model, m.params, m.options, ctx2)}): {result};"]


def concept_lines(model: Model, c: Concept, ctx: Ctx) -> List[str]:
    name = pascal(c.name)
    out = doc(c.note)
    if c.nature == "named type":
        if c.brand:
            return out + [f"export type {name} = string & {{ readonly [{camel(c.name)}Brand]: true }};"]
        if c.pattern == "program code":
            return out + [f"export type {name} = `${{string}}/${{string}}`;"]
        return out + [f"export type {name} = string;"]
    if c.nature == "callback":
        assert c.callback is not None
        return out + [f"export type {name} = {ts_type(c.callback, ctx)};"]
    if c.is_union:
        alts = " | ".join(pascal(v) for v in c.variants)
        return out + [f"export type {name} = {alts};"]
    gen, names = generic(c.type_parameters)
    cctx = Ctx(model, ctx.here, names)
    cctx.imports = ctx.imports
    ext = ""
    members = list(c.members)
    if c.variant_of:
        members = [m for m in model.concept[c.variant_of].members] + members
        if not any(m.name == "kind" for m in c.members):
            pass
    if c.extends is not None:
        ext = f" extends {ts_type(c.extends, cctx)}"
    if c.nature == "shape":
        ext = f" extends Iterable<{names['item']}>"
    lines = [f"export interface {name}{gen}{ext} {{"]
    for m in members:
        if m.trait == "iterate" and c.nature == "shape":
            continue  # Iterable gives it
        if m.name == "kind" and c.variant_of:
            lines += [f"  readonly kind: {s(str(c.kind))};"]
            continue
        lines += member_lines(model, c, m, cctx)
    lines.append("}")
    return out + lines


def function_lines(model: Model, layer: str, ctx: Ctx) -> List[str]:
    """One interface per import path listing its free functions, so a module can be checked against it."""
    by_module: Dict[str, List[str]] = {}
    for f in model.functions:
        mod = model.function_module(f, "ts")
        if mod is None or f.layer != layer:
            continue
        fac = (f.factory or {}).get("ts")
        if fac == "constructor":
            continue
        name = model.package if fac == "package function" else camel(f.name)
        lines = doc(f.note, "  ")
        lines.append(f"  {name}({method_params(model, f.params, f.options, ctx)}): {ts_type(f.returns, ctx)};")
        by_module.setdefault(mod, []).extend(lines)
    out: List[str] = []
    for mod, lines in sorted(by_module.items()):
        suffix = mod.split("/", 1)[1] if "/" in mod else layer
        out += doc(f"The free functions {s(mod)} exports: a module object is checked against it (`const _: X = module`).")
        out += [f"export interface {pascal(suffix.replace('-', ' '))}Functions {{", *lines, "}", ""]
    return out


def layer_module(model: Model, layer: str) -> str:
    ctx = Ctx(model, layer, {})
    body: List[str] = []
    brand = [c for c in model.concepts if c.layer == layer and c.brand and "ts" in c.languages]
    for c in brand:
        body += [f"declare const {camel(c.name)}Brand: unique symbol;", ""]
    for c in model.concepts:
        if c.layer != layer or "ts" not in c.languages or c.is_ == "native":
            continue
        body += concept_lines(model, c, ctx) + [""]
    body += function_lines(model, layer, ctx)
    imports = []
    for file in sorted(ctx.imports):
        imports.append(f"import type {{ {', '.join(sorted(ctx.imports[file]))} }} from \"./{file}.js\";")
    out = head(f'spec/schema/api.json, the {layer} layer') + imports + ([""] if imports else []) + body
    while out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# --- kinds, codes, limits, errors, names -----------------------------------------------------------------------------


def kinds_module(model: Model) -> str:
    out = head('spec/schema/api.json "kinds" and "keywords" (token kind: grammar/Villanelle.g4)')
    for k in model.kinds:
        if "ts" not in k.languages:
            continue
        name = pascal(k.name)
        out += doc(f"The spec's {k.name} list (spec 2.10): compare with a member (`{name}.{kind_key(model, k.name, k.values[0])}`), never a string literal.")
        out.append(f"export const {name} = {{")
        out += [f"  {kind_key(model, k.name, v)}: {s(v)}," for v in k.values]
        out += ["} as const;", f"export type {name} = (typeof {name})[keyof typeof {name}];", ""]
    out += doc("The language statements' keywords, written after '@' (spec 2.5): the one keyword list.")
    out.append("export const Keyword = {")
    out += [f"  {pascal(w)}: {s(w)}," for w, _ in model.keywords]
    out += ["} as const;", "export type Keyword = (typeof Keyword)[keyof typeof Keyword];", ""]
    out += doc("The statement kind each keyword writes: the one dispatch table.")
    out.append("export const STATEMENT_OF_KEYWORD: Readonly<Record<Keyword, StatementKind>> = {")
    out += [f"  [Keyword.{pascal(w)}]: StatementKind.{pascal(sk)}," for w, sk in model.keywords]
    out += ["};", ""]
    out += doc("The statement kind a keyword (its text without '@') writes; undefined for any other word.")
    out += ["export function statementOfKeyword(word: string): StatementKind | undefined {",
            "  return Object.hasOwn(STATEMENT_OF_KEYWORD, word) ? STATEMENT_OF_KEYWORD[word as Keyword] : undefined;",
            "}", ""]
    return "\n".join(out)


def message_expr(model: Model, message: str, imports: Set[str]) -> str:
    if not PLACEHOLDER.search(message):
        return s(message)
    parts, pos = [], 0
    esc = lambda x: x.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")  # noqa: E731
    for m in PLACEHOLDER.finditer(message):
        parts.append(esc(message[pos:m.start()]))
        const = upper_snake(model.limit[m.group(1)].name)
        imports.add(const)
        parts.append(f"${{String({const})}}")
        pos = m.end()
    parts.append(esc(message[pos:]))
    return "`" + "".join(parts) + "`"


def codes_module(model: Model) -> str:
    imports: Set[str] = set()
    entries, messages, facts = [], [], []
    for c in model.codes:
        entries += doc(c.meaning.replace("`", ""), "  ")
        entries.append(f"  {pascal(c.name)}: {s(c.code)},")
        messages.append(f"  {c.code}: {message_expr(model, c.message, imports)},")
        reason = "null" if c.reason is None else s(c.reason)
        facts.append(f"  {c.code}: {{ name: {s(c.name)}, layer: {s(c.layer)}, foundBy: [{', '.join(map(s, c.found_by))}], reason: {reason} }},")
    out = head("spec/schema/diagnostics.json")
    out.append('import type { UnreadableReason } from "./kinds.js";')
    if imports:
        out.append(f"import {{ {', '.join(sorted(imports))} }} from \"./limits.js\";")
    out += ["",
            "/** villanelle's diagnostic codes, by name (spec 2.4). */",
            "export const DiagnosticCode = {", *entries, "} as const;",
            "export type DiagnosticCode = (typeof DiagnosticCode)[keyof typeof DiagnosticCode];", "",
            "/** The base message of each code (spec 2.3: for people, not part of the contract). */",
            "export const MESSAGES: Readonly<Record<DiagnosticCode, string>> = {", *messages, "};", "",
            "/** What the registry says of one code: its spec name, owning layer, who finds it, the reason it gives. */",
            "export interface CodeFacts {",
            "  readonly name: string;",
            "  readonly layer: \"syntax\" | \"written\" | \"include\";",
            "  readonly foundBy: readonly string[];",
            "  readonly reason: UnreadableReason | null;",
            "}", "",
            "/** Each code's facts (spec 2.4), typed so `CODE_FACTS[code].reason` is that code's own reason. */",
            "export const CODE_FACTS = {", *facts, "} as const satisfies Readonly<Record<DiagnosticCode, CodeFacts>>;", "",
            "/** The unreadable reason a code gives (null: a reader's code, which makes nothing unreadable). */",
            "export type ReasonOf<C extends DiagnosticCode> = (typeof CODE_FACTS)[C][\"reason\"];", "",
            "/** One diagnostic's code, message and reason, built from the registry so a raise site cannot pair a code with the",
            " * wrong reason or message (the typed diagnostic constructor; spec/codegen.md section 4). `detail` follows ': '. */",
            "export function describe<C extends DiagnosticCode>(",
            "  code: C,",
            "  detail?: string,",
            "): { readonly code: C; readonly message: string; readonly reason: ReasonOf<C> } {",
            "  const message = detail === undefined ? MESSAGES[code] : `${MESSAGES[code]}: ${detail}`;",
            "  return { code, message, reason: CODE_FACTS[code].reason as ReasonOf<C> };",
            "}", ""]
    return "\n".join(out)


def limits_module(model: Model) -> str:
    out = head('spec/schema/api.json "limits", "reserved names" and "patterns" (the rules module)')
    for c in model.constants:
        name = upper_snake(c.name)
        out += doc(f"{c.about}: {c.means}.")
        if c.sort == "limit":
            out.append(f"export const {name} = {c.value};")
        elif c.sort == "words":
            out.append(f"export const {name}: ReadonlySet<string> = new Set([{', '.join(map(s, c.value))}]);")  # type: ignore[arg-type]
        else:
            out.append(f"export const {name} = /{str(c.value).replace('/', chr(92) + '/')}/u;")
        out.append("")
    return "\n".join(out)


def errors_module(model: Model) -> str:
    ctx = Ctx(model, "errors", {})
    out: List[str] = []
    for g in model.groups:
        if g.builtin("ts"):
            continue
        name = pascal(g.name)
        parent = model.group[g.parent] if g.parent else None
        base = pascal(parent.name) if parent else g.base["ts"]["base"]
        own_fields = [(f, t) for f, t in g.fields if not (parent and any(pf == f for pf, _ in parent.fields))]
        params: List[str] = []
        if g.message.get("given"):
            params.append("message: string")
        for f, t in g.fields:
            ty = ts_type(model.parse(t, g.name), ctx, True)
            params.append(f"{'readonly ' if (f, t) in own_fields else ''}{camel(f)}: {ty}")
        chained = g.cause == "chained" or (g.parent is None and g.sort == "base")
        if chained:
            params.append("options?: ErrorOptions")
        if g.message.get("given"):
            msg = "message"
        else:
            msg = template_expr(g.message, g.fields)
        if parent is None:
            sup = f"super({msg}{', options' if chained else ''});"
        else:
            sup_args = []
            if parent.message.get("given"):
                sup_args.append(msg)
            sup_args += [camel(f) for f, _ in parent.fields]
            if chained and (parent.cause == "chained" or parent.sort == "base"):
                sup_args.append("options")
            sup = f"super({', '.join(sup_args)});"
        out += doc(f"{g.raised_when[0].upper()}{g.raised_when[1:]}. Spec 2.8: {g.sort}.")
        out.append(f"export class {name} extends {base} {{")
        out.append(f"  constructor({', '.join(params)}) {{")
        out.append(f"    {sup}")
        out.append(f"    this.name = {s(name)};")
        out += ["  }", "}", ""]
    out += doc("The argument type error's message (spec 2.8; api.json \"argument type error message\"): the one helper every "
               "member that takes text calls before it changes anything.")
    tmpl = model.argument_type_message["ts"]
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(tmpl):
        parts.append(tmpl[pos:m.start()].replace("`", "\\`"))
        parts.append("${" + camel(m.group(1)) + "}")
        pos = m.end()
    parts.append(tmpl[pos:].replace("`", "\\`"))
    out += ["export function argumentTypeMessage(member: string, parameter: string, got: string): string {",
            f"  return `{''.join(parts)}`;", "}", ""]
    imports = []
    for file in sorted(ctx.imports):
        imports.append(f"import type {{ {', '.join(sorted(ctx.imports[file]))} }} from \"./{file}.js\";")
    return "\n".join(head('spec/schema/api.json "error groups"') + imports + [""] + out)


def template_expr(message: Dict[str, object], fields: List[Tuple[str, str]]) -> str:
    template = str(message["template"])
    sep = str(message.get("separator", ", "))
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(template):
        parts.append(template[pos:m.start()].replace("`", "\\`"))
        ph = m.group(1)
        if ph.endswith(" message"):
            parts.append("${" + camel(ph[: -len(" message")]) + ".message}")
        else:
            ftype = dict(fields)[ph]
            if ftype == "text[]":
                parts.append("${" + camel(ph) + ".join(" + s(sep) + ")}")
            else:
                parts.append("${" + camel(ph) + ".map(String).join(" + s(sep) + ")}")
        pos = m.end()
    parts.append(template[pos:].replace("`", "\\`"))
    return "`" + "".join(parts) + "`"


def names_module(model: Model) -> str:
    out = head("spec/schema/api.json: every public name, derived by the casing rule (spec/binding-guide.md rules 1 and 2)")
    by_mod: Dict[str, Dict[str, List[str]]] = {}
    for mod, name, what in model.public("ts"):
        d = by_mod.setdefault(mod, {"values": [], "types": []})
        if what in ("value", "both"):
            d["values"].append(name)
        if what in ("type", "both"):
            d["types"].append(name)
    out += doc("Every public name by import path: `values` exist at run time, `types` only for the checker (a class or an "
               "as-const list is both). A binding's name test compares each path's exports with this, both ways.")
    out.append("export const PUBLIC_NAMES = {")
    for mod in sorted(by_mod):
        d = by_mod[mod]
        out.append(f"  {s(mod)}: {{")
        out.append(f"    values: [{', '.join(map(s, d['values']))}],")
        out.append(f"    types: [{', '.join(map(s, d['types']))}],")
        out.append("  },")
    out += ["} as const;", ""]
    out += doc("Each error group's class, or the language's own class for a builtin group (spec 2.8), to its spec name.")
    out.append("export const ERROR_GROUP_OF_CLASS: Readonly<Record<string, string>> = {")
    for g in model.groups:
        cls = g.builtin("ts") or pascal(g.name)
        out.append(f"  {cls}: {s(g.name)},")
    out += ["};", ""]
    return "\n".join(out)


# --- the adapter protocol --------------------------------------------------------------------------------------------


def shape_type(t: Type) -> str:
    if t.form == "name":
        b = {"text": "string", "integer": "number", "number": "number", "boolean": "boolean", "json": "Json", "id": "string", "null": "null"}
        if t.name in b:
            return b[t.name]
        return pascal(t.name) + ("" if t.name == "position" else "Dump")
    if t.form == "literal":
        return s(t.name)
    if t.form == "list":
        inner = shape_type(t.item)
        return f"readonly ({inner})[]" if t.item.form in ("union", "list", "tuple") else f"readonly {inner}[]"
    if t.form == "union":
        return " | ".join(shape_type(a) for a in t.args)
    if t.form == "map":
        return f"Readonly<Record<string, {shape_type(t.args[1])}>>"
    if t.form == "tuple":
        return f"readonly [{', '.join(shape_type(a) for a in t.args)}]"
    raise AssertionError(t)


def shapes_module(model: Model) -> str:
    p = model.protocol
    out = head("spec/schema/protocol.json (spec/conformance.md 4); the adapter's message types")
    out += ["export type Json = null | boolean | number | string | readonly Json[] | { readonly [key: string]: Json };", "",
            "/** The protocol version an adapter's hello answers. */", f"export const PROTOCOL = {p.version};", ""]
    for sh in p.shapes:
        name = pascal(sh.name) + ("" if sh.name == "position" else "Dump")
        out += doc(sh.note)
        if sh.tuple_ is not None:
            out.append(f"export type {name} = readonly [{', '.join(shape_type(t) for t in sh.tuple_)}];")
        elif sh.one_of:
            alts = [f"{{ readonly {k}: {shape_type(t)} }}" for k, t in sh.one_of.items()]
            out.append(f"export type {name} = {' | '.join(alts)};")
        else:
            def fields(fs: Dict[str, Type], optional: List[str]) -> str:
                return " ".join(f"readonly {k}{'?' if k in optional else ''}: {shape_type(t)};" for k, t in fs.items())
            if sh.by_kind:
                merged: Dict[str, List[str]] = {}
                for extra in sh.by_kind.values():
                    for k, t in extra.items():
                        alts = merged.setdefault(k, [])
                        if shape_type(t) not in alts:
                            alts.append(shape_type(t))
                extras = " ".join(f"readonly {k}?: {' | '.join(v)};" for k, v in merged.items())
                out.append(f"export type {name} = {{ {fields(sh.fields, sh.optional)} {extras} }};")
            else:
                out.append(f"export type {name} = {{ {fields(sh.fields, sh.optional)} }};")
        out.append("")
    out += doc("Each request's parameters, by op.")
    out.append("export interface RequestParams {")
    for r in p.requests:
        fs = " ".join(f"readonly {k}{'?' if k in r.optional else ''}: {shape_type(t)};" for k, t in r.params.items())
        out.append(f"  readonly {s(r.op)}: {{ {fs} }};")
    out += ["}", "", "/** Each request's ok result, by op. */", "export interface RequestResults {"]
    for r in p.requests:
        out.append(f"  readonly {s(r.op)}: {shape_type(r.result)};")
    out += ["}", ""]
    spell: Dict[str, str] = {}
    for c in model.concepts:
        for m in c.members:
            spell[m.name] = camel(m.name)
    for name in p.edit_members + p.readers:
        spell[name] = camel(name)
    out += doc("Each spec name the driver sends (a member, a reader) to this binding's spelling: the casing rule, applied "
               "once here so no adapter writes it again.")
    out.append("export const SPELLING: Readonly<Record<string, string>> = {")
    out += [f"  {s(k)}: {s(v)}," for k, v in sorted(spell.items())]
    out += ["};", ""]
    return "\n".join(out)


def render(model: Model) -> Dict[str, str]:
    files = {
        "kinds.ts": kinds_module(model),
        "codes.ts": codes_module(model),
        "limits.ts": limits_module(model),
        "errors.ts": errors_module(model),
        "names.ts": names_module(model),
    }
    for layer in LAYER_FILES:
        files[f"{layer}.ts"] = layer_module(model, layer)
    return files


def render_shapes(model: Model) -> Dict[str, str]:
    return {"shapes.ts": shapes_module(model)}

