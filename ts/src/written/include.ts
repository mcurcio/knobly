/**
 * The first-party include extension (R20), as postcss-import is a PostCSS plugin; the package entry
 * "villanelle/include" exports it. `include "palettes.conf";`, or with this place's own variables (R22):
 * `include "palettes.conf" { set $hue 0.3; }`. What an included file sees, and where its own `set` and `snippet`
 * lines are visible, is spec/expansion.md.
 */

import { DiagnosticCode, messageOf } from "../diagnostics.js";
import { DiagnosticError } from "../errors.js";
import { codeError } from "../locate.js";
import { makeLocated } from "../report.js";
import type { IExtension } from "./extension.js";
import type { ExpandedValue } from "./value.js";

/**
 * The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
 * matching files are spliced in code-point order of resolvedPath (vil-bgz.1).
 */
export function include(): IExtension {
  return {
    directive: "include",
    specs({ values, origin }) {
      const [path, extra] = values;
      if (path === undefined) {
        const code = DiagnosticCode.IncludeBadPath;
        throw new DiagnosticError(makeLocated(code, messageOf(code), origin.place, origin.via));
      }
      const bad: ExpandedValue | undefined = path.kind !== "string" ? path : extra;
      if (bad !== undefined) throw codeError(bad.origin, DiagnosticCode.IncludeBadPath, bad.text);
      return [path.string()];
    },
  };
}
