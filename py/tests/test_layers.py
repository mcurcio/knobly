"""The layer check (spec 5, "Layer direction"; owner, 2026-10-29: "The low level shouldn't "depend on" the middle
layer"): no module of the package but the rendered layer itself and the package entry point imports
``villanelle.rendered``, in any form, ``if TYPE_CHECKING:`` blocks included. An allow-list over every module, so an
indirect import through a shared module is caught too (prior art: import-linter's layers contract)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "villanelle"
RENDERED = "villanelle.rendered"


def module_name(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE.parent).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def is_package(path: Path) -> bool:
    return path.name == "__init__.py"


def forbidden_imports(source: str, module: str, *, package: bool) -> list[str]:
    """Every import in ``source`` (the module ``module``) that reaches the rendered layer, relative imports resolved."""
    here = module.split(".") if package else module.split(".")[:-1]
    found: list[str] = []

    def rendered(name: str) -> bool:
        return name == RENDERED or name.startswith(RENDERED + ".")

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if rendered(a.name)]
        elif isinstance(node, ast.ImportFrom):
            base = here[: len(here) - node.level + 1] if node.level else []
            target = ".".join([*base, *([node.module] if node.module else [])])
            if rendered(target) or any(rendered(f"{target}.{a.name}") for a in node.names):
                names = ", ".join(a.name for a in node.names)
                found.append(f"from {'.' * node.level}{node.module or ''} import {names}")
    return found


def governed() -> list[Path]:
    """Every module but the rendered layer and the package entry point (``_api/`` and ``_gen/`` included)."""
    return [
        path
        for path in sorted(PACKAGE.rglob("*.py"))
        if not module_name(path).startswith(RENDERED) and path != PACKAGE / "__init__.py"
    ]


def test_the_check_covers_the_low_level_the_shared_modules_and_the_generated_ones() -> None:
    names = {module_name(path) for path in governed()}
    assert {"villanelle.written.model", "villanelle.written.processor", "villanelle.value"} <= names
    assert {"villanelle._api.kinds", "villanelle.include"} <= names
    assert not any(name.startswith(RENDERED) for name in names)


@pytest.mark.parametrize("path", governed(), ids=lambda path: module_name(path))
def test_no_module_below_the_rendered_layer_imports_it(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert forbidden_imports(source, module_name(path), package=is_package(path)) == []


@pytest.mark.parametrize(
    "line",
    [
        "import villanelle.rendered",
        "import villanelle.rendered._tree as tree",
        "from villanelle.rendered import Rendered",
        "from villanelle.rendered._render import render",
        "from villanelle import rendered",
        "from .. import rendered",
        "from ..rendered import Argument",
        "from ..rendered._tree import Argument",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from villanelle.rendered import Rendered",
    ],
)
def test_the_check_bites_on_a_planted_import(line: str) -> None:
    assert forbidden_imports(line, "villanelle.written.model", package=False) != []


def test_the_check_passes_imports_of_other_layers() -> None:
    source = "from villanelle import value\nfrom . import _bind\nfrom ..origin import Place\nimport villanelle.written"
    assert forbidden_imports(source, "villanelle.written.model", package=False) == []
