"""``villanelle.include``: the first-party include extension (R20). ``@include "palettes.conf";``, or with this place's
own variables (R22): ``@include "palettes.conf" { @set $hue 0.3; }``. What an included file sees, and where its own
``@set`` and ``@snippet`` lines are visible, is spec/expansion.md (3, 4 and 7)."""

from __future__ import annotations

from villanelle import _docs
from villanelle._api.codes import DiagnosticCode, describe
from villanelle._api.errors import DiagnosticError
from villanelle._api.written import Extension, ExtensionUse
from villanelle._report import LocatedDiagnostic
from villanelle.written._value import ExpandedString, value_error


def include() -> Extension:
    # The include ordering both bindings share: vil-bgz.1.
    return _Include()


class _Include:
    __slots__ = ()

    @property
    def directive(self) -> str:
        return "include"

    def specs(self, use: ExtensionUse, /) -> tuple[str, ...]:
        """D18: exactly one quoted path or glob. E3005 at the first value that breaks that: the first value when it
        is not a string, else the second value; with no value, at the directive's name (F1-05)."""
        code = DiagnosticCode.INCLUDE_BAD_PATH
        if not use.values:
            raise DiagnosticError(LocatedDiagnostic(code, describe(code).message, use.origin.place, use.origin.via))
        first = use.values[0]
        bad = first if not isinstance(first, ExpandedString) else (use.values[1] if len(use.values) > 1 else None)
        if bad is not None:
            raise value_error(bad, code, describe(code, bad.text).message)
        return (first.string(),)


__all__ = ["include"]

_docs.document(__name__)
