"""The C++ emitter (spec/codegen.md section 4; .claude/design/cpp/design.md 1.1 to 1.4): renders the loader's model as
the header-only C++ binding's public headers.

    cpp/include/knobly/knobly.hpp   the shared and io layers (namespace knobly); includes the four below
    cpp/include/knobly/kinds.hpp        every kind list as an enum class with to_string
    cpp/include/knobly/codes.hpp        diagnostic_code, to_string, message, code_facts, facts_of, describe
    cpp/include/knobly/limits.hpp       the limits and the reserved names, each in its layer's namespace
    cpp/include/knobly/errors.hpp       the exception class tree (spec 2.8), included by knobly.hpp after the
                                            records its classes hold
    cpp/include/knobly/<layer>.hpp      one header per layer with its own namespace (syntax, written, rendered);
                                            each pattern's matcher over code points sits in its layer's header
                                            (knobly::is_program_code, written::is_variable_name)
    cpp/include/knobly/<module>.hpp     one header per adapter module (files, extensions)
    cpp/include/knobly/implementation.hpp   compiled mode: every layer's definitions, compiled once
    cpp/include/knobly/format.hpp       opt-in: a std::formatter and an operator<< for every type with a to_string
                                            (each people form, each kind list, diagnostic_code), written whole
    cpp/conformance/shapes.hpp              the adapter protocol's version, spellings and error_group_of
    cpp/tests/generated/api_contract_<header>.cpp  odr-uses every hand-defined function and member of one header
    cpp/tests/generated/layers_<header>.cpp   the layer-direction check of one public header, from "may import"
    cpp/tests/generated/layers_<header>_definitions.cpp   the layer-boundary check of one header's definitions: they
                                              compile with every other header's definitions left out (spec 7.0)

Idiom lives here and only here (design.md 1.3; frozen-m1.md section 4): snake_case names, every type spelled fully
qualified from ``::knobly``, ``std::string_view`` in and ``std::string`` out, ``knobly::sequence`` for lists,
``knobly::ordered_map`` for maps, ``std::optional`` for absent, ``std::variant`` for any other union, a view class
(one ``detail::view``) for each handle and snapshot, an immutable class for each record, an abstract class held by
``std::shared_ptr`` for each port, a C++20 concept for each interface, an aggregate for each options record, Doxygen
``///`` comments from the schema's docs. What the generator writes whole is inline here; every free function and every
handle's or snapshot's member is declared with ``KNOBLY_API`` and defined by the hand code in ``detail/``.

Layout does not live here: the output goes through the pinned clang-format (CLANG_FORMAT) with cpp/.clang-format.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from automaton import Nfa, complement, determinize, minimize, normal  # tools/, on the path of every caller

from .loader import (
    CODE_LAYERS,
    HEADER,
    PLACEHOLDER,
    Concept,
    Constant,
    ErrorGroup,
    Formatter,
    Function,
    Language,
    Member,
    Model,
    Param,
    SchemaError,
    Type,
    pascal,
    sentence,
    snake,
)

# The pinned clang-format, its one home: tools/parser/gen.py and the hand-code lint use it through LANGUAGE.formatter
# or this tuple, never a version of their own.
CLANG_FORMAT = ("uv", "tool", "run", "--quiet", "--from", "clang-format==21.1.8", "clang-format")


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    """A C++ name is a type, but a free function, which is a value."""
    return "type" if c is None or c.nature != "free function" else "value"


def _member_spelling(cls: str, member: str) -> str:
    """A member may not share its class's name, own or inherited (design.md 1.2, finding F2): C++ reserves the name
    for the constructor, and the injected class name hides an inherited member of that name. Such a member takes a
    trailing underscore: written::index::index_(), written::list::list_()."""
    return snake(member) + "_" if snake(member) == snake(cls) else snake(member)


def _call_params(params: List[Tuple[str, str, bool]]) -> str:
    """A call's parameters in the docs tables: an optional one (an overload without it) in brackets, the options as the
    options aggregate's designated initializers."""
    plain = [f"[{n}]" if optional else n for n, passed, optional in params if passed != "option"]
    options = [f".{n}" for n, passed, _ in params if passed == "option"]
    return ", ".join(plain + ([f"{{{', '.join(options)}}}"] if options else []))


# C++'s own facts (the schema names no language; spec/codegen.md section 10).
LANGUAGE = Language(
    key="cpp",
    name="C++",
    sep="::",
    function_case=snake,
    code_case=snake,
    public_kind=_public_kind,
    enum_form="`enum class`",
    generic=lambda name, params: f"{name}<{', '.join(params)}>",
    construct=lambda name: f"{name}(...)",
    extends_word="derives from",
    cause_field="std::nested_exception (std::rethrow_if_nested)",
    error_roots={
        "knobly error": {"base": "std::runtime_error"},
        "detached error": {"base": "std::logic_error"},
        "argument type error": {"base": "std::logic_error"},
        "misuse error": {"base": "std::invalid_argument"},
        "index out of range": {"base": "std::out_of_range"},
    },
    argument_type_message="{member}(): argument '{parameter}' must be a live object, not {got}",
    modules={"files": "files", "include": "extensions"},  # no fetch adapter (spec 4.3: MAY)
    omit=lambda name, nature: name == "walk control",
    omitted_as=lambda name, nature: "the walk's descend predicate" if name == "walk control" else "none",
    trait_names=lambda model: [
        (model.package, "sequence", "the list type form"),
        (model.package, "ordered_map", "the map type form"),
        (model.package, "walk_view", "the range a block's walk returns"),
    ],
    formatter=Formatter((".hpp", ".cpp"), ((*CLANG_FORMAT, "-i", "--style=file:cpp/.clang-format"),)),
    type_case=snake,
    constant_case=snake,
    pattern_form=lambda constant: f"is_{snake(constant)}",
    member_spelling=_member_spelling,
    kinds_in_package=True,  # one kinds.hpp, which the generated parser includes (::knobly::token_kind)
    trait_forms={
        "people form": "`to_string(x)`, a free function (`<knobly/format.hpp>` adds `std::format` and `<<`)",
        "iterate": "`begin()` and `end()`: a range",
        "count": "`size()`",
        "index": "`at(i)`, `index_out_of_range` out of range",
        "walk": "`walk(descend)`, a `walk_view` range; `descend(item)` says whether to enter its block",
        "collect": "`collect(read)`, returning `std::optional`",
        "io": "a plain call",
        "passed: keyword": "positional",
        "passed: option": "an options aggregate (`load(path, {.overrides = ...})`)",
        "brand": "a class of its own holding the text (`config_text`)",
        "template": "a class checked when made (a `program_code` literal is checked at compile time)",
        "list": "`knobly::sequence<T>`, an immutable shared list",
        "map": "`knobly::ordered_map<K, V>` (`writable`: held by `std::shared_ptr`, shared with the caller)",
    },
    property_form=lambda name: f"{name}()",  # every property is read through an accessor
    call_params=_call_params,
)

KEY = LANGUAGE.key
API = "KNOBLY_API"
VIEW = "::knobly::detail::view"
ACCESS = "::knobly::detail::access"

# Every identifier the generator writes from a spec name is checked against these: a schema name that spells one
# cannot be a C++ name (a contextual keyword such as `override` or `final` can).
CPP_KEYWORDS = frozenset("""
alignas alignof and and_eq asm auto bitand bitor bool break case catch char char8_t char16_t char32_t class compl
concept const consteval constexpr constinit const_cast continue co_await co_return co_yield decltype default delete do
double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace
new noexcept not not_eq nullptr operator or or_eq private protected public register reinterpret_cast requires return
short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef
typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq
""".split())


def ident(name: str) -> str:
    if name in CPP_KEYWORDS:
        raise SchemaError(f"C++ emitter: {name!r} is a C++ keyword and cannot name a declaration")
    return name


# --- text helpers ----------------------------------------------------------------------------------------------------


def head(source: str) -> List[str]:
    return [f"// {HEADER}", f"// Source: {source}."]


def guard(name: str) -> str:
    """The include guard of a generated header: KNOBLY_<STEM>_HPP (layers_<header>.cpp predefines them)."""
    return f"KNOBLY_{name.upper().replace('.', '_')}"


def lit(text: str) -> str:
    """A C++ string literal holding ``text`` (UTF-8 source; quotes, backslashes and controls escaped)."""
    out = []
    for ch in text:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif ord(ch) < 0x20:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def doc(text: str, tags: Sequence[str] = ()) -> List[str]:
    """A Doxygen comment: the text as a sentence, wrapped, then each tag (``@param``, ``@throws``) on its own lines."""
    body = sentence(text)
    lines = textwrap.wrap(body, 112) if body else []
    for tag in tags:
        if tag:
            lines += textwrap.wrap(tag, 112, subsequent_indent="    ")
    return [f"/// {line}" for line in lines]


def error_class(model: Model, group: str) -> str:
    return ident(snake(model.group[group].name))


def member_doc(model: Model, text: str, params: Sequence[Param], raised: Sequence[Tuple[str, str]], order: str = "") -> List[str]:
    """A member's or free function's comment: its doc and order, each documented parameter, each error it raises."""
    if order:
        text = f"{sentence(text)} Order: {order}.".strip()
    tags = [f"@param {'options' if p.passed == 'option' else ident(snake(p.name))} {p.doc}" for p in params if p.doc]
    tags += [f"@throws knobly::{error_class(model, g)} {why}" for g, why in raised]
    return doc(text, tags)


# --- names and types -------------------------------------------------------------------------------------------------


class Ctx:
    """The type parameters in scope (spec name to C++ template parameter)."""

    def __init__(self, model: Model, type_params: Optional[Dict[str, str]] = None) -> None:
        self.model = model
        self.type_params = dict(type_params or {})

    def with_params(self, names: Sequence[str]) -> "Ctx":
        return Ctx(self.model, {**self.type_params, **{n: template_param(n) for n in names}})


