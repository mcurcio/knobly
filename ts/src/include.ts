/**
 * The "villanelle/include" entry: the first-party include extension (R20), as postcss-import is a PostCSS plugin.
 * `include "palettes.conf";`, or with this place's own variables (R22): `include "palettes.conf" { set $hue 0.3; }`.
 * An included file's top-level `set` and `snippet` are visible after the include line in the including block (L2).
 */

import type { IExtension } from "./load/processor.js";
import { notImplemented } from "./load/todo.js";

/**
 * The include extension. Its one value must be a quoted path or glob (E3005 otherwise, placed on the value);
 * matching files are spliced in code-point order of resolvedPath (vil-bgz.1).
 */
export function include(): IExtension {
  throw notImplemented("include");
}
