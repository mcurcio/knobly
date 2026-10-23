/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * The "villanelle/browser" entry: fetch-based I/O edges.
 */

import type { DocumentLoader, IDocumentWriter } from "./graph/io.js";

/** Options for createFetchWriter. */
export interface IFetchWriterOptions {
  /** HTTP method. Default "PUT". */
  readonly method?: string;
  /** Content-Type header. Default "text/plain". */
  readonly contentType?: string;
}

/**
 * A loader over fetch. Specs resolve as URLs against `context.parentPath`. Globs are not supported (they return
 * no documents); a non-2xx response returns no documents.
 */
export function createFetchLoader(fetchImpl: typeof fetch): DocumentLoader {
  throw new Error("not implemented");
}

/** A writer that sends the text to resolvedPath with fetch. */
export function createFetchWriter(fetchImpl: typeof fetch, options?: IFetchWriterOptions): IDocumentWriter {
  throw new Error("not implemented");
}