def template_param(name: str) -> str:
    """A template parameter is PascalCase (design.md 1.2), so it never meets a snake_case name."""
    return pascal(name)


def namespace(model: Model, c: Concept) -> str:
    """The concept's namespace, fully qualified from the global namespace (``::knobly::written``)."""
    return "::" + model.concept_module(c, KEY)


def qual(model: Model, name: str) -> str:
    """A schema name (concept, kind list, error group, diagnostic code) as a fully qualified C++ type name."""
    if name in model.kind:
        return f"::{model.kind_module(model.kind[name], KEY)}::{ident(snake(name))}"
    if name == "diagnostic code":
        return f"::{model.package}::diagnostic_code"
    if name in model.group:
        return f"::{model.package}::{error_class(model, name)}"
    c = model.concept[name]
    if c.is_ == "native":
        return LANGUAGE.native[name]
    return f"{namespace(model, c)}::{ident(snake(name))}"


def concept_of(model: Model, t: Type) -> Optional[Concept]:
    if t.form == "name" and t.name in model.concept:
        return model.concept[t.name]
    return None


def narrowed(model: Model, t: Type) -> Optional[str]:
    """The named union every arm of an anonymous union is a variant of (its view class narrows them), else None."""
    roots = set()
    for a in t.args:
        c = concept_of(model, a)
        if c is None or not c.variant_of:
            return None
        roots.add(c.variant_of)
    return roots.pop() if len(roots) == 1 else None


def value_type(t: Type, ctx: Ctx) -> str:
    """The C++ type of a value of schema type ``t``: a result, a stored field, an element."""
    m = ctx.model
    if t.form == "name":
        builtin = {"text": "std::string", "integer": "std::int64_t", "number": "double", "boolean": "bool", "nothing": "void"}
        if t.name in builtin:
            return builtin[t.name]
        if t.name == "absent":
            raise SchemaError("C++ emitter: 'absent' outside a union")
        if t.name in ctx.type_params:
            return ctx.type_params[t.name]
        c = m.concept.get(t.name)
        base = qual(m, t.name)
        if c is not None and c.nature == "port":
            return f"std::shared_ptr<{base}>"
        if c is not None and c.nature == "interface":
            raise SchemaError(f"C++ emitter: the interface {t.name!r} is a C++ concept: only a parameter may name it")
        if t.args:
            return f"{base}<{', '.join(value_type(a, ctx) for a in t.args)}>"
        return base
    if t.form == "list":
        return f"::knobly::sequence<{value_type(t.item, ctx)}>"
    if t.form == "union":
        if t.may_be_absent:
            return f"std::optional<{value_type(t.without_absent(), ctx)}>"
        root = narrowed(m, t)
        if root is not None:
            return qual(m, root)
        return f"std::variant<{', '.join(value_type(a, ctx) for a in t.args)}>"
    if t.form == "map":
        key, val = t.args
        mapped = f"::knobly::ordered_map<{value_type(key, ctx)}, {value_type(val, ctx)}>"
        return f"std::shared_ptr<{mapped}>" if t.writable else mapped
    if t.form == "function":
        *params, result = t.args
        return f"std::function<{value_type(result, ctx)}({', '.join(param_type(p, ctx) for p in params)})>"
    raise AssertionError(t)


def by_reference(t: Type, ctx: Ctx) -> bool:
    """A parameter of this type is passed as ``const T&``: a record, handle, snapshot or a type parameter."""
    if t.form != "name":
        return False
    if t.name in ctx.type_params:
        return True
    c = concept_of(ctx.model, t)
    return c is not None and c.nature in ("record", "handle", "snapshot", "shape")


def param_type(t: Type, ctx: Ctx, kept: bool = False) -> str:
    """The C++ type of a parameter: text as ``std::string_view``, a class by ``const&``, everything else by value.
    A map a free function takes is ``kept``: shared, never copied, since what the function makes may read it later
    (a memory source reads the map it is given at each call, design.md 3.1)."""
    if t.form == "name" and t.name == "text":
        return "std::string_view"
    if kept and t.form == "map" and not t.writable:
        return f"std::shared_ptr<const {value_type(t, ctx)}>"
    if by_reference(t, ctx):
        return f"const {value_type(t, ctx)}&"
    return value_type(t, ctx)


def nothrow_copy(model: Model, t: Type) -> bool:
    """Copying a value of this type cannot throw (its accessor is noexcept): scalars, kinds, codes, records of them."""
    if t.form == "name":
        if t.name in ("integer", "number", "boolean") or t.name in model.kind or t.name == "diagnostic code":
            return True
        c = model.concept.get(t.name)
        if c is not None and c.nature == "record" and not c.is_union and not c.variant_of:
            return all(nothrow_copy(model, mem.type) for mem in fields(model, c))
        return False
    if t.form == "union" and t.may_be_absent:
        return nothrow_copy(model, t.without_absent())
    return False


# --- concept classification ------------------------------------------------------------------------------------------


def is_view_class(c: Concept) -> bool:
    """A handle or a snapshot, or a record that is a union or one of its variants (a sequence of a union returns the
    union by value, so its variants share one view class instead of slicing: design.md 1.3 lists `change`)."""
    if c.nature in ("handle", "snapshot"):
        return True
    return c.nature == "record" and (c.is_union or bool(c.variant_of))


def extends_shape(model: Model, c: Concept) -> bool:
    return c.extends is not None and model.concept[c.extends.name].nature == "shape"


def extended(model: Model) -> Set[str]:
    """The concepts another derives from: union roots and every concept some other concept extends."""
    out = {c.variant_of for c in model.concepts if c.variant_of}
    out |= {c.extends.name for c in model.concepts if c.extends is not None}
    return {n for n in out if n}


def fields(model: Model, c: Concept) -> List[Member]:
    """A record's stored properties, in its constructor's order: the match args first when the schema gives them,
    then the rest in schema order, inherited first; a fixed kind is no field (Python's dataclass field order)."""
    props = [m for m in model.all_members(c) if m.member == "property" and not (m.name == "kind" and c.kind is not None)]
    if c.match_args:
        by = {m.name: m for m in props}
        first = [by[a] for a in c.match_args if a in by]
        return first + [m for m in props if m.name not in c.match_args]
    return props


def member_name(c: Concept, m: Member) -> str:
    return ident(LANGUAGE.member_spelling(c.name, m.name))  # type: ignore[misc]


# --- hand-defined declarations (the contract's list) ----------------------------------------------------------------


@dataclass
class Hand:
    """One hand-defined declaration, as the contract odr-uses it: a lambda converted to a volatile function pointer."""

    result: str
    params: List[str]
    call: str  # the body's expression, over a0, a1, ... (and `self` for a member)
    self_type: Optional[str] = None

    def line(self, n: int) -> str:
        ps = ([f"const {self.self_type}&"] if self.self_type else []) + self.params
        names = (["self"] if self.self_type else []) + [f"a{i}" for i in range(len(self.params))]
        decl = ", ".join(f"{p} {nm}" for p, nm in zip(ps, names))
        return (f"{self.result} (*volatile use{n})({', '.join(ps)}) = []({decl}) -> {self.result} {{ return {self.call}; }};"
                f" static_cast<void>(use{n});")


def args(n: int) -> str:
    return ", ".join(f"a{i}" for i in range(n))


@dataclass
class Out:
    """What rendering one header collects beside its text: its hand-defined declarations."""

    hand: List[Hand] = field(default_factory=list)


# --- members ---------------------------------------------------------------------------------------------------------


def overloads(model: Model, params: List[Param], options: Optional[str], ctx: Ctx,
              kept: bool = False) -> List[List[Tuple[str, str]]]:
    """Each overload's (type, name) parameter list: a trailing optional parameter is an overload without it, and the
    option parameters are one options record, an overload without it when every option is optional."""
    plain = [p for p in params if p.passed != "option"]
    full = [(param_type(p.type.without_absent() if p.optional else p.type, ctx, kept), ident(snake(p.name))) for p in plain]
    cut = len(plain)
    while cut > 0 and plain[cut - 1].optional:
        cut -= 1
    lists = [full[:i] for i in range(cut, len(plain) + 1)]
    if options is None:
        return lists
    if KEY not in model.concept[options].languages:
        raise SchemaError(f"C++ emitter: options record {options!r} left out")
    record = (qual(model, options), "options")
    required = any(p.passed == "option" and not p.optional for p in params)
    last = lists[-1]
    return [last + [record]] if required else [*lists, last + [record]]


def signature(ps: List[Tuple[str, str]]) -> str:
    return ", ".join(f"{t} {n}" for t, n in ps)


