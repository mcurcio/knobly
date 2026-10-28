import { describe, expect, it } from "vitest";

import type { IDocumentGraph, IDocumentNode } from "../load/graph.js";
import { loadFiles } from "../load/testing.js";
import { include } from "../include.js";
import { parse } from "../syntax/parse.js";
import { type IDocumentWriter, save } from "./save.js";

const recorder = (): IDocumentWriter & { writes: Array<[string, string]> } => {
  const writes: Array<[string, string]> = [];
  return {
    writes,
    write(resolvedPath, source) {
      writes.push([resolvedPath, source]);
      return Promise.resolve();
    },
  };
};

describe("save", () => {
  it("writes nothing for an unchanged load", async () => {
    const loaded = await loadFiles({ "main.conf": 'a;\ninclude "x";', x: "b  1 ;\n" }, { extensions: [include()] });
    const writer = recorder();
    await save(loaded.graph, writer);
    expect(writer.writes).toEqual([]);
  });

  it("writes each file whose syntax text differs from its source, in nodes order", async () => {
    const node = (resolvedPath: string, source: string, text: string): IDocumentNode => ({ resolvedPath, source, syntax: parse(text) });
    const root = node("r", "old;", "new;");
    const graph: IDocumentGraph = {
      root,
      nodes: new Map([
        ["r", root],
        ["same", node("same", "s;", "s;")],
        ["t", node("t", "", "t 1;")],
      ]),
      edges: [],
    };
    const writer = recorder();
    await save(graph, writer);
    expect(writer.writes).toEqual([
      ["r", "new;"],
      ["t", "t 1;"],
    ]);
  });
});
