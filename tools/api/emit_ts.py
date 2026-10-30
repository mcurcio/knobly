"""The TypeScript emitter (spec/codegen.md section 4): renders the loader's model as TypeScript modules.

    ts/src/gen/api/kinds.ts      every kind list: an as-const object and the string-literal union derived from it;
                                 the keywords and their dispatch table
    ts/src/gen/api/codes.ts      DiagnosticCode, MESSAGES, CODE_FACTS and describe()
    ts/src/gen/api/limits.ts     the rules: limits, reserved words, patterns
    ts/src/gen/api/errors.ts     the error class tree and argumentTypeMessage()
    ts/src/gen/api/<layer>.ts    one interface per concept, union and callback types, options objects, and the layer's
                                 <Layer>Functions interface: one module per layer api.json lists
    ts/conformance/shapes.ts     the adapter protocol's message types, the spec-name spellings an adapter needs and each
                                 error class's group
    ts/test/api-contract.ts      what the binding's tests check it against: every public name per import path

Idiom lives here and only here: readonly properties, readonly arrays, ReadonlyMap results, Readonly<Record> parameters,
options objects, Promise for I/O, toString / Symbol.iterator / length / at / a callback walk for the traits.
"""

from __future__ import annotations

import json
import textwrap
from typing import Dict, List, Optional, Set, Tuple

from .loader import (
    CODE_LAYERS,
    FOUND_BY,
    HEADER,
    PLACEHOLDER,
    Concept,
    Formatter,
    Language,
    Member,
    Model,
    Param,
    Type,
    camel,
    pascal,
    pattern_body,
    sentence,
    upper_snake,
)


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    """A TypeScript name is a type, or a value too when it is a class or an as-const list (``c`` None)."""
    return "both" if c is None or model.constructed(c, "ts") else "type"


# TypeScript's own facts (the schema names no language; spec/codegen.md section 10).
def _call_params(params: List[Tuple[str, str, bool]]) -> str:
    """A call's parameters in the docs tables: an optional one marked ``?``, the options in one object."""
    plain = [f"{n}?" if optional else n for n, passed, optional in params if passed != "option"]
    options = [f"{n}?" if optional else n for n, passed, optional in params if passed == "option"]
    return ", ".join(plain + ([f"{{ {', '.join(options)} }}"] if options else []))


LANGUAGE = Language(
    key="ts",
    name="TypeScript",
    sep="/",
    function_case=camel,
    code_case=pascal,
    public_kind=_public_kind,
    enum_form="as-const object and type",
    generic=lambda name, params: f"{name}<{', '.join(params)}>",
    construct=lambda name: f"new {name}(...)",
    extends_word="extends",
    cause_field="cause",
    error_roots={
        "villanelle error": {"base": "Error"},
        "detached error": {"base": "ReferenceError"},
        "argument type error": {"builtin": "TypeError"},
        "misuse error": {"base": "Error"},
        "index out of range": {"builtin": "RangeError"},
    },
    argument_type_message=('{member}(): argument "{parameter}" must be a string, not {got}; villanelle edits take config '
                           "text: quote() a program string, text() one already written as villanelle text, String() a "
                           "number first"),  # {got}: null, array or typeof
    modules={"files": "node", "fetch": "browser", "include": "include"},
    factory_forms={"processor": "package function"},  # villanelle({ source }); every other factory is a class
    native={"platform fetch": "typeof globalThis.fetch"},  # a native type is the platform's, never declared here
    # Prettier, pinned exactly in ts/package.json and installed by pnpm install; its options are here (no config file,
    # so the hand-written code's editors do not pick them up) and otherwise its defaults.
    formatter=Formatter(".ts", (("ts/node_modules/.bin/prettier", "--write", "--no-config", "--no-editorconfig",
                                 "--print-width", "120", "--log-level", "warn"),)),
    trait_forms={
        "people form": "`toString()`",
        "iterate": "`[Symbol.iterator]()`",
        "count": "`length`",
        "index": "`at(i)`, absent out of range",
        "walk": "`walk(visit)`, callback returns `WalkControl`",
        "collect": "`collect(read)`",
        "io": "returns a `Promise`",
        "passed: keyword": "positional",
        "passed: option": "one options object (`load(path, { overrides })`)",
        "brand": "a branded string",
        "template": "a template literal type (`${string}/${string}`)",
        "list": "`readonly T[]`",
        "map": "`ReadonlyMap` as a result, `Readonly<Record>` as a parameter or an options record's property (`writable`: `Record`)",
    },
    call_params=_call_params,
)


