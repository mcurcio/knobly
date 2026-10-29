"""The Python emitter (spec/codegen.md section 4): renders the loader's model as Python modules.

    py/src/villanelle/_api/kinds.py      every kind list as a StrEnum; Keyword and its dispatch table
    py/src/villanelle/_api/codes.py      DiagnosticCode, MESSAGES, CODE_FACTS and describe()
    py/src/villanelle/_api/limits.py     the rules: limits, reserved words, patterns
    py/src/villanelle/_api/errors.py     the error class tree and argument_type_message()
    py/src/villanelle/_api/<layer>.py    a Protocol per handle, port and interface, a frozen slotted dataclass per plain
                                         record, union and callback aliases, and the layer's <Layer>Functions Protocol
    py/src/villanelle/_api/names.py      every public name per module, each error class's group, each class's match args
    py/conformance/shapes.py             the adapter protocol's message TypedDicts and the spec-name spellings

Idiom lives here and only here: properties, tuples for results, Sequence and Mapping for parameters, positional-only
parameters, keyword-only options, __str__ / __iter__ / __len__ / __getitem__ / a generator walk / a context manager for
the traits. The output is what ruff format writes, so py's ruff and mypy --strict check it as they check hand code.
"""

from __future__ import annotations

import json
import textwrap
from typing import Dict, List, Set, Tuple

from .loader import HEADER, PLACEHOLDER, Concept, Member, Model, Param, Type, pascal, snake, upper_snake

LAYER_FILES = ("shared", "syntax", "io", "written", "rendered")
WIDTH = 120


def s(text: str) -> str:
    """A string literal as ruff format writes it: double quotes unless that would need more escapes."""
    body = json.dumps(text, ensure_ascii=False)[1:-1]
    if '"' in text and "'" not in text:
        return "'" + body.replace('\\"', '"') + "'"
    return '"' + body + '"'


def docstring(text: str, indent: str) -> List[str]:
    text = text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"').strip()
    if not text:
        return []
    if text.endswith('"'):
        text += " "
    lines = textwrap.wrap(text, WIDTH - len(indent) - 3)
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}"""']
    return [f'{indent}"""{lines[0]}', *(f"{indent}{line}" for line in lines[1:]), f'{indent}"""']


def tuple_literal(items: List[str]) -> str:
    """A tuple literal ruff format leaves on one line: a trailing comma only for one item (no magic comma)."""
    return f"({items[0]},)" if len(items) == 1 else f"({', '.join(items)})"


def wrap_string(text: str, indent: str) -> List[str]:
    """A long (f-)string as implicitly joined parts that each fit, split at spaces outside {placeholders}."""
    room = WIDTH - len(indent) - 4
    parts, cur, depth = [], "", 0
    for ch in text:
        cur += ch
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if ch == " " and depth == 0 and len(cur) >= room - 12:
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    return [f"{indent}{'f' if '{' in p else ''}{s(p)}" for p in parts]


def kind_member(model: Model, list_name: str, value: str) -> str:
    return value if model.kind[list_name].from_grammar else upper_snake(value)


class Imports:
    """What one module imports, sorted as ruff's isort writes it (order-by-type: CONSTANTS, Classes, functions)."""

    def __init__(self) -> None:
        self.runtime: Dict[str, Set[str]] = {}
        self.typing_only: Dict[str, Set[str]] = {}

    def add(self, module: str, name: str, runtime: bool = True) -> str:
        (self.runtime if runtime else self.typing_only).setdefault(module, set()).add(name)
        return name

    @staticmethod
    def _key(name: str) -> Tuple[int, str]:
        if name.isupper() and len(name) > 1:
            return (0, name)
        if name[0].isupper():
            return (1, name)
        return (2, name)

    def _lines(self, mods: Dict[str, Set[str]], indent: str) -> List[str]:
        out = []
        std = sorted(m for m in mods if not m.startswith("villanelle"))
        first = sorted(m for m in mods if m.startswith("villanelle"))
        for group in (std, first):
            for m in group:
                names = sorted(mods[m], key=self._key)
                line = f"{indent}from {m} import {', '.join(names)}"
                if len(line) <= WIDTH:
                    out.append(line)
                else:
                    out += [f"{indent}from {m} import (", *(f"{indent}    {n}," for n in names), f"{indent})"]
            if group and group is std and first:
                out.append("")
        return out

    def render(self) -> List[str]:
        typing_only = {m: n - self.runtime.get(m, set()) for m, n in self.typing_only.items()}
        typing_only = {m: n for m, n in typing_only.items() if n}
        rt = {m: set(n) for m, n in self.runtime.items()}
        if typing_only:
            rt.setdefault("typing", set()).add("TYPE_CHECKING")
        out = ["from __future__ import annotations", ""] + self._lines(rt, "")
        if typing_only:
            out += ["", "if TYPE_CHECKING:", *self._lines(typing_only, "    ")]
        return out