def hand_member(model: Model, c: Concept, m: Member, ctx: Ctx, out: Out, cls: str, name: Optional[str] = None,
                template: bool = False) -> List[str]:
    """A handle's, snapshot's or view record's member: declared here, defined by the hand code (``KNOBLY_API``),
    one declaration per overload. A member of a class template is a template itself, so it takes no KNOBLY_API
    and the contract cannot take its address."""
    name = name or member_name(c, m)
    lines = member_doc(model, m.doc, m.params, model.raised(m.errors, m.when), m.order)
    api = "" if template else f"{API} "

    def use(result: str, params: List[str], call: str) -> None:
        if not template:
            out.hand.append(Hand(result, params, call, cls))

    if m.trait == "iterate":
        it = f"{value_type(m.type, ctx)}::iterator"
        for end in ("begin", "end"):
            lines.append(f"{api}{it} {end}() const;")
            use(it, [], f"self.{end}()")
        return lines
    if m.trait == "count":
        lines += [f"{api}std::size_t size() const;", f"{api}bool empty() const;"]
        use("std::size_t", [], "self.size()")
        use("bool", [], "self.empty()")
        return lines
    if m.trait == "index":
        result = value_type(m.type, ctx)
        lines.append(f"{api}{result} at(std::size_t index) const;")
        use(result, ["std::size_t"], "self.at(a0)")
        return lines
    if m.trait == "walk":
        item = value_type(m.type.item, ctx)
        view = f"::knobly::walk_view<{item}>"
        lines += [f"{api}{view} walk() const;", f"{api}{view} walk(std::function<bool(const {item}&)> descend) const;"]
        use(view, [], "self.walk()")
        use(view, [f"std::function<bool(const {item}&)>"], "self.walk(a0)")
        return lines
    if m.trait == "collect":
        # collect(read): std::optional of read's result (bool for a void read); a template, so its definition is in
        # a header (design.md 1.3).
        return lines + ["template <class F>", "    requires std::invocable<F&>", "auto collect(F&& read) const;"]
    if m.trait == "people form":
        raise AssertionError("a people form is a free function")
    result = value_type(m.type, ctx)
    noexcept = " noexcept" if m.name == "kind" and m.member == "property" else ""
    constrained = [p for p in m.params if (pc := concept_of(model, p.type)) is not None and pc.nature == "interface"]
    if constrained:
        # A parameter typed by an interface is a constrained template parameter (design.md 1.3: a C++20 concept).
        tps = [f"{qual(model, p.type.name)} {template_param(p.name)}" for p in constrained]
        sub = Ctx(model, {**ctx.type_params, **{p.type.name: template_param(p.name) for p in constrained}})
        for ps in overloads(model, m.params, m.options, sub):
            lines += [f"template <{', '.join(tps)}>", f"{result} {name}({signature(ps)}) const;"]
        return lines
    for ps in overloads(model, m.params, m.options, ctx):
        lines.append(f"{api}{result} {name}({signature(ps)}) const{noexcept};")
        use(result, [t for t, _ in ps], f"self.{name}({args(len(ps))})")
    return lines


# --- concepts --------------------------------------------------------------------------------------------------------


def base_types(model: Model, c: Concept, ctx: Ctx) -> List[str]:
    bases = []
    if c.variant_of:
        bases.append(qual(model, c.variant_of))
    if c.extends is not None:
        if extends_shape(model, c):  # the shape is the support template (support/block.hpp)
            bases.append(f"::knobly::{ident(snake(c.extends.name))}<{', '.join(value_type(a, ctx) for a in c.extends.args)}>")
        else:
            bases.append(value_type(c.extends, ctx))
    return bases


def class_key(model: Model, c: Concept, ctx: Ctx) -> List[str]:
    """The template line (if generic) and the class key with its bases."""
    tpl = [f"template <{', '.join('class ' + template_param(p) for p in c.type_parameters)}>"] if c.type_parameters else []
    bases = base_types(model, c, ctx)
    return [*tpl, f"class {ident(snake(c.name))}" + (f" : {', '.join('public ' + b for b in bases)}" if bases else "") + " {"]


def view_class(model: Model, c: Concept, out: Out) -> List[str]:
    """A handle, snapshot or view record: one view, its members declared for the hand code; a union root adds kind(),
    as<V>() and visit(f), and each variant derives from it (design.md 2.3). Its view constructor is protected when
    another class derives from it, else private; ``detail::access`` makes and reads them."""
    ctx = Ctx(model).with_params(c.type_parameters)
    name = ident(snake(c.name))
    cls = qual(model, c.name)
    template = bool(c.type_parameters)
    if template:
        cls = f"{cls}<{', '.join(template_param(p) for p in c.type_parameters)}>"
    body: List[str] = ["public:"]
    for f in model.functions:
        if (f.factory or {}).get("of") == c.name and (f.factory or {}).get(KEY) == "constructor":
            for ps in overloads(model, f.params, f.options, Ctx(model)):
                body += member_doc(model, f.doc, f.params, model.raised(f.errors, f.when))
                body.append(f"{API} {'explicit ' if len(ps) == 1 else ''}{name}({signature(ps)});")
                out.hand.append(Hand(cls, [t for t, _ in ps], f"{cls}({args(len(ps))})"))
    for m in c.members:
        if not (c.variant_of and m.name == "kind"):
            body += hand_member(model, c, m, ctx, out, cls, template=template)
    if c.variant_of:
        # An inherited member whose spelling differs here (its name is this class's): declared again, respelled.
        root = model.concept[c.variant_of]
        for m in root.members:
            if m.name != "kind" and m.trait is None and member_name(c, m) != member_name(root, m):
                body += hand_member(model, c, m, ctx, out, cls, name=member_name(c, m))
    if c.is_union:
        body += doc(f"The variant this {c.name} is, when it is a V; empty otherwise.")
        body += ["template <class V>", f"    requires std::derived_from<V, {cls}>", "std::optional<V> as() const;"]
        body += doc(f"Calls f with this {c.name} as its exact variant class, and returns what f returns.")
        body += ["template <class F>", "decltype(auto) visit(F&& f) const;"]
    if not c.variant_of and c.extends is None:
        if c.equal_by is not None:
            by = member_name(c, next(m for m in c.members if m.name == c.equal_by))
            body += doc(f"Whether two {c.name}s are equal: exactly when their {c.equal_by}s are, whatever else differs "
                        "(std::hash agrees).")
            body.append(f"friend bool operator==(const {cls}& a, const {cls}& b) {{ return a.{by}() == b.{by}(); }}")
        else:
            body += doc(f"Whether two views show one {c.name} (std::hash agrees).")
            body.append(f"friend bool operator==(const {cls}& a, const {cls}& b) noexcept {{ return a.view_ == b.view_; }}")
    if c.variant_of:
        ctor = f"explicit {name}({VIEW} view) noexcept : {qual(model, c.variant_of)}(std::move(view)) {{}}"
    elif extends_shape(model, c):
        ctor = f"explicit {name}({VIEW} view) noexcept {{ view_ = std::move(view); }}"
    elif c.extends is not None:
        ctor = f"explicit {name}({VIEW} view) noexcept : {value_type(c.extends, ctx)}(std::move(view)) {{}}"
    else:
        ctor = f"explicit {name}({VIEW} view) noexcept : view_(std::move(view)) {{}}"
    protected = c.name in extended(model)
    body += ["protected:" if protected else "private:", ctor]
    if protected:
        body.append("private:")
    if not c.variant_of and c.extends is None:
        body.append(f"{VIEW} view_;")
    body.append(f"friend struct {ACCESS};")
    return [*doc(c.doc), *class_key(model, c, ctx), *body, "};"]


def literal_split(model: Model, c: Concept, flds: List[Member]) -> Optional[int]:
    """The index of the record field whose union has an arm checked at compile time (a code with a pattern, made from a
    literal by a consteval constructor), else None. Such a field is taken by one constructor per arm, never as one
    std::variant: a literal reaches a consteval constructor only at the call itself, and std::variant's converting
    constructor forwards it to a runtime construction, which no compiler without C++23's consteval propagation (P2564,
    absent from gcc 13) accepts. A record with two such fields is refused rather than multiplied out."""
    def literal(t: Type) -> bool:
        a = model.concept.get(t.name) if t.form == "name" else None
        return a is not None and a.nature == "named type" and a.pattern is not None and not a.brand
    found = [i for i, m in enumerate(flds)
             if m.type.form == "union" and not m.type.may_be_absent and any(literal(a) for a in m.type.args)]
    if len(found) > 1:
        raise SchemaError(f"C++ emitter: record {c.name!r} has more than one union field with a literal-checked arm")
    return found[0] if found else None


def record_class(model: Model, c: Concept, out: Out) -> List[str]:
    """A plain record: an immutable class written whole (frozen-m1.md 4.3): one constructor taking its fields, a const
    accessor per property (noexcept when its copy cannot throw), member-by-member equality. A field holding its own
    record (``address.parent``) is stored behind a shared pointer."""
    ctx = Ctx(model)
    name = ident(snake(c.name))
    cls = qual(model, c.name)
    base = model.concept[c.extends.name] if c.extends is not None else None
    inherited = [m.name for m in fields(model, base)] if base is not None else []
    flds = fields(model, c)
    if [m.name for m in flds[: len(inherited)]] != inherited:
        raise SchemaError(f"C++ emitter: record {c.name!r}: its match args reorder the fields it inherits")

    def indirect(m: Member) -> bool:
        t = m.type
        return t.form == "union" and t.may_be_absent and t.without_absent() == Type("name", name=c.name)

    def stored(m: Member) -> str:
        return f"std::shared_ptr<const {cls}>" if indirect(m) else value_type(m.type, ctx)

    params = [(value_type(m.type, ctx), ident(snake(m.name))) for m in flds]
    inits = [f"{qual(model, base.name)}({', '.join(n for (_, n), m in zip(params, flds) if m.name in inherited)})"] if base else []
    for (_, n), m in zip(params, flds):
        if m.name in inherited:
            continue
        if indirect(m):
            inits.append(f"{n}_({n} ? std::make_shared<const {cls}>(*std::move({n})) : nullptr)")
        else:
            inits.append(f"{n}_({n})" if nothrow_copy(model, m.type) else f"{n}_(std::move({n}))")
    explicit = "explicit " if len(params) == 1 else ""
    init = f"{' : ' + ', '.join(inits) if inits else ''} {{}}"
    split = literal_split(model, c, flds)
    if split is None:
        ctors = [f"{explicit}{name}({signature(params)}){init}"]
    else:  # one constructor per arm of the field, so a literal code meets its consteval constructor at the call
        ctors = [f"{explicit}{name}({signature([(value_type(a, ctx), n) if i == split else (t, n) for i, (t, n) in enumerate(params)])}){init}"
                 for a in flds[split].type.args]
    body = ["public:", *ctors]
    for m in c.members:
        if m.trait == "people form":
            continue
        if m.member != "property":
            raise SchemaError(f"C++ emitter: record {c.name!r} has a method {m.name!r} (a record holds only properties)")
        result = value_type(m.type, ctx)
        body += doc(m.doc)
        mn = member_name(c, m)
        if m.name == "kind" and c.kind is not None:
            body.append(f"{result} {mn}() const noexcept {{ return {result}::{ident(snake(c.kind))}; }}")
        elif indirect(m):
            body.append(f"{result} {mn}() const {{ return {snake(m.name)}_ ? {result}(*{snake(m.name)}_) : std::nullopt; }}")
        else:
            body.append(f"{result} {mn}() const{' noexcept' if nothrow_copy(model, m.type) else ''} {{ return {snake(m.name)}_; }}")
    if any(indirect(m) for m in flds):
        compare = " && ".join(f"a.{member_name(c, m)}() == b.{member_name(c, m)}()" for m in flds)
        body.append(f"friend bool operator==(const {cls}& a, const {cls}& b) {{ return {compare}; }}")
    else:
        body.append(f"friend bool operator==(const {cls}& a, const {cls}& b) = default;")
    own = [m for m in flds if m.name not in inherited]
    if own:
        body += ["private:", *(f"{stored(m)} {snake(m.name)}_;" for m in own)]
    return [*doc(c.doc), *class_key(model, c, ctx), *body, "};", *people_form(model, c, out)]


