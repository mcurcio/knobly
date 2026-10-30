"""The Python emitter (spec/codegen.md section 4): renders the loader's model as Python modules.

    py/src/villanelle/_api/kinds.py      every kind list as a StrEnum; Keyword and its dispatch table
    py/src/villanelle/_api/codes.py      DiagnosticCode, MESSAGES, CODE_FACTS and describe()
    py/src/villanelle/_api/limits.py     the rules: limits, reserved words, patterns
    py/src/villanelle/_api/errors.py     the error class tree and argument_type_message()
    py/src/villanelle/_api/record.py     SlottedRecord, the base of every generated record (copy and pickle)
    py/src/villanelle/_api/<layer>.py    a Protocol per handle, port and interface, a frozen dataclass per plain
                                         record, callback aliases, and union aliases over generated records: one module
                                         per layer api.json lists
    py/conformance/shapes.py             the adapter protocol's message TypedDicts, the spec-name spellings and each
                                         error class's group
    py/tests/api_contract.py             what the binding's tests check it against: every public name per module, each
                                         class's match args, each public union's variants, each module's
                                         <Module>Functions and each constructed class's <Class>Constructor Protocol, and
                                         the assignments that make mypy check the binding against all of them

The public types and the generated types are one (spec/codegen.md section 4): every annotation that names a concept the
binding implements by hand names the binding's public class (``villanelle.rendered.Directive``), imported for the type
checker only; a concept the generator writes whole (a record, a callback or named type, a union of records) is named by
its generated class, which the binding re-exports. So a program annotating with the public classes type-checks against
every generated record, callback and Protocol, and nothing outside the package imports ``villanelle._api``.

Idiom lives here and only here: properties, tuples for results, Sequence and Mapping for parameters, positional-only
parameters, keyword-only options, __str__ / __iter__ / __len__ / __getitem__ / a generator walk / a context manager for
the traits. Layout is not: the output goes through py's pinned ruff (its import sorting, then ruff format) before it is
written (tools/api/formatter.py), so this module writes each statement plainly and wraps only what no formatter splits
(docstrings and long strings, to the line length), and py's ruff and mypy --strict check it as they check hand code.
"""

from __future__ import annotations

import json
import textwrap
from typing import Dict, List, Optional, Set, Tuple

from .loader import (
    HEADER,
    PLACEHOLDER,
    Concept,
    Formatter,
    Function,
    Language,
    Member,
    Model,
    Param,
    SchemaError,
    Type,
    pascal,
    pattern_body,
    sentence,
    snake,
    upper_snake,
)

WIDTH = 120  # py/pyproject.toml's line-length: docstrings and long strings are wrapped to it (no formatter splits them)
CHUNK = 96  # the longest part of a long string: it fits the line at any indentation the generated code reaches
RUFF = ("uv", "run", "--quiet", "--project", "py", "--locked", "ruff")  # the ruff py/pyproject.toml pins exactly
RUFF_CONFIG = ("--config", "py/pyproject.toml", "--no-cache", "--quiet")


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    """A Python class is a value (an enumeration, an error class, a handle, record, port, interface or shape); a named
    type or a callback alias is a type."""
    return "value" if c is None or c.nature in ("handle", "snapshot", "record", "port", "interface", "shape") else "type"


def _trait_names(model: Model) -> List[Tuple[str, str, str]]:
    """The collect trait is a context manager here (``with diagnostics.collecting():``): its class is public beside the
    concept that has the trait."""
    return [(model.concept_module(c, "py"), pascal("collecting"), "value")
            for c in model.concepts if "py" in c.languages and any(m.trait == "collect" for m in c.members)]


def _omit(name: str, nature: str) -> bool:
    """Python passes options as keyword arguments (no options records) and walks with a generator (no walk control)."""
    return nature == "options" or name == "walk control"


def _omitted_as(name: str, nature: str) -> str:
    return "keyword arguments" if nature == "options" else "none"


# Python's own facts (the schema names no language; spec/codegen.md section 10).
LANGUAGE = Language(
    key="py",
    name="Python",
    sep=".",
    function_case=snake,
    code_case=upper_snake,
    public_kind=_public_kind,
    enum_form="`StrEnum`",
    generic=lambda name, params: f"{name}[{', '.join(params)}]",
    construct=lambda name: f"{name}(...)",
    extends_word="subclass of",
    cause_field="__cause__",
    error_roots={
        "villanelle error": {"base": "Exception"},
        "detached error": {"base": "ReferenceError"},
        "argument type error": {"builtin": "TypeError"},
        "misuse error": {"builtin": "ValueError"},
        "index out of range": {"builtin": "IndexError"},
    },
    argument_type_message=("{member}() argument '{parameter}' must be str, not {got}; villanelle edits take config text: "
                           "quote() a program string, text() one already written as villanelle text, str() a number "
                           "first"),  # {got}: type(value).__name__
    modules={"files": "files", "include": "include"},  # no fetch adapter
    omit=_omit,
    omitted_as=_omitted_as,
    trait_names=_trait_names,
    # ruff's documented order: sort the imports (a lint fix), then format.
    formatter=Formatter(".py", ((*RUFF, "check", "--select", "I", "--fix", *RUFF_CONFIG), (*RUFF, "format", *RUFF_CONFIG))),
)


