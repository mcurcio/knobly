/**
 * The I/O ports (spec/schema/api.json, layer io): where files come from, the one port the load reads through for the
 * root file and for every file an extension names (round 11 review finding 3), and where a save writes them
 * (`DocumentWriter`, given `FileWrite`s by `DocumentGraph.save`; the types are generated, gen/api/io.ts). The core does no I/O (R16): "villanelle/node" and
 * "villanelle/browser" give file and fetch sources and writers; `memorySource` and `memoryWriter` serve and keep texts
 * the program already holds (tests, editors). Adapters are named by medium and port (spec/contract.md 5). Every
 * writer refuses a lost update through the one check, `checkLostUpdates` (spec 4.2).
 */

import type { DocumentSource, DocumentWriter, FileWrite } from "./gen/api/io.js";
import { globToRegExp, hasGlob } from "./graph/glob.js";
import { LostUpdateError, MisuseError } from "./gen/api/errors.js";

export function memorySource(files: Readonly<Record<string, string>>): DocumentSource {
  const has = (path: string): boolean => Object.hasOwn(files, path);
  return {
    resolve(spec, context) {
      const path = spec.startsWith("/") ? normalize(spec) : normalize(`${directoryOf(context.parentPath)}${spec}`);
      if (!hasGlob(path)) return Promise.resolve(has(path) ? [path] : []);
      const directory = directoryOf(path);
      const pattern = globToRegExp(path.slice(directory.length));
      return Promise.resolve(
        Object.keys(files).filter((key) => directoryOf(key) === directory && pattern.test(key.slice(directory.length))),
      );
    },
    read(resolvedPath) {
      const text = has(resolvedPath) ? files[resolvedPath] : undefined;
      return text === undefined ? Promise.reject(new Error(`no such file: ${resolvedPath}`)) : Promise.resolve(text);
    },
  };
}

export function checkLostUpdates(files: readonly FileWrite[], current: readonly (string | undefined)[]): void {
  if (current.length !== files.length) {
    throw new MisuseError(`checkLostUpdates: ${files.length} files but ${current.length} current texts`);
  }
  const lost = files.filter((file, i) => (current[i] ?? "") !== file.savedText).map((file) => file.resolvedPath);
  if (lost.length > 0) throw new LostUpdateError(lost);
}

export function memoryWriter(files: Record<string, string>): DocumentWriter {
  return {
    // eslint-disable-next-line @typescript-eslint/require-await -- async so a lost update rejects instead of throwing
    async write(batch) {
      checkLostUpdates(batch, batch.map((file) => (Object.hasOwn(files, file.resolvedPath) ? files[file.resolvedPath] : undefined)));
      for (const file of batch) files[file.resolvedPath] = file.text;
    },
  };
}

/** Everything up to and including the last `/`; empty for a bare name. */
function directoryOf(path: string): string {
  return path.slice(0, path.lastIndexOf("/") + 1);
}

/** POSIX rules: `.` segments and empty segments dropped, each `..` removes the segment before it when there is one. */
function normalize(path: string): string {
  const out: string[] = [];
  for (const segment of path.split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === ".." && out.length > 0 && out.at(-1) !== "..") out.pop();
    else out.push(segment);
  }
  return `${path.startsWith("/") ? "/" : ""}${out.join("/")}`;
}
