/**
 * Saving the edited files, and writing a plain string as villanelle text (round 12 design.md §5; slices.md S1).
 * The core does no I/O: the writer is the program's.
 */

import { canonicalString } from "../load/values.js";
import { SaveError } from "./errors.js";
import type { IDocumentGraph, IDocumentWriter, IFileWrite } from "./model.js";

/**
 * Hand every document whose `text` differs from its `source` to the writer in one batch, in `documents` order;
 * with none, the writer is not called. When the writer resolves, each written document's `source` becomes the text
 * handed over (an edit made while the writer ran stays unsaved); when it rejects, no `source` changes.
 * Returns the resolvedPaths handed over.
 * @throws SaveError { files, cause } when the writer rejects
 */
export async function save(graph: IDocumentGraph, writer: IDocumentWriter): Promise<readonly string[]> {
  const files: IFileWrite[] = [];
  for (const doc of graph.documents.values()) {
    if (doc.text !== doc.source) files.push({ resolvedPath: doc.resolvedPath, text: doc.text, source: doc.source });
  }
  if (files.length === 0) return [];
  try {
    await writer.write(files);
  } catch (error) {
    throw new SaveError(`the writer rejected: ${error instanceof Error ? error.message : String(error)}`, files, error);
  }
  for (const file of files) {
    const doc = graph.documents.get(file.resolvedPath);
    if (doc !== undefined) asSaved(doc).markSaved(file.text);
  }
  return files.map((file) => file.resolvedPath);
}

/** The package's document behind an IDocument (only it can take a new `source`). */
function asSaved(doc: object): { markSaved(text: string): void } {
  const internal = doc as Partial<{ markSaved(text: string): void }>;
  if (typeof internal.markSaved !== "function") throw new TypeError("not a document of this package");
  return internal as { markSaved(text: string): void };
}

/**
 * A plain string as a villanelle string, escapes included: `quote("10.0.60.31")` is `"10.0.60.31"`. The same
 * canonical string text a rendered value has (backslash, quote, newline, tab and carriage return escaped).
 */
export function quote(text: string): string {
  return canonicalString(text);
}
