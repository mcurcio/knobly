import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { SaveError } from "./written/errors.js";
import { include } from "./include.js";
import { villanelle } from "./written/processor.js";
import { rendered } from "./rendered/testing.js";
import { createFileSource, createFsWriter } from "./node.js";

describe("villanelle/node", () => {
  let dir = "";

  beforeAll(async () => {
    dir = await mkdtemp(join(tmpdir(), "villanelle-node-"));
    await mkdir(join(dir, "conf.d"));
    await mkdir(join(dir, "conf.d", "sub.conf"));
    await writeFile(join(dir, "root.conf"), 'include "conf.d/*.conf";\ninclude "plain.conf";\n');
    await writeFile(join(dir, "plain.conf"), "plain 1;\n");
    for (const name of ["b.conf", "C.conf", "é.conf", "a.conf", "a.txt", "x[1].conf"]) {
      await writeFile(join(dir, "conf.d", name), `f "${name}";\n`);
    }
  });

  afterAll(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("resolves specs against the including file's directory and splices glob matches in code-point order", async () => {
    const root = join(dir, "root.conf");
    const loaded = await rendered(villanelle({ source: createFileSource(), extensions: [include()] }), root);
    expect(loaded.diagnostics).toEqual([]);
    // Files only (the sub.conf directory is skipped); the [ ] in a file name match themselves.
    const [glob, plain] = loaded.graph.edges();
    expect(glob?.targets).toEqual(["C.conf", "a.conf", "b.conf", "x[1].conf", "é.conf"].map((name) => join(dir, "conf.d", name)));
    expect(plain?.targets).toEqual([join(dir, "plain.conf")]);
    expect(loaded.block.map((d) => d.values[0]?.text)).toEqual(['"C.conf"', '"a.conf"', '"b.conf"', '"x[1].conf"', '"é.conf"', "1"]);
  });

  it("resolves a relative root through the source, so the root has one path and is read once", async () => {
    await writeFile(join(dir, "self.conf"), 'x "1;\ninclude "self.conf";\ny 1;\n');
    const loaded = await rendered(villanelle({ source: createFileSource(), extensions: [include()] }), relative(process.cwd(), join(dir, "self.conf")));
    expect([...loaded.graph.documents.keys()]).toEqual([join(dir, "self.conf")]);
    expect(loaded.diagnostics.map((d) => d.code)).toEqual(["E1001", "E5006"]);
    expect(loaded.block.map((d) => d.name)).toEqual(["y"]);
  });

  it("matches ? to one character", async () => {
    const found = await createFileSource().resolve("conf.d/?.conf", { parentPath: join(dir, "root.conf") });
    expect([...found].sort()).toEqual(["C.conf", "a.conf", "b.conf", "é.conf"].map((name) => join(dir, "conf.d", name)).sort());
  });

  it("resolves a missing file or directory to no paths (E3001) and rejects reading a missing file", async () => {
    const source = createFileSource();
    const context = { parentPath: join(dir, "root.conf") };
    expect(await source.resolve("missing.conf", context)).toEqual([]);
    expect(await source.resolve("conf.d/*.none", context)).toEqual([]);
    expect(await source.resolve("nodir/*.conf", context)).toEqual([]);
    expect(await source.resolve("conf.d/sub.conf", context)).toEqual([]);
    await expect(source.read(join(dir, "missing.conf"))).rejects.toThrow(/ENOENT/);
    const loaded = await rendered(villanelle({ source, extensions: [include()] }), join(dir, "plain.conf"));
    expect(loaded.diagnostics).toEqual([]);
    await writeFile(join(dir, "missing-include.conf"), 'include "missing.conf";\n');
    const missing = await rendered(villanelle({ source, extensions: [include()] }), join(dir, "missing-include.conf"));
    expect(missing.diagnostics.map((d) => d.code)).toEqual(["E3001"]);
  });

  it("writes text back with the fs writer, and save writes nothing for an unchanged load", async () => {
    const path = join(dir, "written.conf");
    await createFsWriter().write([{ resolvedPath: path, text: "w 1;\n", savedText: "" }]);
    expect(await readFile(path, "utf8")).toBe("w 1;\n");
    const graph = await villanelle({ source: createFileSource() }).load(path);
    expect(await graph.save(createFsWriter())).toEqual([]);
    expect(await readFile(path, "utf8")).toBe("w 1;\n");
  });

  /** The temporary files the fs writer left in a directory. */
  async function temporaries(directory: string): Promise<string[]> {
    return (await readdir(directory)).filter((name) => name.endsWith(".tmp"));
  }

  it("stages a batch beside its targets and renames it over them, updating each source (D18)", async () => {
    const directory = join(dir, "batch");
    await mkdir(directory);
    await writeFile(join(directory, "main.conf"), 'include "part.conf";\nm 1;\n');
    await writeFile(join(directory, "part.conf"), "p 1;\n");
    const graph = await villanelle({ source: createFileSource(), extensions: [include()] }).load(join(directory, "main.conf"));
    const [main, part] = [...graph.documents.values()];
    const m = main?.block.statements[1];
    const p = part?.block.statements[0];
    if (m?.kind !== "directive" || p?.kind !== "directive") throw new Error("fixture");
    m.set("2");
    p.set("2");
    expect(await graph.save(createFsWriter())).toEqual([join(directory, "main.conf"), join(directory, "part.conf")]);
    expect(await readFile(join(directory, "main.conf"), "utf8")).toBe('include "part.conf";\nm 2;\n');
    expect(await readFile(join(directory, "part.conf"), "utf8")).toBe("p 2;\n");
    expect(main?.savedText).toBe(main?.text);
    expect(await temporaries(directory)).toEqual([]);
  });

  it("refuses a lost update, writing nothing, and names the file", async () => {
    const directory = join(dir, "lost");
    await mkdir(directory);
    const [a, b] = [join(directory, "a.conf"), join(directory, "b.conf")];
    await writeFile(a, "a 1;\n");
    await writeFile(b, "b 1;\n");
    const graph = await villanelle({ source: createFileSource() }).load(a);
    const statement = graph.root.block.statements[0];
    if (statement?.kind !== "directive") throw new Error("fixture");
    statement.set("2");
    // Someone else changes b after it was read.
    await writeFile(b, "b changed;\n");
    const batch = [
      { resolvedPath: a, text: "a 2;\n", savedText: "a 1;\n" },
      { resolvedPath: b, text: "b 2;\n", savedText: "b 1;\n" },
    ];
    await expect(createFsWriter().write(batch)).rejects.toThrow(/lost update.*b\.conf/);
    expect(await readFile(a, "utf8")).toBe("a 1;\n");
    expect(await readFile(b, "utf8")).toBe("b changed;\n");
    // Through save: a changed on disk too, so SaveError, and the document keeps its unsaved text.
    await writeFile(a, "a changed;\n");
    await expect(graph.save(createFsWriter())).rejects.toBeInstanceOf(SaveError);
    expect(await readFile(a, "utf8")).toBe("a changed;\n");
    expect(graph.root.text).not.toBe(graph.root.savedText);
    expect(await temporaries(directory)).toEqual([]);
  });

  it("replaces nothing and leaves no temporary file when staging fails part way", async () => {
    const directory = join(dir, "staging");
    await mkdir(directory);
    const a = join(directory, "a.conf");
    await writeFile(a, "a 1;\n");
    const batch = [
      { resolvedPath: a, text: "a 2;\n", savedText: "a 1;\n" },
      // A new file in a directory that is not there: nothing on disk, so no lost update, but it cannot be staged.
      { resolvedPath: join(directory, "missing", "b.conf"), text: "b 1;\n", savedText: "" },
    ];
    await expect(createFsWriter().write(batch)).rejects.toThrow(/ENOENT/);
    expect(await readFile(a, "utf8")).toBe("a 1;\n");
    expect(await temporaries(directory)).toEqual([]);
  });
});
