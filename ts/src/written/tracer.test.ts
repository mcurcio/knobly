/**
 * The round 12 tracer (design.md §14; slices.md S1 A10): fixtures/rasl/split through a memory source and a recording
 * writer, the whole flow through the public API: load, (1)'s table, (2) through `chain[0]`, save, render; then
 * (3) from a fresh load.
 */

import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { render } from "../rendered/render.js";
import type { DocumentWriter, FileWrite, Place } from "../index.js";
import { memorySource, quote, text } from "../index.js";
import type { Directive, Rendered } from "../rendered/index.js";
import { type DocumentGraph, VariableKind, villanelle } from "./index.js";

const SPLIT = new URL("../../../fixtures/rasl/split/", import.meta.url);
const FILES = { "main.conf": readFileSync(new URL("main.conf", SPLIT), "utf8"), "sink.conf": readFileSync(new URL("sink.conf", SPLIT), "utf8") };

/** 1-based `file:line`, as design.md §1 prints it. */
const lineOf = (place: Place): string => `${place.resolvedPath}:${String(place.span.start.line + 1)}`;

function nodeNamed(rendered: Rendered, name: string): Directive {
  let found: Directive | undefined;
  rendered.block.walk((d) => {
    if (d.name === "node" && d.values[1]?.text === name) found = d;
  });
  if (found === undefined) throw new Error(`no node ${name}`);
  return found;
}

function maxCounts(rendered: Rendered): [string, string | undefined, number][] {
  const out: [string, string | undefined, number][] = [];
  rendered.block.walk((d) => {
    if (d.name === "max_count") {
      const [arg] = d.values;
      out.push([arg?.text ?? "", arg?.definition === undefined ? undefined : `${lineOf(arg.definition.place)}:${String(arg.definition.place.span.start.column + 1)}`, arg?.chain.length ?? -1]);
    }
  });
  return out;
}

function recorder(): DocumentWriter & { batches: FileWrite[][] } {
  const batches: FileWrite[][] = [];
  return { batches, write: (files) => (batches.push([...files]), Promise.resolve()) };
}

async function open(): Promise<{ graph: DocumentGraph }> {
  const config = villanelle({ source: memorySource(FILES), extensions: [include()] });
  const graph = await config.load("main.conf", { overrides: { leds_host: quote("10.0.70.1") } });
  return { graph };
}

describe("the round 12 tracer (fixtures/rasl/split)", () => {
  it("lists files, variables and overrides, then changes $pixels itself (2) and saves only main.conf", async () => {
    const { graph } = await open();
    expect([...graph.documents.values()].map((doc) => [doc.resolvedPath, doc.includedBy().map((e) => lineOf(e.copy.statement.place))])).toEqual([
      ["main.conf", []],
      ["sink.conf", ["main.conf:19", "main.conf:24"]],
    ]);
    const table = graph.variables().map((v) => [
      v.name,
      v.kind,
      v.kind === VariableKind.Override ? "an override" : lineOf(v.place),
      v.wins().map((r) => lineOf(r.reference.place)),
      v.shadowedAt().map((r) => [lineOf(r.reference.place), r.winner?.kind]),
    ]);
    expect(table).toEqual([
      ["pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []],
      ["leds_host", "set", "main.conf:5", [], [["main.conf:21", "override"]]],
      ["name", "set", "main.conf:20", ["sink.conf:2"], []],
      ["host", "set", "main.conf:21", ["sink.conf:3"], []],
      ["name", "set", "main.conf:25", ["sink.conf:2"], []],
      ["host", "set", "main.conf:26", ["sink.conf:3"], []],
      ["leds_host", "override", "an override", ["main.conf:21"], []],
    ]);

    const rendered = render(graph);
    const maxCount = nodeNamed(rendered, "leds").block?.directives("max_count")[0]?.values[0];
    const read = maxCount?.chain[0];
    const winner = read?.winner;
    if (winner?.kind !== "set") throw new Error("the winner is not a set line's variable");
    winner.set(text("2400"));
    const writer = recorder();
    expect(await graph.save(writer)).toEqual(["main.conf"]);
    expect(writer.batches).toHaveLength(1);
    const [written] = writer.batches[0] ?? [];
    expect(written?.text).toBe(FILES["main.conf"].replace("@set $pixels 2284;", "@set $pixels 2400;"));
    expect(maxCounts(render(graph))).toEqual([
      ["2400", "main.conf:4:14", 1],
      ["2400", "main.conf:4:14", 1],
    ]);
    // The rendered tree from before the edit is a snapshot: it still reads 2284.
    expect(maxCount?.text).toBe("2284");
  });

  it("changes max_count to no longer use the variable (3): only sink.conf, and $pixels wins nowhere", async () => {
    const { graph } = await open();
    const read = nodeNamed(render(graph), "leds").block?.directives("max_count")[0]?.values[0]?.chain[0];
    const reference = read?.reference;
    expect(reference?.text).toBe("$pixels");
    reference?.replaceWithText(text("2400"));
    const writer = recorder();
    expect(await graph.save(writer)).toEqual(["sink.conf"]);
    expect(writer.batches[0]?.[0]?.text).toBe(FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;"));
    expect(graph.variables("pixels")[0]?.wins()).toEqual([]);
    expect(maxCounts(render(graph))).toEqual([
      ["2400", "sink.conf:6:15", 0],
      ["2400", "sink.conf:6:15", 0],
    ]);
  });
});
