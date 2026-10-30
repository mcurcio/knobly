/**
 * The edge contract's per-binding parts (spec/contract.md 4 and 5; frozen-m2.md section 13, "Per-binding tests"):
 * the error class tree, `save` refusing a non-writer, the memory adapters sharing one object, and `render` taking any
 * object with the document graph's public members (spec 7.0).
 */

import { describe, expect, it } from "vitest";

import * as villanelleModule from "./index.js";
import { BadTextError, checkLostUpdates, DetachedError, DiagnosticError, LostUpdateError, memorySource, memoryWriter, MisuseError, ReadError, SaveError, VillanelleError } from "./index.js";
import { parse } from "./syntax/parse.js";
import { text } from "./index.js";
import { render } from "./rendered/index.js";
import { type DocumentGraph, villanelle } from "./written/index.js";

describe("the error classes (spec 2.8; spec/contract.md 4.2)", () => {
  it("put every expected outcome under VillanelleError and every program bug outside it", () => {
    const tree: [new (...args: never[]) => Error, new (...args: never[]) => Error][] = [
      [DiagnosticError, VillanelleError],
      [ReadError, VillanelleError],
      [SaveError, VillanelleError],
      [LostUpdateError, SaveError],
      [BadTextError, VillanelleError],
      [DetachedError, ReferenceError],
      [MisuseError, Error],
      [VillanelleError, Error],
    ];
    for (const [cls, parent] of tree) expect(cls.prototype instanceof parent, `${cls.name} extends ${parent.name}`).toBe(true);
    for (const bug of [DetachedError, MisuseError]) expect(bug.prototype instanceof VillanelleError, bug.name).toBe(false);
    expect(MisuseError.prototype instanceof TypeError).toBe(false);
    expect(ReadError.prototype instanceof DiagnosticError).toBe(false);
    expect(new DetachedError("x").name).toBe("DetachedError");
    expect(new MisuseError("x").name).toBe("MisuseError");
    expect(new ReadError("x", ["a"]).name).toBe("ReadError");
    expect(new LostUpdateError(["a", "b"]).name).toBe("LostUpdateError");
    expect("NoSetLineError" in villanelleModule).toBe(false);
    expect("EditError" in villanelleModule).toBe(false);
  });

  it("build a bad text error's message from its diagnostics' people forms", () => {
    const error = new BadTextError(parse("x 1;;").diagnostics.concat(parse("{").diagnostics));
    expect(error.message).toBe(`bad text: ${error.diagnostics.map(String).join("; ")}`);
    expect(new BadTextError(parse("x {").diagnostics).message).toMatch(/^bad text: 1:4: E2003: [^;]+$/);
  });

  it("a detached handle throws DetachedError, a program bug outside VillanelleError", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    const [a] = graph.root.block;
    a?.remove();
    let thrown: unknown;
    try {
      void a?.text;
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeInstanceOf(DetachedError);
    expect(thrown).toBeInstanceOf(ReferenceError);
    expect(thrown).not.toBeInstanceOf(VillanelleError);
  });
});

describe("save (writer)", () => {
  it("refuses a writer without a write method with TypeError, before anything", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    graph.root.block.directives()[0]?.set(text("2"));
    const write = (): Promise<void> => Promise.resolve();
    const error: unknown = await graph.save(write as unknown as Parameters<DocumentGraph["save"]>[0]).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(TypeError);
    expect((error as TypeError).message).toBe(
      'save(): argument "writer" must be a document writer (an object with a write method), not function',
    );
    expect(graph.root.savedText).toBe("a 1;\n");
  });
});

