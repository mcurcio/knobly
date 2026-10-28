/**
 * The read loop (round 12 slices.md S1; D12, D26): read the root, then whatever the binding names as unread, until
 * nothing new is named. It takes the first unread edge in walk order each time, so files are read in the order
 * PR 3's expansion read them (depth first), each path once (R21), and a rejection is kept, never retried.
 */

import { DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import type { IExtension } from "../load/processor.js";
import type { IDocumentSource } from "../load/source.js";
import { messageOf } from "../syntax/recovery.js";
import { DocumentGraph } from "./graph.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/**
 * Read the root file at `path` (resolved through the source, as an included file's spec is) and every file its
 * include lines name. @throws (rejects) DiagnosticError E3004 at the root path when the source cannot resolve or
 * read it; TypeError for bad handed-in variables (checked first)
 */
export async function loadGraph(
  source: IDocumentSource,
  extensions: ReadonlyMap<string, IExtension>,
  path: string,
  handed: ReadonlyMap<string, string>,
): Promise<DocumentGraph> {
  const graph = new DocumentGraph(extensions, handed);
  const fail = (reason: string): DiagnosticError => {
    const code = DiagnosticCode.IncludeResolverFailed;
    const at = { kind: "file", resolvedPath: path, span: { start: START, end: START } } as const;
    return new DiagnosticError({ code, message: `${messageOf(code)}: ${path}: ${reason}`, at, via: [] });
  };
  // The root is resolved through the source as an included file's spec is (F1-04), so one file has one path.
  let paths: readonly string[];
  try {
    paths = await source.resolve(path, { parentPath: "" });
  } catch (error) {
    throw fail(reasonOf(error));
  }
  const [resolved] = paths;
  if (resolved === undefined || paths.length > 1) {
    throw fail(paths.length === 0 ? "no such file" : `names ${String(paths.length)} files`);
  }
  let text: string;
  try {
    text = await source.read(resolved);
  } catch (error) {
    throw fail(reasonOf(error));
  }
  graph.recordRead(resolved, text);
  await readUnread(graph, source);
  return graph;
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
          paths = await source.resolve(spec, { parentPath: need.parentPath });
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
      if (graph.read(path) !== undefined) continue;
      let text: string | Error;
      try {
        text = await source.read(path);
      } catch (error) {
        text = asError(error);
      }
      graph.recordRead(path, text);
      if (text instanceof Error) break;
      read.push(path);
    }
  }
}

function asError(error: unknown): Error {
  return error instanceof Error ? error : new Error(String(error));
}

function reasonOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