def people_form(model: Model, c: Concept, out: Out) -> List[str]:
    """The people form trait: a free to_string found by argument-dependent lookup, defined by the hand code."""
    m = next((m for m in c.members if m.trait == "people form"), None)
    if m is None:
        return []
    cls = qual(model, c.name)
    out.hand.append(Hand("std::string", [f"const {cls}&"], "to_string(a0)"))
    return [*doc(m.doc), f"{API} std::string to_string(const {cls}& value);"]


def port_class(model: Model, c: Concept) -> List[str]:
    """A port: an abstract class the program implements, held as std::shared_ptr (design.md 1.3)."""
    ctx = Ctx(model)
    name = ident(snake(c.name))
    body = ["public:", f"virtual ~{name}() = default;"]
    for m in c.members:
        body += member_doc(model, m.doc, m.params, model.raised(m.errors, m.when), m.order)
        ps = ", ".join(f"{param_type(p.type, ctx)} {ident(snake(p.name))}" for p in m.params)
        body.append(f"virtual {value_type(m.type, ctx)} {member_name(c, m)}({ps}) const = 0;")
    return [*doc(c.doc), f"class {name} {{", *body, "};"]


def options_struct(model: Model, c: Concept) -> List[str]:
    """An options record: an aggregate, so a call names what it sets (``{.source = ...}``); an optional field starts
    empty."""
    ctx = Ctx(model)
    body: List[str] = []
    for m in c.members:
        body += doc(m.doc)
        t = m.type.without_absent() if m.optional else m.type
        vt = value_type(t, ctx)
        has_empty = t.form in ("list", "map") or vt.startswith(("std::function<", "std::shared_ptr<", "std::optional<")) or (
            concept_of(model, t) is not None and model.concept[t.name].nature == "callback")
        if m.optional and not has_empty:
            vt = f"std::optional<{vt}>"
        body.append(f"{vt} {member_name(c, m)}{' = {}' if m.optional else ''};")
    return [*doc(c.doc), f"struct {ident(snake(c.name))} {{", *body, "};"]


def interface_concept(model: Model, c: Concept) -> List[str]:
    """An interface: a C++20 concept over its members (design.md 1.3)."""
    ctx = Ctx(model)
    params: List[str] = ["const T& value"]
    reqs: List[str] = []
    for m in c.members:
        names = []
        for p in m.params:
            pn = ident(snake(p.name))
            params.append(f"{param_type(p.type, ctx)} {pn}")
            names.append(pn)
        reqs.append(f"{{ value.{member_name(c, m)}({', '.join(names)}) }} -> std::same_as<{value_type(m.type, ctx)}>;")
    return [*doc(c.doc), "template <class T>", f"concept {ident(snake(c.name))} = requires({', '.join(params)}) {{",
            *reqs, "};"]


def named_type(model: Model, c: Concept, out: Out) -> List[str]:
    """A named text type: a brand made only by the free functions that return it, read through ``view() const&``
    (the rvalue overload deleted, so it cannot dangle); or a code checked against its pattern, at compile time for a
    literal (design.md 1.3)."""
    name = ident(snake(c.name))
    cls = qual(model, c.name)
    if c.is_ == "native":
        return []
    if c.brand:
        makers = [f for f in model.functions if f.returns.form == "name" and f.returns.name == c.name]
        friends = [f"friend {cls} {ident(snake(f.name))}({', '.join(param_type(p.type, Ctx(model)) for p in f.params)});"
                   for f in makers]
        return [*doc(c.doc), f"class {name} {{", "public:",
                *doc("The text, valid while this value lives."),
                "std::string_view view() const& noexcept { return raw_; }",
                "std::string_view view() const&& = delete;",
                f"friend bool operator==(const {cls}&, const {cls}&) = default;",
                "private:", f"explicit {name}(std::string raw) : raw_(std::move(raw)) {{}}", "std::string raw_;",
                *friends, "};"]
    if c.pattern is not None:
        match = LANGUAGE.pattern_form(c.pattern)  # type: ignore[misc]
        refused = f"{name}_literal_does_not_match_its_pattern"
        out.hand.append(Hand(cls, ["std::string_view"], f"{cls}(a0)"))
        return [
            "namespace detail {", "// Never defined: called in a constant expression, it stops the compile.",
            f"void {refused}();", "}  // namespace detail", "",
            *doc(c.doc), f"class {name} {{", "public:",
            *doc(f"A literal code, checked at compile time: one that does not match the {c.pattern} pattern does not "
                 "compile."),
            "template <std::size_t N>",
            f"consteval {name}(const char (&literal)[N]) : view_(literal, N - 1) {{",
            f"if (!{namespace(model, c)}::{match}(view_)) {{ ::knobly::detail::{refused}(); }}", "}",
            *doc("A code known at run time.", [f"@throws knobly::misuse_error when it does not match the "
                                               f"{c.pattern} pattern"]),
            f"{API} explicit {name}(std::string_view code);",
            *doc("The code's text, valid while this value lives."),
            "std::string_view view() const& noexcept { return view_; }",
            "std::string_view view() const&& = delete;",
            f"friend bool operator==(const {cls}& a, const {cls}& b) noexcept {{ return a.view_ == b.view_; }}",
            "private:", "std::shared_ptr<const std::string> owned_;  // empty for a literal", "std::string_view view_;",
            "};"]
    return [*doc(c.doc), f"using {name} = std::string;"]


def equality_root(model: Model, c: Concept) -> Optional[Concept]:
    """The view class whose operator== a view class compares by (its union, or the class it extends), when it is one
    that defines its own; None for a class with no generated operator== (one extending the block shape)."""
    while c.variant_of or c.extends is not None:
        if c.variant_of:
            c = model.concept[c.variant_of]
        else:
            assert c.extends is not None
            base = model.concept.get(c.extends.name)
            if base is None or not is_view_class(base):
                return None
            c = base
    return c if is_view_class(c) else None


def hash_lines(model: Model, c: Concept) -> List[str]:
    """std::hash for a view class, agreeing with its operator== (design.md 1.3, 2.3): the node it shows, or the
    values of the member its root is equal by (spec 2.9's expanded value: its text)."""
    root = equality_root(model, c)
    if is_alias(model, c) or not is_view_class(c) or root is None:
        return []
    cls = qual(model, c.name)
    template = ""
    if c.type_parameters:
        template = ", ".join(f"class {template_param(p)}" for p in c.type_parameters)
        cls = f"{cls}<{', '.join(template_param(p) for p in c.type_parameters)}>"
    if root.equal_by is not None:
        by = member_name(root, next(m for m in root.members if m.name == root.equal_by))
        call, noexcept = f"std::hash<std::string>{{}}(value.{by}())", ""
    else:
        call, noexcept = f"std::hash<const void*>{{}}({ACCESS}::view_of(value).get())", " noexcept"
    return [f"template <{template}>", f"struct hash<{cls}> {{",
            f"std::size_t operator()(const {cls}& value) const{noexcept} {{ return {call}; }}", "};"]


def is_alias(model: Model, c: Concept) -> bool:
    """A callback, or a concept that extends the block shape and adds nothing: a ``using`` alias, declared with the
    forward declarations (its parameters may be incomplete), so every class after it can name it."""
    return c.nature == "callback" or (extends_shape(model, c) and not c.members)


def alias_lines(model: Model, c: Concept) -> List[str]:
    ctx = Ctx(model)
    if c.nature == "callback":
        assert c.callback is not None
        return [*doc(c.doc), f"using {ident(snake(c.name))} = {value_type(c.callback, ctx)};"]
    return [*doc(c.doc), f"using {ident(snake(c.name))} = {base_types(model, c, ctx)[0]};"]


def concept_lines(model: Model, c: Concept, out: Out) -> List[str]:
    if is_alias(model, c):
        return []  # with the forward declarations (alias_lines)
    if c.nature == "named type":
        return named_type(model, c, out)
    if c.nature == "interface":
        return interface_concept(model, c)
    if c.nature == "port":
        return port_class(model, c)
    if c.nature == "options":
        return options_struct(model, c)
    if c.nature == "shape":
        return []  # support/block.hpp: the trait support template, written by hand
    if is_view_class(c):
        return view_class(model, c, out)
    if c.nature == "record":
        return record_class(model, c, out)
    raise SchemaError(f"C++ emitter: concept {c.name!r}: nature {c.nature!r} has no C++ form")


