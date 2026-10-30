"""The public-name check (spec/codegen.md section 10): every public module's ``__all__`` equals its generated
``PUBLIC_NAMES`` entry, both ways (a name the schema lacks, a removed name among them, fails as surely as a missing
one), every listed name exists, every class with a generated ``MATCH_ARGS`` entry has those ``__match_args__``, and
every public union holds exactly the exported variant classes of its ``UNIONS`` entry. Signatures are checked by mypy
in ``api_contract`` itself (generated beside this file): its type checker's block assigns each module to its
``<Module>Functions`` Protocol, each constructed class to its ``<Class>Constructor`` and each hand-written public class
to its concept's generated Protocol, so a drifted member fails mypy with no list kept here. The public docs a program
reads in ``help()`` carry no maintainer history (``test_public_docs_carry_no_history``)."""

from __future__ import annotations

import importlib
import inspect
import re
import types
import typing
from pathlib import Path
from types import ModuleType

import pytest
from api_contract import MATCH_ARGS, PUBLIC_NAMES, UNIONS

import villanelle


@pytest.mark.parametrize("path", sorted(PUBLIC_NAMES))
def test_a_module_exports_exactly_its_public_names(path: str) -> None:
    module = importlib.import_module(path)
    assert sorted(module.__all__) == sorted(PUBLIC_NAMES[path])
    assert [name for name in module.__all__ if not hasattr(module, name)] == []


def classes() -> list[tuple[str, type]]:
    """Every exported class with a generated ``MATCH_ARGS`` entry, with the module that exports it."""
    found: dict[str, type] = {}
    for path in PUBLIC_NAMES:
        module: ModuleType = importlib.import_module(path)
        for name in module.__all__:
            obj = getattr(module, name)
            if name in MATCH_ARGS and isinstance(obj, type):
                found[name] = obj
    return sorted(found.items())


def test_every_match_args_entry_names_an_exported_class() -> None:
    assert sorted(name for name, _ in classes()) == sorted(MATCH_ARGS)


def match_cases() -> list[object]:
    return [pytest.param(name, cls, id=name) for name, cls in classes()]


@pytest.mark.parametrize(("name", "cls"), match_cases())
def test_a_class_matches_by_the_generated_fields(name: str, cls: type) -> None:
    assert getattr(cls, "__match_args__", None) == MATCH_ARGS[name]


def exported(name: str) -> object:
    """The one object a public name is: the binding's own class, read through the module that exports it."""
    [path] = [path for path, names in PUBLIC_NAMES.items() if name in names]
    return getattr(importlib.import_module(path), name)


def union_cases() -> list[object]:
    """Each ``UNIONS`` entry with the public alias of that name (the binding's own union over its own classes, or the
    generated one for a union of generated records) and the exported class of each variant."""
    return [
        pytest.param(exported(name), [exported(v) for v in variants], id=name)
        for name, variants in sorted(UNIONS.items())
    ]


@pytest.mark.parametrize(("public", "variants"), union_cases())
def test_a_public_union_has_the_schema_variants(public: object, variants: list[object]) -> None:
    """By identity, not by name: a union over the generated Protocols, or over same-named classes of another module,
    fails."""
    assert isinstance(public, types.UnionType)
    args = typing.get_args(public)
    assert len(args) == len(variants)
    assert all(any(a is v for a in args) for v in variants)


def test_there_are_union_cases() -> None:
    assert len(union_cases()) >= 4  # Statement, WrittenValue, Variable, ExpandedValue at least


