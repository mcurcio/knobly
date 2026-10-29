/**
 * The I/O ports (spec/schema/api.json, layer io): where files come from, the one port the load reads through for the
 * root file and for every file an extension names (round 11 review finding 3), and where a save writes them
 * (`IDocumentWriter`, given `IFileWrite`s by `IDocumentGraph.save`). The core does no I/O (R16): "villanelle/node" and
 * "villanelle/browser" give file and fetch sources and writers; `memorySource` and `memoryWriter` serve and keep texts
 * the program already holds (tests, editors). Adapters are named by medium and port (spec/contract.md 5).
 */

import { globToRegExp, hasGlob } from "./graph/glob.js";

/** Where a spec is being resolved from. */
export interface ILoadContext {
  /** resolvedPath of the file holding the extension directive; empty when the root path itself is resolved. */
  readonly parentPath: string;
}

/**
 * The document source. The load calls `read` at most once per resolvedPath, however many places splice the file in
 * (R21: "Obviously the file only needs to be read once").
 */
export interface IDocumentSource {
  /**
   * The resolvedPaths a spec names (a path, or a glob with `*` and `?` in its last segment), in any order; empty
   * means not found (E3001). A rejection becomes E3004 at the extension directive.
   */
  resolve(spec: string, context: ILoadContext): Promise<readonly string[]>;
  /** The text of one resolved file. A rejection becomes E3004 (or, for the root file, rejects the load). */
  read(resolvedPath: string): Promise<string>;
}

/** One file a save hands to the writer. */
export interface IFileWrite {
  readonly resolvedPath: string;
  /** What to write. */
  readonly text: string;
  /** The document's `savedText`: compare it with the disk to find a lost update. */
  readonly savedText: string;
}

/** The program's writer. The core does no I/O. */
export interface IDocumentWriter {
  /**
   * One batch: stage every file, then commit them together. Rejecting while staging means nothing was committed; a
   * writer that can fail part way through committing (the fs writer's renames, the fetch writer's requests) leaves
   * the files it committed changed on disk while their `savedText` stays the old text, so the next save refuses them as
   * lost updates until the program reloads (stated cost, D-F1-10).
   */
  write(files: readonly IFileWrite[]): Promise<void>;
}

/**
 * A source over texts held in memory, keyed by path. It reads `files` itself at every call, never a copy made when it
 * was created, so what a `memoryWriter` over the same object writes, a later load or read sees. `resolve` joins the
 * spec to the directory of `parentPath` with POSIX rules (`/` separators; `.` and `..` segments removed; a spec
 * starting with `/` is taken as is) and returns the path when it is a key; a glob in the last segment returns every
 * key in that directory it matches. `read` of a path that is not a key rejects. Pure: no I/O.
 */
export function memorySource(files: Readonly<Record<string, string>>): IDocumentSource {
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

/**
 * A writer into texts held in memory, keyed by path: the writer of `memorySource`, over the same object. A batch is
 * all or nothing: it first checks that every file's text in `files` (`""` when absent) is still its `savedText`, and
 * rejects naming the lost paths, writing nothing, when one is not (a lost update, as the file writer refuses one);
 * then it sets every file's text.
 */
export function memoryWriter(files: Record<string, string>): IDocumentWriter {
  return {
    write(batch) {
      const lost = batch.filter((file) => (Object.hasOwn(files, file.resolvedPath) ? files[file.resolvedPath] : "") !== file.savedText);
      if (lost.length > 0) {
        return Promise.reject(new Error(`lost update: changed since it was read: ${lost.map((file) => file.resolvedPath).join(", ")}`));
      }
      for (const file of batch) files[file.resolvedPath] = file.text;
      return Promise.resolve();
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