def needs(model: Model, c: Concept) -> List[str]:
    """The concepts that must be complete before ``c`` is defined: its bases, the types its stored fields hold by
    value (a sequence or a map holds an incomplete type), and the interfaces its members' parameters name."""
    out: List[str] = []
    if c.variant_of:
        out.append(c.variant_of)
    if c.extends is not None:
        out.append(c.extends.name)

    def held(t: Type) -> None:
        if t.form == "name" and t.name in model.concept:
            out.append(t.name)
            for a in t.args:
                held(a)
        elif t.form == "union":
            for a in t.args:
                held(a)

    if c.nature in ("record", "options") and not is_view_class(c):
        for m in model.all_members(c):
            if m.member == "property":
                held(m.type)
    for m in c.members:
        for p in m.params:
            pc = concept_of(model, p.type)
            if pc is not None and pc.nature == "interface":
                out.append(pc.name)
    return [n for n in out if n != c.name and model.concept[n].nature != "shape"]


def ordered(model: Model, concepts: List[Concept]) -> List[Concept]:
    """Schema order, with each concept after what it needs complete (a depth-first topological order)."""
    here = {c.name for c in concepts}
    done: Set[str] = set()
    out: List[Concept] = []

    def visit(c: Concept, path: Tuple[str, ...]) -> None:
        if c.name in done:
            return
        if c.name in path:
            raise SchemaError(f"C++ emitter: concepts hold each other by value: {' -> '.join(path + (c.name,))}")
        for n in needs(model, c):
            if n in here:
                visit(model.concept[n], path + (c.name,))
        done.add(c.name)
        out.append(c)

    for c in concepts:
        visit(c, ())
    return out


def forward(model: Model, c: Concept) -> Optional[str]:
    """The forward declaration of a class the header defines (aliases, concepts and native types have none)."""
    if c.nature in ("callback", "interface", "shape") or c.is_ == "native":
        return None
    if c.nature == "named type" and not (c.brand or c.pattern):
        return None
    if extends_shape(model, c) and not c.members:
        return None
    key = "struct" if c.nature == "options" else "class"
    tpl = f"template <{', '.join('class ' + template_param(p) for p in c.type_parameters)}> " if c.type_parameters else ""
    return f"{tpl}{key} {ident(snake(c.name))};"


def function_lines(model: Model, f: Function, out: Out, ns: str) -> List[str]:
    """A free function: declared here, defined by the hand code; one declaration per overload."""
    ctx = Ctx(model)
    lines: List[str] = []
    result = value_type(f.returns, ctx)
    name = ident(LANGUAGE.function_case(f.name))
    for ps in overloads(model, f.params, f.options, ctx, kept=True):
        lines += member_doc(model, f.doc, f.params, model.raised(f.errors, f.when))
        lines.append(f"{API} {result} {name}({signature(ps)});")
        out.hand.append(Hand(result, [t for t, _ in ps], f"{ns}::{name}({args(len(ps))})"))
    return lines


# --- pattern matchers: an I-Regexp compiled to an automaton over code points -----------------------------------------

class _Regex:
    """A checked I-Regexp body (the loader checks its grammar) parsed to a tree of code point sets: ("set", ranges),
    ("cat", items), ("alt", arms), ("rep", item, min, max or None). ``\\p{..}`` is refused: a matcher here carries no
    Unicode property tables (spec/codegen.md section 10: an emitter refuses what its engine lacks)."""

    def __init__(self, body: str) -> None:
        self.s, self.pos = body, 0

    def peek(self) -> str:
        return self.s[self.pos] if self.pos < len(self.s) else ""

    def parse(self) -> tuple:
        return self.alt()

    def alt(self) -> tuple:
        arms = [self.cat()]
        while self.peek() == "|":
            self.pos += 1
            arms.append(self.cat())
        return arms[0] if len(arms) == 1 else ("alt", arms)

    def cat(self) -> tuple:
        items = []
        while self.peek() not in ("", "|", ")"):
            atom = self.atom()
            c = self.peek()
            if c and c in "*+?":
                self.pos += 1
                atom = {"*": ("rep", atom, 0, None), "+": ("rep", atom, 1, None), "?": ("rep", atom, 0, 1)}[c]
            elif c == "{":
                end = self.s.index("}", self.pos)
                lo, comma, hi = self.s[self.pos + 1:end].partition(",")
                self.pos = end + 1
                atom = ("rep", atom, int(lo), int(lo) if not comma else (int(hi) if hi else None))
            items.append(atom)
        return ("cat", items)

    def escape(self) -> int:
        self.pos += 1
        c = self.peek()
        if c in ("p", "P"):
            raise SchemaError("C++ matcher: \\p{..} (a Unicode property) is not supported; write the class out")
        self.pos += 1
        return {"n": 10, "r": 13, "t": 9}.get(c, ord(c))

    def atom(self) -> tuple:
        c = self.peek()
        if c == "(":
            self.pos += 1
            node = self.alt()
            self.pos += 1  # ')'
            return node
        if c == "[":
            return ("set", self.klass())
        if c == ".":
            self.pos += 1
            return ("set", list(complement([(10, 10), (13, 13)])))
        if c == "\\":
            cp = self.escape()
            return ("set", [(cp, cp)])
        self.pos += 1
        return ("set", [(ord(c), ord(c))])

    def klass(self) -> List[Tuple[int, int]]:
        self.pos += 1
        negate = self.peek() == "^"
        if negate:
            self.pos += 1
        ranges: List[Tuple[int, int]] = []
        first = True
        while not (self.peek() == "]" and not first):
            lo = hi = self.class_char()
            if self.peek() == "-" and self.s[self.pos + 1:self.pos + 2] not in ("]", ""):
                self.pos += 1
                hi = self.class_char()
            ranges.append((lo, hi))
            first = False
        self.pos += 1
        return list(complement(ranges) if negate else normal(ranges))

    def class_char(self) -> int:
        if self.peek() == "\\":
            return self.escape()
        self.pos += 1
        return ord(self.s[self.pos - 1])


def dfa(regex: str) -> Tuple[List[List[Tuple[int, int, int]]], Set[int]]:
    """The pattern (anchored, ``^...$``) as a minimal deterministic automaton: per state, its (lo, hi, target) moves,
    and the accepting states. Built by tools/automaton.py, the machinery the parser generator's lexer shares."""
    nfa = Nfa()

    def build(node: tuple) -> Tuple[int, int]:
        if node[0] == "set":
            return nfa.ranges(tuple(node[1]))
        if node[0] == "cat":
            return nfa.chain([build(item) for item in node[1]])
        if node[0] == "alt":
            return nfa.choice([build(arm) for arm in node[1]])
        _, inner, lo, hi = node
        parts = [build(inner) for _ in range(lo)]
        if hi is None:
            parts.append(nfa.repeat(build(inner), True, True))
        else:
            parts += [nfa.repeat(build(inner), True, False) for _ in range(hi - lo)]
        return nfa.chain(parts)

    start, final = build(_Regex(regex[1:-1]).parse())
    nfa.accept[final] = 0
    table, accept = minimize(*determinize(nfa, start))
    return table, {s for s, label in enumerate(accept) if label >= 0}


def matcher(model: Model, c: Constant) -> List[str]:
    """A pattern constant as ``constexpr bool is_<name>(std::string_view)``: the text decoded by the one UTF-8 policy
    (detail/text_in.hpp; bytes that do not decode never match), then run through the pattern's automaton."""
    table, accepting = dfa(str(c.value))
    name = ident(LANGUAGE.pattern_form(c.name))  # type: ignore[misc]

    def cond(lo: int, hi: int) -> str:
        if lo == hi:
            return f"cp == 0x{lo:X}U"
        if lo == 0:
            return f"cp <= 0x{hi:X}U"
        return f"(cp >= 0x{lo:X}U && cp <= 0x{hi:X}U)"

    cases: List[str] = []
    for state, row in enumerate(table):
        cases.append(f"case {state}:")
        by_target: Dict[int, List[str]] = {}
        for lo, hi, target in row:
            by_target.setdefault(target, []).append(cond(lo, hi))
        for target, conds in by_target.items():
            cases.append(f"if ({' || '.join(conds)}) {{ state = {target}; break; }}")
        cases.append("return false;")
    accept = " || ".join(f"state == {s}" for s in sorted(accepting)) or "false"
    return [*doc(f"Whether the text matches the {c.about} pattern: {c.means}."),
            f"constexpr bool {name}(std::string_view text) noexcept {{",
            "int state = 0;",
            "for (std::size_t at = 0; at < text.size();) {",
            "char32_t cp = 0;",
            "const std::size_t length = ::knobly::detail::decode_utf8(text, at, cp);",
            "if (length == 0) { return false; }",
            "at += length;",
            "switch (state) {", *cases, "default:", "return false;", "}", "}",
            f"return {accept};", "}"]


# --- headers ---------------------------------------------------------------------------------------------------------

STD = ["<concepts>", "<cstddef>", "<cstdint>", "<functional>", "<memory>", "<optional>", "<string>", "<string_view>",
       "<type_traits>", "<utility>", "<variant>"]
SUPPORT = ["config", "sequence", "ordered_map", "view", "block", "walk_view"]


def header(name: str, source: str, includes: List[str], body: List[str], tail: Sequence[str] = ()) -> str:
    g = guard(name)
    out = [*head(source), f"#ifndef {g}", f"#define {g}", ""]
    out += [f"#include {i}" if i else "" for i in includes]
    out += ["", *body, ""]
    if tail:
        out += [*tail, ""]
    out += [f"#endif  // {g}", ""]
    return "\n".join(out)


