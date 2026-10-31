/**
 * Trees 256 levels deep after expansion (spec 2.5, MAX_EXPANDED_NESTING; kno-bzv.9), worked in a worker with a small
 * stack, so a walk that recursed once per level would overflow it. The Python and C++ bindings test the same trees
 * (py/tests/test_load.py, cpp/tests/unit/written_deep.cpp).
 *
 * Parsing a text 17 blocks deep takes more of the stack than 256 levels of the old recursive walk or closest did, so
 * no stack the load fits in would catch those two: they are held to the frames they put on the stack between the
 * call and the callback, which a recursion makes at least 256. The bound is far below that (fewer than 16), so a
 * helper frame more or less does not matter; one frame a level does. A worker's stack also holds Node's own start (192 KB
 * kept in reserve; a worker that runs nothing fails on 0.26 MB).
 *
 * Measured on Node 24.14 (arm64 macOS), with KNOBLY_DEEP_STACK_MB: the blocks task needs 0.3 MB, so it runs on 0.4.
 * The list task needs 0.28 MB; with the old recursive rebase it needed 0.35, so it runs on 0.31: about 10% above the
 * loop's need and 10% below the recursion's. Linux CI passes it too; if a platform's frames differ, set it again from
 * these two measures, between them.
 */

import { readdirSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { Worker } from "node:worker_threads";

import ts from "typescript";
import { describe, expect, it } from "vitest";

import type { DeepJob, DeepResult, DeepTask } from "./deep-worker.ts";

/**
 * Sixteen snippets of sixteen blocks, each using the next inside its blocks: `leaf` stands inside 256 expanded blocks,
 * while no text nests deeper than 17.
 */
function deepSnippets(leaf: string): string {
  const lines = Array.from({ length: 16 }, (_, i) => {
    const inner = i < 15 ? `@use s${String(i + 2)};` : leaf;
    return `@snippet s${String(i + 1)} { ${"b { ".repeat(16)}${inner} ${"} ".repeat(16)}}`;
  });
  return [...lines, "@use s1;", ""].join("\n");
}

/**
 * 128 variables of two lists each, each holding the one before: `leaf $v128;` reads a value 256 lists deep, while no
 * text nests deeper than 2.
 */
function deepList(): string {
  const sets = Array.from({ length: 128 }, (_, i) => `@set $v${String(i + 1)} [[${i === 0 ? "x" : `$v${String(i)}`}]];`);
  return [...sets, "leaf $v128;", ""].join("\n");
}

/** The package's modules as JavaScript, by `.ts` URL: compiled here, so the worker's small stack runs only knobly. */
function modules(): Record<string, string> {
  const src = new URL("../src/", import.meta.url);
  const files = readdirSync(src, { recursive: true, encoding: "utf8" }).filter((file) => file.endsWith(".ts") && !file.endsWith(".test.ts"));
  return Object.fromEntries(
    files.map((file) => {
      const url = new URL(file, src);
      const compiled = ts.transpileModule(readFileSync(url, "utf8"), {
        fileName: url.pathname,
        compilerOptions: { target: ts.ScriptTarget.ES2023, module: ts.ModuleKind.ESNext, isolatedModules: true },
      });
      return [pathToFileURL(url.pathname).href, compiled.outputText];
    }),
  );
}

/** `task` in a worker whose stack is `stackSizeMb` (KNOBLY_DEEP_STACK_MB when set, to measure). */
function onSmallStack(stackSizeMb: number, task: DeepTask): Promise<DeepResult> {
  const given = process.env["KNOBLY_DEEP_STACK_MB"];
  const resourceLimits = { stackSizeMb: given === undefined ? stackSizeMb : Number(given) };
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("deep-worker.ts", import.meta.url), { workerData: { ...task, modules: modules() } satisfies DeepJob, resourceLimits });
    worker.once("message", (result: DeepResult) => {
      resolve(result);
      void worker.terminate();
    });
    worker.once("error", reject);
    worker.once("exit", (code) => {
      reject(new Error(`the deep worker exited with ${String(code)} before it answered`));
    });
  });
}

/** Fewer frames than this between a walk's call and its callback: far below the 256 a recursion a level would make. */
const FRAME_BOUND = 16;

describe("a tree 256 levels deep after expansion", () => {
  it("is loaded, rendered, walked, addressed, diffed and climbed on a small stack, with no frame a level", async () => {
    const result = await onSmallStack(0.4, { task: "blocks", before: deepSnippets("leaf;"), after: deepSnippets("leaf 1;") });
    const { walkFrames, closestFrames, ...rest } = result as Extract<DeepResult, { walked: number }>;
    expect(rest).toEqual({ diagnostics: 0, walked: 257, deepestAddress: 257, changes: [["changed", 257]], closest: "b" });
    expect(walkFrames).toBeLessThan(FRAME_BOUND);
    expect(closestFrames).toBeLessThan(FRAME_BOUND);
  }, 30_000);

  it("is a list read through 128 variables, each read rebasing the list below it on a small stack", async () => {
    const result = await onSmallStack(0.31, { task: "list", text: deepList() });
    expect(result).toEqual({ diagnostics: 0, depth: 256, via: 128, text: `${"[".repeat(256)}x${"]".repeat(256)}` });
  }, 30_000);
});
