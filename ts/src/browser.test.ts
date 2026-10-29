import { describe, expect, it } from "vitest";

import { createFetchSource, createFetchWriter } from "./browser.js";
import { include } from "./include.js";
import { villanelle } from "./written/processor.js";
import { rendered } from "./rendered/testing.js";

/** A fetch over a map of URL to body that records every call. */
const fakeFetch = (
  pages: Record<string, string>,
): { calls: Array<[string, RequestInit | undefined]>; fetchImpl: typeof fetch } => {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const fetchImpl = (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = input instanceof Request ? input.url : input.toString();
    calls.push([url, init]);
    const body = pages[url];
    const write = init?.method !== undefined && init.method !== "GET";
    return Promise.resolve(body === undefined && !write ? new Response("nope", { status: 404 }) : new Response(body ?? ""));
  };
  return { calls, fetchImpl };
};

describe("villanelle/browser", () => {
  it("loads specs as URLs relative to the including file", async () => {
    const { fetchImpl } = fakeFetch({
      "https://h.test/root.conf": 'include "conf/a.conf";',
      "https://h.test/conf/a.conf": 'include "../b.conf";',
      "https://h.test/b.conf": "b 1;",
    });
    const loaded = await rendered(villanelle({ source: createFetchSource(fetchImpl), extensions: [include()] }), "https://h.test/root.conf");
    expect(loaded.diagnostics).toEqual([]);
    expect([...loaded.graph.documents.keys()]).toEqual(["https://h.test/root.conf", "https://h.test/conf/a.conf", "https://h.test/b.conf"]);
    expect(loaded.block.map((d) => d.name)).toEqual(["b"]);
  });

  it("resolves without fetching, resolves a glob to nothing, and rejects a non-2xx read", async () => {
    const { calls, fetchImpl } = fakeFetch({});
    const source = createFetchSource(fetchImpl);
    const context = { parentPath: "https://h.test/root.conf" };
    expect(await source.resolve("missing.conf", context)).toEqual(["https://h.test/missing.conf"]);
    expect(await source.resolve("*.conf", context)).toEqual([]);
    expect(calls).toEqual([]);
    await expect(source.read("https://h.test/missing.conf")).rejects.toThrow(/404/);
    expect(calls.map(([url]) => url)).toEqual(["https://h.test/missing.conf"]);
  });

  it("writes with PUT text/plain by default, or the given method and content type, one request per file", async () => {
    const { calls, fetchImpl } = fakeFetch({});
    await createFetchWriter(fetchImpl).write([
      { resolvedPath: "https://h.test/a", text: "a;", savedText: "" },
      { resolvedPath: "https://h.test/c", text: "c;", savedText: "" },
    ]);
    await createFetchWriter(fetchImpl, { method: "POST", contentType: "text/x-conf" }).write([{ resolvedPath: "https://h.test/b", text: "b;", savedText: "" }]);
    expect(calls).toEqual([
      ["https://h.test/a", { method: "PUT", headers: { "content-type": "text/plain" }, body: "a;" }],
      ["https://h.test/c", { method: "PUT", headers: { "content-type": "text/plain" }, body: "c;" }],
      ["https://h.test/b", { method: "POST", headers: { "content-type": "text/x-conf" }, body: "b;" }],
    ]);
  });

  it("rejects on the first failed request, sending none after it", async () => {
    const calls: string[] = [];
    const fetchImpl = (input: string | URL | Request): Promise<Response> => {
      const url = input instanceof Request ? input.url : input.toString();
      calls.push(url);
      return Promise.resolve(new Response("no", { status: url.endsWith("/a") ? 500 : 200 }));
    };
    const writer = createFetchWriter(fetchImpl);
    const files = ["a", "b"].map((n) => ({ resolvedPath: `https://h.test/${n}`, text: `${n};`, savedText: "" }));
    await expect(writer.write(files)).rejects.toThrow(/500/);
    expect(calls).toEqual(["https://h.test/a"]);
  });
});
