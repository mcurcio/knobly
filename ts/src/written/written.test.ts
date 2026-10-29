/**
 * The low level's documents, handles, save and the one home of the lookup rule (slices.md S1: A7, A8, A9).
 */

import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { villanelle } from "./processor.js";
import { memorySource } from "../source.js";
import { BadTextError, DetachedError, SaveError } from "./errors.js";
import type { IDocumentGraph, IDocumentWriter, IFileWrite, ISetLine, IWrittenDirective } from "./model.js";
import { quote } from "../text.js";

async function load(files: Record<string, string>, overrides?: Record<string, string>): Promise<IDocumentGraph> {
  const processor = villanelle({ source: memorySource(files), extensions: [include()] });
  return processor.load("main.conf", overrides === undefined ? undefined : { overrides });
}

function recorder(): IDocumentWriter & { batches: IFileWrite[][] } {
  const batches: IFileWrite[][] = [];
  return {
    batches,
    write(files) {
      batches.push([...files]);
      return Promise.resolve();
    },
  };
}

describe("documents and handles", () => {
  it("keeps one handle per statement and value across an edit elsewhere in the file (===)", async () => {
    const graph = await load({ "main.conf": "set $a 1;\nb 2 3;\nc { d 4; }\n" });
    const body = graph.root.block;
    const [set, b, c] = body.statements as [ISetLine, IWrittenDirective, IWrittenDirective];
    const [two, three] = b.values;
    const d = c.block?.statements[0];
    set.set("100 200");
    expect(graph.root.text).toBe("set $a 100 200;\nb 2 3;\nc { d 4; }\n");
    expect(body.statements[0]).toBe(set);
    expect(body.statements[1]).toBe(b);
    expect(b.values[0]).toBe(two);
    expect(b.values[1]).toBe(three);
    expect(c.block?.statements[0]).toBe(d);
    expect([b.text, two?.text, three?.text, d?.text, set.text]).toEqual(["b 2 3;", "2", "3", "d 4;", "set $a 100 200;"]);
    expect(set.variable).toBe(graph.variables("a")[0]);
    expect(b.place.span.start).toEqual({ offset: 16, line: 1, column: 0 });
  });

  it("detaches a replaced value: every member but kind throws DetachedError", async () => {
    const graph = await load({ "main.conf": "x 1;\n" });
    const [value] = (graph.root.block.statements[0] as IWrittenDirective).values;
    if (value === undefined) throw new Error("no value");
    const [made] = value.replaceWithText("2");
    expect(made?.text).toBe("2");
    expect(value.kind).toBe("word");
    expect(() => value.text).toThrow(DetachedError);
    expect(() => value.replaceWithText("3")).toThrow(DetachedError);
  });

  it("owns the comment lines directly above a statement and its trailing comment", async () => {
    const graph = await load({ "main.conf": "# far\n\n# near\n  b 2; # end\nc;\n" });
    const [b] = graph.root.block.statements;
    expect(b?.text).toBe("# near\n  b 2; # end");
    expect(b?.place.span.start).toMatchObject({ line: 2, column: 0 });
    b?.remove();
    expect(graph.root.text).toBe("# far\n\nc;\n");
  });

  it("changes nothing when an edit's text is refused", async () => {
    const graph = await load({ "main.conf": "set $a 1;\n" });
    const set = graph.root.block.statements[0] as ISetLine;
    for (const text of ["1; x", "{", "", "\"open"]) {
      expect(() => set.set(text), text).toThrow(BadTextError);
      expect(graph.root.text).toBe("set $a 1;\n");
    }
    expect(set.text).toBe("set $a 1;");
  });
});

describe("save", () => {
  it("hands only changed files to the writer in one call, then updates source; nothing changed: no call", async () => {
    const graph = await load({ "main.conf": 'include "p.conf";\nx 1;\n', "p.conf": "y 2;\n" });
    const writer = recorder();
    expect(await graph.save(writer)).toEqual([]);
    expect(writer.batches).toEqual([]);
    const p = graph.documents.get("p.conf");
    (p?.block.statements[0] as IWrittenDirective).values[0]?.replaceWithText("3");
    expect(await graph.save(writer)).toEqual(["p.conf"]);
    expect(writer.batches).toEqual([[{ resolvedPath: "p.conf", text: "y 3;\n", savedText: "y 2;\n" }]]);
    expect(p?.savedText).toBe("y 3;\n");
    expect(await graph.save(writer)).toEqual([]);
    expect(writer.batches).toHaveLength(1);
  });

  it("throws SaveError with the files and the cause when the writer rejects, and changes no source", async () => {
    const graph = await load({ "main.conf": "x 1;\n" });
    (graph.root.block.statements[0] as IWrittenDirective).values[0]?.replaceWithText("2");
    const cause = new Error("disk full");
    const error: unknown = await graph.save({ write: () => Promise.reject(cause) }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SaveError);
    expect((error as SaveError).files.map((f) => f.resolvedPath)).toEqual(["main.conf"]);
    expect((error as SaveError).cause).toBe(cause);
    expect(graph.root.savedText).toBe("x 1;\n");
    expect(graph.root.text).not.toBe(graph.root.savedText);
  });

  it("keeps an edit made while the writer ran unsaved", async () => {
    const graph = await load({ "main.conf": "x 1;\n" });
    const x = graph.root.block.statements[0] as IWrittenDirective;
    x.values[0]?.replaceWithText("2");
    let release: () => void = () => undefined;
    const pending = graph.save({ write: () => new Promise<void>((resolve) => (release = resolve)) });
    x.values[0]?.replaceWithText("3");
    release();
    await pending;
    expect(graph.root.savedText).toBe("x 2;\n");
    expect(graph.root.text).toBe("x 3;\n");
  });

  it("quotes a plain string as the canonical villanelle string", () => {
    expect(quote('10.0.60.31 "x"\n')).toBe('"10.0.60.31 \\"x\\"\\n"');
  });
});

describe("the binding is the one home of the lookup rule (A8)", () => {
  it("has no scope class or lookup outside written/bind.ts", () => {
    const dir = new URL("../", import.meta.url);
    const offenders = readdirSync(dir, { recursive: true, encoding: "utf8" })
      .map((name) => name.split("\\").join("/"))
      .filter((name) => name.endsWith(".ts") && !name.endsWith(".test.ts") && !name.startsWith("gen/") && name !== "written/bind.ts")
      .filter((name) => /class \w*Scope\b|\blookup\(/u.test(readFileSync(new URL(name, dir), "utf8")));
    expect(offenders).toEqual([]);
  });

  it("gives a reference the declaration the binding picks at every copy (2.5, 2.6)", async () => {
    const graph = await load({
      "main.conf": "snippet s $a {\n    x {\n        set $a 1;\n        y $a;\n    }\n    z $a;\n}\nuse s 2;\nuse s 3;\n",
    });
    const references = graph.variables().flatMap((v) => v.references());
    expect(references).toHaveLength(2);
    for (const reference of new Set(references)) {
      const winners = reference.resolutions().map((r) => r.winner);
      expect(winners).toHaveLength(2);
      for (const winner of winners) expect(winner).toBe(reference.declaration);
    }
  });
});
