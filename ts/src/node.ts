/**
 * The "villanelle/node" entry: filesystem I/O edges for Node.js.
 */

import { randomBytes } from "node:crypto";
import { readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import { globToRegExp, hasGlob } from "./graph/glob.js";
import { checkLostUpdates } from "./source.js";
import type { NodeFunctions } from "./gen/api/io.js";

export const fileSource: NodeFunctions["fileSource"] = () => {
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
};

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

export const fileWriter: NodeFunctions["fileWriter"] = () => {
  return {
    async write(files) {
      const current: (string | undefined)[] = [];
      for (const file of files) current.push(await readIfThere(file.resolvedPath));
      checkLostUpdates(files, current);
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
};

/** A file's text, or undefined when nothing is there. Other failures reject. */
async function readIfThere(path: string): Promise<string | undefined> {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    if (isMissing(error)) return undefined;
    throw error;
  }
}
