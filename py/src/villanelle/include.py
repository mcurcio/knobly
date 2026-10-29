"""``villanelle.include``: the first-party include extension (R20). ``include "palettes.conf";``, or with this place's
own variables (R22): ``include "palettes.conf" { set $hue 0.3; }``. An included file's top-level ``set`` and
``snippet`` are visible after the include line in the including block (L2)."""

from __future__ import annotations

from collections.abc import Sequence

from villanelle.diagnostics import DiagnosticCode, DiagnosticError
from villanelle.extension import Extension, ExtensionUse
from villanelle.report import LocatedDiagnostic
from villanelle.syntax._recovery import message_of
from villanelle.value import ValueKind, value_error


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
        """D18: exactly one quoted path or glob. E3005 at the first value that breaks that: the first value when it
        is not a string, else the second value; with no value, at the directive's name (F1-05)."""
        code = DiagnosticCode.INCLUDE_BAD_PATH
        if not use.values:
            raise DiagnosticError(LocatedDiagnostic(code, message_of(code), use.origin.place, use.origin.via))
        first = use.values[0]
        bad = first if first.kind is not ValueKind.STRING else (use.values[1] if len(use.values) > 1 else None)
        if bad is not None:
            raise value_error(bad, code, f"{message_of(code)}: {bad.text}")
        return [use.values[0].as_str()]
