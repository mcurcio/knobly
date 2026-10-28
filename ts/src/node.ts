/**
 * The "villanelle/node" entry: filesystem I/O edges for Node.js.
 */

import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";

import { globToRegExp, hasGlob } from "./graph/glob.js";
import type { IDocumentWriter } from "./graph/save.js";
import type { IDocumentSource } from "./load/source.js";

/**
 * A document source over the filesystem. `read` reads a path as given, as UTF-8; `resolve` joins a spec to the
 * directory of `context.parentPath`; a glob (`*` and `?` in the last path segment only) lists that directory and
 * returns every matching file. A missing file resolves to no paths (E3001).
 */
export function createFileSource(): IDocumentSource {
  return {
    async resolve(spec, context) {
      const path = resolve(dirname(context.parentPath), spec);
      if (!hasGlob(spec)) return (await isFile(path)) ? [path] : [];
      const directory = dirname(path);
      const pattern = globToRegExp(basename(path));
      let entries;
      try {
        entries = await readdir(directory, { withFileTypes: true });
      } catch (error) {
        if (isMissing(error)) return [];
        throw error;
      }
      return entries.filter((entry) => entry.isFile() && pattern.test(entry.name)).map((entry) => resolve(directory, entry.name));
    },
    read(resolvedPath) {
      return readFile(resolvedPath, "utf8");
    },
  };
}

/** Whether `path` names a file; false when nothing is there. Other failures (permissions) reject. */
async function isFile(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isFile();
  } catch (error) {
    if (isMissing(error)) return false;
    throw error;
  }
}

function isMissing(error: unknown): boolean {
  const code = (error as { code?: unknown } | null)?.code;
  return code === "ENOENT" || code === "ENOTDIR";
}

/** A writer that replaces the file at resolvedPath with the text, as UTF-8. */
export function createFsWriter(): IDocumentWriter {
  return {
    async write(resolvedPath, source) {
      await writeFile(resolvedPath, source, "utf8");
    },
  };
}
