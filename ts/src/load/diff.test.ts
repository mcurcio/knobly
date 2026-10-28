/**
 * Addresses, the key rule (slices.md §1.4) and `diff` (§1.5), through the public processor.
 */

import { describe, expect, it } from "vitest";

import type { IDirective, IKeyInput, KeyRule } from "./directive.js";
import type { IProcessor } from "./processor.js";
import { villanelle } from "./processor.js";
import { type IDocumentSource, memorySource } from "./source.js";
import { addresses, loadText, processorOf } from "./testing.js";

const RASL_KEY: KeyRule = (d) => (d.name === "node" && d.parent?.name === "graph" ? d.args[1]?.text : undefined);

/** A processor whose `main.conf` is whatever `text()` holds at each read. */
function changing(text: () => string, key?: KeyRule): IProcessor {
  const source: IDocumentSource = {
    resolve: (spec, context) => memorySource({ "main.conf": text() }).resolve(spec, context),
    read: (path) => memorySource({ "main.conf": text() }).read(path),
  };
  return villanelle({ source, ...(key === undefined ? {} : { key }) });
}

/** `diff` of two texts as `[kind, address]` pairs. */
async function changes(before: string, after: string, key?: KeyRule): Promise<[string, string][]> {
  let text = before;
  const processor = changing(() => text, key);
  const first = await processor.load("main.conf");
  text = after;
  const second = await processor.load("main.conf");
  return processor.diff(first, second).map((c) => [c.kind, c.address.toString()]);
}

describe("address", () => {
  it("counts occurrences among earlier siblings with the same name and key", async () => {
    const loaded = await loadText("a;\nb;\na;\nc { a; a; }\n");
    expect(addresses(loaded)).toEqual(["a", "b", "a #1", "c", "c > a", "c > a #1"]);
    const keyed = await loadText("graph {\n  node A x;\n  other;\n  node B y;\n  node C x;\n}\n", { key: RASL_KEY });
    expect(addresses(keyed)).toEqual(["graph", 'graph > node "x"', "graph > other", 'graph > node "y"', 'graph > node "x" #1']);
  });

  it("has JSON text with the same bytes as Python's, and a parent", async () => {
    const loaded = await loadText('graph {\n  node A "le\\"ds" { max_count 1; }\n}\n', { key: RASL_KEY });
    let deepest: IDirective | undefined;
    loaded.walk((d) => {
      deepest = d;
    });
    const address = deepest?.address;
    expect(address?.text).toBe('[["graph",null,0],["node","\\"le\\\\\\"ds\\"",0],["max_count",null,0]]');
    expect(address?.toString()).toBe('graph > node "\\"le\\\\\\"ds\\"" > max_count');
    expect(address?.steps.map((s) => [s.name, s.key, s.occurrence])).toEqual([
      ["graph", undefined, 0],
      ["node", '"le\\"ds"', 0],
      ["max_count", undefined, 0],
    ]);
    expect(address?.parent?.toString()).toBe('graph > node "\\"le\\\\\\"ds\\""');
    expect(address?.parent?.parent?.parent).toBeUndefined();
  });

  it("gives a directive spliced at two places two addresses", async () => {
    const loaded = await loadText("snippet s { x; }\na { use s; use s; }\n");
    expect(addresses(loaded)).toEqual(["a", "a > x", "a > x #1"]);
  });
});

describe("key rule", () => {
  it("sees expanded values, whether there is a block, and its parent's input, parents first", async () => {
    const seen: IKeyInput[] = [];
    const key: KeyRule = (d) => {
      seen.push(d);
      return undefined;
    };
    await loadText("set $id leds;\ngraph {\n  node A $id { x; }\n  flag;\n}\n", { key });
    expect(seen.map((d) => [d.name, d.args.map((a) => a.text), d.hasBlock, d.parent?.name])).toEqual([
      ["graph", [], true, undefined],
      ["node", ["A", "leds"], true, "graph"],
      ["x", [], false, "node"],
      ["flag", [], false, "graph"],
    ]);
    expect(seen[2]?.parent).toBe(seen[1]);
    expect(seen[2]?.parent?.parent).toBe(seen[0]);
  });

  it("ends the load with whatever it throws", async () => {
    const boom = new RangeError("program bug");
    const key: KeyRule = (d) => {
      if (d.name === "b") throw boom;
      return undefined;
    };
    await expect(loadText("a;\nb;\n", { key })).rejects.toBe(boom);
  });

  it("is called only for readable directives", async () => {
    const names: string[] = [];
    await loadText("a $nope;\nb;\n", {
      key: (d) => {
        names.push(d.name);
        return undefined;
      },
    });
    expect(names).toEqual(["b"]);
  });
});

