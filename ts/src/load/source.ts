/**
 * Where files come from: the one port the load reads through, for the root file and for every file an extension
 * names (round 11 review finding 3). The core does no I/O (R16): "villanelle/node" and "villanelle/browser" give
 * file and fetch sources; `memorySource` serves texts the program already holds (tests, editors).
 */

import { notImplemented } from "./todo.js";

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
  throw notImplemented("memorySource", files);
}
