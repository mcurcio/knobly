"""Gives each public name its doc from the generated code at import: the mechanism is spec/codegen.md section 3."""

from __future__ import annotations

import importlib
import inspect
import sys

from knobly._api.docs import CONSTRUCTORS, FUNCTIONS

_API = "knobly._api."


def _generated(path: str) -> type:
    """A generated Protocol by its dotted path (imported here, for the module being documented only)."""
    module, _, name = path.rpartition(".")
    found: type = getattr(importlib.import_module(module), name)
    return found


def protocols(cls: type) -> list[type]:
    """The generated classes a hand-written class takes its docs from, nearest first."""
    return [base for base in cls.__mro__[1:] if base.__module__.startswith(_API)]


def _documented(member: object) -> bool:
    return (inspect.isfunction(member) or isinstance(member, property)) and bool(member.__doc__)


def _give(target: object, doc: str | None) -> None:
    if doc is not None and getattr(target, "__doc__", None) is None:
        target.__doc__ = doc


def _give_class(cls: type, doc: str | None) -> None:
    own = cls.__dict__.get("__doc__")
    # A dataclass writes its signature as the doc of a class that has none: that is no hand-written doc.
    if own is None or own == cls.__name__ + str(inspect.signature(cls)).replace(" -> None", ""):
        cls.__doc__ = doc


def document(module: str) -> None:
    """Give the public names of ``module`` (its ``__all__``) the docs of the generated code."""
    namespace = vars(sys.modules[module])
    for path in FUNCTIONS.get(module, ()):
        for name, member in vars(_generated(path)).items():
            if name in namespace and _documented(member):
                _give(namespace[name], member.__doc__)
    for name in namespace["__all__"]:
        cls = namespace[name]
        if not inspect.isclass(cls) or not cls.__module__.startswith("knobly.") or cls.__module__.startswith(_API):
            continue
        bases = protocols(cls)
        if not bases:
            continue
        _give_class(cls, bases[0].__doc__)
        for base in bases:
            for attr, member in vars(base).items():
                if not _documented(member):
                    continue
                owner = next(c for c in cls.__mro__ if attr in vars(c))
                target = vars(owner)[attr]
                # A slot (a frozen dataclass field) cannot hold a doc: its Protocol's property keeps it.
                if not owner.__module__.startswith(_API) and (
                    inspect.isfunction(target) or isinstance(target, property)
                ):
                    _give(target, member.__doc__)
        constructor = CONSTRUCTORS.get(f"{module}.{name}")
        if constructor is not None:
            _give(cls.__init__, _generated(constructor).__call__.__doc__)
