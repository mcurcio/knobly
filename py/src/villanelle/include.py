"""``villanelle.include``: the first-party include extension (R20). ``include "palettes.conf";``, or with this place's
own variables (R22): ``include "palettes.conf" { set $hue 0.3; }``. An included file's top-level ``set`` and
``snippet`` are visible after the include line in the including block (L2)."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.directives import value_error
from villanelle.processor import Extension, ExtensionUse
from villanelle.report import LocatedDiagnostic
from villanelle.syntax._recovery import message_of
from villanelle.value import ValueKind


def include() -> Extension:
    """The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
    matching files are spliced in code-point order of resolved path (vil-bgz.1)."""
    return _Include()


class _Include:
    __slots__ = ()

    @property
    def directive(self) -> str:
        return "include"

    def specs(self, use: ExtensionUse, /) -> Sequence[str]:
        """D18: exactly one quoted path or glob. E3005 at the first value that is not a string, else at the second
        value, else (no value) at the directive's name."""
        code = DiagnosticCode.INCLUDE_BAD_PATH
        if not use.args:
            raise DiagnosticError(LocatedDiagnostic(code, message_of(code), use.origin.written, use.origin.via))
        bad = next((arg for arg in use.args if arg.kind is not ValueKind.STRING), None)
        if bad is None and len(use.args) > 1:
            bad = use.args[1]
        if bad is not None:
            raise value_error(bad, code, f"{message_of(code)}: {bad.text}")
        return [use.args[0].as_str()]