class Ctx:
    def __init__(self, model: Model, here: str, imports: Imports, type_params: Dict[str, str]) -> None:
        self.model, self.here, self.imports, self.type_params = model, here, imports, type_params

    def ref(self, name: str, runtime: bool = False) -> str:
        m = self.model
        if name in self.type_params:
            return self.type_params[name]
        if name in m.kind:
            return self.imports.add("villanelle._api.kinds", pascal(name), runtime)
        if name == "diagnostic code":
            return self.imports.add("villanelle._api.codes", "DiagnosticCode", runtime)
        if name in m.group:
            g = m.group[name]
            if g.builtin("py"):
                return g.builtin("py") or ""
            return self.imports.add("villanelle._api.errors", pascal(name), runtime)
        c = m.concept[name]
        if c.layer == self.here and self.here != "errors":
            return pascal(name)
        return self.imports.add(f"villanelle._api.{c.layer}", pascal(name), runtime)

    def abc(self, name: str) -> str:
        return self.imports.add("collections.abc", name, False)


def py_type(t: Type, ctx: Ctx, param: bool = False) -> str:
    if t.form == "name":
        b = {"text": "str", "integer": "int", "number": "float", "boolean": "bool", "nothing": "None", "absent": "None"}
        if t.name in b:
            return b[t.name]
        base = ctx.ref(t.name)
        if t.args:
            return f"{base}[{', '.join(py_type(a, ctx) for a in t.args)}]"
        return base
    if t.form == "list":
        if param:
            return f"{ctx.abc('Sequence')}[{py_type(t.item, ctx, param)}]"
        return f"tuple[{py_type(t.item, ctx)}, ...]"
    if t.form == "union":
        return " | ".join(py_type(a, ctx, param) for a in t.args)
    if t.form == "map":
        key, value = t.args
        kind = "MutableMapping" if t.writable else "Mapping"
        return f"{ctx.abc(kind)}[{py_type(key, ctx)}, {py_type(value, ctx, param)}]"
    if t.form == "function":
        *params, result = t.args
        return f"{ctx.abc('Callable')}[[{', '.join(py_type(p, ctx) for p in params)}], {py_type(result, ctx)}]"
    raise AssertionError(t)


def type_vars(params: List[str], covariant: bool) -> Dict[str, str]:
    return {p: pascal(p) + ("T_co" if covariant else "T") for p in params}


# --- signatures, written as ruff format writes them ------------------------------------------------------------------


def signature(indent: str, name: str, params: List[str], result: str, body: str = " ...") -> List[str]:
    one = f"{indent}def {name}({', '.join(params)}) -> {result}:{body}"
    if len(one) <= WIDTH:
        return [one]
    hug = f"{indent}    {', '.join(params)}"
    if len(hug) <= WIDTH and not params[-1].endswith(","):
        tail = f"{indent}) -> {result}:{body}"
        return [f"{indent}def {name}(", hug, tail]
    return [f"{indent}def {name}(", *(f"{indent}    {p}," for p in params), f"{indent}) -> {result}:{body}"]


def param_list(m_params: List[Param], ctx: Ctx, self_: bool = True) -> List[str]:
    out = ["self"] if self_ else []
    positional = [p for p in m_params if p.passed == "position"]
    keyword = [p for p in m_params if p.passed != "position"]
    for p in positional:
        t = py_type(p.type.without_absent() if p.optional else p.type, ctx, True)
        out.append(f"{snake(p.name)}: {t} | None = None" if p.optional else f"{snake(p.name)}: {t}")
    if positional:
        out.append("/")
    if keyword:
        out.append("*")
        for p in keyword:
            t = py_type(p.type.without_absent() if p.optional else p.type, ctx, True)
            out.append(f"{snake(p.name)}: {t} | None = None" if p.optional else f"{snake(p.name)}: {t}")
    return out


