/**
 * Addresses, the key rule (slices.md §1.4; round 12 D4, D5: passed to `addresses()` and `diff`) and `diff` (§1.5),
 * through the public processor.
 */

import { describe, expect, it } from "vitest";

import { type Processor, villanelle } from "../written/index.js";
import { addresses, loadText, only, processorOf, rendered } from "./testing.js";
import { type DocumentSource, memorySource } from "../index.js";
import type { Directive, KeyRule } from "./index.js";

const RASL_KEY: KeyRule = (d) => (d.name === "node" && d.parent?.name === "graph" ? d.values[1]?.text : undefined);

/** A processor whose `main.conf` is whatever `text()` holds at each read. */
function changing(text: () => string): Processor {
  const source: DocumentSource = {
    resolve: (spec, context) => memorySource({ "main.conf": text() }).resolve(spec, context),
    read: (path) => memorySource({ "main.conf": text() }).read(path),
  };
  return villanelle({ source });
}

/** `diff` of two texts as `[kind, address]` pairs. */
async function changes(before: string, after: string, key?: KeyRule): Promise<[string, string][]> {
  let text = before;
  const processor = changing(() => text);
  const first = await rendered(processor, "main.conf");
  text = after;
  const second = await rendered(processor, "main.conf");
  return first.diff(second, key === undefined ? undefined : { key }).map((c) => [c.kind, c.address.toString()]);
}

describe("address", () => {
  it("counts occurrences among earlier siblings with the same name and key", async () => {
    const loaded = await loadText("a;\nb;\na;\nc { a; a; }\n");
    expect(addresses(loaded)).toEqual(["a", "b", "a #1", "c", "c > a", "c > a #1"]);
    const keyed = await loadText("graph {\n  node A x;\n  other;\n  node B y;\n  node C x;\n}\n");
    expect(addresses(keyed, { key: RASL_KEY })).toEqual(["graph", 'graph > node "x"', "graph > other", 'graph > node "y"', 'graph > node "x" #1']);
  });

  it("has JSON text with the same bytes as Python's, and a parent", async () => {
    const loaded = await loadText('graph {\n  node A "le\\"ds" { max_count 1; }\n}\n');
    const address = [...loaded.addresses({ key: RASL_KEY }).values()].at(-1);
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
    const loaded = await loadText("@snippet s { x; }\na { @use s; @use s; }\n");
    expect(addresses(loaded)).toEqual(["a", "a > x", "a > x #1"]);
  });
});

describe("key rule", () => {
  it("sees each rendered directive, parents first, once per call, and names only that call's addresses", async () => {
    const loaded = await loadText("@set $id leds;\ngraph {\n  node A $id { x; }\n  flag;\n}\n");
    const seen: Directive[] = [];
    const key: KeyRule = (d) => {
      seen.push(d);
      return d.name === "node" ? d.values[1]?.text : undefined;
    };
    expect(addresses(loaded, { key })).toEqual(["graph", 'graph > node "leds"', 'graph > node "leds" > x', "graph > flag"]);
    expect(seen.map((d) => [d.name, d.values.map((a) => a.text), d.block !== undefined, d.parent?.name])).toEqual([
      ["graph", [], true, undefined],
      ["node", ["A", "leds"], true, "graph"],
      ["x", [], false, "node"],
      ["flag", [], false, "graph"],
    ]);
    expect(seen[2]?.parent).toBe(seen[1]);
    expect(seen[1]?.parent).toBe(seen[0]);
    // Without a key, by position: a key given to one call is not kept by the render.
    expect(addresses(loaded)).toEqual(["graph", "graph > node", "graph > node > x", "graph > flag"]);
    expect(seen).toHaveLength(4);
  });

  it("propagates whatever it throws from addresses() and diff", async () => {
    const boom = new RangeError("program bug");
    const key: KeyRule = (d) => {
      if (d.name === "b") throw boom;
      return undefined;
    };
    const processor = processorOf({ "main.conf": "a;\nb;\n" });
    const loaded = await rendered(processor, "main.conf");
    expect(() => loaded.addresses({ key })).toThrow(boom);
    expect(() => loaded.diff(loaded, { key })).toThrow(boom);
  });

  it("throws a TypeError from addresses() and diff when it returns anything but a string or undefined", async () => {
    const processor = processorOf({ "main.conf": "a;\n" });
    const loaded = await rendered(processor, "main.conf");
    for (const returned of [1, null, ["a"], { toString: () => "a" }]) {
      const key = (() => returned) as unknown as KeyRule;
      expect(() => loaded.addresses({ key }), String(returned)).toThrow(TypeError);
      expect(() => loaded.diff(loaded, { key }), String(returned)).toThrow(TypeError);
    }
  });

  it("is called only for readable directives", async () => {
    const names: string[] = [];
    const loaded = await loadText("a $nope;\nb;\n");
    loaded.addresses({
      key: (d) => {
        names.push(d.name);
        return undefined;
      },
    });
    expect(names).toEqual(["b"]);
  });

  it("gives every change the address of its key rule", async () => {
    let text = "graph {\n  node A one;\n}\n";
    const processor = changing(() => text);
    const first = await rendered(processor, "main.conf");
    text = "graph {\n  node A two;\n}\n";
    const second = await rendered(processor, "main.conf");
    const key: KeyRule = (d) => (d.name === "node" ? d.values[1]?.text : undefined);
    expect(first.diff(second, { key }).map((c) => [c.kind, c.address.toString()])).toEqual([
      ["removed", 'graph > node "one"'],
      ["added", 'graph > node "two"'],
    ]);
    expect(only(first.diff(second)).kind).toBe("changed");
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

  it("compares renders of any two processors: no ownership check (D27 retired)", async () => {
    const a = await rendered(processorOf({ "main.conf": "a;\n" }), "main.conf");
    const b = await rendered(processorOf({ "main.conf": "a 1;\n" }), "main.conf");
    expect(a.diff(b).map((c) => [c.kind, c.address.toString()])).toEqual([["changed", "a"]]);
    expect(a.diff(a)).toEqual([]);
  });

  it("gives each change its directives", async () => {
    let text = "a 1;\nb;\n";
    const processor = changing(() => text);
    const first = await rendered(processor, "main.conf");
    text = "a 2;\nc;\n";
    const second = await rendered(processor, "main.conf");
    const [removed, changed, added] = first.diff(second);
    expect(removed).toMatchObject({ kind: "removed", before: first.block.at(1) });
    expect(changed).toMatchObject({ kind: "changed", before: first.block.at(0), after: second.block.at(0) });
    expect(added).toMatchObject({ kind: "added", after: second.block.at(1) });
  });
});
