"""The public-name check (spec/codegen.md, "Milestone 1"): every member spec/schema/api.json lists for a concept
exists on that concept's class, under this binding's casing (snake_case) or the member's "spell", as a property or
a method as the schema says. It also checks the concept classes, the free functions and the error classes the schema
names. It reads the schema directly (no generated copy) and fails the build when a name drifts. The reverse
direction (a public name the schema lacks) is a later milestone."""

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
    """The identifier a binding spelling starts with ("EditError (subclass of ValueError)" -> "EditError")."""
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


def concept_problems(concept: dict[str, Any]) -> list[str]:
    name = leading(concept["py"])
    if not hasattr(villanelle, name):
        return [f"villanelle exports no {name}"]
    variants = classes_of(getattr(villanelle, name))
    out = []
    for member in concept.get("members", []):
        if "py" in member.get("later", {}):  # the schema defers this member here to a later milestone
            continue
        found = {k: problems_on(k, member) for k in variants}
        # A member whose value may be absent may be missing from a variant that never has it (Added has no before).
        if member.get("absent") and len(variants) > 1 and any(not p for p in found.values()):
            continue
        for p in found.values():
            out += p
    return out


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


def group_class(group: dict[str, Any]) -> object:
    name = leading(group["py"])
    return getattr(builtins, name) if hasattr(builtins, name) else getattr(villanelle, name, None)


@pytest.mark.parametrize("group", GROUPS, ids=[g["name"] for g in GROUPS])
def test_error_group(group: dict[str, Any]) -> None:
    cls = group_class(group)
    assert isinstance(cls, type) and issubclass(cls, Exception), f"villanelle exports no exception {group['py']}"
    parent = next((p for p in GROUPS if p["name"] == group.get("parent")), None)
    if parent is not None:
        base = group_class(parent)
        assert isinstance(base, type) and issubclass(cls, base), f"{group['py']} does not extend {parent['py']}"