def member_lines(model: Model, c: Concept, m: Member, ctx: Ctx, indent: str = "    ") -> List[str]:
    if m.trait == "people form":
        return signature(indent, "__str__", ["self"], "str")
    if m.trait == "iterate":
        return signature(indent, "__iter__", ["self"], f"{ctx.abc('Iterator')}[{py_type(m.type.item, ctx)}]")
    if m.trait == "count":
        return signature(indent, "__len__", ["self"], "int")
    if m.trait == "index":
        return signature(indent, "__getitem__", ["self", "index: int", "/"], py_type(m.type, ctx))
    if m.trait == "walk":
        item = py_type(m.type.item, ctx)
        return signature(indent, "walk", ["self", "*", f"descend: {ctx.abc('Callable')}[[{item}], bool] | None = None"],
                         f"{ctx.abc('Iterator')}[{item}]")
    if m.trait == "collect":
        cm = ctx.imports.add("contextlib", "AbstractContextManager", False)
        return signature(indent, "collecting", ["self"], f"{cm}[None]")
    if m.member == "property":
        if m.name == "kind" and c.kind is not None:
            lst = next(t for t in [m.type] if t.form == "name").name
            t = f"Literal[{ctx.ref(lst)}.{kind_member(model, lst, c.kind)}]"
            ctx.imports.add("typing", "Literal", False)
        else:
            t = py_type(m.type, ctx)
        return [f"{indent}@property", *signature(indent, snake(m.name), ["self"], t)]
    tvs = type_vars(m.type_parameters, False)
    mctx = Ctx(model, ctx.here, ctx.imports, {**ctx.type_params, **tvs})
    return signature(indent, snake(m.name), param_list(m.params, mctx), py_type(m.type, mctx))


def is_record(model: Model, c: Concept) -> bool:
    """A plain record the generator writes whole: record or snapshot data with properties only."""
    if c.nature not in ("record", "snapshot") or c.is_union or c.extends is not None and model.concept[c.extends.name].nature == "shape":
        return False
    return all(m.member == "property" and m.trait is None for m in model.all_members(c))


def record_lines(model: Model, c: Concept, ctx: Ctx, tvs: Dict[str, str]) -> List[str]:
    name = pascal(c.name)
    ctx.imports.add("dataclasses", "dataclass")
    eq = ", eq=False" if c.nature == "snapshot" else ""
    bases = []
    if c.extends is not None:
        args = ", ".join(s(py_type(a, ctx)) for a in c.extends.args)
        base = ctx.ref(c.extends.name, runtime=True)
        bases.append(f"{base}[{args}]" if args else base)
    if tvs:
        bases.append(f"{ctx.imports.add('typing', 'Generic')}[{', '.join(tvs.values())}]")
    out = ["@final", f"@dataclass(frozen=True, slots=True{eq})"] if not any(
        o.extends is not None and o.extends.name == c.name for o in model.concepts) else [f"@dataclass(frozen=True, slots=True{eq})"]
    if out[0] == "@final":
        ctx.imports.add("typing", "final")
    out.append(f"class {name}({', '.join(bases)}):" if bases else f"class {name}:")
    out += docstring(c.note or f"The spec's {c.name}.", "    ")
    own = [m for m in c.members]
    if c.variant_of:
        own = [m for m in model.concept[c.variant_of].members if m.name != "kind"] + own
    fields = [m for m in own if not (m.name == "kind" and c.kind is not None)]
    order = {a: i for i, a in enumerate(c.match_args)}
    fields.sort(key=lambda m: order.get(m.name, len(order)))
    if c.match_args or fields:
        out.append("")
    for m in fields:
        out.append(f"    {snake(m.name)}: {py_type(m.type, ctx)}")
    if c.kind is not None:
        list_name = model.kind_list_of(c)
        kind_type = ctx.ref(list_name, runtime=True)
        member = kind_member(model, list_name, c.kind)
        ctx.imports.add("typing", "Literal", False)
        out += ["", "    @property", f"    def kind(self) -> Literal[{kind_type}.{member}]:", f"        return {kind_type}.{member}"]
    return out


