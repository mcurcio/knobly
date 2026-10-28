/**
 * The "villanelle/node" entry: filesystem I/O edges for Node.js.
 */

import { randomBytes } from "node:crypto";
import { readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { globToRegExp, hasGlob } from "./graph/glob.js";
import type { IDocumentSource } from "./load/source.js";
import type { IDocumentWriter } from "./written/model.js";

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

/**
 * One batch on disk (D18): reads each target first and rejects, writing nothing, when one no longer holds its
 * `source` (a lost update; the Error names the paths; a missing file holds ""); else writes each text, as UTF-8, to
 * a temporary file beside its target (`<name>.<random>.tmp`), then renames each over its target in batch order. A
 * failure while staging removes the temporaries and rejects with nothing replaced; a failure while renaming can
 * leave earlier files replaced (stated cost) and removes the temporaries not yet renamed.
 */
export function createFsWriter(): IDocumentWriter {
  return {
    async write(files) {
      const lost: string[] = [];
      for (const file of files) {
        if ((await readOrEmpty(file.resolvedPath)) !== file.source) lost.push(file.resolvedPath);
      }
      if (lost.length > 0) throw new Error(`lost update: changed on disk since it was read: ${lost.join(", ")}`);
      const staged: { readonly temporary: string; readonly target: string }[] = [];
      const removeLeft = async (from: number): Promise<void> => {
        await Promise.all(staged.slice(from).map(({ temporary }) => rm(temporary, { force: true })));
      };
      try {
        for (const file of files) {
          const temporary = join(dirname(file.resolvedPath), `${basename(file.resolvedPath)}.${randomBytes(6).toString("hex")}.tmp`);
          staged.push({ temporary, target: file.resolvedPath });
          await writeFile(temporary, file.text, { encoding: "utf8", flag: "wx" });
        }
      } catch (error) {
        await removeLeft(0);
        throw error;
      }
      for (const [i, { temporary, target }] of staged.entries()) {
        try {
          await rename(temporary, target);
        } catch (error) {
          await removeLeft(i);
          throw error;
        }
      }
    },
  };
}

/** A file's text, or "" when nothing is there. Other failures reject. */
async function readOrEmpty(path: string): Promise<string> {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    if (isMissing(error)) return "";
    throw error;
  }
}
