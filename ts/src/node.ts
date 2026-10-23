/**
 * The "villanelle/node" entry: filesystem I/O edges for Node.js.
 */

import type { DocumentLoader, IDocumentWriter } from "./graph/io.js";

/**
 * A loader over the filesystem. Specs resolve against the directory of `context.parentPath`. A glob (* and ? in
 * the last path segment only) lists that directory and returns every matching file, sorted by compareCodePoints.
 * A missing file without a glob rejects (parseGraph reports E3004).
 */
export function createFsLoader(): DocumentLoader {
  throw new Error("not implemented");
}

/** A writer that replaces the file at resolvedPath with the text, as UTF-8. */
export function createFsWriter(): IDocumentWriter {
  throw new Error("not implemented");
}
