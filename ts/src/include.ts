/**
 * The "villanelle/include" entry: the first-party include extension (spec 5). It lives in the low level, which owns
 * expansion (written/include.ts).
 */

import type { IncludeFunctions } from "./gen/api/written.js";
import * as extension from "./written/include.js";

// The public function is typed by its generated signature, which carries the schema's doc.
export const include: IncludeFunctions["include"] = extension.include;
