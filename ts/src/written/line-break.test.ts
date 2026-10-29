/**
 * vil-5ya (frozen-m2.md section 10): a values text with a line break outside a list would split the statement in
 * two, so the check of a values text refuses it (E2001), in `set`, a value's `replaceWithText` and an override.
 */

import { describe, expect, it } from "vitest";

import { memorySource } from "../source.js";
import { BadTextError } from "./errors.js";
import { villanelle } from "./processor.js";

async function load(text: string): Promise<Awaited<ReturnType<ReturnType<typeof villanelle>["load"]>>> {
  return villanelle({ source: memorySource({ "main.conf": text }) }).load("main.conf");
}

function refusal(run: () => unknown): [string, number, number][] {
  try {
    run();
  } catch (error) {
    if (!(error instanceof BadTextError)) throw error;
    return error.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]);
  }
  throw new Error("not refused");
}

describe("a line break in a values text (vil-5ya)", () => {
  it('refuses set("1\\n2") on `port 80;` with one E2001 at 1:0 and leaves the text unchanged', async () => {
    const graph = await load("port 80;\n");
    const [port] = graph.root.block.directives();
    if (port === undefined) throw new Error("no port");
    expect(refusal(() => port.set("1\n2"))).toEqual([["E2001", 1, 0]]);
    expect(graph.root.text).toBe("port 80;\n");
  });

  it("refuses a trailing or leading line break, and a value's replaceWithText across lines", async () => {
    const graph = await load("port 80;\n");
    const [port] = graph.root.block.directives();
    if (port === undefined) throw new Error("no port");
    expect(refusal(() => port.set("1\n"))).toEqual([["E2001", 0, 1]]);
    expect(refusal(() => port.set("\n1"))).toEqual([["E2001", 1, 0]]);
    expect(refusal(() => port.set("1 # note\n 2"))).toEqual([["E2001", 1, 1]]);
    const [value] = port.values;
    expect(refusal(() => value?.replaceWithText("1\n2"))).toEqual([["E2001", 1, 0]]);
    expect(graph.root.text).toBe("port 80;\n");
  });

  it("refuses an override text ending or starting with a line break, by the same rule", async () => {
    const graph = await load("x $a;\n");
    expect(refusal(() => graph.setOverride("a", "1\n"))).toEqual([["E2001", 0, 1]]);
    expect(refusal(() => graph.setOverride("a", "\n1"))).toEqual([["E2001", 1, 0]]);
    expect(refusal(() => graph.setOverride("a", "1\n2"))).toEqual([["E2001", 1, 0]]);
  });

  it("leaves a line break inside a list alone", async () => {
    const graph = await load("port 80;\n");
    const [port] = graph.root.block.directives();
    port?.set("[1,\n2]");
    expect(graph.root.text).toBe("port [1,\n2];\n");
  });
});
