"""``villanelle.include``: the first-party include extension (R20). ``include "palettes.conf";``, or with this place's
own variables (R22): ``include "palettes.conf" { set $hue 0.3; }``. An included file's top-level ``set`` and
``snippet`` are visible after the include line in the including block (L2)."""

from __future__ import annotations

from villanelle.processor import Extension


def include() -> Extension:
    """The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
    matching files are spliced in code-point order of resolved path (vil-bgz.1)."""
    raise NotImplementedError("include")
