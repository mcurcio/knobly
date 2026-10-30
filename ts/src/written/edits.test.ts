/**
 * The rest of the low level's surface (slices.md S2: B3, B5, B9, B10): reading what an edit made unread, override
 * values without a reload, rendered directives pointing at what is written, renames and inserts keeping handles,
 * and the root read failure.
 */

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { render } from "../rendered/render.js";
import { countingSource } from "../rendered/testing.js";
import { BadTextError, DetachedError, DiagnosticError, type FileWrite, memorySource, MisuseError, ReadError, text, KnoblyError } from "../index.js";
import { type DocumentGraph, type ExtensionLine, StatementKind, VariableKind, knobly, type WrittenDirective } from "./index.js";

const MAIN = "a;\n";

describe("read(graph)", () => {
  it("reads an include line an edit added once, keeps every unsaved text, and render then splices it (B3)", async () => {
    const { source, reads } = countingSource({ "main.conf": MAIN, "part.conf": "p 1;\n", "other.conf": "o 1;\n" });
    const processor = knobly({ source, extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [a] = [...graph.root.block] as [WrittenDirective];
    a.set(text("2"));
    const [line] = graph.root.block.addStatements(text('@include "part.conf";'));
    expect(line?.kind).toBe("extension");
    expect(graph.unread()).toHaveLength(1);
    expect([...render(graph).block].map((d) => d.name)).toEqual(["a"]);
    expect(render(graph).unreadable.map((u) => u.reason)).toEqual(["unread"]);
    expect(reads.get("part.conf")).toBeUndefined();

    expect(await graph.read()).toEqual(["part.conf"]);
    expect(graph.unread()).toEqual([]);
    expect(graph.root.text).toBe('a 2;\n@include "part.conf";\n');
    expect([...render(graph).block].map((d) => [d.name, d.values.map((v) => v.text)])).toEqual([
      ["a", ["2"]],
      ["p", ["1"]],
    ]);
    // Nothing new is named: a second read reads nothing, and no file is read twice.
    expect(await graph.read()).toEqual([]);
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
    const processor = knobly({ source: counted, extensions: [include()] });
    const graph = await processor.load("main.conf");
    graph.root.block.addStatements(text('@include "gone.conf";'));
    const before = resolves;
    expect(await graph.read()).toEqual([]);
    expect(await graph.read()).toEqual([]);
    expect(resolves).toBe(before + 1);
    expect(render(graph).diagnostics.map((d) => d.code)).toEqual(["E3001"]);
  });

  it("reads through the source the graph was loaded with (no processor ownership check, D27 retired)", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "a;\n", "part.conf": "p;\n" }) }).load("main.conf");
    graph.root.block.addStatements(text('@include "part.conf";'));
    await expect(graph.read()).resolves.toEqual([]);
    const withInclude = await knobly({ source: memorySource({ "main.conf": "a;\n", "part.conf": "p;\n" }), extensions: [include()] }).load("main.conf");
    withInclude.root.block.addStatements(text('@include "part.conf";'));
    await expect(withInclude.read()).resolves.toEqual(["part.conf"]);
    expect([...render(withInclude).block].map((d) => d.name)).toEqual(["a", "p"]);
  });
});

describe("load's root failure", () => {
  it("rejects with ReadError, paths the root path and no diagnostic, when the source resolves no file (B10)", async () => {
    const processor = knobly({ source: memorySource({}) });
    const error: unknown = await processor.load("nope.conf").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ReadError);
    expect(error).toBeInstanceOf(KnoblyError);
    expect(error).not.toBeInstanceOf(DiagnosticError);
    expect((error as ReadError).paths).toEqual(["nope.conf"]);
    expect((error as ReadError).cause).toBeUndefined();
    expect("diagnostic" in (error as object)).toBe(false);
  });

  it("chains the source's rejection as the cause", async () => {
    const cause = new Error("disk gone");
    const source = { resolve: () => Promise.resolve(["main.conf"]), read: () => Promise.reject(cause) };
    const error: unknown = await knobly({ source }).load("main.conf").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ReadError);
    expect((error as ReadError).paths).toEqual(["main.conf"]);
    expect((error as ReadError).cause).toBe(cause);
  });
});

describe("Document.replaceWithText (B4)", () => {
  it("keeps source, detaches every handle, and save writes the new text", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    const [a] = [...graph.root.block] as [WrittenDirective];
    graph.root.replaceWithText(text("b 2;\n"));
    expect(graph.root.savedText).toBe("a 1;\n");
    expect(() => a.text).toThrow(DetachedError);
    const batches: FileWrite[][] = [];
    const writer = {
      write: (files: readonly FileWrite[]) => {
        batches.push([...files]);
        return Promise.resolve();
      },
    };
    expect(await graph.save(writer)).toEqual(["main.conf"]);
    expect(batches).toEqual([[{ resolvedPath: "main.conf", text: "b 2;\n", savedText: "a 1;\n" }]]);
  });
});