def concept_lines(model: Model, c: Concept, ctx: Ctx) -> Tuple[List[str], List[str]]:
    """The concept's class (first) or its alias (second: aliases go after every class of the module)."""
    name = pascal(c.name)
    if c.nature == "named type":
        if c.brand:
            ctx.imports.add("typing", "NewType")
            return [f'{name} = NewType("{name}", str)', *docstring(c.note, "")], []
        ctx.imports.add("typing", "TypeAlias")
        return [], [f"{name}: TypeAlias = str", *docstring(c.note, "")]
    if c.nature == "callback":
        assert c.callback is not None
        ctx.imports.add("typing", "TypeAlias")
        *params, result = c.callback.args
        rt = py_type(result, ctx).replace(" | ", " | ")
        callable_ = ctx.imports.add("collections.abc", "Callable")
        args = ", ".join(py_type(p, ctx) for p in params)
        return [], [f'{name}: TypeAlias = {callable_}[[{args}], "{rt}"]', *docstring(c.note, "")]
    if c.is_union:
        ctx.imports.add("typing", "TypeAlias")
        line = f"{name}: TypeAlias = {' | '.join(pascal(v) for v in c.variants)}"
        if len(line) > WIDTH:
            line = f"{name}: TypeAlias = (\n" + "".join(f"    {pascal(v)}\n    | " for v in c.variants)[:-7] + "\n)"
            line = f"{name}: TypeAlias = (\n    " + "\n    | ".join(pascal(v) for v in c.variants) + "\n)"
        return [], [line, *docstring(c.note, "")]
    covariant = c.nature == "shape"
    tvs = type_vars(c.type_parameters, covariant and True)
    cctx = Ctx(model, ctx.here, ctx.imports, tvs)
    if is_record(model, c):
        return record_lines(model, c, cctx, tvs), []
    proto = ctx.imports.add("typing", "Protocol")
    bases = []
    if c.extends is not None:
        args = ", ".join(s(py_type(a, cctx)) for a in c.extends.args)
        bases.append(f"{ctx.ref(c.extends.name, runtime=True)}[{args}]")
    bases.append(f"{proto}[{', '.join(tvs.values())}]" if tvs else proto)
    out = [f"class {name}({', '.join(bases)}):"]
    out += docstring(c.note or f"The spec's {c.name}.", "    ")
    members = list(c.members)
    if c.variant_of:
        members = list(model.concept[c.variant_of].members) + members
    if not members:
        return out, []
    for m in members:
        out.append("")
        out += member_lines(model, c, m, cctx)
    return out, []


def functions_lines(model: Model, layer: str, ctx: Ctx) -> List[str]:
    by_module: Dict[str, List[str]] = {}
    for f in model.functions:
        mod = model.function_module(f, "py")
        if mod is None or f.layer != layer or (f.factory or {}).get("py") == "constructor":
            continue
        lines = by_module.setdefault(mod, [])
        lines.append("")
        lines += signature("    ", snake(f.name), param_list(f.params, ctx), py_type(f.returns, ctx))
    out: List[str] = []
    for mod, lines in sorted(by_module.items()):
        suffix = mod.split(".", 1)[1] if "." in mod else layer
        proto = ctx.imports.add("typing", "Protocol")
        out += ["", "", f"class {pascal(suffix)}Functions({proto}):",
                *docstring(f"The free functions {mod} exports: mypy checks the module against it (`_: X = module`).", "    "),
                *lines]
    return out


