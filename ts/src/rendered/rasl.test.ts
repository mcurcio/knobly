/**
 * rasl acceptance: rasl's real configs (fixtures/rasl/) load through the file source and the include extension,
 * with an override variable, and a `$pixels` edit gives the expected change list under rasl's key rule.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { fileSource } from "../node.js";
import type { IDirective, IRendered, KeyRule } from "./model.js";
import { villanelle, type WrittenValue } from "../written/index.js";
import type { IDocumentSource } from "../source.js";
import { rendered } from "./testing.js";
import { text } from "../text.js";

const FIXTURES = new URL("../../../fixtures/rasl/", import.meta.url);

interface IExpected {
  readonly nodes: readonly string[];
  readonly diagnostics: readonly unknown[];
  readonly changes: readonly (readonly [string, string])[];
}

const EXPECTED = JSON.parse(readFileSync(new URL("expected.json", FIXTURES), "utf8")) as Record<string, IExpected>;

/** The "rasl" key rule of conformance/keys.json. */
const RASL_KEY: KeyRule = (d) => {
  if (d.name === "node" && d.parent?.name === "graph") return d.values[1]?.text;
  if (d.name === "connect") return d.values.map((a) => a.text).join(" ");
  if (d.name === "fill") return d.values[0]?.text;
  return undefined;
};

/** The file source, with `@set $pixels 2284;` read as `2400` once `edited` is set. */
function source(): { source: IDocumentSource; edit: () => void } {
  const files = fileSource();
  let edited = false;
  return {
    edit: () => {
      edited = true;
    },
    source: {
      resolve: (spec, context) => files.resolve(spec, context),
      read: async (path) => {
        const text = await files.read(path);
        return edited ? text.replace("@set $pixels 2284;", "@set $pixels 2400;") : text;
      },
    },
  };
}

function nodeIds(loaded: IRendered): string[] {
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.values[1]?.text ?? "");
  });
  return ids;
}

const OVERRIDES = { leds_host: text('"10.0.70.1"') };

describe("rasl's configs", () => {
  it.each(Object.keys(EXPECTED))("%s loads with the expected nodes and reload changes", async (name) => {
    const expected = EXPECTED[name] as IExpected;
    const { source: files, edit } = source();
    const processor = villanelle({ source: files, extensions: [include()] });
    const path = fileURLToPath(new URL(name, FIXTURES));
    const options = { overrides: OVERRIDES };
    const first = await rendered(processor, path, options);
    expect(first.diagnostics).toEqual(expected.diagnostics);
    expect(nodeIds(first)).toEqual(expected.nodes);
    edit();
    const second = await rendered(processor, path, options);
    expect(first.diff(second, { key: RASL_KEY }).map((c) => [c.kind, c.address.toString()])).toEqual(expected.changes);
  });

  it("splits one sink file over two places, each with its own include-block values and the override host", async () => {
    const processor = villanelle({ source: fileSource(), extensions: [include()] });
    const path = fileURLToPath(new URL("split/main.conf", FIXTURES));
    const loaded = await rendered(processor, path, { overrides: OVERRIDES });
    const targets: [string, string][] = [];
    const named = loaded.addresses({ key: RASL_KEY });
    loaded.walk((d) => {
      if (d.name === "target") targets.push([named.get(d)?.toString() ?? "", d.values[0]?.text ?? ""]);
    });
    expect(targets).toEqual([
      ['graph > node "leds" > target', '"10.0.70.1"'],
      ['graph > node "porch" > target', '"10.0.60.31"'],
    ]);
    expect([...loaded.graph.documents.keys()]).toEqual([path, fileURLToPath(new URL("split/sink.conf", FIXTURES))]);
    expect(loaded.graph.edges()).toHaveLength(2);
    // Without the override, the file's own default is used.
    const plain = await rendered(processor, path);
    let host = "";
    plain.walk((d) => {
      if (d.name === "target" && host === "") host = d.values[0]?.text ?? "";
    });
    expect(host).toBe('"10.0.60.30"');
  });

  it("edits a line an included file shares between two copies with the natural loop: one handle, set twice", async () => {
    const processor = villanelle({ source: fileSource(), extensions: [include()] });
    const path = fileURLToPath(new URL("split/main.conf", FIXTURES));
    const loaded = await rendered(processor, path);
    // sink.conf is included twice: both rendered `max_count`s share the one written `$pixels` of its line, and a
    // value's `set` keeps its handle (spec 6.1), so setting it through each copy just writes again.
    const written: WrittenValue[] = [];
    loaded.walk((d) => {
      const arg = d.values[0];
      if (d.name !== "max_count" || arg === undefined) return;
      written.push(arg.written);
      arg.written.set(text("2400"));
    });
    expect(written).toHaveLength(2);
    expect(written[0]).toBe(written[1]);
    expect(written[0]?.kind).toBe("word");
    const sink = loaded.graph.documents.get(fileURLToPath(new URL("split/sink.conf", FIXTURES)));
    expect(sink?.text).toContain("    max_count 2400;\n");
  });
});
