/**
 * The rest of the low level's surface (slices.md S2: B3, B5, B9, B10): reading what an edit made unread, handed-in
 * values without a reload, rendered directives pointing at what is written, renames and inserts keeping handles,
 * and the root read failure.
 */

import { describe, expect, it } from "vitest";

import { DiagnosticError } from "../diagnostics.js";
import { include } from "../include.js";
import { villanelle } from "../load/processor.js";
import { memorySource } from "../load/source.js";
import { countingSource } from "../load/testing.js";
import { BadTextError, DetachedError, NoSetLineError, ReadError } from "./errors.js";
import type { IFileWrite, ISetLine, ISnippetLine, IWrittenDirective } from "./model.js";
import { save } from "./save.js";

const MAIN = "a;\n";

describe("read(graph)", () => {
  it("reads an include line an edit added once, keeps every unsaved text, and render then splices it (B3)", async () => {
    const { source, reads } = countingSource({ "main.conf": MAIN, "part.conf": "p 1;\n", "other.conf": "o 1;\n" });
    const processor = villanelle({ source, extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [a] = graph.root.body.statements as [IWrittenDirective];
    a.setValues("2");
    const [line] = graph.root.body.addStatements('include "part.conf";');
    expect(line?.kind).toBe("extension");
    expect(graph.unread()).toHaveLength(1);
    expect(processor.render(graph).body.map((d) => d.name)).toEqual(["a"]);
    expect(reads.get("part.conf")).toBeUndefined();

    expect(await processor.read(graph)).toEqual(["part.conf"]);
    expect(graph.unread()).toEqual([]);
    expect(graph.root.text).toBe('a 2;\ninclude "part.conf";\n');
    expect(processor.render(graph).body.map((d) => [d.name, d.args.map((v) => v.text)])).toEqual([
      ["a", ["2"]],
      ["p", ["1"]],
    ]);
    // Nothing new is named: a second read reads nothing, and no file is read twice.
    expect(await processor.read(graph)).toEqual([]);
    expect([...reads.entries()]).toEqual([
      ["main.conf", 1],
      ["part.conf", 1],
    ]);
  });

  it("keeps a rejection: a missing file is not resolved again", async () => {
    const { source } = countingSource({ "main.conf": MAIN });
    let resolves = 0;
    const counted = {
      read: (path: string) => source.read(path),
      resolve: (spec: string, context: { parentPath: string }) => {
        resolves++;
        return source.resolve(spec, context);
      },
    };
    const processor = villanelle({ source: counted, extensions: [include()] });
    const graph = await processor.load("main.conf");
    graph.root.body.addStatements('include "gone.conf";');
    const before = resolves;
    expect(await processor.read(graph)).toEqual([]);
    expect(await processor.read(graph)).toEqual([]);
    expect(resolves).toBe(before + 1);
    expect(processor.render(graph).diagnostics.map((d) => d.code)).toEqual(["E3001"]);
  });

  it("refuses another processor's graph with a TypeError", async () => {
    const one = villanelle({ source: memorySource({ "main.conf": MAIN }) });
    const other = villanelle({ source: memorySource({ "main.conf": MAIN }) });
    const graph = await other.load("main.conf");
    await expect(one.read(graph)).rejects.toBeInstanceOf(TypeError);
    expect(() => one.render(graph)).toThrow(TypeError);
  });
});

describe("load's root failure", () => {
  it("rejects with ReadError, a DiagnosticError E3004 at the root path (B10)", async () => {
    const processor = villanelle({ source: memorySource({}) });
    const error: unknown = await processor.load("nope.conf").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ReadError);
    expect(error).toBeInstanceOf(DiagnosticError);
    expect((error as ReadError).diagnostic.code).toBe("E3004");
    expect((error as ReadError).diagnostic.at).toMatchObject({ kind: "file", resolvedPath: "nope.conf" });
  });
});

describe("IDocument.replaceWithText (B4)", () => {
  it("keeps source, detaches every handle, and save writes the new text", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    const [a] = graph.root.body.statements as [IWrittenDirective];
    graph.root.replaceWithText("b 2;\n");
    expect(graph.root.source).toBe("a 1;\n");
    expect(() => a.text).toThrow(DetachedError);
    const batches: IFileWrite[][] = [];
    const writer = {
      write: (files: readonly IFileWrite[]) => {
        batches.push([...files]);
        return Promise.resolve();
      },
    };
    expect(await save(graph, writer)).toEqual(["main.conf"]);
    expect(batches).toEqual([[{ resolvedPath: "main.conf", text: "b 2;\n", source: "a 1;\n" }]]);
  });
});

describe("setHanded", () => {
  it("changes resolutions and render without a reload, one variable per name for the graph's life (B5, D28)", async () => {
    const { source, reads } = countingSource({ "main.conf": "set $a 0;\nx $a;\n" });
    const processor = villanelle({ source });
    const graph = await processor.load("main.conf", { variables: { a: "1" } });
    const handed = graph.variables("a").find((v) => v.kind === "handed");
    graph.setHanded("a", "2 3");
    expect(processor.render(graph).body[0]?.args.map((v) => v.text)).toEqual(["2", "3"]);
    graph.setHanded("a", undefined);
    expect([...graph.handed.keys()]).toEqual([]);
    expect(graph.variables("a").map((v) => v.kind)).toEqual(["set"]);
    expect(processor.render(graph).body[0]?.args.map((v) => v.text)).toEqual(["0"]);
    graph.setHanded("b", "9");
    graph.setHanded("a", "4");
    expect([...graph.handed.keys()]).toEqual(["b", "a"]);
    expect(graph.variables("a").find((v) => v.kind === "handed")).toBe(handed);
    expect(handed?.reaches()).toHaveLength(1);
    expect(reads.get("main.conf")).toBe(1);
  });

  it("refuses a text that is not values without a $name, and a bad name, changing nothing", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "x $a;\n" }) }).load("main.conf", { variables: { a: "1" } });
    const refused = (text: string): unknown[] => {
      try {
        graph.setHanded("a", text);
      } catch (error) {
        if (error instanceof BadTextError) return error.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]);
        throw error;
      }
      return [];
    };
    expect(refused("1;")).toEqual([["E2001", 0, 1]]);
    expect(refused("1 $b")).toEqual([["E2001", 0, 2]]);
    expect(refused('"\\q"')).toEqual([["E4003", 0, 0]]);
    expect(refused("")).toEqual([["E2001", 0, 0]]);
    expect(() => graph.setHanded("a-b", "1")).toThrow(TypeError);
    expect(graph.handed.get("a")).toBe("1");
  });
});

