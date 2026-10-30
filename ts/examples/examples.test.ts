// The user guide's samples (examples/samples.json; .claude/design/cpp/frozen-docs.md): every ts/examples/<id>.ts runs
// in a fresh copy of its fixture folder, and what it prints with console.log must be examples/expected/<id>.txt byte
// for byte. The same table drives py/tests/test_examples.py and cpp/examples/CMakeLists.txt, so the three bindings'
// samples print the same text. TypeScript's file source makes paths absolute (Python's and C++'s stay relative), so
// the run folder is cut from the output before comparing. A reader runs a sample with plain `node <file>.ts`, whose
// type stripping refuses TypeScript-only syntax (parameter properties, enums, namespaces) that vitest would compile,
// so each sample must also strip as Node strips it.
import { stripTypeScriptTypes } from "node:module";
import { cpSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { format } from "node:util";

import { describe, expect, it } from "vitest";

interface Samples {
  readonly samples: Readonly<Record<string, { readonly fixture: string | null }>>;
}

const REPO = join(import.meta.dirname, "..", "..");
const TABLE = JSON.parse(readFileSync(join(REPO, "examples", "samples.json"), "utf8")) as Samples;
const FILES = readdirSync(import.meta.dirname).filter((f) => f.endsWith(".ts") && !f.endsWith(".test.ts"));

/** Runs one sample in `folder`, giving back what it printed. */
async function run(file: string, folder: string): Promise<string> {
  const printed: string[] = [];
  const log = console.log;
  const cwd = process.cwd();
  console.log = (...args: unknown[]): void => void printed.push(format(...args) + "\n");
  process.chdir(folder);
  try {
    await import(join(import.meta.dirname, file));
  } finally {
    process.chdir(cwd);
    console.log = log;
  }
  return printed.join("");
}

describe("the user guide's samples", () => {
  it.each(FILES)("%s is in examples/samples.json", (file) => {
    expect(Object.keys(TABLE.samples)).toContain(basename(file, ".ts"));
  });

  it.each(FILES)("%s runs under plain node (erasable TypeScript only)", (file) => {
    expect(() => stripTypeScriptTypes(readFileSync(join(import.meta.dirname, file), "utf8"))).not.toThrow();
  });

  it.each(FILES.filter((f) => basename(f, ".ts") in TABLE.samples))("%s prints its expected output", async (file) => {
    const id = basename(file, ".ts");
    const fixture = TABLE.samples[id]?.fixture ?? null;
    const folder = realpathSync(mkdtempSync(join(tmpdir(), `villanelle-${id}-`)));
    try {
      if (fixture !== null) cpSync(join(REPO, fixture), folder, { recursive: true });
      const printed = (await run(file, folder)).replaceAll(folder + "/", "");
      expect(printed).toBe(readFileSync(join(REPO, "examples", "expected", `${id}.txt`), "utf8"));
    } finally {
      rmSync(folder, { recursive: true, force: true });
    }
  });
});