def s(text: str) -> str:
    """A string literal (ruff format picks its quotes)."""
    return json.dumps(text, ensure_ascii=False)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"').strip()


def docstring(text: str, indent: str, sections: Optional[List[Tuple[str, List[Tuple[str, str]]]]] = None) -> List[str]:
    """A docstring: the text as a sentence, wrapped, then each Google-style section (``Args:``, ``Raises:``) with one
    entry a name."""
    width = WIDTH - len(indent) - 6  # room for both quotes
    lines = textwrap.wrap(_escape(sentence(text)), width)
    for title, entries in sections or []:
        if entries:  # the loader gives every member a doc, so a section never opens the docstring
            lines += ["", f"{title}:"]
            for name, d in entries:
                lines += textwrap.wrap(f"{name}: {_escape(d)}", width, initial_indent="    ", subsequent_indent="        ")
    if not lines:
        return []
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}{" " if lines[0].endswith(chr(34)) else ""}"""']
    return [f'{indent}"""{lines[0]}', *(f"{indent}{line}" if line else "" for line in lines[1:]), f'{indent}"""']


def error_class(model: Model, group: str) -> str:
    g = model.group[group]
    return g.builtin("py") or pascal(g.name)


def member_docstring(model: Model, text: str, params: List[Param], raised: List[Tuple[str, str]], order: str, indent: str) -> List[str]:
    """A member's docstring: its doc and order, an ``Args`` section for its documented parameters, and a ``Raises``
    section for the error groups it raises (as TypeScript writes ``@param`` and ``@throws``)."""
    if order:
        text = f"{sentence(text)} Order: {order}.".strip()
    args = [(snake(p.name), p.doc) for p in params if p.doc]
    raises = [(error_class(model, e), why) for e, why in raised]
    return docstring(text, indent, [("Args", args), ("Raises", raises)])


WALK_DESCEND = ("asked of each item after it is given and before its block; false passes over its block. None goes into every "
                "block; break ends the walk")


def tuple_literal(items: List[str]) -> str:
    """A tuple literal: one item takes the comma that makes it a tuple."""
    return f"({items[0]},)" if len(items) == 1 else f"({', '.join(items)})"


def long_string(text: str, f: bool = False) -> str:
    """A string (an f-string when ``f``) as implicitly joined parts of at most CHUNK characters, split at spaces
    outside {placeholders}, in parentheses: ruff format joins the parts that fit a line and lays out the rest."""
    parts, cur, depth = [], "", 0
    for ch in text:
        cur += ch
        depth += {"{": 1, "}": -1}.get(ch, 0) if f else 0
        if ch == " " and depth == 0 and len(cur) >= CHUNK - 12:
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    if len(parts) == 1:
        return f"{'f' if f else ''}{s(text)}"
    return "(" + " ".join(f"{'f' if f and '{' in p else ''}{s(p)}" for p in parts) + ")"


def kind_member(model: Model, list_name: str, value: str) -> str:
    return value if model.kind[list_name].from_grammar else upper_snake(value)


class Imports:
    """What one module imports (ruff's import sorting orders and groups them)."""

    def __init__(self) -> None:
        self.runtime: Dict[str, Set[str]] = {}
        self.typing_only: Dict[str, Set[str]] = {}
        self.modules: Set[str] = set()  # `import villanelle.rendered`, for the type checker only

    def module(self, module: str) -> str:
        self.modules.add(module)
        return module

    def add(self, module: str, name: str, runtime: bool = True) -> str:
        (self.runtime if runtime else self.typing_only).setdefault(module, set()).add(name)
        return name

    @staticmethod
    def _lines(mods: Dict[str, Set[str]], indent: str, plain: Set[str] = frozenset()) -> List[str]:  # type: ignore[assignment]
        return [*(f"{indent}import {m}" for m in sorted(plain)),
                *(f"{indent}from {m} import {', '.join(sorted(mods[m]))}" for m in sorted(mods))]

    def render(self) -> List[str]:
        typing_only = {m: n - self.runtime.get(m, set()) for m, n in self.typing_only.items()}
        typing_only = {m: n for m, n in typing_only.items() if n}
        rt = {m: set(n) for m, n in self.runtime.items()}
        if typing_only or self.modules:
            rt.setdefault("typing", set()).add("TYPE_CHECKING")
        out = ["from __future__ import annotations", ""] + self._lines(rt, "")
        if typing_only or self.modules:
            out += ["", "if TYPE_CHECKING:", *self._lines(typing_only, "    ", self.modules)]
        return out


def generated_public(model: Model, c: Concept) -> bool:
    """The generator writes the concept whole and the binding re-exports it as its public name: a plain record, a named
    type, a callback, or a union whose variants are all such records. Every other concept is a Protocol the binding
    implements with its own public class (spec/codegen.md section 4)."""
    if c.is_union:
        return all(generated_public(model, model.concept[v]) for v in c.variants)
    return c.nature in ("named type", "callback") or is_record(model, c)


class Ctx:
    def __init__(self, model: Model, here: str, imports: Imports, type_params: Dict[str, str], public: bool = False) -> None:
        self.model, self.here, self.imports, self.type_params = model, here, imports, type_params
        self.public = public  # outside the package (api_contract.py): every name through its public module

    def qualified(self, module: str, name: str) -> str:
        self.imports.module(module)
        return f"{module}.{name}"

    def ref(self, name: str, runtime: bool = False) -> str:
        """A name as this module writes it. ``runtime``: evaluated when the module runs (a base class), so it must be
        the generated class itself; otherwise an annotation, where a concept the binding implements by hand is its
        public class (``villanelle.rendered.Directive``), imported for the type checker only."""
        m = self.model
        if name in self.type_params:
            return self.type_params[name]
        if name in m.kind:
            if self.public:
                return self.qualified(m.module(m.kind[name].layer, "."), pascal(name))
            return self.imports.add("villanelle._api.kinds", pascal(name), runtime)
        if name == "diagnostic code":
            if self.public:
                return self.qualified(m.package, "DiagnosticCode")
            return self.imports.add("villanelle._api.codes", "DiagnosticCode", runtime)
        if name in m.group:
            g = m.group[name]
            if g.builtin("py"):
                return g.builtin("py") or ""
            if self.public:
                return self.qualified(m.package, pascal(name))
            return self.imports.add("villanelle._api.errors", pascal(name), runtime)
        c = m.concept[name]
        if c.is_ == "native":
            raise SchemaError(f"native type {name!r}: Python has none (leave its module out of LANGUAGE.modules, or omit it)")
        if self.public or not runtime and not generated_public(m, c):
            return self.qualified(m.concept_module(c, "py"), pascal(name))
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


# --- signatures -------------------------------------------------------------------------------------------------------


def signature(indent: str, name: str, params: List[str], result: str, body: str = " ...") -> List[str]:
    return [f"{indent}def {name}({', '.join(params)}) -> {result}:{body}"]


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


def documented(indent: str, name: str, params: List[str], result: str, note: List[str]) -> List[str]:
    """A Protocol member's signature, with its docstring lines (``member_docstring``) as its body."""
    if not note:
        return signature(indent, name, params, result)
    return signature(indent, name, params, result, "") + note


def member_lines(model: Model, c: Concept, m: Member, ctx: Ctx, indent: str = "    ") -> List[str]:
    params = [Param("descend", m.type, doc=WALK_DESCEND)] if m.trait == "walk" else m.params
    note = member_docstring(model, m.doc, params, model.raised(m.errors, m.when), m.order, indent + "    ")
    if m.trait == "people form":
        return documented(indent, "__str__", ["self"], "str", note)
    if m.trait == "iterate":
        return documented(indent, "__iter__", ["self"], f"{ctx.abc('Iterator')}[{py_type(m.type.item, ctx)}]", note)
    if m.trait == "count":
        return documented(indent, "__len__", ["self"], "int", note)
    if m.trait == "index":
        return sequence_lines(m, ctx, indent)
    if m.trait == "walk":
        item = py_type(m.type.item, ctx)
        return documented(indent, "walk", ["self", "*", f"descend: {ctx.abc('Callable')}[[{item}], bool] | None = None"],
                          f"{ctx.abc('Iterator')}[{item}]", note)
    if m.trait == "collect":
        cm = ctx.imports.add("contextlib", "AbstractContextManager", False)
        return documented(indent, "collecting", ["self"], f"{cm}[None]", note)
    if m.member == "property":
        if m.name == "kind" and c.kind is not None:
            lst = m.type.name
            t = f"Literal[{ctx.ref(lst)}.{kind_member(model, lst, c.kind)}]"
            ctx.imports.add("typing", "Literal", False)
        else:
            t = py_type(m.type, ctx)
        return [f"{indent}@property", *documented(indent, snake(m.name), ["self"], t, note)]
    tvs = type_vars(m.type_parameters, False)
    mctx = Ctx(model, ctx.here, ctx.imports, {**ctx.type_params, **tvs})
    return documented(indent, snake(m.name), param_list(m.params, mctx), py_type(m.type, mctx), note)


def sequence_lines(m: Member, ctx: Ctx, indent: str) -> List[str]:
    """The index trait in Python: the read side of ``collections.abc.Sequence`` (a Protocol cannot extend the ABC, so
    it states the methods; with the count and iterate traits a program can index, slice, ``reversed()``, ``in``,
    ``.index()`` and ``.count()`` a value typed by it, as spec 2.11 says of a block)."""
    item = py_type(m.type, ctx)
    overload = ctx.imports.add("typing", "overload")
    it = ctx.abc("Iterator")
    return [f"{indent}@{overload}", *signature(indent, "__getitem__", ["self", "index: int", "/"], item), "",
            f"{indent}@{overload}", *signature(indent, "__getitem__", ["self", "index: slice", "/"], f"tuple[{item}, ...]"), "",
            *signature(indent, "__contains__", ["self", "value: object", "/"], "bool"), "",
            *signature(indent, "__reversed__", ["self"], f"{it}[{item}]"), "",
            *signature(indent, "index", ["self", "value: object", "start: int = 0", f"stop: int = {ctx.imports.add('sys', 'maxsize')}", "/"], "int"), "",
            *signature(indent, "count", ["self", "value: object", "/"], "int")]


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
    else:
        bases.append(ctx.imports.add("villanelle._api.record", "SlottedRecord"))
    if tvs:
        bases.append(f"{ctx.imports.add('typing', 'Generic')}[{', '.join(tvs.values())}]")
    own = [m for m in c.members]
    if c.variant_of:
        own = [m for m in model.concept[c.variant_of].members if m.name != "kind"] + own
    fields = [m for m in own if not (m.name == "kind" and c.kind is not None)]
    order = {a: i for i, a in enumerate(c.match_args)}
    fields.sort(key=lambda m: order.get(m.name, len(order)))
    # A dataclass matches on every field unless told otherwise; the spec's match args may be fewer (spec 2.10).
    explicit = bool(c.match_args) and [m.name for m in fields] != list(c.match_args)
    # Slotted by hand, not slots=True: a __slots__ dict gives each field's slot its doc, which help() shows.
    flags = f"frozen=True{eq}{', match_args=False' if explicit else ''}"
    out = ["@final", f"@dataclass({flags})"] if not any(
        o.extends is not None and o.extends.name == c.name for o in model.concepts) else [f"@dataclass({flags})"]
    if out[0] == "@final":
        ctx.imports.add("typing", "final")
    out.append(f"class {name}({', '.join(bases)}):" if bases else f"class {name}:")
    out += docstring(c.doc, "    ")
    if explicit:
        out += ["", match_args_line(c, ctx)] if c.doc else [match_args_line(c, ctx)]
    out += ([""] if c.doc or explicit else []) + slots_lines(fields)
    if fields:
        out.append("")
    for m in fields:
        out.append(f"    {snake(m.name)}: {py_type(m.type, ctx)}")
        out += member_docstring(model, m.doc, [], [], m.order, "    ")
    if c.kind is not None:
        list_name = model.kind_list_of(c)
        kind_type = ctx.ref(list_name, runtime=True)
        member = kind_member(model, list_name, c.kind)
        ctx.imports.add("typing", "Literal", False)
        out += ["", "    @property", f"    def kind(self) -> Literal[{kind_type}.{member}]:", f"        return {kind_type}.{member}"]
    if len(out) == 1 + out.index(next(line for line in out if line.startswith("class "))):
        out.append("    pass")  # a record with no doc, no field and no kind
    return out


def slots_lines(fields: List[Member]) -> List[str]:
    """``__slots__`` as a dict from each field to its doc, sorted (RUF023): pydoc shows a slot's dict value as its doc,
    so help() and each slot's ``__doc__`` give the schema's doc (a ``slots=True`` dataclass's slots cannot hold one)."""
    if not fields:
        return ["    __slots__ = ()"]
    entries = sorted((snake(m.name), sentence(m.doc)) for m in fields)
    return ["    __slots__ = {" + ", ".join(f"{s(n)}: {long_string(d)}" for n, d in entries) + "}"]


def match_args_line(c: Concept, ctx: Ctx) -> str:
    """``__match_args__`` typed by its literal names (mypy narrows positional patterns by them; a Protocol member must
    be typed, and a Protocol member cannot be Final)."""
    names = [s(snake(a)) for a in c.match_args]
    lit = ctx.imports.add("typing", "Literal", False)
    cv = ctx.imports.add("typing", "ClassVar")  # at run time: dataclasses read the annotation to skip the field
    return f"    __match_args__: {cv}[tuple[{', '.join(f'{lit}[{n}]' for n in names)}]] = {tuple_literal(names)}"


def concept_lines(model: Model, c: Concept, ctx: Ctx) -> Tuple[List[str], List[str]]:
    """The concept's class (first) or its alias (second: aliases go after every class of the module)."""
    name = pascal(c.name)
    if c.nature == "named type":
        if c.brand:
            ctx.imports.add("typing", "NewType")
            return [f'{name} = NewType("{name}", str)', *docstring(c.doc, "")], []
        ctx.imports.add("typing", "TypeAlias")
        return [], [f"{name}: TypeAlias = str", *docstring(c.doc, "")]
    if c.nature == "callback":
        assert c.callback is not None
        ctx.imports.add("typing", "TypeAlias")
        *params, result = c.callback.args
        rt = py_type(result, ctx)
        callable_ = ctx.imports.add("collections.abc", "Callable")
        args = ", ".join(f'"{py_type(p, ctx)}"' for p in params)  # evaluated at run time: each name stays a string
        return [], [f'{name}: TypeAlias = {callable_}[[{args}], "{rt}"]', *docstring(c.doc, "")]
    if c.is_union:
        if not generated_public(model, c):
            return [], []  # a union over the binding's own classes is the binding's (api_contract.UNIONS checks it)
        ctx.imports.add("typing", "TypeAlias")
        return [], [f"{name}: TypeAlias = {' | '.join(pascal(v) for v in c.variants)}", *docstring(c.doc, "")]
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
    out += docstring(c.doc, "    ")
    if c.match_args:
        # A class that implements the Protocol inherits it, so `case SetLine(variable, values):` binds the spec's fields.
        out += ["", match_args_line(c, ctx)] if c.doc else [match_args_line(c, ctx)]
    members = list(c.members)
    if c.variant_of:
        members = list(model.concept[c.variant_of].members) + members
    for m in members:
        if len(out) > 1:
            out.append("")
        out += member_lines(model, c, m, cctx)
    if len(out) == 1:
        out.append("    pass")  # a Protocol with no doc and no member
    return out, []


def functions_suffix(model: Model, f: Function) -> str:
    """What names the ``<Module>Functions`` Protocol that lists a free function: its module's last part, or its layer."""
    mod = model.function_module(f, "py") or ""
    return mod.split(".", 1)[1] if "." in mod else f.layer


def functions_protocol(model: Model, f: Function) -> str:
    return f"{pascal(functions_suffix(model, f))}Functions"


def docs_module(model: Model) -> str:
    """``_api/docs.py``: where each public module's functions and constructed classes take their docs from (the
    package's ``_docs`` gives them at import), so a hand-written function or constructor carries the schema's doc. The
    Protocols are named by their dotted paths, imported only for the module being documented, so no layer imports a
    layer above it through this table."""
    imports = Imports()
    imports.add("typing", "Final")
    imports.add("collections.abc", "Mapping")
    imports.add("types", "MappingProxyType")
    functions: Dict[str, Set[str]] = {}
    constructors: List[str] = []
    for f in model.functions:
        mod = model.function_module(f, "py")
        if mod is None:
            continue
        layer = f"{model.package}._api.{f.layer}"
        if (f.factory or {}).get("py") == "constructor":
            of = pascal(f.factory["of"])  # type: ignore[index]
            constructors.append(f"{s(mod + '.' + of)}: {s(f'{layer}.{of}Constructor')}")
        else:
            functions.setdefault(mod, set()).add(s(f"{layer}.{functions_protocol(model, f)}"))
    entries = [f"{s(mod)}: {tuple_literal(sorted(protos))}" for mod, protos in sorted(functions.items())]
    body = ["", *frozen_map("FUNCTIONS", "str, tuple[str, ...]", entries,
                            "Each public module's <Module>Functions Protocols: each of its functions takes its doc from one."),
            "", *frozen_map("CONSTRUCTORS", "str, str", sorted(constructors),
                            "Each constructed class's <Class>Constructor Protocol: its __init__ takes the doc of __call__.")]
    head = [f'"""{HEADER}', "", 'Source: spec/schema/api.json "free functions": the docs of the public functions and constructors.'
            '"""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


def functions_lines(model: Model, layer: str, ctx: Ctx) -> List[str]:
    by_module: Dict[str, List[str]] = {}
    for f in model.functions:
        mod = model.function_module(f, "py")
        if mod is None or f.layer != layer or (f.factory or {}).get("py") == "constructor":
            continue
        lines = by_module.setdefault(mod, [])
        lines.append("")
        lines += documented("    ", snake(f.name), param_list(f.params, ctx), py_type(f.returns, ctx),
                            member_docstring(model, f.doc, f.params, model.raised(f.errors, f.when), "", "        "))
    out: List[str] = []
    for mod, lines in sorted(by_module.items()):
        suffix = mod.split(".", 1)[1] if "." in mod else layer
        proto = ctx.imports.add("typing", "Protocol")
        out += ["", "", f"class {pascal(suffix)}Functions({proto}):",
                *docstring(f"The free functions {mod} exports.", "    "),
                *lines]
    for f in model.functions:
        if f.layer != layer or (f.factory or {}).get("py") != "constructor" or model.function_module(f, "py") is None:
            continue
        of = f.factory["of"]  # type: ignore[index]
        proto = ctx.imports.add("typing", "Protocol")
        out += ["", "", f"class {pascal(of)}Constructor({proto}):",
                *docstring(f"The signature of {pascal(of)}(...).", "    "),
                "", *documented("    ", "__call__", param_list(f.params, ctx), ctx.ref(of),
                                member_docstring(model, f.doc, f.params, model.raised(f.errors, f.when), "", "        "))]
    return out


def layer_module(model: Model, layer: str) -> str:
    imports = Imports()
    ctx = Ctx(model, layer, imports, {})
    classes: List[List[str]] = []
    aliases: List[List[str]] = []
    for c in model.concepts:
        if c.layer != layer or "py" not in c.languages or c.is_ == "native" or c.nature == "options":
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
    body: List[str] = []
    if tvars:
        body += ["", *tvars]
    for block in classes:
        body += ["", "", *block]
    for block in aliases:
        body += ["", "", *block]
    body += functions_lines(model, layer, ctx)
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
        first = f"{pascal(k.name)}.{kind_member(model, k.name, k.values[0])}"
        doc = "\n".join(docstring(f"{sentence(k.doc)} Each value is a string every binding shares; compare with a member, such as "
                                  f"{first}.", "    "))
        blocks.append(f"class {pascal(k.name)}(StrEnum):\n{doc}\n\n{members}")
    kw = "\n".join(f"    {upper_snake(w)} = {s(w)}" for w, _ in model.keywords)
    blocks.append(f'class Keyword(StrEnum):\n    """The language statements\' keywords, written after \'@\': the one keyword list."""\n\n{kw}')
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
        found = tuple_literal([s(f) for f in c.found_by])
        facts.append(f"        DiagnosticCode.{upper_snake(c.name)}: CodeFacts({s(c.name)}, {s(c.layer)}, {found}, {reason}),")
    head = [f'"""{HEADER}', "", 'Source: spec/schema/diagnostics.json."""', "", "from collections.abc import Mapping",
            "from dataclasses import dataclass", "from enum import StrEnum", "from types import MappingProxyType",
            "from typing import Final", "", "from villanelle._api.kinds import UnreadableReason"]
    if imports:
        head.append(f"from villanelle._api.limits import {', '.join(sorted(imports))}")
    return "\n".join([
        *head, "", "",
        "class DiagnosticCode(StrEnum):",
        '    """villanelle\'s diagnostic codes, by name."""', "",
        *members, "", "",
        "MESSAGES: Final[Mapping[DiagnosticCode, str]] = MappingProxyType(", "    {", *messages, "    }", ")",
        '"""The base message of each code (for people, not part of the contract)."""', "", "",
        "@dataclass(frozen=True, slots=True)",
        "class CodeFacts:",
        '    """What the registry says of one code: its spec name, owning layer, who finds it, the reason it gives."""', "",
        "    name: str", "    layer: str", "    found_by: tuple[str, ...]", "    reason: UnreadableReason | None", "", "",
        "CODE_FACTS: Final[Mapping[DiagnosticCode, CodeFacts]] = MappingProxyType(", "    {", *facts, "    }", ")",
        '"""Each code\'s facts."""', "", "",
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
            body = pattern_body(str(c.value), _regex_char)
            if "\\p" in body or "\\P" in body:
                raise SchemaError(f"pattern {c.about!r}: Python's re has no \\p{{..}}: write the class out")
            # Python's $ also matches before a final newline; \Z is the text's end. In a raw string \" is a quote.
            regex = "^" + body.replace('"', '\\"') + "\\Z"
            parts = []  # implicitly joined raw strings of at most CHUNK characters, none ending on a backslash
            while regex:
                cut = min(CHUNK, len(regex))
                while regex[:cut].endswith("\\") and cut > 1:
                    cut -= 1
                parts.append(regex[:cut])
                regex = regex[cut:]
            out += [f"{name}: Final = re.compile({' '.join(f'r{chr(34)}{part}{chr(34)}' for part in parts)})"]
        out += docstring(f"{c.about}: {c.means}.", "") + [""]
    while out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def _regex_char(cp: int) -> str:
    return f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}"


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
        body += docstring(g.class_doc(), "    ")
        own = [(f, t) for f, t in g.fields if not (parent and any(pf == f for pf, _ in parent.fields))]
        if not g.fields:
            continue
        for f, t in own:
            body += ["", f"    {snake(f)}: {py_type(t, ctx)}"]
        params = ["self"]
        if g.message.get("given"):
            params.append("message: str")
        for f, t in g.fields:
            params.append(f"{snake(f)}: {py_type(t, ctx, True)}")
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
            conv = f"tuple({snake(f)})" if t.form == "list" else snake(f)
            body.append(f"        self.{snake(f)} = {conv}")
    tmpl = model.argument_type_message["py"]
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(tmpl):
        parts.append(tmpl[pos:m.start()])
        parts.append("{" + snake(m.group(1)) + "}")
        pos = m.end()
    parts.append(tmpl[pos:])
    body += ["", "", "def argument_type_message(member: str, parameter: str, got: str, /) -> str:",
             *docstring("The argument type error's message: the one helper every member that takes text calls.", "    "),
             f"    return {long_string(''.join(parts), f=True)}"]
    head = [f'"""{HEADER}', "", 'Source: spec/schema/api.json "error groups"."""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


def template(message: Dict[str, object], fields: List[Tuple[str, Type]]) -> str:
    text = str(message["template"])
    sep = str(message.get("separator", ", "))
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(text):
        parts.append(text[pos:m.start()].replace("{", "{{").replace("}", "}}"))
        ph = m.group(1)
        if ph.endswith(" message"):
            parts.append("{" + snake(ph[: -len(" message")]) + ".message}")
        elif dict(fields)[ph].item == Type("name", name="text"):  # the loader refuses a placeholder on a non-list
            parts.append("{" + s(sep).replace('"', "'") + ".join(" + snake(ph) + ")}")
        else:
            parts.append("{" + s(sep).replace('"', "'") + ".join(str(d) for d in " + snake(ph) + ")}")
        pos = m.end()
    parts.append(text[pos:].replace("{", "{{").replace("}", "}}"))
    return "f" + s("".join(parts))


def frozen_map(name: str, kind: str, entries: List[str], what: str) -> List[str]:
    """A read-only module constant; each entry ends in a comma, so ruff format keeps one entry a line."""
    return [f"{name}: Final[Mapping[{kind}]] = MappingProxyType({{{''.join(e + ', ' for e in entries).rstrip()}}})",
            f'"""{what}"""']


def contract_module(model: Model) -> str:
    """py/tests/api_contract.py: the generated half of the binding's public-name test. It lives beside the tests, not in
    the package, and names every type through its public module, so the tests import nothing private."""
    imports = Imports()
    imports.add("typing", "Final")
    imports.add("collections.abc", "Mapping")
    imports.add("types", "MappingProxyType")
    by_mod: Dict[str, List[str]] = {}
    for mod, name, _ in model.public("py"):
        by_mod.setdefault(mod, []).append(name)
    names = [f"{s(mod)}: frozenset({{{', '.join(s(n) for n in sorted(by_mod[mod]))}}})" for mod in sorted(by_mod)]
    matches = [f"{s(pascal(c.name))}: {tuple_literal([s(snake(a)) for a in c.match_args])}"
               for c in model.concepts if c.match_args and "py" in c.languages]
    unions = [f"{s(pascal(c.name))}: {tuple_literal([s(pascal(v)) for v in c.variants])}"
              for c in model.concepts if c.is_union and "py" in c.languages]
    body = ["", *frozen_map("PUBLIC_NAMES", "str, frozenset[str]", names,
                            "Every public name by module: each module's __all__ must equal its set (the name test)."),
            "", "", *frozen_map("MATCH_ARGS", "str, tuple[str, ...]", matches,
                                "Each class's __match_args__, in the same field order in every layer (spec 2.10)."),
            "", "", *frozen_map("UNIONS", "str, tuple[str, ...]", unions,
                                "Each public union's variant classes: the binding's union must hold exactly these.")]
    ctx = Ctx(model, "contract", imports, {}, public=True)
    body += contract_checks(model, ctx)
    head = [f'"""{HEADER}', "", "Source: spec/schema/api.json: what the binding's tests check it against (spec/codegen.md section 4).",
            "Every type is named through its public module; only the type checker's block at the end names the generated",
            'Protocols, to check the public classes against them."""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


def checked_by_protocol(model: Model, c: Concept) -> bool:
    """A concept whose public class the binding writes by hand against its generated Protocol (a handle, or a snapshot
    or record with methods). A port or interface is the generated Protocol itself, re-exported, so there is no second
    class to check; a shape's class is abstract (each concrete block, which extends it, is checked); a union is checked
    by ``UNIONS``."""
    return ("py" in c.languages and not c.is_union and c.nature in ("handle", "snapshot", "record")
            and not generated_public(model, c))


def contract_checks(model: Model, ctx: Ctx) -> List[str]:
    """Assignments mypy checks and nothing runs: each public module against its ``<Module>Functions`` Protocol (PEP
    544's modules as protocols), each constructed class against its ``<Class>Constructor``, and each hand-written public
    class against its concept's generated Protocol, structurally (so a class that forgets to subclass it is still
    checked). The list comes from the schema, so a new module, factory or concept is checked with no hand edit."""
    lines: List[str] = []

    def assign(var: str, annotation: str, value: str) -> None:
        lines.append(f"    {var}: {annotation} = {value}")

    seen: Set[str] = set()
    for f in model.functions:
        mod = model.function_module(f, "py")
        if mod is None:
            continue
        api_mod = ctx.imports.module(f"{model.package}._api.{f.layer}")
        if (f.factory or {}).get("py") == "constructor":
            of = f.factory["of"]  # type: ignore[index]
            assign(f"_{snake(of)}_constructor", f"{api_mod}.{pascal(of)}Constructor", ctx.ref(of))
            continue
        proto = functions_protocol(model, f)
        if proto not in seen:
            seen.add(proto)
            assign(f"_{snake(functions_suffix(model, f))}_functions", f"{api_mod}.{proto}", ctx.imports.module(mod))
    for c in model.concepts:
        if checked_by_protocol(model, c):
            api_mod = ctx.imports.module(f"{model.package}._api.{c.layer}")
            args = ""
            if c.type_parameters:
                args = f"[{', '.join(ctx.imports.add('typing', 'Any', False) for _ in c.type_parameters)}]"
            assign(f"_{snake(c.name)}", f"type[{api_mod}.{pascal(c.name)}{args}]", ctx.ref(c.name))
    if not lines:
        return []
    return ["", "", "if TYPE_CHECKING:", *lines]


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
        elif sh.by_kind:
            # A discriminated union: one TypedDict per kind with that kind's own fields required (Other: the kinds with
            # none of their own).
            alts = []
            for kind, extra in [*sh.by_kind.items(), ("other", {})]:
                kinds = sh.other_kinds if kind == "other" else [kind]
                literal = Type("union", args=tuple(Type("literal", name=k) for k in kinds)) if len(kinds) > 1 else Type("literal", name=kinds[0])
                fields = {k: (literal if k == "kind" else t) for k, t in sh.fields.items()}
                alts.append(f"{name}{pascal(kind)}")
                body += td(alts[-1], {**fields, **extra}, list(sh.optional))
            body += ["", "", f"{name}: TypeAlias = (", *(f"    {'| ' if i else ''}{a}" for i, a in enumerate(alts)), ")"]
        else:
            body += td(name, dict(sh.fields), list(sh.optional))
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
    groups = [f"    {s(g.builtin('py') or pascal(g.name))}: {s(g.name)}," for g in model.groups]
    body += ["", "", "ERROR_GROUP_OF_CLASS: Final[Mapping[str, str]] = {", *groups, "}",
             '"""Each error group\'s class (or the language\'s own, for a builtin group) to its spec name (spec 2.8)."""']
    head = [f'"""{HEADER}', "", 'Source: spec/schema/protocol.json (spec/conformance.md 4): the adapter\'s message types."""', ""]
    return "\n".join(head + imports.render() + body) + "\n"


RECORD_MODULE = f'''"""{HEADER}

The base of every generated record: its fields' docs live in a __slots__ dict, so the dataclass is slotted by hand, not
with slots=True, and copy and pickle need the state methods slots=True would have added for a frozen class."""

from dataclasses import Field, fields
from typing import Any, ClassVar, Self


class SlottedRecord:
    """A frozen dataclass slotted by hand: copied and pickled field by field."""

    __slots__ = ()
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    def __reduce__(self) -> tuple[type[Self], tuple[object, ...]]:
        return type(self), tuple(getattr(self, f.name) for f in fields(self))
'''


def render(model: Model) -> Dict[str, str]:
    files = {
        "__init__.py": f'"""{HEADER}"""\n',
        "kinds.py": kinds_module(model),
        "codes.py": codes_module(model),
        "limits.py": limits_module(model),
        "errors.py": errors_module(model),
        "docs.py": docs_module(model),
        "record.py": RECORD_MODULE,
        # The folder is generated and never committed: ignore it from inside, as tools/gen.sh's own output is ignored.
        ".gitignore": f"# {HEADER}\n*\n",
    }
    for layer in model.layers:
        files[f"{layer.name}.py"] = layer_module(model, layer.name)
    return files


def render_shapes(model: Model) -> Dict[str, str]:
    return {"shapes.py": shapes_module(model)}


def render_contract(model: Model) -> Dict[str, str]:
    return {"api_contract.py": contract_module(model)}