describe("the memory adapters (spec/contract.md 5)", () => {
  it("share one object: a save through memoryWriter is what the next load reads", async () => {
    const files: Record<string, string> = { "main.conf": "a 1;\n" };
    const processor = villanelle({ source: memorySource(files) });
    const graph = await processor.load("main.conf");
    graph.root.block.directives()[0]?.set(text("2"));
    expect(await graph.save(memoryWriter(files))).toEqual(["main.conf"]);
    expect(files["main.conf"]).toBe("a 2;\n");
    expect((await processor.load("main.conf")).root.text).toBe("a 2;\n");
  });

  it("memorySource reads the object live: a key added after it was made is found", async () => {
    const files: Record<string, string> = {};
    const processor = villanelle({ source: memorySource(files) });
    files["late.conf"] = "x;\n";
    expect((await processor.load("late.conf")).root.text).toBe("x;\n");
  });

  it("memoryWriter refuses a lost update with a LostUpdateError, raised by save as it is, writing nothing", async () => {
    const files: Record<string, string> = { "main.conf": "a 1;\n", "b.conf": "b;\n" };
    const graph = await villanelle({ source: memorySource(files) }).load("main.conf");
    graph.root.block.directives()[0]?.set(text("2"));
    files["main.conf"] = "changed;\n";
    const error: unknown = await graph.save(memoryWriter(files)).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(LostUpdateError);
    expect((error as LostUpdateError).paths).toEqual(["main.conf"]);
    expect((error as LostUpdateError).message).toBe("lost update: changed since read: main.conf");
    expect((error as LostUpdateError).cause).toBeUndefined();
    expect(files["main.conf"]).toBe("changed;\n");
    expect(graph.root.savedText).toBe("a 1;\n");
  });

  it("checkLostUpdates names only the conflicting files, in batch order, an absent file read as empty", () => {
    const batch = [
      { resolvedPath: "a", text: "1", savedText: "x" },
      { resolvedPath: "b", text: "2", savedText: "y" },
      { resolvedPath: "c", text: "3", savedText: "" },
    ];
    expect(() => checkLostUpdates(batch, ["x", "y", undefined])).not.toThrow();
    const error: unknown = (() => {
      try {
        checkLostUpdates(batch, ["z", "y", "w"]);
      } catch (e) {
        return e;
      }
      return undefined;
    })();
    expect(error).toBeInstanceOf(LostUpdateError);
    expect((error as LostUpdateError).paths).toEqual(["a", "c"]);
  });

  it("checkLostUpdates refuses a current list not as long as the batch, as a misuse error", () => {
    expect(() => checkLostUpdates([{ resolvedPath: "a", text: "1", savedText: "y" }], [])).toThrow(MisuseError);
    expect(() => checkLostUpdates([{ resolvedPath: "a", text: "1", savedText: "" }], [])).toThrow(MisuseError);
  });

  it("memoryWriter treats a missing key as empty text", async () => {
    const files: Record<string, string> = {};
    await memoryWriter(files).write([{ resolvedPath: "new.conf", text: "n;\n", savedText: "" }]);
    expect(files).toEqual({ "new.conf": "n;\n" });
  });
});

describe("render (graph) on the public low level (spec 7.0)", () => {
  it("takes any object with the document graph's public members", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "@set $a 1;\nx $a { y; }\n" }) }).load("main.conf");
    const facade: DocumentGraph = {
      get root() {
        return graph.root;
      },
      documents: graph.documents,
      overrides: graph.overrides,
      diagnostics: graph.diagnostics,
      setOverride: (name, text) => graph.setOverride(name, text),
      read: () => graph.read(),
      save: (writer) => graph.save(writer),
      edges: () => graph.edges(),
      unread: () => graph.unread(),
      variables: (name) => graph.variables(name),
      expand: () => graph.expand(),
    };
    const rendered = render(facade);
    expect(rendered.graph).toBe(facade);
    expect([...rendered.block].map((d) => [d.name, d.values.map((v) => v.text), (d.block === undefined ? undefined : [...d.block].map((c) => c.name))])).toEqual([["x", ["1"], ["y"]]]);
    expect(String(rendered.origin.place)).toBe("main.conf:1:1");
  });

  it("expand () is a snapshot: the same object until an edit, a new one after", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "x 1;\n" }) }).load("main.conf");
    const first = graph.expand();
    expect(graph.expand()).toBe(first);
    const [x] = first.block;
    expect(x?.written.name).toBe("x");
    expect(x?.values.map((v) => [v.text, v.written.text, v.definition?.text, v.chain.length])).toEqual([["1", "1", "1", 0]]);
    expect(first.diagnostics).toBe(graph.diagnostics);
    graph.root.block.directives()[0]?.set(text("2"));
    expect(graph.expand()).not.toBe(first);
    expect(graph.expand().block.at(0)?.values[0]?.text).toBe("2");
  });

  it("builds the rendered directive on the expansion's own objects (spec 7.0)", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "@set $p [1, 2];\nx $p;\nbad $nope;\nb { c 1; }\n" }) }).load("main.conf");
    const expansion = graph.expand();
    const rendered = render(graph);
    expect(rendered.block.at(0)?.values).toBe(expansion.block.at(0)?.values);
    expect(rendered.block.at(0)?.written).toBe(expansion.block.at(0)?.written);
    expect(rendered.block.at(0)?.origin).toBe(expansion.block.at(0)?.origin);
    expect(rendered.unreadable).toBe(expansion.unreadable);
    expect(rendered.diagnostics).toBe(graph.diagnostics);
    expect(graph.diagnostics.map((d) => d.code)).toEqual(["E5001"]);
    const [list] = rendered.block.at(0)?.values ?? [];
    expect(list?.kind === "list" ? list.items.map((i) => [i.text, i.written.text, i.definition?.text]) : []).toEqual([
      ["1", "$p", "1"],
      ["2", "$p", "2"],
    ]);
  });
});