def kinds_header(model: Model) -> str:
    body = ["KNOBLY_NAMESPACE_BEGIN", ""]
    for k in model.kinds:
        if KEY not in k.languages:
            continue
        name = ident(snake(k.name))
        values = [v if k.from_grammar else ident(snake(v)) for v in k.values]
        body += [*doc(k.doc), f"enum class {name} : std::uint8_t {{ {', '.join(values)} }};", ""]
        body += doc(f"The {k.name}'s value as the spec writes it.")
        body += [f"constexpr std::string_view to_string({name} kind) noexcept {{", "switch (kind) {"]
        body += [f"case {name}::{spelled}: return {lit(v)};" for v, spelled in zip(k.values, values)]
        body += ["}", "return {};", "}", ""]
    body.append("KNOBLY_NAMESPACE_END")
    return header("kinds.hpp", 'spec/schema/api.json "kinds" (token kind: grammar/Knobly.g4)',
                  ["<cstdint>", "<string_view>", "", "<knobly/support/config.hpp>"], body)


def codes_header(model: Model) -> str:
    entries, strings, messages, facts, found = [], [], [], [], []
    for c in model.codes:
        name = ident(LANGUAGE.code_case(c.name))
        entries += [*doc(c.meaning.replace("`", "")), f"{name} = {int(c.code[1:])},"]
        strings.append(f"case diagnostic_code::{name}: return {lit(c.code)};")
        message = PLACEHOLDER.sub(lambda m: str(model.limit[m.group(1)].value), c.message)
        messages.append(f"case diagnostic_code::{name}: return {lit(message)};")
        found.append(f"inline constexpr std::string_view found_by_{c.code}[] = {{{', '.join(lit(f) for f in c.found_by)}}};")
        reason = "std::nullopt" if c.reason is None else f"::knobly::unreadable_reason::{ident(snake(c.reason))}"
        facts.append(f"case diagnostic_code::{name}: return {{{lit(c.name)}, {lit(c.layer)}, detail::found_by_{c.code}, {reason}}};")
    body = ["KNOBLY_NAMESPACE_BEGIN", "",
            *doc("knobly's diagnostic codes, by name; each value is its code's number (E1001 is 1001)."),
            "enum class diagnostic_code : std::uint16_t {", *entries, "};", "",
            *doc("The code as the spec writes it: \"E1001\"."),
            "inline std::string to_string(diagnostic_code code) {", "switch (code) {", *strings, "}", "return {};", "}", "",
            *doc("The base message of each code (for people, not part of the contract)."),
            "constexpr std::string_view message(diagnostic_code code) noexcept {", "switch (code) {", *messages, "}",
            "return {};", "}", "",
            *doc(f"What the registry says of one code: its spec name, its owning layer (one of {', '.join(CODE_LAYERS)}), "
                 "who finds it, and the unreadable reason it gives (none: a reader's code, which makes nothing "
                 "unreadable)."),
            "struct code_facts {", "std::string_view name;", "std::string_view layer;",
            "std::span<const std::string_view> found_by;", "std::optional<::knobly::unreadable_reason> reason;", "};",
            "", "namespace detail {", *found, "}  // namespace detail", "",
            *doc("Each code's facts."),
            "constexpr code_facts facts_of(diagnostic_code code) noexcept {", "switch (code) {", *facts, "}",
            "return {};", "}", "",
            *doc("One diagnostic's code, message and reason, built from the registry, so a raise site cannot pair a code "
                 "with the wrong reason or message."),
            "struct described {", "diagnostic_code code;", "std::string message;",
            "std::optional<::knobly::unreadable_reason> reason;", "};", "",
            *doc("A code's description with its base message."),
            "inline described describe(diagnostic_code code) {",
            "return {code, std::string(message(code)), facts_of(code).reason};", "}", "",
            *doc("A code's description: its base message, ': ', then the detail."),
            "inline described describe(diagnostic_code code, std::string_view detail) {",
            "std::string text(message(code));", "text += \": \";", "text += detail;",
            "return {code, std::move(text), facts_of(code).reason};", "}", "",
            "KNOBLY_NAMESPACE_END"]
    return header("codes.hpp", "spec/schema/diagnostics.json",
                  ["<cstdint>", "<optional>", "<span>", "<string>", "<string_view>", "<utility>", "",
                   "<knobly/kinds.hpp>", "<knobly/support/config.hpp>"], body)


def layer_namespace(model: Model, layer: str) -> Optional[str]:
    """The namespace a layer's names sit in below the package's, or None for a layer in the package's own."""
    return None if model.layer[layer].namespace == "package" else ident(snake(layer))


def limits_header(model: Model) -> str:
    body = ["KNOBLY_NAMESPACE_BEGIN", ""]
    for c in model.constants:
        if c.sort == "pattern":
            continue  # a matcher, in its layer's header
        ns = layer_namespace(model, c.layer)
        name = ident(LANGUAGE.constant_case(c.name))
        lines = doc(f"{c.about}: {c.means}.")
        if c.sort == "limit":
            lines.append(f"inline constexpr std::int64_t {name} = {c.value};")
        else:
            words_ = list(c.value)  # type: ignore[call-overload]
            lines.append(f"inline constexpr std::array<std::string_view, {len(words_)}> {name} = "
                         f"{{{', '.join(lit(w) for w in words_)}}};")
        body += ([f"namespace {ns} {{", *lines, f"}}  // namespace {ns}"] if ns else lines) + [""]
    body.append("KNOBLY_NAMESPACE_END")
    return header("limits.hpp", 'spec/schema/api.json "limits" and "reserved names"',
                  ["<array>", "<cstdint>", "<string_view>", "", "<knobly/support/config.hpp>"], body)


def concat(parts: List[str]) -> str:
    return " + ".join(parts) or "std::string()"


def template_expr(g: ErrorGroup) -> str:
    """An error class's message built from its template: a field's message, or a list field joined."""
    template = str(g.message["template"])
    sep = str(g.message.get("separator", ", "))
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(template):
        if template[pos:m.start()]:
            parts.append(f"std::string({lit(template[pos:m.start()])})")
        ph = m.group(1)
        if ph.endswith(" message"):
            parts.append(f"{ident(snake(ph[: -len(' message')]))}.message()")
        else:
            parts.append(f"::knobly::detail::join_for_message({ident(snake(ph))}, {lit(sep)})")
        pos = m.end()
    if template[pos:]:
        parts.append(f"std::string({lit(template[pos:])})")
    return concat(parts)


def errors_header(model: Model) -> str:
    """The exception class tree (design.md 2.2): each group's class under its parent or its root's standard class,
    with a constructor taking the message (when given) then its fields, and a const accessor per own field."""
    ctx = Ctx(model)
    tmpl = model.argument_type_message[KEY]
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(tmpl):
        if tmpl[pos:m.start()]:
            parts.append(f"std::string({lit(tmpl[pos:m.start()])})")
        parts.append(f"std::string({ident(snake(m.group(1)))})")
        pos = m.end()
    if tmpl[pos:]:
        parts.append(f"std::string({lit(tmpl[pos:])})")
    body = ["KNOBLY_NAMESPACE_BEGIN", "", "namespace detail {", "",
            *doc("A list field in an error's message: texts as they are, anything else by its people form."),
            "template <class T>",
            "std::string join_for_message(const ::knobly::sequence<T>& items, std::string_view separator) {",
            "std::string out;", "for (std::size_t i = 0; i < items.size(); ++i) {",
            "if (i != 0) { out += separator; }",
            "if constexpr (std::is_same_v<T, std::string>) { out += items.at(i); } else { out += to_string(items.at(i)); }",
            "}", "return out;", "}", "",
            *doc("The argument type error's message: the one helper every member that checks an argument calls."),
            "inline std::string argument_type_message(std::string_view member, std::string_view parameter, "
            "std::string_view got) {", f"return {concat(parts)};", "}", "", "}  // namespace detail", ""]
    for g in model.groups:
        name = error_class(model, g.name)
        parent = model.group[g.parent] if g.parent else None
        base = f"::knobly::{error_class(model, parent.name)}" if parent else g.base[KEY]["base"]
        inherited = {f for f, _ in parent.fields} if parent else set()
        params = ["std::string message"] if g.message.get("given") else []
        params += [f"{value_type(t, ctx)} {ident(snake(f))}" for f, t in g.fields]
        msg = "std::move(message)" if g.message.get("given") else template_expr(g)
        if parent is None:
            sup = f"{base}({msg})"
        else:
            sup_args = ([msg] if parent.message.get("given") else []) + [ident(snake(f)) for f, _ in parent.fields]
            sup = f"{base}({', '.join(sup_args)})"
        own = [(f, t) for f, t in g.fields if f not in inherited]
        inits = [sup] + [f"{snake(f)}_(std::move({ident(snake(f))}))" for f, _ in own]
        explicit = "explicit " if len(params) == 1 else ""
        cls = [*doc(g.class_doc()), f"class KNOBLY_DETAIL_VISIBLE {name} : public {base} {{", "public:",
               f"{explicit}{name}({', '.join(params)}) : {', '.join(inits)} {{}}"]
        cls += [f"{value_type(t, ctx)} {ident(snake(f))}() const {{ return {snake(f)}_; }}" for f, t in own]
        if own:
            cls += ["private:", *(f"{value_type(t, ctx)} {snake(f)}_;" for f, t in own)]
        body += [*cls, "};", ""]
    body.append("KNOBLY_NAMESPACE_END")
    g = guard("errors.hpp")
    package = guard(f"{model.package}.hpp")
    return "\n".join([
        *head('spec/schema/api.json "error groups"'),
        "// The classes hold records the package header declares, so the package header includes this one after them;",
        "// included first, this header includes the package header, which includes it back.",
        f"#ifndef {package}", f"#include <knobly/{model.package}.hpp>", "#else", f"#ifndef {g}", f"#define {g}", "",
        "#include <cstddef>", "#include <stdexcept>", "#include <string>", "#include <string_view>", "#include <type_traits>",
        "#include <utility>", "", "#include <knobly/support/config.hpp>", "#include <knobly/support/sequence.hpp>",
        "", "// Default visibility, so a catch in one shared library sees a throw from another (design.md 2.5).",
        "#if defined(__GNUC__) || defined(__clang__)", '#define KNOBLY_DETAIL_VISIBLE [[gnu::visibility("default")]]',
        "#else", "#define KNOBLY_DETAIL_VISIBLE", "#endif", "", *body, "", f"#endif  // {g}", f"#endif  // {package}",
        ""])


