/**
 * The worker deep.test.ts starts with a small stack: it loads the package source (compiled by the test and served
 * here through Node's module hooks, so no compiler runs on the small stack), runs the deep walks over `main.conf` and
 * posts what they found, or the error that stopped them.
 */

import { registerHooks } from "node:module";
import { parentPort, workerData } from "node:worker_threads";

import type * as root from "../src/index.ts";
import type * as rendered from "../src/rendered/index.ts";
import type * as written from "../src/written/index.ts";

/**
 * The worker's task. `blocks`: load and render `before` and `after`, then walk, address, diff and climb `before`.
 * `list`: load and render `text`, whose first directive reads a list through variables.
 */
export type DeepTask = { readonly task: "blocks"; readonly before: string; readonly after: string } | { readonly task: "list"; readonly text: string };

/** What the worker is given: its task, and the package's modules as JavaScript, by `.ts` URL. */
export type DeepJob = DeepTask & { readonly modules: Readonly<Record<string, string>> };

/** What the walks found, or the error that stopped them. */
export type DeepResult =
  | {
      readonly diagnostics: number;
      readonly walked: number;
      /** The frames between `walk`'s caller and the visit of the deepest directive. */
      readonly walkFrames: number;
      readonly deepestAddress: number;
      readonly changes: readonly (readonly [string, number])[];
      readonly closest: string | undefined;
      /** The frames between `closest`'s caller and the predicate's call on the outermost directive. */
      readonly closestFrames: number;
    }
  | { readonly diagnostics: number; readonly depth: number; readonly via: number; readonly text: string | undefined }
  | { readonly error: string };

const job = workerData as DeepJob;
const SRC = new URL("../src/", import.meta.url).href;

registerHooks({
  // The package's own imports name the emitted `.js`; under `src/` each is the `.ts` module beside it.
  resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith(SRC) === true && specifier.startsWith(".") && specifier.endsWith(".js")) {
      const url = new URL(specifier.replace(/\.js$/, ".ts"), context.parentURL).href;
      if (url in job.modules) return { url, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    const source = job.modules[url];
    return source === undefined ? nextLoad(url, context) : { format: "module", source, shortCircuit: true };
  },
});

/** The frames on the stack where it is called. */
function frames(): number {
  const limit = Error.stackTraceLimit;
  Error.stackTraceLimit = Infinity;
  const stack = new Error().stack ?? "";
  Error.stackTraceLimit = limit;
  return stack.split("\n").length - 1;
}

async function walks(): Promise<DeepResult> {
  const { memorySource } = (await import(new URL("index.ts", SRC).href)) as typeof root;
  const { knobly } = (await import(new URL("written/index.ts", SRC).href)) as typeof written;
  const { render } = (await import(new URL("rendered/index.ts", SRC).href)) as typeof rendered;
  const load = async (text: string): Promise<rendered.Rendered> => render(await knobly({ source: memorySource({ "main.conf": text }) }).load("main.conf"));

  if (job.task === "list") {
    // Each variable's read rebases the whole list below it (ExpandedRecord.rebase).
    const loaded = await load(job.text);
    let depth = 0;
    let via = 0;
    for (let value = loaded.block.at(0)?.values[0]; value !== undefined; value = value.kind === "list" ? value.items[0] : undefined) {
      if (value.kind === "list") depth += 1;
      via = value.origin.via.length;
    }
    return { diagnostics: loaded.diagnostics.length, depth, via, text: loaded.block.at(0)?.values[0]?.text };
  }

  const before = await load(job.before);
  const after = await load(job.after);
  let walked = 0;
  let walkFrames = 0;
  let leaf: rendered.Directive | undefined;
  const atWalk = frames();
  before.block.walk((directive) => {
    walked += 1;
    if (directive.name !== "leaf") return;
    leaf = directive;
    walkFrames = frames() - atWalk;
  });
  let deepestAddress = 0;
  for (const address of before.addresses().values()) deepestAddress = Math.max(deepestAddress, address.steps.length);
  const changes = before.diff(after).map((change) => [change.kind, change.address.steps.length] as const);
  let closestFrames = 0;
  const atClosest = frames();
  const closest = leaf?.closest((directive) => {
    if (directive.parent !== undefined) return false;
    closestFrames = frames() - atClosest;
    return true;
  })?.name;
  return { diagnostics: before.diagnostics.length, walked, walkFrames, deepestAddress, changes, closest, closestFrames };
}

parentPort?.postMessage(await walks().catch((error: unknown): DeepResult => ({ error: error instanceof Error ? String(error.stack) : String(error) })));
