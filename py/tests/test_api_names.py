"""The public-name check (spec/codegen.md section 10; frozen-m6.md 2.B): every public module's ``__all__`` equals its
generated ``PUBLIC_NAMES`` entry, both ways (a name the schema lacks, a removed name among them, fails as surely as a
missing one), every listed name exists, and every class with a generated ``MATCH_ARGS`` entry has those
``__match_args__``. Each module is also checked against its generated ``<Module>Functions`` Protocol, by mypy
(modules as protocols, PEP 544): a free function whose signature drifts from the schema is a type error. Members are
checked by mypy too, where each handle class subclasses its generated Protocol."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

import villanelle
from villanelle import files, include, rendered, syntax, written
from villanelle._api.io import FilesFunctions, IoFunctions
from villanelle._api.names import MATCH_ARGS, PUBLIC_NAMES
from villanelle._api.rendered import RenderedFunctions
from villanelle._api.shared import SharedFunctions
from villanelle._api.syntax import SyntaxFunctions
from villanelle._api.written import IncludeFunctions, WrittenFunctions

_shared: SharedFunctions = villanelle
_io: IoFunctions = villanelle
_syntax: SyntaxFunctions = syntax
_written: WrittenFunctions = written
_include: IncludeFunctions = include
_files: FilesFunctions = files
_rendered: RenderedFunctions = rendered


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


# The generator writes these two snapshots as dataclasses whose __match_args__ are every field, not MATCH_ARGS'
# shorter list (a `match_args=False` with an explicit __match_args__ is missing): .claude/errata.md, milestone 6
# Python lane. Strict, so the test fails once the generator is fixed and the mark must go.
GENERATOR_MATCH_ARGS = frozenset({"DirectiveExpansion", "UnreadableExpansion"})


def match_cases() -> list[object]:
    return [
        pytest.param(name, cls, id=name, marks=[pytest.mark.xfail(strict=True)] if name in GENERATOR_MATCH_ARGS else [])
        for name, cls in classes()
    ]


@pytest.mark.parametrize(("name", "cls"), match_cases())
def test_a_class_matches_by_the_generated_fields(name: str, cls: type) -> None:
    assert getattr(cls, "__match_args__", None) == MATCH_ARGS[name]
