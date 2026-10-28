/**
 * The round 12 tracer (design.md §14; slices.md S1 A10): fixtures/rasl/split through a memory source and a recording
 * writer, the whole flow through the public API: load, (1)'s table, (2) through `resolutions[0]`, save, render; then
 * (3) from a fresh load.
 */

import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import type { IDirective } from "../load/directive.js";
import { type IRendered, villanelle } from "../load/processor.js";
import { memorySource } from "../load/source.js";
import type { IDocumentWriter, IFileWrite, IPlace } from "../index.js";
import { save } from "./save.js";

const SPLIT = new URL("../../../fixtures/rasl/split/", import.meta.url);
const FILES = { "main.conf": readFileSync(new URL("main.conf", SPLIT), "utf8"), "sink.conf": readFileSync(new URL("sink.conf", SPLIT), "utf8") };

/** 1-based `file:line`, as design.md §1 prints it. */
const lineOf = (place: IPlace): string => `${place.resolvedPath}:${String(place.span.start.line + 1)}`;

function nodeNamed(rendered: IRendered, name: string): IDirective {
  let found: IDirective | undefined;
  rendered.walk((d) => {
    if (d.name === "node" && d.args[1]?.text === name) found = d;
  });
  if (found === undefined) throw new Error(`no node ${name}`);
  return found;
}

function maxCounts(rendered: IRendered): [string, string | undefined, number][] {
  const out: [string, string | undefined, number][] = [];
  rendered.walk((d) => {
    if (d.name === "max_count") {
      const [arg] = d.args;
      out.push([arg?.text ?? "", arg?.written === undefined ? undefined : `${lineOf(arg.written.place)}:${String(arg.written.place.span.start.column + 1)}`, arg?.resolutions.length ?? -1]);
    }
  });
  return out;
}

function recorder(): IDocumentWriter & { batches: IFileWrite[][] } {
  const batches: IFileWrite[][] = [];
  return { batches, write: (files) => (batches.push([...files]), Promise.resolve()) };
}

async function open(): Promise<{ config: ReturnType<typeof villanelle>; graph: Awaited<ReturnType<ReturnType<typeof villanelle>["load"]>> }> {
  const config = villanelle({ source: memorySource(FILES), extensions: [include()] });
  const graph = await config.load("main.conf", { variables: { leds_host: '"10.0.70.1"' } });
  return { config, graph };
}

describe("the round 12 tracer (fixtures/rasl/split)", () => {
  it("lists files, variables and overrides, then changes $pixels itself (2) and saves only main.conf", async () => {
    const { config, graph } = await open();
    expect([...graph.documents.values()].map((doc) => [doc.resolvedPath, doc.includedBy().map((e) => lineOf(e.copy.statement.place))])).toEqual([
      ["main.conf", []],
      ["sink.conf", ["main.conf:19", "main.conf:24"]],
    ]);
    const table = graph.variables().map((v) => [
      v.name,
      v.kind,
      v.place === undefined ? "handed in" : lineOf(v.place),
      v.reaches().map((r) => lineOf(r.reference.place)),
      v.overridden().map((r) => [lineOf(r.reference.place), r.winner?.kind]),
    ]);
    expect(table).toEqual([
      ["pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []],
      ["leds_host", "set", "main.conf:5", [], [["main.conf:21", "handed"]]],
      ["name", "set", "main.conf:20", ["sink.conf:2"], []],
      ["host", "set", "main.conf:21", ["sink.conf:3"], []],
      ["name", "set", "main.conf:25", ["sink.conf:2"], []],
      ["host", "set", "main.conf:26", ["sink.conf:3"], []],
      ["leds_host", "handed", "handed in", ["main.conf:21"], []],
    ]);

    const rendered = config.render(graph);
    const maxCount = nodeNamed(rendered, "leds").body?.find((d) => d.name === "max_count")?.args[0];
    const read = maxCount?.resolutions[0];
    expect(read?.winner?.kind).toBe("set");
    read?.winner?.setValues("2400");
    const writer = recorder();
    expect(await save(graph, writer)).toEqual(["main.conf"]);
    expect(writer.batches).toHaveLength(1);
    const [written] = writer.batches[0] ?? [];
    expect(written?.text).toBe(FILES["main.conf"].replace("set $pixels 2284;", "set $pixels 2400;"));
    expect(maxCounts(config.render(graph))).toEqual([
      ["2400", "main.conf:4:13", 1],
      ["2400", "main.conf:4:13", 1],
    ]);
    // The rendered tree from before the edit is a snapshot: it still reads 2284.
    expect(maxCount?.text).toBe("2284");
  });

  it("changes max_count to no longer use the variable (3): only sink.conf, and $pixels reaches nothing", async () => {
    const { config, graph } = await open();
    const read = nodeNamed(config.render(graph), "leds").body?.find((d) => d.name === "max_count")?.args[0]?.resolutions[0];
    const reference = read?.reference;
    expect(reference?.text).toBe("$pixels");
    reference?.replaceWithText("2400");
    const writer = recorder();
    expect(await save(graph, writer)).toEqual(["sink.conf"]);
    expect(writer.batches[0]?.[0]?.text).toBe(FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;"));
    expect(graph.variables("pixels")[0]?.reaches()).toEqual([]);
    expect(maxCounts(config.render(graph))).toEqual([
      ["2400", "sink.conf:6:15", 0],
      ["2400", "sink.conf:6:15", 0],
    ]);
  });
});
