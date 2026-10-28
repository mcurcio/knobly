import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { include } from "./include.js";
import type { IDirective, KeyRule } from "./load/directive.js";
import { type IKeyOptions, type IRendered, type IProcessor, villanelle } from "./load/processor.js";
import { type IDocumentSource, memorySource } from "./load/source.js";
import { originText as origin, rendered } from "./load/testing.js";

const LOAD = new URL("../../conformance/load/", import.meta.url);
const EXPECTED = new URL("expected/", LOAD);

/** conformance/load/format.md. */
interface ICase {
  readonly name: string;
  readonly needs: readonly string[];
  readonly files: Readonly<Record<string, string>>;
  readonly root: string;
  readonly variables?: Readonly<Record<string, string>>;
  readonly key?: "rasl";
  readonly extensions?: readonly "include"[];
  readonly after?: Readonly<Record<string, string>>;
}

const CASES = JSON.parse(readFileSync(new URL("cases.json", LOAD), "utf8")) as ICase[];

/** The "rasl" key rule of format.md. */
const RASL_KEY: KeyRule = (d) => {
  if (d.name === "node" && d.parent?.name === "graph") return d.args[1]?.text;
  if (d.name === "connect") return d.args.map((a) => a.text).join(" ");
  if (d.name === "fill") return d.args[0]?.text;
  return undefined;
};

function format(loaded: IRendered, key: IKeyOptions, changes: unknown[][] | undefined): string {
  const directives: unknown[] = [];
  const unreadable: unknown[] = loaded.unreadable.map((u) => ["", u.kind, origin(u.origin)]);
  const named = loaded.addresses(key);
  loaded.walk((d: IDirective) => {
    const address = named.get(d)?.toString();
    directives.push([address, d.body !== undefined, origin(d.origin), d.args.map((a) => [a.text, origin(a.origin)])]);
    for (const u of d.unreadable) unreadable.push([address, u.kind, origin(u.origin)]);
  });
  const value: Record<string, unknown> = {
    files: [...loaded.graph.documents.keys()],
    directives,
    unreadable,
    diagnostics: loaded.diagnostics.map((d) => [d.code, origin({ written: d.at, via: d.via })]),
  };
  if (changes !== undefined) value.changes = changes;
  const json = JSON.stringify(value).replace(/[\u0080-￿]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return `${json}\n`;
}

/** One processor for both loads; its source serves whatever `files()` holds at each read. */
function processor(c: ICase, files: () => Readonly<Record<string, string>>): IProcessor {
  const source: IDocumentSource = {
    resolve: (spec, context) => memorySource(files()).resolve(spec, context),
    read: (resolvedPath) => memorySource(files()).read(resolvedPath),
  };
  return villanelle({
    source,
    ...(c.extensions?.includes("include") === true ? { extensions: [include()] } : {}),
  });
}

describe("load conformance (conformance/load/)", () => {
  it.each(CASES.map((c) => [c.name, c] as const))("%s", async (name, c) => {
    const options = c.variables === undefined ? undefined : { variables: c.variables };
    // The second load reads `after`'s texts in place of the first load's; other files are unchanged.
    let files: Readonly<Record<string, string>> = c.files;
    const p = processor(c, () => files);
    const key: IKeyOptions = c.key === "rasl" ? { key: RASL_KEY } : {};
    const first = await rendered(p, c.root, options);
    let changes: unknown[][] | undefined;
    if (c.after !== undefined) {
      files = { ...c.files, ...c.after };
      const second = await rendered(p, c.root, options);
      changes = p.diff(first, second, key).map((change) => [change.kind, change.address.toString()]);
    }
    expect(format(first, key, changes)).toBe(readFileSync(new URL(`${name}.json`, EXPECTED), "utf8"));
  });
});