def s(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def doc(text: str, indent: str = "", tags: Optional[List[str]] = None) -> List[str]:
    """A JSDoc comment: the text as a sentence, wrapped, then each tag (``@param``, ``@throws``) on lines of its own."""
    blocks = [b.replace("*/", "*\\/").strip() for b in [sentence(text), *(tags or [])]]
    body, tag_lines = blocks[0], [b for b in blocks[1:] if b]
    if not body and not tag_lines:
        return []
    width = 114 - len(indent)
    lines = textwrap.wrap(body, width) if body else []
    if len(lines) == 1 and not tag_lines:
        return [f"{indent}/** {lines[0]} */"]
    for tag in tag_lines:
        lines += textwrap.wrap(tag, width, subsequent_indent="  ")
    return [f"{indent}/**", *(f"{indent} * {line}" for line in lines), f"{indent} */"]


def error_class(model: Model, group: str) -> str:
    g = model.group[group]
    return g.builtin("ts") or pascal(g.name)


def member_doc(model: Model, text: str, params: List[Param], raised: List[Tuple[str, str]], order: str, indent: str) -> List[str]:
    """A member's or free function's JSDoc: its doc and order, each documented parameter, each error group it raises."""
    if order:
        text = f"{sentence(text)} Order: {order}.".strip()
    tags = [f"@param {'options.' if p.passed == 'option' else ''}{camel(p.name)} {p.doc}" for p in params if p.doc]
    tags += [f"@throws {{{error_class(model, e)}}} {why}" for e, why in raised]
    return doc(text, indent, tags)


WALK_VISIT = ("called with each item in turn, before the items of its block; return {control}.Skip to pass over its block, "
              "or {control}.Stop to end the walk")


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
            return LANGUAGE.native[name]  # the loader checks every native type the binding keeps has one
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
        names = [camel(p.name) if p.form == "name" and p.name not in ctx.type_params else "value" for p in params]
        names = [f"{n}{names[:i].count(n) + 1}" if names.count(n) > 1 else n for i, n in enumerate(names)]
        ps = ", ".join(f"{n}: {ts_type(p, ctx)}" for n, p in zip(names, params))
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
    out = member_doc(model, m.doc, m.params, model.raised(m.errors, m.when), m.order, "  ")
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
        control = ctx.use("kinds", "WalkControl")
        out = member_doc(model, m.doc, [Param("visit", m.type, doc=WALK_VISIT.format(control=control))], [], m.order, "  ")
        return out + [f"  walk(visit: ({camel('item')}: {item}) => {control} | void): void;"]
    if m.member == "property":
        if m.name == "kind" and c.kind is not None:
            return out + [f"  readonly kind: {s(c.kind)};"]
        opt = "?" if m.optional else ""
        t = m.type.without_absent() if m.optional else m.type
        # An options record is passed in: its maps are a parameter's (Readonly<Record>), as spec/codegen.md section 3 says.
        return out + [f"  readonly {camel(m.name)}{opt}: {ts_type(t, ctx, c.nature == 'options')};"]
    gen, names = generic(m.type_parameters)
    ctx2 = Ctx(model, ctx.here, {**ctx.type_params, **names})
    ctx2.imports = ctx.imports
    result = ts_type(m.type, ctx2)
    if m.io:
        result = f"Promise<{result}>"
    return out + [f"  {camel(m.name)}{gen}({method_params(model, m.params, m.options, ctx2)}): {result};"]


def concept_lines(model: Model, c: Concept, ctx: Ctx) -> List[str]:
    name = pascal(c.name)
    out = doc(c.doc)
    if c.nature == "named type":
        if c.brand:
            return out + [f"export type {name} = string & {{ readonly [{camel(c.name)}Brand]: true }};"]
        if c.template is not None:
            literal = c.template.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${").replace("{text}", "${string}")
            return out + [f"export type {name} = `{literal}`;"]
        return out + [f"export type {name} = string;"]
    if c.nature == "callback":
        assert c.callback is not None
        return out + [f"export type {name} = {ts_type(c.callback, ctx)};"]
    gen, names = generic(c.type_parameters)
    cctx = Ctx(model, ctx.here, names)
    cctx.imports = ctx.imports
    if c.is_union:
        # The members every variant has go once, on <Union>Common, which each variant extends.
        alts = " | ".join(pascal(v) for v in c.variants)
        common = [*doc(f"The members every {c.name} has, whichever its kind."), f"export interface {common_name(c)} {{"]
        for m in c.members:
            common += member_lines(model, c, m, cctx)
        return common + ["}", "", *out, f"export type {name} = {alts};"]
    bases = []
    if c.variant_of:
        bases.append(common_name(model.concept[c.variant_of]))
    if c.extends is not None:
        bases.append(ts_type(c.extends, cctx))
    members = list(c.members)
    if c.nature == "shape":
        iterate = next(m for m in members if m.trait == "iterate")
        bases.append(f"Iterable<{ts_type(iterate.type.item, cctx)}>")  # a block is Iterable; its own member keeps the doc
    lines: List[str] = []
    if c.kind is not None and c.variant_of:
        lines.append(f"  readonly kind: {s(c.kind)};")
    for m in members:
        if not (m.name == "kind" and c.variant_of):
            lines += member_lines(model, c, m, cctx)
    if not lines and len(bases) == 1:
        return out + [f"export type {name}{gen} = {bases[0]};"]  # adds nothing: an alias, not an empty interface
    ext = f" extends {', '.join(bases)}" if bases else ""
    return out + [f"export interface {name}{gen}{ext} {{", *lines, "}"]


def common_name(union: Concept) -> str:
    return pascal(union.name) + "Common"


def function_lines(model: Model, layer: str, ctx: Ctx) -> List[str]:
    """One interface per import path listing its free functions, so a module can be checked against it."""
    by_module: Dict[str, List[str]] = {}
    for f in model.functions:
        mod = model.function_module(f, "ts")
        if mod is None or f.layer != layer:
            continue
        fac = (f.factory or {}).get("ts")
        if fac == "constructor":
            continue  # constructor_lines
        name = model.package if fac == "package function" else camel(f.name)
        lines = member_doc(model, f.doc, f.params, model.raised(f.errors, f.when), "", "  ")
        lines.append(f"  {name}({method_params(model, f.params, f.options, ctx)}): {ts_type(f.returns, ctx)};")
        by_module.setdefault(mod, []).extend(lines)
    out: List[str] = []
    for mod, lines in sorted(by_module.items()):
        suffix = mod.split("/", 1)[1] if "/" in mod else layer
        out += doc(f"The free functions {s(mod)} exports.")
        out += [f"export interface {pascal(suffix.replace('-', ' '))}Functions {{", *lines, "}", ""]
    return out + constructor_lines(model, layer, ctx)


def constructor_lines(model: Model, layer: str, ctx: Ctx) -> List[str]:
    """A constructor factory's signature as a construct signature: the class is checked against it (`const _: X = Class`)."""
    out: List[str] = []
    for f in model.functions:
        if f.layer != layer or (f.factory or {}).get("ts") != "constructor" or model.function_module(f, "ts") is None:
            continue
        of = pascal(f.factory["of"])  # type: ignore[index]
        out += doc(f"The signature of `new {of}(...)`.")
        out += [f"export interface {of}Constructor {{", *member_doc(model, f.doc, f.params, model.raised(f.errors, f.when), "", "  "),
                f"  new ({method_params(model, f.params, f.options, ctx)}): {ctx.ref(f.factory['of'])};",  # type: ignore[index]
                "}", ""]
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
        out += doc(f"{sentence(k.doc)} Each value is a string every binding shares; compare with a member, such as "
                   f"`{name}.{kind_key(model, k.name, k.values[0])}`.")
        out.append(f"export const {name} = {{")
        out += [f"  {kind_key(model, k.name, v)}: {s(v)}," for v in k.values]
        out += ["} as const;", f"export type {name} = (typeof {name})[keyof typeof {name}];", ""]
    out += doc("The language statements' keywords, written after '@': the one keyword list.")
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
            "/** villanelle's diagnostic codes, by name. */",
            "export const DiagnosticCode = {", *entries, "} as const;",
            "export type DiagnosticCode = (typeof DiagnosticCode)[keyof typeof DiagnosticCode];", "",
            "/** The base message of each code (for people, not part of the contract). */",
            "export const MESSAGES: Readonly<Record<DiagnosticCode, string>> = {", *messages, "};", "",
            "/** What the registry says of one code: its spec name, owning layer, who finds it, the reason it gives. */",
            "export interface CodeFacts {",
            "  readonly name: string;",
            f"  readonly layer: {' | '.join(map(s, CODE_LAYERS))};",
            f"  readonly foundBy: readonly ({' | '.join(map(s, FOUND_BY))})[];",
            "  readonly reason: UnreadableReason | null;",
            "}", "",
            "/** Each code's facts, typed so `CODE_FACTS[code].reason` is that code's own reason. */",
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
            body = pattern_body(str(c.value), lambda cp: f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\u{{{cp:x}}}")
            out.append(f"export const {name} = /^{body.replace('/', chr(92) + '/')}$/u;")
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
            params.append(f"{'readonly ' if (f, t) in own_fields else ''}{camel(f)}: {ts_type(t, ctx, True)}")
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
        out += doc(g.class_doc())
        out.append(f"export class {name} extends {base} {{")
        out.append(f"  constructor({', '.join(params)}) {{")
        out.append(f"    {sup}")
        out.append(f"    this.name = {s(name)};")
        out += ["  }", "}", ""]
    out += doc("The argument type error's message: the one helper every member that takes text calls before it "
               "changes anything.")
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


def template_expr(message: Dict[str, object], fields: List[Tuple[str, Type]]) -> str:
    template = str(message["template"])
    sep = str(message.get("separator", ", "))
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(template):
        parts.append(template[pos:m.start()].replace("`", "\\`"))
        ph = m.group(1)
        if ph.endswith(" message"):
            parts.append("${" + camel(ph[: -len(" message")]) + ".message}")
        else:
            item = dict(fields)[ph].item  # the loader refuses a placeholder on anything but a list
            if item.form == "name" and item.name == "text":
                parts.append("${" + camel(ph) + ".join(" + s(sep) + ")}")
            else:
                parts.append("${" + camel(ph) + ".map(String).join(" + s(sep) + ")}")
        pos = m.end()
    parts.append(template[pos:].replace("`", "\\`"))
    return "`" + "".join(parts) + "`"


def contract_module(model: Model) -> str:
    """ts/test/api-contract.ts: what the binding's tests check it against, outside src/ so the package never ships it."""
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
        out += doc(sh.doc)
        if sh.tuple_ is not None:
            out.append(f"export type {name} = readonly [{', '.join(shape_type(t) for t in sh.tuple_)}];")
        elif sh.one_of:
            alts = [f"{{ readonly {k}: {shape_type(t)} }}" for k, t in sh.one_of.items()]
            out.append(f"export type {name} = {' | '.join(alts)};")
        else:
            def fields(fs: Dict[str, Type], optional: List[str]) -> str:
                return " ".join(f"readonly {k}{'?' if k in optional else ''}: {shape_type(t)};" for k, t in fs.items())
            if sh.by_kind:
                # A discriminated union: one alternative per kind, with that kind's own fields required.
                common = {k: t for k, t in sh.fields.items() if k != "kind"}
                alts = [f"({{ readonly kind: {s(kind)}; {fields(common, sh.optional)} {fields(extra, [])} }})"
                        for kind, extra in sh.by_kind.items()]
                alts.append(f"({{ readonly kind: {' | '.join(map(s, sh.other_kinds))}; {fields(common, sh.optional)} }})")
                out.append(f"export type {name} =")
                out += [f"  | {a.replace('  ', ' ')}" for a in alts]
                out[-1] += ";"
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
    spell, _ = model.spellings(LANGUAGE.key)
    out += doc("Each spec name the driver sends (a member, a reader) to this binding's spelling: the casing rule, applied "
               "once here so no adapter writes it again.")
    out.append("export const SPELLING: Readonly<Record<string, string>> = {")
    out += [f"  {s(k)}: {s(v)}," for k, v in sorted(spell.items())]
    out += ["};", ""]
    out += doc("Each error group's class, or the language's own class for a builtin group (spec 2.8), to its spec name.")
    out.append("export const ERROR_GROUP_OF_CLASS: Readonly<Record<string, string>> = {")
    out += [f"  {error_class(model, g.name)}: {s(g.name)}," for g in model.groups]
    out += ["};", ""]
    return "\n".join(out)


def render(model: Model) -> Dict[str, str]:
    files = {
        "kinds.ts": kinds_module(model),
        "codes.ts": codes_module(model),
        "limits.ts": limits_module(model),
        "errors.ts": errors_module(model),
    }
    for layer in model.layers:
        files[f"{layer.name}.ts"] = layer_module(model, layer.name)
    return files


def render_shapes(model: Model) -> Dict[str, str]:
    return {"shapes.ts": shapes_module(model)}


def render_contract(model: Model) -> Dict[str, str]:
    return {"api-contract.ts": contract_module(model)}

