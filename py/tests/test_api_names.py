"""The public-name check (spec/codegen.md, "Milestone 1" and "Milestone 2"): every member spec/schema/api.json lists
for a concept exists on that concept's class, under this binding's casing (snake_case) or the member's "spell", as a
property or a method as the schema says. A variant has its union's members, the members of the concept it
``extends`` (and that concept's union's), and its own; its ``kind`` is typed as the schema's one value of its list; its
``__match_args__`` are the schema's ``py match args``. A union's classes are exactly its variants' classes. A concept
with ``py module`` is exported by that module and absent from the package root. The error classes form the schema's
tree. Nothing is skipped. It reads the schema directly (no generated copy) and fails the build when a name drifts.
The reverse direction (a public name the schema lacks) is a later milestone."""

from __future__ import annotations

import builtins
import functools
import importlib
import inspect
import json
import re
import types
import typing
from pathlib import Path
from typing import Any

import pytest

import villanelle

SCHEMA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[2] / "spec" / "schema" / "api.json").read_text(encoding="utf-8")
)
CONCEPTS: list[dict[str, Any]] = SCHEMA["concepts"]
FREE: list[dict[str, Any]] = SCHEMA["free functions"]
GROUPS: list[dict[str, Any]] = SCHEMA["error groups"]

# --- names: binding guide rule 1 and the schema's "spell" ------------------------------------------------------


def snake(name: str) -> str:
    return "_".join(re.split(r"[ -]+", name.strip()))


def leading(text: str) -> str:
    """The identifier a binding spelling starts with ("ReadError (subclass of X)" -> "ReadError")."""
    m = re.match(r"[A-Za-z_]\w*", text)
    assert m is not None, f"no name in {text!r}"
    return m.group()


class Names(typing.NamedTuple):
    names: tuple[str, ...]
    protocol: bool  # spelled as a Python protocol (len(), str(), a Sequence): presence only, not property or method


def names_of(item: dict[str, Any]) -> Names:
    """The attribute names a spec member or function has in Python: snake_case, or what its "spell" says."""
    spell = item.get("spell", {}).get("py")
    if spell is None:
        return Names((snake(item["name"]),), False)
    if m := re.fullmatch(r"(len|str|repr|iter|bool)\(\w+\)", spell):
        return Names((f"__{m.group(1)}__",), True)
    if spell.endswith("is a Sequence"):
        return Names(("__getitem__", "__len__"), True)
    if m := re.fullmatch(r"with \w+\.(\w+)\(\):", spell):
        return Names((m.group(1),), False)
    if re.match(r"[A-Za-z_]\w*[\[<]", spell):  # a type spelling ("Mapping[str, str]") keeps the name's casing
        return Names((snake(item["name"]),), False)
    if m := re.fullmatch(r"([A-Za-z_]\w*)(?:\(.*|\s+\(.*)?", spell, re.S):
        return Names((m.group(1),), m.group(1).startswith("__"))
    raise AssertionError(f"api-names: cannot read the Python spell {spell!r} of {item['name']}")


# --- classes ---------------------------------------------------------------------------------------------------

_ANNOTATED = object()


def classes_of(obj: object) -> list[type]:
    """A class, or each class of a union alias (``Statement = WrittenDirective | ...``)."""
    if isinstance(obj, type):
        return [obj]
    value = getattr(obj, "__value__", obj)  # a `type X = ...` alias
    args = typing.get_args(value)
    if args and all(isinstance(a, type) for a in args):
        return list(args)
    raise AssertionError(f"{obj!r} is neither a class nor a union of classes")


def lookup(klass: type, name: str) -> object | None:
    """What `klass` defines for `name` (its MRO, `object` aside); an annotation-only field counts as a property."""
    for k in klass.__mro__:
        if k is object:
            continue
        if name in vars(k):
            found: object = vars(k)[name]
            return found
        if name in inspect.get_annotations(k):
            return _ANNOTATED
    return None


def is_method(value: object) -> bool:
    return isinstance(value, (types.FunctionType, staticmethod, classmethod, functools.partialmethod))


def problems_on(klass: type, member: dict[str, Any]) -> list[str]:
    want = names_of(member)
    out = []
    for name in want.names:
        value = lookup(klass, name)
        if value is None:
            out.append(f"{klass.__name__}: {member['name']}: no {member['member']} {name}")
        elif want.protocol:
            continue
        elif member["member"] == "method" and not is_method(value):
            out.append(f"{klass.__name__}: {member['name']}: {name} is a property; the schema says a method")
        elif member["member"] == "property" and is_method(value):
            out.append(f"{klass.__name__}: {member['name']}: {name} is a method; the schema says a property")
    return out


BY_NAME: dict[str, dict[str, Any]] = {c["name"]: c for c in CONCEPTS}