describe("diff", () => {
  it("lists added, removed and changed (values and block), each added or removed directive alone", async () => {
    const before = "keep 1;\ngone { inner; }\nedit 1;\nblock;\nlost;\n";
    const after = "keep 1;\nedit 2;\nblock {}\nnew { inner; }\n";
    expect(await changes(before, after)).toEqual([
      ["removed", "gone"],
      ["removed", "lost"],
      ["changed", "edit"],
      ["changed", "block"],
      ["added", "new"],
    ]);
  });

  it("compares a changed or unchanged directive's block at its own addresses", async () => {
    expect(await changes("a { x 1; y 1; }\n", "a { x 2; z; }\n")).toEqual([
      ["removed", "a > y"],
      ["changed", "a > x"],
      ["added", "a > z"],
    ]);
    expect(await changes("a 1 { x 1; }\n", "a 2 { x 1; }\n")).toEqual([["changed", "a"]]);
  });

  it("orders removed and unknown by the first load's walk, then added and changed by the second's", async () => {
    expect(await changes("a;\nb { c; }\nd;\n", "d 1;\nnew;\nb { e; }\n")).toEqual([
      ["removed", "a"],
      ["removed", "b > c"],
      ["changed", "d"],
      ["added", "new"],
      ["added", "b > e"],
    ]);
  });

  it("calls a directive unknown, not removed, when its container in the second load holds an unreadable line", async () => {
    expect(await changes("g {\n  a 1;\n  b 2;\n}\nh;\n", 'g {\n  a 1;\n  b x"y";\n}\n')).toEqual([
      ["unknown", "g > b"],
      ["removed", "h"],
    ]);
    expect(await changes("a;\nb;\n", "a;\nb $nope;\n")).toEqual([["unknown", "b"]]);
  });

  it("follows a keyed node that moved: no change", async () => {
    const text = (first: string, second: string): string => `graph {\n  ${first}\n  ${second}\n}\n`;
    const one = "node A one { x 1; }";
    const two = "node B two { x 2; }";
    expect(await changes(text(one, two), text(two, one), RASL_KEY)).toEqual([]);
    expect(await changes(text(one, two), text(two, one))).toEqual([
      ["changed", "graph > node"],
      ["changed", "graph > node > x"],
      ["changed", "graph > node #1"],
      ["changed", "graph > node #1 > x"],
    ]);
  });

  it("compares canonical texts: a comment or a quote style is no change, a number's spelling is", async () => {
    expect(await changes("c [1, # warm\n 2];\ns 'x';\n", 'c [1, # cool\n 2,];\ns "x";\n')).toEqual([]);
    expect(await changes("n 0.5;\n", "n 0.50;\n")).toEqual([["changed", "n"]]);
  });

  it("refuses loads of another processor with a TypeError", async () => {
    const one = processorOf({ "main.conf": "a;\n" });
    const other = processorOf({ "main.conf": "a;\n" });
    const a = await one.load("main.conf");
    const b = await other.load("main.conf");
    expect(() => one.diff(a, b)).toThrow(TypeError);
    expect(() => one.diff(b, a)).toThrow(TypeError);
    expect(one.diff(a, a)).toEqual([]);
  });

  it("gives each change its directives", async () => {
    let text = "a 1;\nb;\n";
    const processor = changing(() => text);
    const first = await processor.load("main.conf");
    text = "a 2;\nc;\n";
    const second = await processor.load("main.conf");
    const [removed, changed, added] = processor.diff(first, second);
    expect(removed).toMatchObject({ kind: "removed", before: first.body[1] });
    expect(changed).toMatchObject({ kind: "changed", before: first.body[0], after: second.body[0] });
    expect(added).toMatchObject({ kind: "added", after: second.body[1] });
  });
});
