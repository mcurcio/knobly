/**
 * Include glob rules (spec 4.1) shared by the core's bind (W3005 or E3001 for an empty result), memorySource and
 * the document sources of ./node and ./browser. Private to the package.
 */

/** Whether an include spec is a glob: it holds * or ?. */
export function hasGlob(spec: string): boolean {
  return /[*?]/.test(spec);
}

/** A file-name pattern: * matches any run of characters, ? one character, everything else itself. */
export function globToRegExp(pattern: string): RegExp {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${escaped.replace(/\*/g, ".*").replace(/\?/g, ".")}$`, "su");
}