def layer_module(model: Model, layer: str) -> str:
    imports = Imports()
    ctx = Ctx(model, layer, imports, {})
    classes: List[List[str]] = []
    aliases: List[List[str]] = []
    for c in model.concepts:
        if c.layer != layer or "py" not in c.languages or c.is_ == "native" or c.nature == "options" or c.name == "collecting":
            continue
        cls, alias = concept_lines(model, c, ctx)
        if cls:
            classes.append(cls)
        if alias:
            aliases.append(alias)
    tvars: List[str] = []
    for c in model.concepts:
        if c.layer == layer and "py" in c.languages:
            covariant = c.nature == "shape"
            for p, tv in type_vars(c.type_parameters, covariant).items():
                imports.add("typing", "TypeVar")
                tvars.append(f'{tv} = TypeVar("{tv}"{", covariant=True" if covariant else ""})')
            for m in c.members:
                for p, tv in type_vars(m.type_parameters, False).items():
                    line = f'{tv} = TypeVar("{tv}")'
                    if line not in tvars:
                        imports.add("typing", "TypeVar")
                        tvars.append(line)
    funcs = functions_lines(model, layer, ctx)
    body: List[str] = []
    if tvars:
        body += ["", *tvars]
    for block in classes:
        body += ["", "", *block]
    for block in aliases:
        body += ["", *block] if body and body[-1].startswith(tuple(pascal(c.name) for c in model.concepts)) else ["", "", *block]
    body += funcs
    head = [f'"""{HEADER}', "", f'Source: spec/schema/api.json, the {layer} layer."""', ""]
    out = head + imports.render() + body
    return "\n".join(out).rstrip("\n") + "\n"


# --- kinds, codes, limits, errors, names -----------------------------------------------------------------------------


def kinds_module(model: Model) -> str:
    blocks = [f'"""{HEADER}\n\nSource: spec/schema/api.json "kinds" and "keywords" (token kind: grammar/Villanelle.g4)."""\n\n'
              "from collections.abc import Mapping\nfrom enum import StrEnum\nfrom types import MappingProxyType\nfrom typing import Final"]
    for k in model.kinds:
        if "py" not in k.languages:
            continue
        members = "\n".join(f"    {kind_member(model, k.name, v)} = {s(v)}" for v in k.values)
        blocks.append(f'class {pascal(k.name)}(StrEnum):\n    """The spec\'s {k.name} list (spec 2.10): compare members, never strings."""\n\n{members}')
    kw = "\n".join(f"    {upper_snake(w)} = {s(w)}" for w, _ in model.keywords)
    blocks.append(f'class Keyword(StrEnum):\n    """The language statements\' keywords, written after \'@\' (spec 2.5): the one keyword list."""\n\n{kw}')
    table = "\n".join(f"        Keyword.{upper_snake(w)}: StatementKind.{upper_snake(sk)}," for w, sk in model.keywords)
    blocks.append("STATEMENT_OF_KEYWORD: Final[Mapping[Keyword, StatementKind]] = MappingProxyType(\n    {\n"
                  f"{table}\n    }}\n)\n" + '"""The statement kind each keyword writes: the one dispatch table."""')
    blocks.append("def statement_of_keyword(word: str, /) -> StatementKind | None:\n"
                  '    """The statement kind a keyword (its text without \'@\') writes; None for any other word."""\n'
                  "    for keyword, kind in STATEMENT_OF_KEYWORD.items():\n"
                  "        if keyword.value == word:\n"
                  "            return kind\n"
                  "    return None")
    return "\n\n\n".join(blocks) + "\n"


def message_expr(model: Model, message: str, imports: Set[str]) -> str:
    if not PLACEHOLDER.search(message):
        return s(message)
    out, pos = [], 0
    for m in PLACEHOLDER.finditer(message):
        out.append(message[pos:m.start()].replace("{", "{{").replace("}", "}}"))
        const = upper_snake(model.limit[m.group(1)].name)
        imports.add(const)
        out.append("{" + const + "}")
        pos = m.end()
    out.append(message[pos:].replace("{", "{{").replace("}", "}}"))
    return "f" + s("".join(out))


