"""The public-name check (spec/codegen.md section 10): every public module's ``__all__`` equals its generated
``PUBLIC_NAMES`` entry, both ways (a name the schema lacks, a removed name among them, fails as surely as a missing
one), every listed name exists, every class with a generated ``MATCH_ARGS`` entry has those ``__match_args__``, and
every public union holds exactly the variant classes of its ``UNIONS`` entry. Each module is also checked against its
generated ``<Module>Functions`` Protocol, by mypy (modules as protocols, PEP 544): a free function whose signature
drifts from the schema is a type error. Members are checked by mypy too, where each handle class subclasses its
generated Protocol. All of these come from ``api_contract`` (generated beside this file), which names every type
through its public module."""

from __future__ import annotations

import importlib
import types
import typing
from pathlib import Path
from types import ModuleType

import pytest
from api_contract import (
    MATCH_ARGS,
    PUBLIC_NAMES,
    UNIONS,
    DiagnosticsConstructor,
    FilesFunctions,
    IncludeFunctions,
    IoFunctions,
    ProcessorConstructor,
    RenderedFunctions,
    SharedFunctions,
    SyntaxFunctions,
    WrittenFunctions,
)

import villanelle
from villanelle import files, include, rendered, syntax, written

_shared: SharedFunctions = villanelle
_io: IoFunctions = villanelle
_syntax: SyntaxFunctions = syntax
_written: WrittenFunctions = written
_include: IncludeFunctions = include
_files: FilesFunctions = files
_rendered: RenderedFunctions = rendered
# A class a program constructs is checked against its generated constructor (the schema's constructor factory).
_diagnostics: DiagnosticsConstructor = villanelle.Diagnostics
_processor: ProcessorConstructor = written.Processor


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


def union_cases() -> list[object]:
    """Each ``UNIONS`` entry with the public alias of that name (the binding's own union over its own classes, or the
    generated one for a union of generated records)."""
    cases: list[object] = []
    for name, variants in sorted(UNIONS.items()):
        [path] = [path for path, names in PUBLIC_NAMES.items() if name in names]
        cases.append(pytest.param(getattr(importlib.import_module(path), name), variants, id=f"{path}.{name}"))
    return cases


@pytest.mark.parametrize(("public", "variants"), union_cases())
def test_a_public_union_has_the_schema_variants(public: object, variants: tuple[str, ...]) -> None:
    assert isinstance(public, types.UnionType)
    assert sorted(t.__name__ for t in typing.get_args(public)) == sorted(variants)


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
