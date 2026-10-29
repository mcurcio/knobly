/**
 * The edge contract's per-binding parts (spec/contract.md 4 and 5; frozen-m2.md section 13, "Per-binding tests"):
 * the error class tree, `save` refusing a non-writer, the memory adapters sharing one object, and `render` taking any
 * object with the document graph's public members (spec 7.0).
 */

import { describe, expect, it } from "vitest";

import * as villanelleModule from "./index.js";
import {
  BadTextError,
  DetachedError,
  DiagnosticError,
  EditError,
  type IDocumentGraph,
  memorySource,
  memoryWriter,
  ReadError,
  render,
  SaveError,
  villanelle,
  VillanelleError,
} from "./index.js";

describe("the error classes (spec/contract.md 4.2)", () => {
  it("are one tree under VillanelleError, each named after its class", () => {
    const tree: [new (...args: never[]) => Error, new (...args: never[]) => Error][] = [
      [DiagnosticError, VillanelleError],
      [ReadError, VillanelleError],
      [SaveError, VillanelleError],
      [EditError, VillanelleError],
      [BadTextError, EditError],
      [DetachedError, VillanelleError],
      [VillanelleError, Error],
    ];
    for (const [cls, parent] of tree) expect(cls.prototype instanceof parent, `${cls.name} extends ${parent.name}`).toBe(true);
    expect(DetachedError.prototype instanceof EditError).toBe(false);
    expect(ReadError.prototype instanceof DiagnosticError).toBe(false);
    expect(new DetachedError("x").name).toBe("DetachedError");
    expect(new ReadError("x", ["a"]).name).toBe("ReadError");
    expect("NoSetLineError" in villanelleModule).toBe(false);
  });

  it("a detached handle throws DetachedError, which is not an edit error", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    const [a] = graph.root.block.statements;
    a?.remove();
    let thrown: unknown;
    try {
      void a?.text;
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toBeInstanceOf(DetachedError);
    expect(thrown).toBeInstanceOf(VillanelleError);
    expect(thrown).not.toBeInstanceOf(EditError);
  });
});

describe("save (writer)", () => {
  it("refuses a writer without a write method with TypeError, before anything", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a 1;\n" }) }).load("main.conf");
    graph.root.block.directives()[0]?.set("2");
    const write = (): Promise<void> => Promise.resolve();
    const error: unknown = await graph.save(write as unknown as Parameters<IDocumentGraph["save"]>[0]).catch((e: unknown) => e);
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
    graph.root.block.directives()[0]?.set("2");
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

  it("memoryWriter refuses a lost update, naming the path and writing nothing", async () => {
    const files: Record<string, string> = { "main.conf": "a 1;\n", "b.conf": "b;\n" };
    const graph = await villanelle({ source: memorySource(files) }).load("main.conf");
    graph.root.block.directives()[0]?.set("2");
    files["main.conf"] = "changed;\n";
    const error: unknown = await graph.save(memoryWriter(files)).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SaveError);
    expect((error as SaveError).paths).toEqual(["main.conf"]);
    expect(String((error as SaveError).cause)).toContain("main.conf");
    expect(files["main.conf"]).toBe("changed;\n");
    expect(graph.root.savedText).toBe("a 1;\n");
  });

  it("memoryWriter treats a missing key as empty text", async () => {
    const files: Record<string, string> = {};
    await memoryWriter(files).write([{ resolvedPath: "new.conf", text: "n;\n", savedText: "" }]);
    expect(files).toEqual({ "new.conf": "n;\n" });
  });
});

describe("render (graph) on the public low level (spec 7.0)", () => {
  it("takes any object with the document graph's public members", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "set $a 1;\nx $a { y; }\n" }) }).load("main.conf");
    const facade: IDocumentGraph = {
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
    expect(rendered.block.map((d) => [d.name, d.values.map((v) => v.text), d.block?.map((c) => c.name)])).toEqual([["x", ["1"], ["y"]]]);
    expect(String(rendered.origin.place)).toBe("main.conf:1:1");
  });

  it("expand () is a snapshot: the same object until an edit, a new one after", async () => {
    const graph = await villanelle({ source: memorySource({ "main.conf": "x 1;\n" }) }).load("main.conf");
    const first = graph.expand();
    expect(graph.expand()).toBe(first);
    const [x] = first.block;
    expect(x?.statement.name).toBe("x");
    expect(x?.values.map((v) => [v.value.text, v.written.text, v.definition?.text, v.chain.length, v.items.length])).toEqual([["1", "1", "1", 0, 0]]);
    graph.root.block.directives()[0]?.set("2");
    expect(graph.expand()).not.toBe(first);
    expect(graph.expand().block[0]?.values[0]?.value.text).toBe("2");
  });
});