def codes_module(model: Model) -> str:
    members, messages, facts = [], [], []
    imports: Set[str] = set()
    for c in model.codes:
        members.append(f"    {upper_snake(c.name)} = {s(c.code)}")
        members += docstring(c.meaning.replace("`", ""), "    ")
        messages.append(f"        DiagnosticCode.{upper_snake(c.name)}: {message_expr(model, c.message, imports)},")
        reason = "None" if c.reason is None else f"UnreadableReason.{upper_snake(c.reason)}"
        found = ", ".join(s(f) for f in c.found_by)
        found = tuple_literal([s(f) for f in c.found_by])
        fact = f"        DiagnosticCode.{upper_snake(c.name)}: CodeFacts({s(c.name)}, {s(c.layer)}, {found}, {reason}),"
        if len(fact) > WIDTH:
            fact = (f"        DiagnosticCode.{upper_snake(c.name)}: CodeFacts(\n            {s(c.name)}, {s(c.layer)}, {found}, {reason}\n"
                    "        ),")
        facts.append(fact)
    head = [f'"""{HEADER}', "", 'Source: spec/schema/diagnostics.json."""', "", "from collections.abc import Mapping",
            "from dataclasses import dataclass", "from enum import StrEnum", "from types import MappingProxyType",
            "from typing import Final", "", "from villanelle._api.kinds import UnreadableReason"]
    if imports:
        head.append(f"from villanelle._api.limits import {', '.join(sorted(imports))}")
    return "\n".join([
        *head, "", "",
        "class DiagnosticCode(StrEnum):",
        '    """villanelle\'s diagnostic codes, by name (spec 2.4)."""', "",
        *members, "", "",
        "MESSAGES: Final[Mapping[DiagnosticCode, str]] = MappingProxyType(", "    {", *messages, "    }", ")",
        '"""The base message of each code (spec 2.3: for people, not part of the contract)."""', "", "",
        "@dataclass(frozen=True, slots=True)",
        "class CodeFacts:",
        '    """What the registry says of one code: its spec name, owning layer, who finds it, the reason it gives."""', "",
        "    name: str", "    layer: str", "    found_by: tuple[str, ...]", "    reason: UnreadableReason | None", "", "",
        "CODE_FACTS: Final[Mapping[DiagnosticCode, CodeFacts]] = MappingProxyType(", "    {", *facts, "    }", ")",
        '"""Each code\'s facts (spec 2.4)."""', "", "",
        "@dataclass(frozen=True, slots=True)",
        "class Described:",
        '    """One diagnostic\'s code, message and reason, built from the registry."""', "",
        "    code: DiagnosticCode", "    message: str", "    reason: UnreadableReason | None", "", "",
        "def describe(code: DiagnosticCode, detail: str | None = None, /) -> Described:",
        '    """The typed diagnostic constructor (spec/codegen.md section 4): a raise site names the code and its detail, and',
        '    the message and reason come from the registry, so they cannot disagree with it. ``detail`` follows \': \'."""',
        "    base = MESSAGES[code]",
        '    message = base if detail is None else f"{base}: {detail}"',
        "    return Described(code, message, CODE_FACTS[code].reason)", "",
    ])