describe("setOverride", () => {
  it("changes resolutions and render without a reload, one variable per name for the graph's life (B5, D28)", async () => {
    const { source, reads } = countingSource({ "main.conf": "@set $a 0;\nx $a;\n" });
    const processor = knobly({ source });
    const graph = await processor.load("main.conf", { overrides: { a: text("1") } });
    const override = graph.variables("a").find((v) => v.kind === VariableKind.Override);
    graph.setOverride("a", text("2 3"));
    expect(render(graph).block.at(0)?.values.map((v) => v.text)).toEqual(["2", "3"]);
    graph.setOverride("a", undefined);
    expect([...graph.overrides.keys()]).toEqual([]);
    expect(graph.variables("a").map((v) => v.kind)).toEqual(["set"]);
    expect(render(graph).block.at(0)?.values.map((v) => v.text)).toEqual(["0"]);
    graph.setOverride("b", text("9"));
    graph.setOverride("a", text("4"));
    expect([...graph.overrides.keys()]).toEqual(["b", "a"]);
    expect(graph.variables("a").find((v) => v.kind === VariableKind.Override)).toBe(override);
    expect(override?.wins()).toHaveLength(1);
    expect(reads.get("main.conf")).toBe(1);
  });

  it("refuses a text that is not values without a $name, and a bad name, changing nothing", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "x $a;\n" }) }).load("main.conf", { overrides: { a: text("1") } });
    const refused = (given: string): unknown[] => {
      try {
        graph.setOverride("a", text(given));
      } catch (error) {
        if (error instanceof BadTextError) return error.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]);
        throw error;
      }
      return [];
    };
    expect(refused("1;")).toEqual([["E2001", 0, 1]]);
    expect(refused("1 $b")).toEqual([["E2001", 0, 2]]);
    expect(refused('"\\q"')).toEqual([["E1005", 0, 0]]);
    expect(refused("c[x]")).toEqual([["E2007", 0, 2]]);
    expect(refused("")).toEqual([["E2001", 0, 0]]);
    expect(() => graph.setOverride("a-b", text("1"))).toThrow(MisuseError);
    expect(graph.overrides.get("a")).toBe("1");
  });
});

describe("rendered directives point at what is written (B9)", () => {
  it("gives both copies of a line read twice the same statement, and an unreadable copy its statement", async () => {
    const files = { "main.conf": 'g {\n  @include "s.conf";\n}\nh {\n  @include "s.conf";\n}\n', "s.conf": "x 1;\ny $nope;\n" };
    const processor = knobly({ source: memorySource(files), extensions: [include()] });
    const graph = await processor.load("main.conf");
    const rendered = render(graph);
    const [g, h] = rendered.block;
    const x = graph.documents.get("s.conf")?.block.at(0);
    const y = graph.documents.get("s.conf")?.block.at(1);
    expect(g?.block?.at(0)?.written).toBe(x);
    expect(h?.block?.at(0)?.written).toBe(x);
    expect(g?.unreadable[0]?.written).toBe(y);
    expect(h?.unreadable[0]?.written).toBe(y);
    expect(g?.written).toBe(graph.root.block.at(0));
  });
});

describe("rename", () => {
  it("renames a directive keeping its handle and values", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "fps 20;\n" }) }).load("main.conf");
    const [fps] = [...graph.root.block] as [WrittenDirective];
    const [twenty] = fps.values;
    fps.rename("rate");
    expect(graph.root.block.at(0)).toBe(fps);
    expect(fps.name).toBe("rate");
    expect(fps.values[0]).toBe(twenty);
    expect(() => {
      fps.rename("include");
    }).not.toThrow();
  });

  it("has no rename on an extension line; a directive renamed to an extension's name stays a directive (no name is reserved)", async () => {
    const processor = knobly({ source: memorySource({ "main.conf": '@include "p.conf";\nx;\n', "p.conf": "" }), extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [line, x] = [...graph.root.block] as [ExtensionLine, WrittenDirective];
    expect(line.kind).toBe("extension");
    expect("rename" in line).toBe(false);
    expect(() => {
      x.rename("@include");
    }).toThrow(MisuseError);
    expect(graph.root.text).toBe(graph.root.savedText);
    x.rename("include");
    expect(graph.root.block.at(1)).toBe(x);
    expect(x.kind).toBe("directive");
    expect(graph.edges()).toHaveLength(1);
  });

  it("renames a set line's and a parameter's $name only, keeping the variable", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "@set $a 1;\n@snippet s $p { x $p; }\ny $a;\n" }) }).load("main.conf");
    const [set, snippet] = [...graph.root.block];
    if (set?.kind !== StatementKind.Set || snippet?.kind !== StatementKind.Snippet) throw new Error("unexpected body");
    const variable = set.variable;
    const [parameter] = snippet.parameters;
    variable.rename("b");
    parameter?.rename("q");
    expect(graph.root.text).toBe("@set $b 1;\n@snippet s $q { x $p; }\ny $a;\n");
    expect(set.variable).toBe(variable);
    expect(snippet.parameters[0]).toBe(parameter);
    expect([variable.name, parameter?.name]).toEqual(["b", "q"]);
    expect(() => {
      variable.rename("not-a-name");
    }).toThrow(MisuseError);
    expect(() => {
      parameter?.rename("");
    }).toThrow(MisuseError);
    expect(graph.root.text).toBe("@set $b 1;\n@snippet s $q { x $p; }\ny $a;\n");
  });
});