def headers(model: Model) -> Dict[str, Tuple[List[str], Optional[str]]]:
    """Each public header to the layers whose declarations it holds and the adapter module it is (None: a layer
    header): the package's (the layers in the package's namespace), one per layer with its own namespace, one per
    adapter module the binding has."""
    out: Dict[str, Tuple[List[str], Optional[str]]] = {
        f"{model.package}.hpp": ([layer.name for layer in model.layers if layer.namespace == "package"], None)}
    for layer in model.layers:
        if layer.namespace != "package":
            out[f"{layer.name}.hpp"] = ([layer.name], None)
    for module, path in LANGUAGE.modules.items():
        out[f"{path}.hpp"] = ([], module)
    return out


def own_layers(model: Model, layers: List[str], module: Optional[str]) -> List[str]:
    """A header's layers; an adapter module's are those of its functions and concepts."""
    if module is None:
        return layers
    found = {f.layer for f in model.functions if f.module == module} | {c.layer for c in model.concepts if c.module == module}
    return sorted(found)


def header_of_layer(model: Model, layer: str) -> str:
    return f"{model.package}.hpp" if model.layer[layer].namespace == "package" else f"{layer}.hpp"


def allowed_layers(model: Model, layers: Sequence[str]) -> Set[str]:
    out: Set[str] = set()
    for name in layers:
        out |= {name, *model.layer[name].may_import}
    return out


def detail_dirs(layers: List[str], module: Optional[str]) -> List[str]:
    return [LANGUAGE.modules[module]] if module else layers


def union_templates(model: Model, c: Concept) -> List[str]:
    """A union root's ``as<V>()`` and ``visit(f)``, defined whole from the schema's variant list (each variant's kind):
    out of the class, after every variant is defined. They read only ``kind()`` (which works on a detached view, contract
    4.3) and build the variant from the same view through ``detail::access``."""
    cls = qual(model, c.name)
    kind = next(m for m in c.members if m.name == "kind")
    kind_t = value_type(kind.type, Ctx(model))
    variants = [(qual(model, v), f"{kind_t}::{ident(snake(model.concept[v].kind or ''))}") for v in c.variants]
    own = ident(snake(c.name))  # defined inside the layer's namespace: "std::optional<V> ::x" would parse as one name
    lines = ["template <class V>", f"    requires std::derived_from<V, {cls}>", f"std::optional<V> {own}::as() const {{",
             f"if constexpr (std::is_same_v<V, {cls}>) {{", "return *this;"]
    for v, k in variants:
        lines += [f"}} else if constexpr (std::is_same_v<V, {v}>) {{",
                  f"if (kind() == {k}) {{ return {ACCESS}::make<V>(view_); }}", "return std::nullopt;"]
    lines += ["} else {", "return std::nullopt;", "}", "}", "",
              "template <class F>", f"decltype(auto) {own}::visit(F&& f) const {{", "switch (kind()) {"]
    lines += [f"case {k}: return std::forward<F>(f)({ACCESS}::make<{v}>(view_));" for v, k in variants]
    if c.except_kinds:  # kinds of the list no variant has (an expanded value is never a reference)
        lines.append("default: break;")
    lines += ["}", "::knobly::detail::bad_kind();", "}"]
    return lines


def template_layers(model: Model, concepts: List[Concept]) -> List[str]:
    """The layers of a header whose classes have member templates the hand code defines (a class template's members,
    ``collect``, a member taking an interface) or that spell the block shape (whose support template reads the layer's
    ``detail::block_traits`` specialization): their definitions and specializations sit in
    ``detail/<layer>/templates.hpp``, which the header includes in both modes, since a template cannot be compiled
    once (errata A3; frozen-m2.md 3.1)."""
    out: List[str] = []
    for c in concepts:
        hand = bool(c.type_parameters and c.members) or extends_shape(model, c) or any(
            m.trait == "collect" or any((pc := concept_of(model, p.type)) is not None and pc.nature == "interface"
                                        for p in m.params)
            for m in c.members)
        if hand and c.layer not in out:
            out.append(c.layer)
    return out


SUPPORT_TEMPLATES = ("sequence", "ordered_map", "block", "walk_view")


def instantiations(model: Model, text: str) -> List[str]:
    """Every specialization of a support template or a generated class template that ``text`` spells, in order, for
    explicit instantiation in compiled mode (design.md 2.5, point 2): read from what the header spells, so no
    instantiation it uses can be missed. A block adds the walk view and the directive sequence its members return.
    Specializations over a template's own parameters are left out."""
    generated = [qual(model, c.name) for c in model.concepts if c.type_parameters and KEY in c.languages]
    params = {template_param(p) for c in model.concepts for p in c.type_parameters}
    heads = [f"::knobly::{t}<" for t in SUPPORT_TEMPLATES] + [f"{g}<" for g in generated]
    found: List[str] = []

    def add(spec: str) -> None:
        if spec not in found and not any(re.search(rf"\b{p}\b", spec) for p in params):
            found.append(spec)

    at = 0
    while True:
        hits = [(text.find(h, at), h) for h in heads]
        hits = [(i, h) for i, h in hits if i >= 0]
        if not hits:
            return found
        start, h = min(hits)
        depth, end = 0, start + len(h) - 1
        for end in range(start + len(h) - 1, len(text)):
            depth += {"<": 1, ">": -1}.get(text[end], 0)
            if depth == 0:
                break
        spec = text[start:end + 1]
        for inner in instantiations(model, spec[len(h):-1]):
            add(inner)
        add(spec)
        if h == "::knobly::block<":
            item, directive = split_args(spec[len(h):-1])
            add(f"::knobly::walk_view<{item}>")
            add(f"::knobly::sequence<{directive}>")
        at = start + len(h)


def split_args(args: str) -> List[str]:
    """A template argument list's top-level arguments."""
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        depth += {"<": 1, ">": -1, "(": 1, ")": -1}.get(ch, 0)
        cur += ch
    return [*out, cur.strip()]


def extern_templates(specs: Sequence[str]) -> List[str]:
    """Compiled mode: the specializations this header spells first, instantiated once in implementation.hpp."""
    if not specs:
        return []
    return ["#if !KNOBLY_HEADER_ONLY  // compiled mode: instantiated once, in <knobly/implementation.hpp>",
            *(f"extern template class {s};" for s in specs), "#endif", ""]


def layer_header(model: Model, name: str, layers: List[str], module: Optional[str], out: Out,
                 seen: Optional[List[str]] = None) -> str:
    package = name == f"{model.package}.hpp"
    mine = own_layers(model, layers, module)
    if module is None:
        concepts = [c for c in model.concepts if c.layer in layers and c.module is None and KEY in c.languages]
        functions = [f for f in model.functions if f.layer in layers and f.module is None]
        ns = None if package else ident(snake(layers[0]))
        patterns = [c for c in model.constants if c.sort == "pattern" and c.layer in layers]
        where = "::" + model.module(layers[0], "::")
    else:
        concepts = [c for c in model.concepts if c.module == module and KEY in c.languages]
        functions = [f for f in model.functions if f.module == module]
        ns = ident(LANGUAGE.modules[module])
        patterns = []
        where = f"::{model.package}::{ns}"
    includes = list(STD)
    if package:
        includes += ["", *(f"<knobly/support/{s}.hpp>" for s in SUPPORT), "<knobly/detail/text_in.hpp>",
                     "<knobly/kinds.hpp>", "<knobly/codes.hpp>", "<knobly/limits.hpp>"]
    else:
        allowed = allowed_layers(model, mine)
        deps = dict.fromkeys(header_of_layer(model, layer.name) for layer in model.layers if layer.name in allowed)
        includes += ["", *(f"<knobly/{d}>" for d in deps if d != name)]
    body: List[str] = ["KNOBLY_NAMESPACE_BEGIN"]
    if package:
        body += ["", "// The error classes, defined in errors.hpp (included at the end, after the records they hold).",
                 *(f"class {error_class(model, g.name)};" for g in model.groups if not g.builtin(KEY))]
    if ns:
        body.append(f"namespace {ns} {{")
    fwd = [x for x in (forward(model, c) for c in concepts) if x]
    if fwd:
        body += ["", *fwd]
    for c in concepts:
        if is_alias(model, c):
            body += ["", *alias_lines(model, c)]
    for p in patterns:
        body += ["", *matcher(model, p)]
    for c in ordered(model, concepts):
        lines = concept_lines(model, c, out)
        if lines:
            body += ["", *lines]
    for c in concepts:
        if c.is_union and is_view_class(c):
            body += ["", *union_templates(model, c)]
    for f in functions:
        if model.function_module(f, KEY) is not None and (f.factory or {}).get(KEY) != "constructor":
            body += ["", *function_lines(model, f, out, where)]
    if ns:
        body += ["", f"}}  // namespace {ns}"]
    body += ["", "KNOBLY_NAMESPACE_END"]
    hashes = [line for c in concepts for line in ["", *hash_lines(model, c)] if hash_lines(model, c)]
    if hashes:
        body += ["", "// Each view class hashes as it compares, so it can key an unordered container (design.md 2.3).",
                 "namespace std {", *hashes, "", "}  // namespace std"]
    tail = ["#include <knobly/errors.hpp>  // after the records its classes hold", ""] if package else []
    tail += [*(f"#include <knobly/detail/{d}/templates.hpp>  // templates and block traits: both modes"
               for d in template_layers(model, concepts)), ""]
    if seen is not None:
        mine = [s for s in instantiations(model, "\n".join(body)) if s not in seen]
        seen.extend(mine)
        tail += extern_templates(mine)
    tail += ["#if KNOBLY_HEADER_ONLY", *(f"#include <knobly/detail/{d}/definitions.hpp>" for d in detail_dirs(layers, module)),
             "#endif"]
    what = (f"the {' and '.join(layers)} layer{'s' if len(layers) > 1 else ''}" if module is None
            else f"the {module} adapter module")
    return header(name, f"spec/schema/api.json, {what}", includes, body, tail)


