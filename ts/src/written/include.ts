/**
 * The first-party include extension (R20), as postcss-import is a PostCSS plugin; the package entry
 * "villanelle/include" exports it. `@include "palettes.conf";`, or with this place's own variables (R22):
 * `@include "palettes.conf" { @set $hue 0.3; }`. What an included file sees, and where its own `set` and `snippet`
 * lines are visible, is spec/expansion.md.
 */

import { codeError } from "../locate.js";
import { makeLocated } from "../report.js";
import type { ExpandedValue, Extension } from "../gen/api/written.js";
import { DiagnosticCode, describe } from "../gen/api/codes.js";
import { DiagnosticError } from "../gen/api/errors.js";
import { ValueKind } from "../gen/api/kinds.js";

/**
 * The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
 * matching files are spliced in code-point order of resolvedPath.
 */
// The include ordering both bindings share: vil-bgz.1.
export function include(): Extension {
  return {
    directive: "include",
    specs({ values, origin }) {
      const [path, extra] = values;
      if (path === undefined) {
        const code = DiagnosticCode.IncludeBadPath;
        throw new DiagnosticError(makeLocated(code, describe(code).message, origin.place, origin.via));
      }
      const bad: ExpandedValue | undefined = path.kind !== ValueKind.String ? path : extra;
      if (bad !== undefined) throw codeError(bad.origin, DiagnosticCode.IncludeBadPath, bad.text);
      return [path.string()];
    },
  };
}
