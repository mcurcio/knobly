"""A third binding in miniature: the proof that a new binding is an emitter and an adapter, with no schema edit
(spec/codegen.md section 10). ``tools/gen-api.py --check`` builds the model with this Language beside the real ones and
renders its names list; it fails if the schema names a language, or holds a fact only the two real bindings supply.

Its facts are made up (a language called Toylang, ``::`` between module parts, two classes of its own): they stand for what a
real emitter states about its language. Nothing is written to disk."""

from __future__ import annotations

from typing import Dict, Optional

from .loader import Concept, Language, Model, snake


def _public_kind(model: Model, c: Optional[Concept]) -> str:
    return "value"


LANGUAGE = Language(
    key="toy",
    name="Toylang",
    sep="::",
    function_case=snake,
    public_kind=_public_kind,
    error_roots={
        "villanelle error": {"base": "Failure"},
        "detached error": {"base": "Failure"},
        "misuse error": {"base": "Failure"},
        "argument type error": {"builtin": "TypeFailure"},  # a group with no message of its own is the language's class
        "index out of range": {"builtin": "RangeFailure"},
    },
    argument_type_message="{member}: {parameter} wants text, got {got}",
    modules={"files": "disk"},  # no fetch or include adapter: their functions and concepts are left out
)


def render(model: Model) -> Dict[str, str]:
    """The binding's public names, one ``module name`` a line: the smallest thing an emitter renders."""
    return {"names.txt": "".join(f"{module} {name}\n" for module, name, _ in model.public(LANGUAGE.key))}
