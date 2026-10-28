import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { save } from "./graph/save.js";
import { include } from "./include.js";
import { villanelle } from "./load/processor.js";
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
    const loaded = await villanelle({ source: createFileSource(), extensions: [include()] }).load(root);
    expect(loaded.diagnostics).toEqual([]);
    // Files only (the sub.conf directory is skipped); the [ ] in a file name match themselves.
    const [glob, plain] = loaded.graph.edges;
    expect(glob?.targets).toEqual(["C.conf", "a.conf", "b.conf", "x[1].conf", "é.conf"].map((name) => join(dir, "conf.d", name)));
    expect(plain?.targets).toEqual([join(dir, "plain.conf")]);
    expect(loaded.body.map((d) => d.args[0]?.text)).toEqual(['"C.conf"', '"a.conf"', '"b.conf"', '"x[1].conf"', '"é.conf"', "1"]);
  });

  it("resolves a relative root through the source, so the root has one path and is read once", async () => {
    await writeFile(join(dir, "self.conf"), 'x "1;\ninclude "self.conf";\ny 1;\n');
    const loaded = await villanelle({ source: createFileSource(), extensions: [include()] }).load(relative(process.cwd(), join(dir, "self.conf")));
    expect([...loaded.graph.nodes.keys()]).toEqual([join(dir, "self.conf")]);
    expect(loaded.diagnostics.map((d) => d.code)).toEqual(["E1001", "E5006"]);
    expect(loaded.body.map((d) => d.name)).toEqual(["y"]);
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
    const loaded = await villanelle({ source, extensions: [include()] }).load(join(dir, "plain.conf"));
    expect(loaded.diagnostics).toEqual([]);
    await writeFile(join(dir, "missing-include.conf"), 'include "missing.conf";\n');
    const missing = await villanelle({ source, extensions: [include()] }).load(join(dir, "missing-include.conf"));
    expect(missing.diagnostics.map((d) => d.code)).toEqual(["E3001"]);
  });

  it("writes text back with the fs writer, and save writes nothing for an unchanged load", async () => {
    const path = join(dir, "written.conf");
    await createFsWriter().write(path, "w 1;\n");
    expect(await readFile(path, "utf8")).toBe("w 1;\n");
    const loaded = await villanelle({ source: createFileSource() }).load(path);
    await save(loaded.graph, createFsWriter());
    expect(await readFile(path, "utf8")).toBe("w 1;\n");
  });
});
