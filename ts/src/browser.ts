/**
 * The "villanelle/browser" entry: fetch-based I/O edges.
 */

import { LostUpdateError } from "./errors.js";
import { hasGlob } from "./graph/glob.js";
import { checkLostUpdates, type IDocumentSource, type IDocumentWriter } from "./source.js";

/**
 * A document source over fetch. `resolve` resolves a spec as a URL against `context.parentPath` and returns it
 * without fetching; globs resolve to no paths. `read` fetches the URL and rejects on a non-2xx response.
 */
export function fetchSource(fetchImpl: typeof fetch): IDocumentSource {
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

/** Options for fetchWriter. */
export interface IFetchWriterOptions {
  /** HTTP method. Default "PUT". */
  readonly method?: string;
  /** Content-Type header. Default "text/plain". */
  readonly contentType?: string;
}

/**
 * A writer that sends each file's text to its resolvedPath with fetch (spec 4.3). First it `GET`s every file and
 * calls `checkLostUpdates` with the bodies (a 404 is absent), so a lost update rejects with a LostUpdateError before
 * anything is sent; then one request per file, in batch order, with the precondition `If-Match: <the GET's ETag>`
 * when the `GET` gave one (RFC 9110 13.1.1): a `412 Precondition Failed` rejects with a LostUpdateError for that file.
 * Without an ETag the window between the `GET` and the write stays open (the server cannot enforce it). It rejects
 * on the first failure (a non-2xx response or a rejected fetch), so it is not all-or-nothing: files sent before the
 * failure stay written.
 */
export function fetchWriter(fetchImpl: typeof fetch, options?: IFetchWriterOptions): IDocumentWriter {
  const method = options?.method ?? "PUT";
  const contentType = options?.contentType ?? "text/plain";
  return {
    async write(files) {
      const current: (string | undefined)[] = [];
      const tags: (string | null)[] = [];
      for (const file of files) {
        const response = await fetchImpl(file.resolvedPath);
        if (response.status === 404) {
          current.push(undefined);
          tags.push(null);
          continue;
        }
        if (!response.ok) throw new Error(`GET ${file.resolvedPath}: HTTP ${String(response.status)}`);
        current.push(await response.text());
        tags.push(response.headers.get("etag"));
      }
      checkLostUpdates(files, current);
      for (const [i, file] of files.entries()) {
        const tag = tags[i];
        const headers: Record<string, string> = { "content-type": contentType, ...(tag == null ? {} : { "if-match": tag }) };
        const response = await fetchImpl(file.resolvedPath, { method, headers, body: file.text });
        if (response.status === 412) throw new LostUpdateError([file.resolvedPath]);
        if (!response.ok) throw new Error(`${method} ${file.resolvedPath}: HTTP ${String(response.status)}`);
      }
    },
  };
}