def limits_module(model: Model) -> str:
    out = [f'"""{HEADER}', "", 'Source: spec/schema/api.json "limits", "reserved names" and "patterns" (the rules module)."""', "",
           "import re", "from typing import Final", ""]
    for c in model.constants:
        name = upper_snake(c.name)
        if c.sort == "limit":
            out += [f"{name}: Final = {c.value}"]
        elif c.sort == "words":
            out += [f"{name}: Final = frozenset({{{', '.join(s(w) for w in c.value)}}})"]  # type: ignore[union-attr]
        else:
            regex = str(c.value)[:-1] + "\\Z"  # Python's $ also matches before a final newline; \Z is the text's end
            out += [f'{name}: Final = re.compile(r"{regex}")']
        out += docstring(f"{c.about}: {c.means}.", "") + [""]
    while out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def errors_module(model: Model) -> str:
    imports = Imports()
    ctx = Ctx(model, "errors", imports, {})
    body: List[str] = []
    for g in model.groups:
        if g.builtin("py"):
            continue
        name = pascal(g.name)
        parent = model.group[g.parent] if g.parent else None
        base = pascal(parent.name) if parent else g.base["py"]["base"]
        body += ["", "", f"class {name}({base}):"]
        body += docstring(f"{g.raised_when[0].upper()}{g.raised_when[1:]}. Spec 2.8: {g.sort}.", "    ")
        own = [(f, t) for f, t in g.fields if not (parent and any(pf == f for pf, _ in parent.fields))]
        if not g.fields:
            continue
        for f, t in own:
            body += ["", f"    {snake(f)}: {py_type(model.parse(t, g.name), ctx)}"]
        params = ["self"]
        if g.message.get("given"):
            params.append("message: str")
        for f, t in g.fields:
            params.append(f"{snake(f)}: {py_type(model.parse(t, g.name), ctx, True)}")
        if g.message.get("given"):
            msg = "message"
        else:
            msg = template(g.message, g.fields)
        body += [""] + signature("    ", "__init__", params, "None", "")
        if parent is None or not parent.fields:
            body.append(f"        super().__init__({msg})")
        else:
            args = ([msg] if parent.message.get("given") else []) + [snake(f) for f, _ in parent.fields]
            body.append(f"        super().__init__({', '.join(args)})")
        for f, t in own:
            conv = f"tuple({snake(f)})" if t.endswith("[]") else snake(f)
            body.append(f"        self.{snake(f)} = {conv}")
    tmpl = model.argument_type_message["py"]
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(tmpl):
        parts.append(tmpl[pos:m.start()])
        parts.append("{" + snake(m.group(1)) + "}")
        pos = m.end()
    parts.append(tmpl[pos:])
    body += ["", "", "def argument_type_message(member: str, parameter: str, got: str, /) -> str:",
             *docstring("The argument type error's message (spec 2.8): the one helper every member that takes text calls.", "    "),
             "    return (", *wrap_string("".join(parts), "        "), "    )"]
    head = [f'"""{HEADER}', "", 'Source: spec/schema/api.json "error groups"."""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


def template(message: Dict[str, object], fields: List[Tuple[str, str]]) -> str:
    text = str(message["template"])
    sep = str(message.get("separator", ", "))
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(text):
        parts.append(text[pos:m.start()].replace("{", "{{").replace("}", "}}"))
        ph = m.group(1)
        if ph.endswith(" message"):
            parts.append("{" + snake(ph[: -len(" message")]) + ".message}")
        elif dict(fields)[ph] == "text[]":
            parts.append("{" + s(sep).replace('"', "'") + ".join(" + snake(ph) + ")}")
        else:
            parts.append("{" + s(sep).replace('"', "'") + ".join(str(d) for d in " + snake(ph) + ")}")
        pos = m.end()
    parts.append(text[pos:].replace("{", "{{").replace("}", "}}"))
    return "f" + s("".join(parts))


def names_module(model: Model) -> str:
    by_mod: Dict[str, List[str]] = {}
    for mod, name, _ in model.public("py"):
        by_mod.setdefault(mod, []).append(name)
    out = [f'"""{HEADER}', "", 'Source: spec/schema/api.json: every public name, derived by the casing rule."""', "",
           "from collections.abc import Mapping", "from types import MappingProxyType", "from typing import Final", "",
           "PUBLIC_NAMES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(", "    {"]
    for mod in sorted(by_mod):
        names = ", ".join(s(n) for n in sorted(by_mod[mod]))
        line = f"        {s(mod)}: frozenset({{{names}}}),"
        if len(line) <= WIDTH:
            out.append(line)
        else:
            out += [f"        {s(mod)}: frozenset(", "            {", *(f"                {s(n)}," for n in sorted(by_mod[mod])),
                    "            }", "        ),"]
    out += ["    }", ")", '"""Every public name by module: each module\'s __all__ must equal its set (the name test)."""', "",
            "ERROR_GROUP_OF_CLASS: Final[Mapping[str, str]] = MappingProxyType(", "    {"]
    for g in model.groups:
        out.append(f"        {s(g.builtin('py') or pascal(g.name))}: {s(g.name)},")
    out += ["    }", ")", '"""Each error group\'s class (or the language\'s own, for a builtin group) to its spec name."""', "",
            "MATCH_ARGS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(", "    {"]
    for c in model.concepts:
        if c.match_args:
            out.append(f"        {s(pascal(c.name))}: {tuple_literal([s(snake(a)) for a in c.match_args])},")
    out += ["    }", ")", '"""Each class\'s __match_args__, in the same field order in every layer (spec 2.10)."""']
    return "\n".join(out) + "\n"


# --- the adapter protocol --------------------------------------------------------------------------------------------


def shape_type(t: Type, imports: Imports) -> str:
    if t.form == "name":
        b = {"text": "str", "integer": "int", "number": "float", "boolean": "bool", "json": "Json", "id": "str", "null": "None"}
        if t.name in b:
            return b[t.name]
        return f"{pascal(t.name)}Dump" if t.name != "position" else "Position"
    if t.form == "literal":
        imports.add("typing", "Literal")
        return f"Literal[{s(t.name)}]"
    if t.form == "list":
        return f"list[{shape_type(t.item, imports)}]"
    if t.form == "union":
        return " | ".join(shape_type(a, imports) for a in t.args)
    if t.form == "map":
        return f"dict[str, {shape_type(t.args[1], imports)}]"
    if t.form == "tuple":
        return f"tuple[{', '.join(shape_type(a, imports) for a in t.args)}]"
    raise AssertionError(t)


def shapes_module(model: Model) -> str:
    p = model.protocol
    imports = Imports()
    imports.add("typing", "TypeAlias")
    imports.add("typing", "TypedDict")
    body = ["", 'Json: TypeAlias = "bool | int | float | str | list[Json] | dict[str, Json] | None"', "",
            f"PROTOCOL = {p.version}", '"""The protocol version an adapter\'s hello answers."""']

    def td(name: str, fields: Dict[str, Type], optional: List[str], total_optional: bool = False) -> List[str]:
        out = ["", "", f"class {name}(TypedDict{', total=False' if total_optional else ''}):"]
        if not fields:
            return out + ["    pass"]
        for k, t in fields.items():
            ty = shape_type(t, imports)
            if k in optional:
                imports.add("typing", "NotRequired")
                ty = f"NotRequired[{ty}]"
            out.append(f"    {k}: {ty}")
        return out

    for sh in p.shapes:
        name = pascal(sh.name) + ("" if sh.name == "position" else "Dump")
        if sh.tuple_ is not None:
            body += ["", "", f"{name}: TypeAlias = {s('tuple[' + ', '.join(shape_type(t, imports) for t in sh.tuple_) + ']')}"]
        elif sh.one_of:
            alts = []
            for k, t in sh.one_of.items():
                alts.append(f"{name}{pascal(k)}")
                body += td(f"{name}{pascal(k)}", {k: t}, [])
            body += ["", "", f"{name}: TypeAlias = (", *(f"    {'| ' if i else ''}{a}" for i, a in enumerate(alts)), ")"]
        else:
            fields = dict(sh.fields)
            optional = list(sh.optional)
            for extra in sh.by_kind.values():
                for k, t in extra.items():
                    if k not in fields:
                        fields[k] = t
                        optional.append(k)
            body += td(name, fields, optional)
    spell: Dict[str, str] = {}
    for c in model.concepts:
        for m in c.members:
            spell[m.name] = snake(m.name)
    for name in p.edit_members + p.readers:
        spell[name] = snake(name)
    imports.add("collections.abc", "Mapping")
    imports.add("typing", "Final")
    body += ["", "", "SPELLING: Final[Mapping[str, str]] = {", *(f"    {s(k)}: {s(v)}," for k, v in sorted(spell.items())), "}",
             '"""Each spec name the driver sends (a member, a reader) to this binding\'s spelling: the casing rule, once."""']
    head = [f'"""{HEADER}', "", 'Source: spec/schema/protocol.json (spec/conformance.md 4): the adapter\'s message types."""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


def render(model: Model) -> Dict[str, str]:
    files = {
        "__init__.py": f'"""{HEADER}"""\n',
        "kinds.py": kinds_module(model),
        "codes.py": codes_module(model),
        "limits.py": limits_module(model),
        "errors.py": errors_module(model),
        "names.py": names_module(model),
        # The folder is generated and never committed: ignore it from inside, as tools/gen.sh's own output is ignored.
        ".gitignore": f"# {HEADER}\n*\n",
    }
    for layer in LAYER_FILES:
        files[f"{layer}.py"] = layer_module(model, layer)
    return files


def render_shapes(model: Model) -> Dict[str, str]:
    return {"shapes.py": shapes_module(model)}