def test_no_public_path_but_the_public_modules() -> None:
    """Rule 9: a name is never exported under a second path. Every module under villanelle/ that is not one of
    PUBLIC_NAMES' paths is private (its name, or a package's, starts with ``_``), so ``villanelle.written._model`` is
    plainly not an import path."""
    root = Path(villanelle.__file__).resolve().parent
    public = []
    for path in sorted(root.rglob("*.py")):
        parts = list(path.relative_to(root.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        name = ".".join(parts)
        if name not in PUBLIC_NAMES and not any(p.startswith("_") for p in parts):
            public.append(name)
    assert public == []


# What a public doc may not carry (spec/codegen.md section 3, "Docs and rationale"): it belongs in a comment.
HISTORY = re.compile(r"\bvil-[a-z0-9]{3}(\.[0-9]+)*\b|\bmilestone [0-9]|\bowner, [0-9]{4}-|\bvillanelle\._|\btests/")


def public_docs() -> list[tuple[str, str]]:
    """Every doc ``help()`` shows for a public name: each public module's, each exported object's and, for a class,
    each member it defines itself (an inherited member's doc is checked where it is defined)."""
    found: dict[str, str] = {}
    for path in sorted(PUBLIC_NAMES):
        module = importlib.import_module(path)
        found[path] = module.__doc__ or ""
        for name in sorted(PUBLIC_NAMES[path]):
            obj = getattr(module, name)
            if getattr(obj, "__module__", "").startswith("villanelle"):
                found[f"{path}.{name}"] = inspect.getdoc(obj) or ""
            if isinstance(obj, type) and obj.__module__.startswith("villanelle"):
                for attr, value in vars(obj).items():
                    doc = getattr(value, "__doc__", None)
                    if isinstance(value, (types.FunctionType, property, classmethod, staticmethod)) and doc:
                        found[f"{path}.{name}.{attr}"] = doc
    return sorted(found.items())


def test_public_docs_carry_no_history() -> None:
    bad = [f"{where}: {m.group()!r}" for where, doc in public_docs() if (m := HISTORY.search(doc))]
    assert bad == []


def schema_docs() -> list[tuple[str, str | None, str | None]]:
    """Each public doc that comes from the schema, as (where, what a program reads, what it must be). A hand-written
    class and each member it implements read their generated Protocol's docs; a public function has a doc, which
    ``test_public_functions_take_no_hand_written_doc`` shows is not written in its source (the package gives each its
    ``<Module>Functions`` Protocol's doc at import)."""
    out: list[tuple[str, str | None, str | None]] = []
    for path in sorted(PUBLIC_NAMES):
        module = importlib.import_module(path)
        for name in sorted(PUBLIC_NAMES[path]):
            obj = getattr(module, name)
            here = getattr(obj, "__module__", "") or ""
            if not here.startswith("villanelle.") or here.startswith("villanelle._api."):
                continue
            if inspect.isfunction(obj):
                out.append((f"{path}.{name}", obj.__doc__, None))
                continue
            if not isinstance(obj, type):
                continue
            bases = [b for b in obj.__mro__[1:] if b.__module__.startswith("villanelle._api.")]
            if not bases:
                continue
            out.append((f"{path}.{name}", obj.__doc__, bases[0].__doc__))
            for base in bases:
                for attr, member in vars(base).items():
                    if isinstance(member, (types.FunctionType, property)) and member.__doc__:
                        owner = next(c for c in obj.__mro__ if attr in vars(c))
                        target = vars(owner)[attr]
                        if not owner.__module__.startswith("villanelle._api.") and not isinstance(
                            target, types.MemberDescriptorType
                        ):
                            out.append((f"{path}.{name}.{attr}", target.__doc__, member.__doc__))
    return out


def written_in_source(obj: object, doc: str) -> bool:
    try:
        return doc.splitlines()[0].strip() in inspect.getsource(obj)  # type: ignore[arg-type]
    except (OSError, TypeError):
        return False


def test_public_docs_are_the_schema_docs() -> None:
    """The schema is the one home of each public doc (spec/codegen.md section 3): what ``help()`` shows for a public
    function, class or member is the generated doc, never a hand-written copy, and nothing the schema describes is
    left without one."""
    bad = []
    for where, doc, expected in schema_docs():
        if not doc:
            bad.append(f"{where}: no doc")
        elif expected is not None and doc != expected:
            bad.append(f"{where}: not its Protocol's doc")
    assert bad == []


def test_public_functions_take_no_hand_written_doc() -> None:
    bad = []
    for path in sorted(PUBLIC_NAMES):
        module = importlib.import_module(path)
        for name in sorted(PUBLIC_NAMES[path]):
            obj = getattr(module, name)
            hand = inspect.isfunction(obj) and obj.__module__.startswith("villanelle.")
            if hand and obj.__doc__ and written_in_source(obj, obj.__doc__):
                bad.append(f"{path}.{name}")
    assert bad == []
