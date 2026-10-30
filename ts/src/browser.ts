/**
 * The "villanelle/browser" entry: fetch-based I/O edges.
 */

import type { BrowserFunctions, FetchWriterOptions } from "./gen/api/io.js";
import { hasGlob } from "./graph/glob.js";
import { checkLostUpdates } from "./source.js";
import { LostUpdateError } from "./gen/api/errors.js";

export type { FetchWriterOptions };

export const fetchSource: BrowserFunctions["fetchSource"] = (fetchImpl) => {
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
};

export const fetchWriter: BrowserFunctions["fetchWriter"] = (fetchImpl, options) => {
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
};
