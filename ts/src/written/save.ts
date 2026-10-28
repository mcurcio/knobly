/**
 * Saving the edited files, and writing a plain string as villanelle text (round 12 design.md §5; slices.md S1).
 * The core does no I/O: the writer is the program's.
 */

import type { IDocumentGraph, IDocumentWriter } from "./model.js";

/**
 * Hand every document whose `text` differs from its `source` to the writer in one batch, in `documents` order;
 * with none, the writer is not called. When the writer resolves, each written document's `source` becomes the text
 * handed over (an edit made while the writer ran stays unsaved); when it rejects, no `source` changes.
 * Returns the resolvedPaths handed over.
 * @throws SaveError { files, cause } when the writer rejects
 */
export function save(graph: IDocumentGraph, writer: IDocumentWriter): Promise<readonly string[]> {
  void graph;
  void writer;
  return Promise.reject(new Error("not implemented: save (slices.md S1)"));
}

/**
 * A plain string as a villanelle string, escapes included: `quote("10.0.60.31")` is `"10.0.60.31"`. The same
 * canonical string text a rendered value has (backslash, quote, newline, tab and carriage return escaped).
 */
export function quote(text: string): string {
  void text;
  throw new Error("not implemented: quote (slices.md S1)");
}
