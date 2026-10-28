/**
 * rasl acceptance: rasl's real configs (fixtures/rasl/) load through the file source and the include extension,
 * with a handed-in variable, and a `$pixels` edit gives the expected change list under rasl's key rule.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { createFileSource } from "../node.js";
import type { IDirective, KeyRule } from "./directive.js";
import { type ILoaded, villanelle } from "./processor.js";
import type { IDocumentSource } from "./source.js";

const FIXTURES = new URL("../../../fixtures/rasl/", import.meta.url);

interface IExpected {
  readonly nodes: readonly string[];
  readonly diagnostics: readonly unknown[];
  readonly changes: readonly (readonly [string, string])[];
}

const EXPECTED = JSON.parse(readFileSync(new URL("expected.json", FIXTURES), "utf8")) as Record<string, IExpected>;

/** The "rasl" key rule of conformance/load/format.md. */
const RASL_KEY: KeyRule = (d) => {
  if (d.name === "node" && d.parent?.name === "graph") return d.args[1]?.text;
  if (d.name === "connect") return d.args.map((a) => a.text).join(" ");
  if (d.name === "fill") return d.args[0]?.text;
  return undefined;
};

/** The file source, with `set $pixels 2284;` read as `2400` once `edited` is set. */
function source(): { source: IDocumentSource; edit: () => void } {
  const files = createFileSource();
  let edited = false;
  return {
    edit: () => {
      edited = true;
    },
    source: {
      resolve: (spec, context) => files.resolve(spec, context),
      read: async (path) => {
        const text = await files.read(path);
        return edited ? text.replace("set $pixels 2284;", "set $pixels 2400;") : text;
      },
    },
  };
}

function nodeIds(loaded: ILoaded): string[] {
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.args[1]?.text ?? "");
  });
  return ids;
}

const HANDED = { leds_host: '"10.0.70.1"' };

describe("rasl's configs", () => {
  it.each(Object.keys(EXPECTED))("%s loads with the expected nodes and reload changes", async (name) => {
    const expected = EXPECTED[name] as IExpected;
    const { source: files, edit } = source();
    const processor = villanelle({ source: files, extensions: [include()], key: RASL_KEY });
    const path = fileURLToPath(new URL(name, FIXTURES));
    const options = { variables: HANDED };
    const first = await processor.load(path, options);
    expect(first.diagnostics).toEqual(expected.diagnostics);
    expect(nodeIds(first)).toEqual(expected.nodes);
    edit();
    const second = await processor.load(path, options);
    expect(processor.diff(first, second).map((c) => [c.kind, c.address.toString()])).toEqual(expected.changes);
  });

  it("splits one sink file over two places, each with its own include-block values and the handed-in host", async () => {
    const processor = villanelle({ source: createFileSource(), extensions: [include()], key: RASL_KEY });
    const path = fileURLToPath(new URL("split/main.conf", FIXTURES));
    const loaded = await processor.load(path, { variables: HANDED });
    const targets: [string, string][] = [];
    loaded.walk((d) => {
      if (d.name === "target") targets.push([d.address.toString(), d.args[0]?.text ?? ""]);
    });
    expect(targets).toEqual([
      ['graph > node "leds" > target', '"10.0.70.1"'],
      ['graph > node "porch" > target', '"10.0.60.31"'],
    ]);
    expect([...loaded.graph.nodes.keys()]).toEqual([path, fileURLToPath(new URL("split/sink.conf", FIXTURES))]);
    expect(loaded.graph.edges).toHaveLength(2);
    // Without the handed-in value, the file's own default is used.
    const plain = await processor.load(path);
    let host = "";
    plain.walk((d) => {
      if (d.name === "target" && host === "") host = d.args[0]?.text ?? "";
    });
    expect(host).toBe('"10.0.60.30"');
  });
});
