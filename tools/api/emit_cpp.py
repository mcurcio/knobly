"""The C++ emitter (spec/codegen.md section 4; .claude/design/cpp/design.md 1.1 to 1.4): renders the loader's model as
the header-only C++ binding's public headers.

    cpp/include/villanelle/villanelle.hpp   the shared and io layers (namespace villanelle), including the four below
    cpp/include/villanelle/kinds.hpp        every kind list as an enum class with to_string
    cpp/include/villanelle/codes.hpp        diagnostic_code, messages, code_facts, describe
    cpp/include/villanelle/limits.hpp       the limits and the reserved names
    cpp/include/villanelle/errors.hpp       the exception class tree (spec 2.8)
    cpp/include/villanelle/<layer>.hpp      one header per layer with its own namespace (syntax, written, rendered);
                                            each pattern's matcher over code points sits in its layer's header
                                            (villanelle::is_program_code, written::is_variable_name)
    cpp/include/villanelle/<module>.hpp     one header per adapter module (files, extensions)
    cpp/include/villanelle/implementation.hpp   compiled mode: every layer's definitions, compiled once
    cpp/conformance/shapes.hpp              the adapter protocol's spellings and ERROR_GROUP_OF_CLASS
    cpp/tests/generated/api_contract_<layer>.cpp  a use of every public member of one layer (link-checks the hand code)
    cpp/tests/generated/layers_<header>.cpp   the layer-direction check of one public header, from "may import"

Idiom lives here and only here (frozen-m1.md section 4). Layout does not: the output goes through the pinned
clang-format (CLANG_FORMAT) with cpp/.clang-format.

Milestone 1 skeleton: the descriptor is complete as far as the loader's Language takes it today; kinds.hpp is real;
every other file is a placeholder that compiles. Lane A replaces the placeholders and adds the loader hooks the
descriptor needs (frozen-m1.md section 4).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .loader import HEADER, Concept, Formatter, Language, Model, snake

# The pinned clang-format, its one home: tools/parser/gen.py and the hand-code lint use it through LANGUAGE.formatter
# or this tuple, never a version of their own.
CLANG_FORMAT = ("uv", "tool", "run", "--quiet", "--from", "clang-format==21.1.8", "clang-format")


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    """A C++ name is a type, but a free function, which is a value."""
    return "type" if c is None or c.nature != "free function" else "value"


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
        "villanelle error": {"base": "std::runtime_error"},
        "detached error": {"base": "std::logic_error"},
        "argument type error": {"base": "std::logic_error"},
        "misuse error": {"base": "std::invalid_argument"},
        "index out of range": {"base": "std::out_of_range"},
    },
    argument_type_message="{member}(): argument '{parameter}' must be a live object, not {got}",
    modules={"files": "files", "include": "extensions"},  # no fetch adapter (spec 4.3: MAY)
    omit=lambda name, nature: name == "walk control",
    omitted_as=lambda name, nature: "the walk's descend predicate" if name == "walk control" else "none",
    formatter=Formatter((".hpp", ".cpp"), ((*CLANG_FORMAT, "-i", "--style=file:cpp/.clang-format"),)),
)


def head(source: str) -> List[str]:
    return [f"// {HEADER}", f"// Source: {source}."]


def guard(name: str) -> str:
    """The include guard of a generated header: VILLANELLE_<STEM>_HPP (tests/generated/layers.cpp predefines them)."""
    return f"VILLANELLE_{name.upper().replace('.', '_')}"


def header(name: str, source: str, includes: List[str], body: List[str], tail: List[str]) -> str:
    g = guard(name)
    out = [*head(source), f"#ifndef {g}", f"#define {g}", ""]
    out += [f"#include {i}" if i else "" for i in includes]
    out += ["", *body, "", *tail, f"#endif  // {g}", ""]
    return "\n".join(out)


def kinds_header(model: Model) -> str:
    body = ["VILLANELLE_NAMESPACE_BEGIN", ""]
    for k in model.kinds:
        if LANGUAGE.key not in k.languages:
            continue
        values = k.values if k.from_grammar else [snake(v) for v in k.values]
        body.append(f"enum class {snake(k.name)} : std::uint8_t {{ {', '.join(values)} }};")
    body += ["", "VILLANELLE_NAMESPACE_END"]
    return header("kinds.hpp", "spec/schema/api.json kinds", ["<cstdint>", "", "<villanelle/support/config.hpp>"],
                  body, [])


def placeholder(name: str, includes: List[str], namespace: Optional[str], definitions: List[str]) -> str:
    body = ["// PLACEHOLDER (milestone 1 skeleton): Lane A renders this header's declarations.", "VILLANELLE_NAMESPACE_BEGIN"]
    if namespace:
        body += [f"namespace {namespace} {{}}"]
    body += ["VILLANELLE_NAMESPACE_END"]
    tail = ["#if VILLANELLE_HEADER_ONLY", *(f"#include <villanelle/detail/{d}/definitions.hpp>" for d in definitions),
            "#endif", ""] if definitions else []
    return header(name, "spec/schema/api.json", ["<villanelle/support/config.hpp>", *includes], body, tail)


def headers(model: Model) -> Dict[str, List[str]]:
    """Each public header to the detail folders whose definitions it includes: the package's (shared and io layers),
    one per layer with its own namespace, one per adapter module."""
    out: Dict[str, List[str]] = {"villanelle.hpp": [layer.name for layer in model.layers if layer.namespace == "package"]}
    for layer in model.layers:
        if layer.namespace != "package":
            out[f"{layer.name}.hpp"] = [layer.name]
    for path in LANGUAGE.modules.values():
        out[f"{path}.hpp"] = [path]
    return out


def render(model: Model) -> Dict[str, str]:
    files = {"kinds.hpp": kinds_header(model)}
    for name in ("codes.hpp", "limits.hpp", "errors.hpp"):
        files[name] = placeholder(name, [], None, [])
    shared = ["<villanelle/kinds.hpp>", "<villanelle/codes.hpp>", "<villanelle/limits.hpp>", "<villanelle/errors.hpp>"]
    for name, definitions in headers(model).items():
        includes = shared if name == "villanelle.hpp" else ["<villanelle/villanelle.hpp>"]
        namespace = None if name == "villanelle.hpp" else name[: -len(".hpp")]
        files[name] = placeholder(name, includes, namespace, definitions)
    every = [d for definitions in headers(model).values() for d in definitions]
    files["implementation.hpp"] = header(
        "implementation.hpp", "spec/schema/api.json layers",
        ["<villanelle/support/config.hpp>"],
        ["#if VILLANELLE_HEADER_ONLY",
         '#error "<villanelle/implementation.hpp> is for compiled mode: define VILLANELLE_HEADER_ONLY=0"', "#endif",
         "", *(f"#include <villanelle/{name}>" for name in headers(model)),
         "", *(f"#include <villanelle/detail/{d}/definitions.hpp>" for d in every)], [])
    return files


def render_shapes(model: Model) -> Dict[str, str]:
    return {"shapes.hpp": placeholder("shapes.hpp", ["<villanelle/villanelle.hpp>"], None, [])}


def render_contract(model: Model) -> Dict[str, str]:
    files = {}
    for name in headers(model):
        stem = name[: -len(".hpp")]
        for target in (f"api_contract_{stem}.cpp", f"layers_{stem}.cpp"):
            files[target] = "\n".join([*head("spec/schema/api.json"), "// PLACEHOLDER (milestone 1 skeleton).",
                                       f"#include <villanelle/{name}>", ""])
    return files
