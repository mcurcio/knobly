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


# --- The second check: the rendered layer builds only on the low level's public API (vil-9fy; spec 7.0) -----------

WRITTEN = "villanelle.written"


def public_written_names() -> frozenset[str]:
    """``villanelle.written.__all__``, read from its source (no import, so the check needs no built package)."""
    tree = ast.parse((PACKAGE / "written" / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            value = ast.literal_eval(node.value)
            assert isinstance(value, list)
            return frozenset(str(name) for name in value)
    raise AssertionError("villanelle.written has no __all__")


def private_reaches(source: str, module: str, *, package: bool, public: frozenset[str]) -> list[str]:
    """Everything in ``source`` (a module of the rendered layer) that reaches the low level other than through
    ``from villanelle.written import <public name>``: a submodule import in any form, a private or unlisted name, an
    attribute starting with one ``_`` on anything but ``self`` or ``cls`` (dunders aside), and ``getattr`` with such a
    literal."""
    here = module.split(".") if package else module.split(".")[:-1]
    found: list[str] = []

    def low(name: str) -> bool:
        return name == WRITTEN or name.startswith(WRITTEN + ".")

    def private(name: str) -> bool:
        return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if low(a.name)]
        elif isinstance(node, ast.ImportFrom):
            base = here[: len(here) - node.level + 1] if node.level else []
            target = ".".join([*base, *([node.module] if node.module else [])])
            line = f"from {'.' * node.level}{node.module or ''} import {', '.join(a.name for a in node.names)}"
            if target == WRITTEN:
                if any(a.name not in public for a in node.names):
                    found.append(line)
            elif low(target) or (target == "villanelle" and any(a.name == "written" for a in node.names)):
                found.append(line)
        elif isinstance(node, ast.Attribute) and private(node.attr):
            if not (isinstance(node.value, ast.Name) and node.value.id in ("self", "cls")):
                found.append(f"{ast.unparse(node)}")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and private(node.args[1].value)
        ):
            found.append(ast.unparse(node))
    return found


def rendered_modules() -> list[Path]:
    return sorted((PACKAGE / "rendered").rglob("*.py"))


def test_the_public_check_covers_every_rendered_module() -> None:
    names = {module_name(path) for path in rendered_modules()}
    assert {"villanelle.rendered", "villanelle.rendered._render", "villanelle.rendered._tree"} <= names


@pytest.mark.parametrize("path", rendered_modules(), ids=lambda path: module_name(path))
def test_the_rendered_layer_reaches_the_low_level_only_through_its_public_api(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    found = private_reaches(source, module_name(path), package=is_package(path), public=public_written_names())
    assert found == []


@pytest.mark.parametrize(
    "line",
    [
        "from villanelle.written import _document",
        "from villanelle.written import _document, _graph",
        "from villanelle.written import NotAPublicName",
        "from villanelle.written._bind import BoundItem",
        "from villanelle.written.model import DocumentGraph",
        "import villanelle.written._graph",
        "import villanelle.written",
        "from villanelle import written",
        "from ..written import _bind",
        "from ..written.model import Statement",
        "from .. import written",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from villanelle.written.model import Statement",
        "doc = statement._doc",
        "x = after._block",
        "directive._freeze()",
        "x = graph._binding().items",
        "x = getattr(statement, '_node')",
    ],
)
def test_the_public_check_bites_on_a_planted_private_reach(line: str) -> None:
    found = private_reaches(line, "villanelle.rendered._render", package=False, public=public_written_names())
    assert found != []


def test_the_public_check_passes_public_imports_and_own_private_state() -> None:
    source = (
        "from villanelle.written import DocumentGraph, WrittenDirective\n"
        "from villanelle.value import ExpandedWord\n"
        "from . import _tree\n"
        "self._block = ()\n"
        "x = cls._made\n"
        "y = after.block.__class__\n"
    )
    found = private_reaches(source, "villanelle.rendered._render", package=False, public=public_written_names())
    assert found == []