describe("insertStatements", () => {
  it("inserts before a statement and its comments, at an index, keeping other handles", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "b {\n    a 1;\n    # about c\n    c 3;\n}\n" }) }).load("main.conf");
    const [b] = [...graph.root.block] as [WrittenDirective];
    const block = b.block;
    if (block === undefined) throw new Error("no block");
    const [a, c] = block;
    const made = block.insertStatements(1, text("x 1;\ny 2;"));
    expect(made.map((s) => s.text)).toEqual(["x 1;", "y 2;"]);
    expect(graph.root.text).toBe("b {\n    a 1;\n    x 1;\n    y 2;\n    # about c\n    c 3;\n}\n");
    expect([...block]).toEqual([a, ...made, c]);
    expect(c?.text).toBe("# about c\n    c 3;");
    expect(() => block.insertStatements(9, text("z;"))).toThrow(RangeError);
    expect(() => block.insertStatements(0, text("z {"))).toThrow(BadTextError);
    expect(block.insertStatements(0, text("  "))).toEqual([]);
  });

  it("inserts into an empty document, and between two statements of one line", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "# only a comment" }) }).load("main.conf");
    graph.root.block.addStatements(text("a;"));
    expect(graph.root.text).toBe("# only a comment\na;\n");
    const shared = await knobly({ source: memorySource({ "main.conf": "a; b;\n" }) }).load("main.conf");
    shared.root.block.insertStatements(1, text("x;"));
    expect(shared.root.text).toBe("a; x;\nb;\n");
  });

  it("refuses an insert that breaks a text-alone rule (E5002), changing nothing", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "@set $a 1;\n" }) }).load("main.conf");
    expect(() => graph.root.block.addStatements(text("@set $a 2;"))).toThrow(BadTextError);
    expect(graph.root.text).toBe("@set $a 1;\n");
  });
});

describe("a value's set keeps its handle (spec 6.1, milestone 5)", () => {
  const open = (main: string): Promise<DocumentGraph> => knobly({ source: memorySource({ "main.conf": main }) }).load("main.conf");
  const first = (graph: DocumentGraph): WrittenDirective => graph.root.block.directives()[0] as WrittenDirective;

  it("sets a slice's name and bound in place: the slice, its name and the bound keep their handles", async () => {
    const graph = await open("@set $s leds;\nx $s[0~3];\n");
    const [slice] = first(graph).values;
    if (slice?.kind !== "slice") throw new Error("not a slice");
    const name = slice.name;
    expect([name.kind, name.text]).toEqual(["reference", "$s"]);
    expect(graph.variables("s")[0]?.references()).toEqual([name]);
    name.set(text("strip"));
    expect(graph.root.text).toBe("@set $s leds;\nx strip[0~3];\n");
    expect(first(graph).values[0]).toBe(slice);
    expect(slice.name).toBe(name);
    expect(name.kind).toBe("word");
    const end = slice.end;
    end?.set(text("$n"));
    expect(slice.end).toBe(end);
    expect(graph.root.text).toBe("@set $s leds;\nx strip[0~$n];\n");
    expect(() => name.set(text("a b"))).toThrow(BadTextError);
    expect(() => end?.set(text("x"))).toThrow(BadTextError);
  });

  it("detaches the old items, bounds and name of a value set to another kind; the new ones are new handles", async () => {
    const graph = await open("x [1, 2] a[1~2];\n");
    const [list, slice] = first(graph).values;
    if (list?.kind !== "list" || slice?.kind !== "slice") throw new Error("kinds");
    const [one] = list.items;
    const name = slice.name;
    list.set(text("w"));
    slice.set(text("b[3]"));
    expect(graph.root.text).toBe("x w b[3];\n");
    expect(first(graph).values).toEqual([list, slice]);
    expect([list.kind, slice.kind]).toEqual(["word", "index"]);
    expect(() => one?.text).toThrow(DetachedError);
    expect(() => name.text).toThrow(DetachedError);
  });

  it("takes exactly one value, and a statement's set takes no-value text only when it is empty", async () => {
    const graph = await open("port 80;\n");
    const statement = first(graph);
    const [value] = statement.values;
    for (const given of ["1 2", "", "1;", "1 # c"]) expect(() => value?.set(text(given)), given).toThrow(BadTextError);
    for (const given of ["# c\n", "\n", "  "]) expect(() => statement.set(text(given)), given).toThrow(BadTextError);
    expect(graph.root.text).toBe("port 80;\n");
    statement.set(text(""));
    expect(graph.root.text).toBe("port;\n");
  });
});

describe("render of something that is not a graph (spec 7.0, milestone 5)", () => {
  it("raises the argument type error before any other work", async () => {
    const graph = await knobly({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    const message = 'render(): argument "graph" must be a document graph (an object with an expand method), not object';
    expect(() => render(graph.root as unknown as DocumentGraph)).toThrow(new TypeError(message));
    expect(() => render(null as unknown as DocumentGraph)).toThrow(TypeError);
  });
});
