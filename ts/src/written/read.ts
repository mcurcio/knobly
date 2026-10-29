/**
 * The read loop (round 12 slices.md S1; D12, D26): read the root, then whatever the binding names as unread, until
 * nothing new is named. It takes the first unread edge in walk order each time, so files are read in the order
 * PR 3's expansion read them (depth first), each path once (R21), and a rejection is kept, never retried.
 */

import { ReadError } from "../errors.js";
import type { IDocumentSource } from "../source.js";
import { typeNameOf } from "../text.js";
import { isTexts } from "./bind.js";
import type { DocumentGraph } from "./graph.js";

/**
 * Read the root file at `path` (resolved through the source, as an included file's spec is) into an empty graph,
 * then every file its include lines name. @throws (rejects) ReadError, `paths` = `[path]`, when the source cannot
 * resolve it to exactly one file (no cause) or rejects resolving or reading it (its rejection as the cause)
 */
export async function readRoot(graph: DocumentGraph, source: IDocumentSource, path: string): Promise<void> {
  const fail = (reason: string, cause?: unknown): ReadError =>
    new ReadError(`cannot read the root file ${path}: ${reason}`, [path], cause === undefined ? undefined : { cause });
  // The root is resolved through the source as an included file's spec is (F1-04), so one file has one path.
  let paths: readonly string[];
  try {
    paths = checkedPaths(await source.resolve(path, { parentPath: "" }));
  } catch (error) {
    throw fail(reasonOf(error), error);
  }
  const [resolved] = paths;
  if (resolved === undefined || paths.length > 1) {
    throw fail(paths.length === 0 ? "the source resolved no file" : `the source resolved ${String(paths.length)} files`);
  }
  let text: string;
  try {
    text = checkedText(await source.read(resolved));
  } catch (error) {
    throw fail(reasonOf(error), error);
  }
  graph.recordRead(resolved, text);
  await readUnread(graph, source);
}

/** Resolve and read what `graph.unread()` names, until nothing new is named. Returns the paths read, in read order. */
export async function readUnread(graph: DocumentGraph, source: IDocumentSource): Promise<readonly string[]> {
  const read: string[] = [];
  for (;;) {
    const binding = graph.binding();
    const [edge] = binding.unread;
    if (edge === undefined) return read;
    const need = binding.needOf(edge);
    if (need === undefined) throw new Error("an unread edge without a need");
    if (need.kind === "resolve") {
      for (const spec of need.specs) {
        if (graph.resolved(need.parentPath, spec) !== undefined) continue;
        let paths: readonly string[] | Error;
        try {
          paths = checkedPaths(await source.resolve(spec, { parentPath: need.parentPath }));
        } catch (error) {
          paths = asError(error);
        }
        graph.recordResolved(need.parentPath, spec, paths);
        // Expansion stops at the first spec that fails: the later ones are not resolved (PR 3's order).
        if (paths instanceof Error || paths.length === 0) break;
      }
      continue;
    }
    for (const path of need.paths) {
      if (graph.readOf(path) !== undefined) continue;
      let text: string | Error;
      try {
        text = checkedText(await source.read(path));
      } catch (error) {
        text = asError(error);
      }
      graph.recordRead(path, text);
      if (text instanceof Error) break;
      read.push(path);
    }
  }
}

/**
 * The source's results are checked at run time (spec 4.1, vil-umh.12): `resolve` gives an array of strings and `read`
 * a string; anything else is the source's failure. @throws Error naming the port and the type it got
 */
function checkedPaths(paths: unknown): readonly string[] {
  if (!isTexts(paths)) throw new Error(`the document source's resolve returned ${typeNameOf(paths)}, not an array of strings`);
  return paths;
}

function checkedText(text: unknown): string {
  if (typeof text !== "string") throw new Error(`the document source's read returned ${typeNameOf(text)}, not a string`);
  return text;
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
