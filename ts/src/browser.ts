/**
 * The "villanelle/browser" entry: fetch-based I/O edges.
 */

import { hasGlob } from "./graph/glob.js";
import type { IDocumentWriter } from "./graph/save.js";
import type { IDocumentSource } from "./load/source.js";

/**
 * A document source over fetch. `resolve` resolves a spec as a URL against `context.parentPath` and returns it
 * without fetching; globs resolve to no paths. `read` fetches the URL and rejects on a non-2xx response.
 */
export function createFetchSource(fetchImpl: typeof fetch): IDocumentSource {
  return {
    resolve(spec, context) {
      return Promise.resolve(hasGlob(spec) ? [] : [new URL(spec, context.parentPath).toString()]);
    },
    async read(resolvedPath) {
      const response = await fetchImpl(resolvedPath);
      if (!response.ok) throw new Error(`fetch ${resolvedPath}: HTTP ${String(response.status)}`);
      return response.text();
    },
  };
}

/** Options for createFetchWriter. */
export interface IFetchWriterOptions {
  /** HTTP method. Default "PUT". */
  readonly method?: string;
  /** Content-Type header. Default "text/plain". */
  readonly contentType?: string;
}

/** A writer that sends the text to resolvedPath with fetch. */
export function createFetchWriter(fetchImpl: typeof fetch, options?: IFetchWriterOptions): IDocumentWriter {
  const method = options?.method ?? "PUT";
  const contentType = options?.contentType ?? "text/plain";
  return {
    async write(resolvedPath, source) {
      await fetchImpl(resolvedPath, { method, headers: { "content-type": contentType }, body: source });
    },
  };
}