describe("rendered directives point at what is written (B9)", () => {
  it("gives both copies of a line read twice the same statement, and an unreadable copy its statement", async () => {
    const files = { "main.conf": 'g {\n  include "s.conf";\n}\nh {\n  include "s.conf";\n}\n', "s.conf": "x 1;\ny $nope;\n" };
    const processor = villanelle({ source: memorySource(files), extensions: [include()] });
    const graph = await processor.load("main.conf");
    const rendered = processor.render(graph);
    const [g, h] = rendered.body;
    const x = graph.documents.get("s.conf")?.body.statements[0];
    const y = graph.documents.get("s.conf")?.body.statements[1];
    expect(g?.body?.[0]?.written).toBe(x);
    expect(h?.body?.[0]?.written).toBe(x);
    expect(g?.unreadable[0]?.written).toBe(y);
    expect(h?.unreadable[0]?.written).toBe(y);
    expect(g?.written).toBe(graph.root.body.statements[0]);
  });
});

describe("rename", () => {
  it("renames a directive keeping its handle and values", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "fps 20;\n" }) }).load("main.conf");
    const [fps] = graph.root.body.statements as [IWrittenDirective];
    const [twenty] = fps.values;
    fps.rename("rate");
    expect(graph.root.body.statements[0]).toBe(fps);
    expect(fps.name).toBe("rate");
    expect(fps.values[0]).toBe(twenty);
    expect(() => {
      fps.rename("include");
    }).not.toThrow();
  });

  it("refuses renaming an extension line, or to a registered extension's name", async () => {
    const processor = villanelle({ source: memorySource({ "main.conf": 'include "p.conf";\nx;\n', "p.conf": "" }), extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [line, x] = graph.root.body.statements as [IWrittenDirective, IWrittenDirective];
    expect(() => {
      line.rename("other");
    }).toThrow(BadTextError);
    expect(() => {
      x.rename("include");
    }).toThrow(BadTextError);
    expect(graph.root.text).toBe(graph.root.source);
  });

  it("renames a set line's and a parameter's $name only, keeping the variable", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "set $a 1;\nsnippet s $p { x $p; }\ny $a;\n" }) }).load("main.conf");
    const [set, snippet] = graph.root.body.statements as [ISetLine, ISnippetLine];
    const variable = set.variable;
    const [parameter] = snippet.parameters;
    variable.rename("b");
    parameter?.rename("q");
    expect(graph.root.text).toBe("set $b 1;\nsnippet s $q { x $p; }\ny $a;\n");
    expect(set.variable).toBe(variable);
    expect(snippet.parameters[0]).toBe(parameter);
    expect([variable.name, parameter?.name]).toEqual(["b", "q"]);
    expect(() => {
      variable.rename("not-a-name");
    }).toThrow(BadTextError);
    const handed = (await villanelle({ source: memorySource({ "main.conf": "x;\n" }) }).load("main.conf", { variables: { h: "1" } })).variables("h")[0];
    expect(() => handed?.rename("g")).toThrow(NoSetLineError);
  });
});

describe("insertStatements", () => {
  it("inserts before a statement and its comments, at an index, keeping other handles", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "b {\n    a 1;\n    # about c\n    c 3;\n}\n" }) }).load("main.conf");
    const [b] = graph.root.body.statements as [IWrittenDirective];
    const block = b.block;
    if (block === undefined) throw new Error("no block");
    const [a, c] = block.statements;
    const made = block.insertStatements(1, "x 1;\ny 2;");
    expect(made.map((s) => s.text)).toEqual(["x 1;", "y 2;"]);
    expect(graph.root.text).toBe("b {\n    a 1;\n    x 1;\n    y 2;\n    # about c\n    c 3;\n}\n");
    expect(block.statements).toEqual([a, ...made, c]);
    expect(c?.text).toBe("# about c\n    c 3;");
    expect(() => block.insertStatements(9, "z;")).toThrow(RangeError);
    expect(() => block.insertStatements(0, "z {")).toThrow(BadTextError);
    expect(block.insertStatements(0, "  ")).toEqual([]);
  });

  it("inserts into an empty document, and between two statements of one line", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "# only a comment" }) }).load("main.conf");
    graph.root.body.addStatements("a;");
    expect(graph.root.text).toBe("# only a comment\na;\n");
    const shared = await villanelle({ source: memorySource({ "main.conf": "a; b;\n" }) }).load("main.conf");
    shared.root.body.insertStatements(1, "x;");
    expect(shared.root.text).toBe("a; x;\nb;\n");
  });

  it("refuses an insert that breaks a text-alone rule (E5002), changing nothing", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "set $a 1;\n" }) }).load("main.conf");
    expect(() => graph.root.body.addStatements("set $a 2;")).toThrow(BadTextError);
    expect(graph.root.text).toBe("set $a 1;\n");
  });
});
