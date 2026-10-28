/**
 * Where files come from: the one port the load reads through, for the root file and for every file an extension
 * names (round 11 review finding 3). The core does no I/O (R16): "villanelle/node" and "villanelle/browser" give
 * file and fetch sources; `memorySource` serves texts the program already holds (tests, editors).
 */

import { globToRegExp, hasGlob } from "../graph/glob.js";

/** Where a spec is being resolved from. */
export interface ILoadContext {
  /** resolvedPath of the file holding the extension directive. */
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

/**
 * A source over texts held in memory, keyed by path. `resolve` joins the spec to the directory of `parentPath` with
 * POSIX rules (`/` separators; `.` and `..` segments removed; a spec starting with `/` is taken as is) and returns
 * the path when it is a key; a glob in the last segment returns every key in that directory it matches. `read` of
 * a path that is not a key rejects. Pure: no I/O.
 */
export function memorySource(files: Readonly<Record<string, string>>): IDocumentSource {
  const texts = new Map(Object.entries(files));
  return {
    resolve(spec, context) {
      const path = spec.startsWith("/") ? normalize(spec) : normalize(`${directoryOf(context.parentPath)}${spec}`);
      if (!hasGlob(path)) return Promise.resolve(texts.has(path) ? [path] : []);
      const directory = directoryOf(path);
      const pattern = globToRegExp(path.slice(directory.length));
      return Promise.resolve(
        [...texts.keys()].filter((key) => directoryOf(key) === directory && pattern.test(key.slice(directory.length))),
      );
    },
    read(resolvedPath) {
      const text = texts.get(resolvedPath);
      return text === undefined ? Promise.reject(new Error(`no such file: ${resolvedPath}`)) : Promise.resolve(text);
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
