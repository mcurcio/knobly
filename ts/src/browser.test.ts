import { describe, expect, it } from "vitest";

import { fetchSource, fetchWriter } from "./browser.js";
import { LostUpdateError } from "./errors.js";
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
    const loaded = await rendered(villanelle({ source: fetchSource(fetchImpl), extensions: [include()] }), "https://h.test/root.conf");
    expect(loaded.diagnostics).toEqual([]);
    expect([...loaded.graph.documents.keys()]).toEqual(["https://h.test/root.conf", "https://h.test/conf/a.conf", "https://h.test/b.conf"]);
    expect(loaded.block.map((d) => d.name)).toEqual(["b"]);
  });

  it("resolves without fetching, resolves a glob to nothing, and rejects a non-2xx read", async () => {
    const { calls, fetchImpl } = fakeFetch({});
    const source = fetchSource(fetchImpl);
    const context = { parentPath: "https://h.test/root.conf" };
    expect(await source.resolve("missing.conf", context)).toEqual(["https://h.test/missing.conf"]);
    expect(await source.resolve("*.conf", context)).toEqual([]);
    expect(calls).toEqual([]);
    await expect(source.read("https://h.test/missing.conf")).rejects.toThrow(/404/);
    expect(calls.map(([url]) => url)).toEqual(["https://h.test/missing.conf"]);
  });

  it("GETs every file first, then writes with PUT text/plain by default, or the given method and content type", async () => {
    const { calls, fetchImpl } = fakeFetch({});
    await fetchWriter(fetchImpl).write([
      { resolvedPath: "https://h.test/a", text: "a;", savedText: "" },
      { resolvedPath: "https://h.test/c", text: "c;", savedText: "" },
    ]);
    await fetchWriter(fetchImpl, { method: "POST", contentType: "text/x-conf" }).write([{ resolvedPath: "https://h.test/b", text: "b;", savedText: "" }]);
    expect(calls).toEqual([
      ["https://h.test/a", undefined],
      ["https://h.test/c", undefined],
      ["https://h.test/a", { method: "PUT", headers: { "content-type": "text/plain" }, body: "a;" }],
      ["https://h.test/c", { method: "PUT", headers: { "content-type": "text/plain" }, body: "c;" }],
      ["https://h.test/b", undefined],
      ["https://h.test/b", { method: "POST", headers: { "content-type": "text/x-conf" }, body: "b;" }],
    ]);
  });

  it("refuses a lost update before sending anything, and sends If-Match on the GET's ETag (spec 4.3)", async () => {
    const calls: Array<[string, RequestInit | undefined]> = [];
    const server: Record<string, string> = { "https://h.test/a": "old;", "https://h.test/b": "theirs;" };
    const fetchImpl = (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
      const url = input instanceof Request ? input.url : input.toString();
      calls.push([url, init]);
      if (init?.method === undefined) return Promise.resolve(new Response(server[url] ?? "", { headers: { etag: `"${url.slice(-1)}1"` } }));
      const match = (init.headers as Record<string, string>)["if-match"];
      return Promise.resolve(new Response("", { status: match === '"a1"' ? 200 : 412 }));
    };
    const lost: unknown = await fetchWriter(fetchImpl)
      .write([
        { resolvedPath: "https://h.test/a", text: "new;", savedText: "old;" },
        { resolvedPath: "https://h.test/b", text: "mine;", savedText: "old;" },
      ])
      .catch((e: unknown) => e);
    expect(lost).toBeInstanceOf(LostUpdateError);
    expect((lost as LostUpdateError).paths).toEqual(["https://h.test/b"]);
    expect(calls.every(([, init]) => init === undefined)).toBe(true);

    calls.length = 0;
    await fetchWriter(fetchImpl).write([{ resolvedPath: "https://h.test/a", text: "new;", savedText: "old;" }]);
    expect(calls[1]).toEqual(["https://h.test/a", { method: "PUT", headers: { "content-type": "text/plain", "if-match": '"a1"' }, body: "new;" }]);

    server["https://h.test/c"] = "old;";
    const raced: unknown = await fetchWriter(fetchImpl)
      .write([{ resolvedPath: "https://h.test/c", text: "new;", savedText: "old;" }])
      .catch((e: unknown) => e);
    expect(raced).toBeInstanceOf(LostUpdateError);
    expect((raced as LostUpdateError).paths).toEqual(["https://h.test/c"]);
  });

  it("rejects on the first failed request, sending none after it", async () => {
    const calls: string[] = [];
    const fetchImpl = (input: string | URL | Request): Promise<Response> => {
      const url = input instanceof Request ? input.url : input.toString();
      calls.push(url);
      return Promise.resolve(new Response("no", { status: url.endsWith("/a") ? 500 : 200 }));
    };
    const writer = fetchWriter(fetchImpl);
    const files = ["a", "b"].map((n) => ({ resolvedPath: `https://h.test/${n}`, text: `${n};`, savedText: "" }));
    await expect(writer.write(files)).rejects.toThrow(/500/);
    expect(calls).toEqual(["https://h.test/a"]);
    calls.length = 0;
    const put = fetchWriter((input, init) => {
      const url = input instanceof Request ? input.url : input.toString();
      calls.push(url);
      return Promise.resolve(new Response("", { status: init?.method === "PUT" && url.endsWith("/a") ? 500 : 404 }));
    });
    await expect(put.write(files)).rejects.toThrow(/PUT https:\/\/h.test\/a: HTTP 500/);
    expect(calls).toEqual(["https://h.test/a", "https://h.test/b", "https://h.test/a"]);
  });
});
