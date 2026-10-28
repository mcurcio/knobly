/**
 * The "villanelle/include" entry: the first-party include extension (R20), as postcss-import is a PostCSS plugin.
 * `include "palettes.conf";`, or with this place's own variables (R22): `include "palettes.conf" { set $hue 0.3; }`.
 * An included file's top-level `set` and `snippet` are visible after the include line in the including block (L2).
 */

import { DiagnosticCode, DiagnosticError } from "./diagnostics.js";
import type { IArgument } from "./load/directive.js";
import { codeError } from "./load/locate.js";
import type { IExtension } from "./load/processor.js";
import { messageOf } from "./syntax/recovery.js";
import { ValueKind } from "./value.js";

/**
 * The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
 * matching files are spliced in code-point order of resolvedPath (vil-bgz.1).
 */
export function include(): IExtension {
  return {
    directive: "include",
    specs({ args, origin }) {
      const [path, extra] = args;
      if (path === undefined) {
        const code = DiagnosticCode.IncludeBadPath;
        throw new DiagnosticError({ code, message: messageOf(code), at: origin.written, via: origin.via });
      }
      const bad: IArgument | undefined = path.kind !== ValueKind.String ? path : extra;
      if (bad !== undefined) throw codeError(bad.origin, DiagnosticCode.IncludeBadPath, bad.text);
      return [path.string()];
    },
  };
}