def implementation_header(model: Model, specs: Sequence[str] = ()) -> str:
    hs = headers(model)
    every = [d for layers, module in hs.values() for d in detail_dirs(layers, module)]
    instantiated = ["", "// Every support and class template specialization the headers spell, instantiated once here (each header",
                    "// declares its own extern in compiled mode).", *(f"template class {s};" for s in specs)] if specs else []
    return header("implementation.hpp", "spec/schema/api.json layers", ["<knobly/support/config.hpp>"],
                  ["#if KNOBLY_HEADER_ONLY",
                   '#error "<knobly/implementation.hpp> is for compiled mode: define KNOBLY_HEADER_ONLY=0"',
                   "#endif", "", *(f"#include <knobly/{name}>" for name in hs), "",
                   *(f"#include <knobly/detail/{d}/definitions.hpp>" for d in every), *instantiated])


def format_header(model: Model) -> str:
    """The opt-in formatting header (design.md 3.5): for every type with a to_string (each concept's people form, each
    kind list, diagnostic_code), a std::formatter (width, fill and alignment as for a string) and an operator<< found
    by argument-dependent lookup, both calling that to_string. Written whole: which types have one is a schema fact."""
    by_ns: Dict[str, List[str]] = {}
    includes: Dict[str, None] = {}
    for c in model.concepts:
        if KEY in c.languages and c.module is None and any(m.trait == "people form" for m in c.members):
            by_ns.setdefault(namespace(model, c), []).append(qual(model, c.name))
            includes[f"<knobly/{header_of_layer(model, c.layer)}>"] = None
    for k in model.kinds:
        if KEY in k.languages:
            by_ns.setdefault("::" + model.kind_module(k, KEY), []).append(qual(model, k.name))
    by_ns.setdefault(f"::{model.package}", []).append(qual(model, "diagnostic code"))
    every = [t for types in by_ns.values() for t in types]
    body = ["KNOBLY_NAMESPACE_BEGIN", "namespace detail {", "",
            *doc("A formatter that formats a value's to_string as a string (width, fill and alignment included)."),
            "template <class T>", "struct people_formatter : std::formatter<std::string_view, char> {",
            "template <class Context>", "auto format(const T& value, Context& context) const {",
            "const auto text = to_string(value);",
            "return std::formatter<std::string_view, char>::format(std::string_view(text), context);", "}", "};", "",
            "}  // namespace detail", "KNOBLY_NAMESPACE_END", ""]
    for ns, types in by_ns.items():
        inner = ns[len(f"::{model.package}"):].lstrip(":")
        body += ["KNOBLY_NAMESPACE_BEGIN", *([f"namespace {inner} {{"] if inner else []), ""]
        for t in types:
            body += [*doc("Writes `to_string(value)`."),
                     f"inline std::ostream& operator<<(std::ostream& out, const {t}& value) {{ return out << to_string(value); }}", ""]
        body += [*([f"}}  // namespace {inner}"] if inner else []), "KNOBLY_NAMESPACE_END", ""]
    body += [f"template <> struct std::formatter<{t}, char> : ::knobly::detail::people_formatter<{t}> {{}};" for t in every]
    return header("format.hpp", "spec/schema/api.json (every people form, kind list and diagnostic_code)",
                  ["<format>", "<ostream>", "<string_view>", "", f"<knobly/{model.package}.hpp>",
                   *(i for i in includes if i != f"<knobly/{model.package}.hpp>")], body)


def render_with_hands(model: Model) -> Tuple[Dict[str, str], Dict[str, List[Hand]]]:
    files = {"kinds.hpp": kinds_header(model), "codes.hpp": codes_header(model), "limits.hpp": limits_header(model),
             "errors.hpp": errors_header(model)}
    hands: Dict[str, List[Hand]] = {}
    seen: List[str] = []
    for name, (layers, module) in headers(model).items():
        out = Out()
        files[name] = layer_header(model, name, layers, module, out, seen)
        hands[name] = out.hand
    files["implementation.hpp"] = implementation_header(model, seen)
    files["format.hpp"] = format_header(model)
    return files, hands


def render(model: Model) -> Dict[str, str]:
    return render_with_hands(model)[0]


# --- the adapter's shapes --------------------------------------------------------------------------------------------


def render_shapes(model: Model) -> Dict[str, str]:
    p = model.protocol
    spell, by_concept = model.spellings(KEY)
    rows = [f"{{{lit(k)}, {lit(v)}}}," for k, v in sorted(spell.items())]
    exceptions = [f"{{{lit(snake(c))}, {lit(m)}, {lit(v)}}}," for (c, m), v in sorted(by_concept.items())]
    order: List[ErrorGroup] = []

    def down(g: ErrorGroup) -> None:  # the most specific group first
        for kid in model.groups:
            if kid.parent == g.name:
                down(kid)
        order.append(g)

    for g in model.groups:
        if g.parent is None:
            down(g)
    checks = [f"if (dynamic_cast<const ::knobly::{error_class(model, g.name)}*>(&error) != nullptr) {{ return {lit(g.name)}; }}"
              for g in order]
    body = ["namespace adapter::shapes {", "",
            *doc("The protocol version an adapter's hello answers."),
            f"inline constexpr int protocol = {p.version};", "",
            "namespace detail {",
            f"inline constexpr std::array<std::pair<std::string_view, std::string_view>, {len(rows)}> spellings = {{{{",
            *rows, "}};",
            *doc("The members a class spells otherwise (one named as its class takes a trailing underscore): (class, "
                 "spec name, spelling)."),
            "inline constexpr std::array<std::array<std::string_view, 3>, "
            f"{len(exceptions)}> member_spellings = {{{{", *exceptions, "}};", "}  // namespace detail", "",
            *doc("Each spec name the driver sends (a member, a reader) in this binding's spelling, snake_case; empty "
                 "for a name the schema does not have."),
            "constexpr std::string_view spelling(std::string_view spec_name) noexcept {",
            "for (const auto& [name, spelled] : detail::spellings) {",
            "if (name == spec_name) { return spelled; }", "}", "return {};", "}", "",
            *doc("A member's spelling in one class (its C++ name, snake_case): where the class spells it otherwise "
                 "(written::index::index_()), that; else spelling(spec_name)."),
            "constexpr std::string_view spelling(std::string_view class_name, std::string_view spec_name) noexcept {",
            "for (const auto& [cls, name, spelled] : detail::member_spellings) {",
            "if (cls == class_name && name == spec_name) { return spelled; }", "}", "return spelling(spec_name);", "}", "",
            *doc("The error group an exception is, the most specific first; empty for any other exception."),
            "inline std::optional<std::string_view> error_group_of(const std::exception& error) {",
            *checks, "return std::nullopt;", "}", "",
            "}  // namespace adapter::shapes"]
    return {"shapes.hpp": header("shapes.hpp", "spec/schema/protocol.json (spec/conformance.md 4) and api.json's error groups",
                                 ["<array>", "<exception>", "<optional>", "<string_view>", "<utility>", "",
                                  f"<knobly/{model.package}.hpp>"], body)}


# --- the test contract -----------------------------------------------------------------------------------------------


def render_contract(model: Model) -> Dict[str, str]:
    _, hands = render_with_hands(model)
    hs = headers(model)
    files: Dict[str, str] = {}
    for name, (layers, module) in hs.items():
        stem = name[: -len(".hpp")]
        files[f"api_contract_{stem}.cpp"] = "\n".join([
            *head(f"spec/schema/api.json, <knobly/{name}>"),
            "// Odr-uses every hand-defined function and member of the header, each through a volatile function pointer",
            "// no optimizer drops: a declaration whose definition is missing fails to link. The file also compiles",
            "// before a layer's definitions exist, so a missing inline definition is the linker's to report.",
            "#if defined(__clang__)", '#pragma clang diagnostic ignored "-Wundefined-inline"', "#endif", "",
            f"#include <knobly/{name}>", "",
            "int main() {", *(h.line(i) for i, h in enumerate(hands[name])), "return 0;", "}", ""])
        allowed = allowed_layers(model, own_layers(model, layers, module))
        # A header holds a layer this one may import (the package header holds shared and io together), or it is
        # forbidden; an adapter module's header is forbidden to every other header (the core never imports one).
        forbidden = [other for other, (olayers, omodule) in hs.items()
                     if other != name and (omodule is not None or not set(olayers) & allowed)]
        files[f"layers_{stem}.cpp"] = "\n".join([
            *head(f"spec/schema/api.json \"may import\", <knobly/{name}>"),
            "// The layer-direction check: every header this one's layers may not import is marked as already included,",
            "// so an include of one leaves its names undeclared and this file fails to compile.",
            *(f"#define {guard(f)}" for f in forbidden), "",
            f"#include <knobly/{name}>", ""])
        files[f"layers_{stem}_definitions.cpp"] = "\n".join([
            *head(f"spec/schema/api.json, the definitions of <knobly/{name}>"),
            "// The layer-boundary check (spec 7.0: render builds on the written layer's public objects only; the",
            "// binding guide's second check): this header's definitions compiled in compiled mode, where no public",
            "// header includes its layer's definitions, so every other layer's detail types are undeclared and a",
            "// definition here that reaches into one fails to compile. Compiled, never linked.",
            "#define KNOBLY_HEADER_ONLY 0", "",
            *(f"#include <knobly/detail/{d}/definitions.hpp>" for d in detail_dirs(layers, module)), ""])
    return files
