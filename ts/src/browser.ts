/**
 * The "villanelle/browser" entry: fetch-based I/O edges.
 */

import { hasGlob } from "./graph/glob.js";
import type { IDocumentSource } from "./source.js";
import type { IDocumentWriter } from "./written/model.js";

/**
 * A document source over fetch. `resolve` resolves a spec as a URL against `context.parentPath` and returns it
 * without fetching; globs resolve to no paths. `read` fetches the URL and rejects on a non-2xx response.
 */
export function createFetchSource(fetchImpl: typeof fetch): IDocumentSource {
  return {
    resolve(spec, context) {
      if (hasGlob(spec)) return Promise.resolve([]);
      // The root path has no parent: it must be a whole URL.
      return Promise.resolve([(context.parentPath === "" ? new URL(spec) : new URL(spec, context.parentPath)).toString()]);
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

/**
 * A writer that sends each file's text to its resolvedPath with fetch: one request per file, in batch order. It
 * rejects on the first failure (a non-2xx response or a rejected fetch), so it is not all-or-nothing: files sent
 * before the failure stay written.
 */
export function createFetchWriter(fetchImpl: typeof fetch, options?: IFetchWriterOptions): IDocumentWriter {
  const method = options?.method ?? "PUT";
  const contentType = options?.contentType ?? "text/plain";
  return {
    async write(files) {
      for (const file of files) {
        const response = await fetchImpl(file.resolvedPath, { method, headers: { "content-type": contentType }, body: file.text });
        if (!response.ok) throw new Error(`${method} ${file.resolvedPath}: HTTP ${String(response.status)}`);
      }
    },
  };
}
