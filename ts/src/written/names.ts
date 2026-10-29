/**
 * The name checks (spec 2.8, vil-umh.7): every bad name a program passes is a misuse error, through one check per
 * kind of name, the same from every member that takes one. Package-internal.
 */

import { MisuseError } from "../errors.js";
import { RESERVED, VARIABLE_NAME } from "../gen/api/limits.js";
import { parseEntry } from "../syntax/parse.js";

/**
 * A variable or override name, without `$`: `load`'s override names, `setOverride` and a variable's `rename`.
 * @throws MisuseError unless it matches the variable name pattern (letters, digits and `_`)
 */
export function checkVariableName(name: string): void {
  if (!VARIABLE_NAME.test(name)) throw new MisuseError(`not a variable name (letters, digits and _): ${JSON.stringify(name)}`);
}

/**
 * A directive's new name (`rename`): what the grammar's `nameText` entry rule takes (one word that does not start
 * with a digit or `-`), and not a name that would change the line's kind (a reserved word or a registered
 * extension's name). @throws MisuseError otherwise
 */
export function checkDirectiveName(name: string, extensionNames: ReadonlySet<string>): void {
  if (parseEntry(name, "nameText").diagnostics.length > 0) throw new MisuseError(`not a directive name: ${JSON.stringify(name)}`);
  if (RESERVED.has(name) || extensionNames.has(name)) {
    throw new MisuseError(`a directive cannot be renamed to ${JSON.stringify(name)}: the name would change its kind`);
  }
}