def module_for(concept: dict[str, Any]) -> types.ModuleType:
    return importlib.import_module(concept.get("py module", "villanelle"))


def members_of(concept: dict[str, Any]) -> list[dict[str, Any]]:
    """Its own members, its union's, and those of the concept it extends (transitively)."""
    out = list(concept.get("members", []))
    for parent in (concept.get("variant of"), concept.get("extends")):
        if parent is not None:
            out += members_of(BY_NAME[parent])
    return out


def kind_value(klass: type) -> str:
    """The one value a variant's ``kind`` is typed as: the ``Literal`` its property returns."""
    prop = lookup(klass, "kind")
    assert isinstance(prop, property) and prop.fget is not None, f"{klass.__name__}: kind is not a property"
    hint = typing.get_type_hints(prop.fget)["return"]
    assert typing.get_origin(hint) is typing.Literal, f"{klass.__name__}: kind is typed {hint}, not a Literal"
    (value,) = typing.get_args(hint)
    return str(value.value)


def concept_problems(concept: dict[str, Any]) -> list[str]:
    name = leading(concept["py"])
    module = module_for(concept)
    if not hasattr(module, name):
        return [f"{module.__name__} exports no {name}"]
    variants = classes_of(getattr(module, name))
    out = [p for k in variants for member in members_of(concept) for p in problems_on(k, member)]
    if "py module" in concept and hasattr(villanelle, name):
        out.append(f"{name} is exported by the package root; the schema says {concept['py module']} only")
    if "variants" in concept:
        want = {leading(BY_NAME[v]["py"]) for v in concept["variants"]}
        if {k.__name__ for k in variants} != want:
            out.append(f"{name} is {sorted(k.__name__ for k in variants)}; the schema's variants are {sorted(want)}")
    if "kind" in concept:
        (klass,) = variants
        if kind_value(klass) != concept["kind"]:
            out.append(f"{name}.kind is {kind_value(klass)!r}; the schema says {concept['kind']!r}")
    if "py match args" in concept:
        (klass,) = variants
        want_args = tuple(snake(arg) for arg in concept["py match args"])
        if getattr(klass, "__match_args__", None) != want_args:
            out.append(f"{name}.__match_args__ is {getattr(klass, '__match_args__', None)}; the schema: {want_args}")
    return out


def test_every_kind_list_with_variants_maps_each_value_to_its_concept() -> None:
    for list_name, kinds in SCHEMA["kinds"].items():
        for value, concept in kinds.get("variants", {}).items():
            assert BY_NAME[concept].get("kind") == value, f"{list_name}: {value} -> {concept}"


@pytest.mark.parametrize("concept", CONCEPTS, ids=[c["name"] for c in CONCEPTS])
def test_concept(concept: dict[str, Any]) -> None:
    assert concept_problems(concept) == []


def module_of(spell: str | None) -> str:
    """The module a free function's spell names ("... from villanelle.files"), else the package."""
    m = re.search(r"\bfrom (villanelle(?:\.\w+)*)\b", spell or "")
    return m.group(1) if m else "villanelle"


SPELLED_FREE = [f for f in FREE if f.get("spell", {}).get("py") != "absent"]


@pytest.mark.parametrize("function", SPELLED_FREE, ids=[f["name"] for f in SPELLED_FREE])
def test_free_function(function: dict[str, Any]) -> None:
    spell = function.get("spell", {}).get("py")
    module = importlib.import_module(module_of(spell))
    (name,) = names_of(function).names
    assert callable(getattr(module, name, None)), f"{module.__name__} has no {name}"


def named_class(name: str) -> object:
    return getattr(builtins, name) if hasattr(builtins, name) else getattr(villanelle, name, None)


def group_class(group: dict[str, Any]) -> object:
    return named_class(leading(group["py"]))


@pytest.mark.parametrize("group", GROUPS, ids=[g["name"] for g in GROUPS])
def test_error_group(group: dict[str, Any]) -> None:
    cls = group_class(group)
    assert isinstance(cls, type) and issubclass(cls, Exception), f"villanelle exports no exception {group['py']}"
    parent = next((p for p in GROUPS if p["name"] == group.get("parent")), None)
    if parent is not None:
        base = group_class(parent)
        assert isinstance(base, type) and issubclass(cls, base), f"{group['py']} does not extend {parent['py']}"
    # "DetachedError (subclass of ReferenceError, ...)": every class the spelling names is a base.
    if m := re.search(r"\(subclass of ([^)]*)\)", group["py"]):
        for base_name in re.split(r"\s+and\s+", m.group(1).split(",")[0]):
            base = named_class(base_name.strip())
            assert isinstance(base, type) and issubclass(cls, base), f"{group['py']} is not a {base_name}"
