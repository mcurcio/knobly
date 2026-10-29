/**
 * The public-name check (spec/codegen.md, "Milestone 1"): every member spec/schema/api.json lists for a concept
 * exists, under this binding's casing (camelCase) or the member's "spell", on a real object of that concept, as a
 * property or a method as the schema says. It also checks the free functions and the error classes the schema
 * names. Interfaces do not exist at run time, so the objects come from a probe: a memory-source graph loaded with an
 * override, two renders, a diff, a save, and the ports' calls. Which object is which concept follows the schema's
 * member types from those roots, so the walk itself only uses spec names.
 *
 * It reads the schema directly (no generated copy) and fails the build when a name drifts. The reverse direction (a
 * public name the schema lacks) is a later milestone.
 */
import { readFileSync } from "node:fs";

import { beforeAll, describe, expect, it } from "vitest";

interface IParam {
  readonly name: string;
  readonly optional?: boolean;
}
interface ISpell {
  readonly ts?: string;
  readonly py?: string;
}
interface IMember {
  readonly name: string;
  readonly member: "property" | "method";
  readonly type?: string;
  readonly returns?: string;
  readonly params?: readonly IParam[];
  readonly io?: boolean;
  readonly spell?: ISpell;
}
interface IConcept {
  readonly name: string;
  readonly ts: string;
  readonly members?: readonly IMember[];
  readonly variants?: readonly string[];
  readonly extends?: string;
}
interface IFreeFunction {
  readonly name: string;
  readonly params?: readonly IParam[];
  readonly returns?: string;
  readonly spell?: ISpell;
}
interface IErrorGroup {
  readonly name: string;
  readonly parent?: string;
  readonly ts: string;
}
interface ISchema {
  readonly kinds: Readonly<Record<string, { readonly values?: readonly string[] }>>;
  readonly concepts: readonly IConcept[];
  readonly "free functions": readonly IFreeFunction[];
  readonly "error groups": readonly IErrorGroup[];
}

type Bag = Record<PropertyKey, unknown>;
type Fn = (...args: unknown[]) => unknown;

const SCHEMA = JSON.parse(readFileSync(new URL("../../spec/schema/api.json", import.meta.url), "utf8")) as ISchema;
const CONCEPTS = new Map(SCHEMA.concepts.map((c) => [c.name, c]));
const FREE = new Map(SCHEMA["free functions"].map((f) => [f.name, f]));
/** Every kind word: an alternative named by none of them is the default one ("place or override", kind "file"). */
const KIND_WORDS = new Set(Object.values(SCHEMA.kinds).flatMap((k) => k.values ?? []));

// --- names: binding guide rule 1 and the schema's "spell" ------------------------------------------------------

function words(name: string): string[] {
  return name.trim().split(/[ -]+/u);
}

function camel(name: string): string {
  return words(name)
    .map((w, i) => (i === 0 ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join("");
}

/** The property key a spec name has here: camelCase, or what the member's TypeScript "spell" says. */
function keyOf(item: { readonly name: string; readonly spell?: ISpell }): PropertyKey {
  const spell = item.spell?.ts;
  if (spell === undefined) return camel(item.name);
  if (spell === "[Symbol.iterator]") return Symbol.iterator;
  // A type spelling ("ReadonlyMap<string, string>") keeps the name's casing.
  if (/^[A-Za-z_$][\w$]*[<[]/u.test(spell)) return camel(item.name);
  const m = /^(?:new\s+)?([A-Za-z_$][\w$]*)(?:\(.*|\s+\(.*)?$/su.exec(spell);
  if (m?.[1] === undefined) throw new Error(`api-names: cannot read the TypeScript spell ${JSON.stringify(spell)} of ${item.name}`);
  return m[1];
}

function show(key: PropertyKey): string {
  return typeof key === "symbol" ? `[${key.description ?? "symbol"}]` : String(key);
}

// --- modules ---------------------------------------------------------------------------------------------------

const modules = new Map<string, Bag>();

/** "villanelle" -> ./index.js, "villanelle/node" -> ./node.js. */
async function module(spec: string): Promise<Bag> {
  let loaded = modules.get(spec);
  if (loaded === undefined) {
    const file = spec === "villanelle" ? "index" : spec.slice("villanelle/".length);
    loaded = (await import(`./${file}.js`)) as Bag;
    modules.set(spec, loaded);
  }
  return loaded;
}

/** The module a free function's spell names ("... from villanelle/node"), else the package entry point. */
function moduleOf(f: IFreeFunction): string {
  return /\bfrom (villanelle(?:\/[a-z]+)?)(?![\w/])/u.exec(f.spell?.ts ?? "")?.[1] ?? "villanelle";
}

/** Arguments in the spell's shape: `name(a, { b, c })` puts b and c in one options object; no spell: positional. */
function argsFor(f: { readonly params?: readonly IParam[]; readonly spell?: ISpell }, values: Readonly<Record<string, unknown>>): unknown[] {
  const params = f.params ?? [];
  const inner = /\((.*)\)/su.exec(f.spell?.ts ?? "")?.[1];
  if (inner === undefined || !inner.includes("{")) return params.filter((p) => p.name in values).map((p) => values[p.name]);
  const byKey = new Map(params.map((p) => [camel(p.name), p.name]));
  const args: unknown[] = [];
  for (const piece of inner.match(/\{[^}]*\}|[^,{}]+/gu) ?? []) {
    if (piece.startsWith("{")) {
      const options: Bag = {};
      for (const key of piece.slice(1, -1).split(",").map((s) => s.trim()).filter(Boolean)) {
        const name = byKey.get(key);
        if (name !== undefined && name in values) options[key] = values[name];
      }
      args.push(options);
    } else if (piece.trim() !== "") {
      const name = byKey.get(piece.trim().split(/\s/u)[0] ?? "");
      if (name !== undefined && name in values) args.push(values[name]);
    }
  }
  return args;
}

async function callFree(name: string, values: Readonly<Record<string, unknown>> = {}): Promise<unknown> {
  const f = FREE.get(name);
  if (f === undefined) throw new Error(`api-names: the schema has no free function ${name}`);
  const key = keyOf(f);
  const target = (await module(moduleOf(f)))[key];
  if (typeof target !== "function") throw new Error(`${show(key)} is not exported`);
  const args = argsFor(f, values);
  return /^new\s/u.test(f.spell?.ts ?? "") ? Reflect.construct(target, args) : (target as Fn)(...args);
}

// --- the walk: which object is which concept --------------------------------------------------------------------

function get(o: object, key: PropertyKey): unknown {
  try {
    return (o as Bag)[key];
  } catch {
    return undefined;
  }
}

/** The concepts a schema type names, for map keys and for values ("map of directive to address", "X[]", "X or Y"). */
function conceptsIn(type: string | undefined): { readonly keys: string[]; readonly values: string[] } {
  const alts = (s: string): string[] =>
    s
      .split(" or ")
      .map((a) => a.replace(/\[\]$/u, "").trim())
      .filter((a) => CONCEPTS.has(a));
  if (type === undefined) return { keys: [], values: [] };
  const map = /^(?:ordered )?map of (.+?)(?: to (.+))?$/u.exec(type);
  if (map?.[1] !== undefined) return map[2] === undefined ? { keys: [], values: alts(map[1]) } : { keys: alts(map[1]), values: alts(map[2]) };
  return { keys: [], values: alts(type) };
}

/** Among alternatives, the one the object's kind names; with none named, the one no kind word names. */
function pick(alts: readonly string[], o: object): string[] {
  if (alts.length <= 1) return [...alts];
  const kind = get(o, "kind");
  const named = alts.filter((a) => typeof kind === "string" && words(a).includes(kind));
  if (named.length === 1) return named;
  const plain = alts.filter((a) => !words(a).some((w) => KIND_WORDS.has(w)));
  return plain.length === 1 ? plain : [];
}

const instances = new Map<string, Set<object>>(SCHEMA.concepts.map((c) => [c.name, new Set()]));
const problems: string[] = [];

function take(alts: readonly string[], value: unknown, queue: [string, object][], keyAlts: readonly string[] = []): void {
  if (alts.length === 0 && keyAlts.length === 0) return;
  if (value === null || (typeof value !== "object" && typeof value !== "function")) return;
  if (value instanceof Promise) {
    value.catch(() => undefined);
    return;
  }
  if (value instanceof Map) {
    for (const [k, v] of value as Map<unknown, unknown>) {
      take(keyAlts, k, queue);
      take(alts, v, queue);
    }
    return;
  }
  if (Array.isArray(value) || value instanceof Set) {
    for (const v of value as Iterable<unknown>) take(alts, v, queue);
    return;
  }
  if (typeof get(value, "next") === "function" && typeof get(value, Symbol.iterator) === "function") {
    for (const v of value as Iterable<unknown>) take(alts, v, queue);
    return;
  }
  if (typeof value === "function") return;
  for (const concept of pick(alts, value)) queue.push([concept, value]);
}

/** Records `root` as `concept`, then follows every member whose type names a concept (methods: no-argument, not I/O). */
function walk(concept: string, root: unknown): void {
  const queue: [string, object][] = [];
  take([concept], root, queue);
  while (queue.length > 0) {
    const [name, o] = queue.shift() as [string, object];
    const seen = instances.get(name);
    const c = CONCEPTS.get(name);
    if (seen === undefined || c === undefined || seen.has(o)) continue;
    seen.add(o);
    if (c.extends !== undefined) queue.push([c.extends, o]);
    for (const variant of pick(c.variants ?? [], o)) queue.push([variant, o]);
    for (const m of c.members ?? []) {
      const { keys, values } = conceptsIn(m.type ?? m.returns);
      if (keys.length === 0 && values.length === 0) continue;
      const value = get(o, keyOf(m));
      if (m.member === "property") {
        take(values, value, queue, keys);
      } else if (typeof value === "function" && m.io !== true && !(m.params ?? []).some((p) => p.optional !== true)) {
        try {
          take(values, (value as Fn).call(o), queue, keys);
        } catch {
          // a reader that does not fit this value (items() on a word): nothing to follow
        }
      }
    }
  }
}

async function step(what: string, run: () => Promise<void> | void): Promise<void> {
  try {
    await run();
  } catch (e) {
    problems.push(`${what}: ${e instanceof Error ? e.message : String(e)}`);
  }
}

function member(o: unknown, concept: string, name: string): unknown {
  const c = CONCEPTS.get(concept);
  const m = c?.members?.find((x) => x.name === name);
  if (m === undefined || o === null || typeof o !== "object") throw new Error(`no ${concept} ${name} to use`);
  const value = get(o, keyOf(m));
  if (value === undefined) throw new Error(`${concept} has no ${show(keyOf(m))}`);
  return value;
}

function method(o: unknown, concept: string, name: string, values: Readonly<Record<string, unknown>> = {}): unknown {
  const f = member(o, concept, name);
  const m = CONCEPTS.get(concept)?.members?.find((x) => x.name === name);
  if (typeof f !== "function" || m === undefined) throw new Error(`${concept} ${name} is not a method`);
  return (f as Fn).apply(o, argsFor(m, values));
}

/** An object whose members the schema names, made by this test (a port the library calls back). */
function port(concept: string, impl: Readonly<Record<string, unknown>>): Bag {
  const c = CONCEPTS.get(concept);
  const out: Bag = {};
  for (const [name, value] of Object.entries(impl)) {
    const m = c?.members?.find((x) => x.name === name);
    if (m === undefined) throw new Error(`api-names: the schema's ${concept} has no ${name}`);
    out[keyOf(m)] = value;
  }
  return out;
}

const MAIN = `set $n 3;
set $port 80;
snippet twinkle $a {
    light $a;
}
use twinkle 5;
server "web" [1, 2] c[0:$n] c[$n] $port {
    listen $port;
}
given $o;
files {
    include "other.conf";
    probe 1;
}
gone 1;
use missing;
oops ] ;
`;

async function probe(): Promise<void> {
  const files = { "main.conf": MAIN, "other.conf": "extra 1;\n" };
  const contexts: unknown[] = [];
  const uses: unknown[] = [];
  const writes: unknown[] = [];

  // Free functions that need nothing (adapters, include, a diagnostics collection): their results are roots.
  for (const f of SCHEMA["free functions"]) {
    const returns = conceptsIn(f.returns).values;
    if (f.spell?.ts === "absent" || returns.length === 0 || (f.params ?? []).some((p) => p.optional !== true)) continue;
    await step(`${f.name} ()`, async () => {
      for (const concept of returns) walk(concept, await callFree(f.name));
    });
  }

  let source: unknown;
  await step("memory source (files)", async () => {
    source = await callFree("memory source", { files });
    walk("document source", source);
  });
  const recording = port("document source", {
    resolve: (spec: unknown, context: unknown) => {
      contexts.push(context);
      return method(source, "document source", "resolve", { spec, context });
    },
    read: (resolvedPath: unknown) => method(source, "document source", "read", { "resolved path": resolvedPath }),
  });
  const probeExtension = port("extension", {
    directive: "probe",
    specs: (use: unknown) => {
      uses.push(use);
      return [];
    },
  });

  let graph: unknown;
  let before: unknown;
  await step("make processor, load (path, overrides)", async () => {
    const include = await callFree("include");
    const processor = await callFree("make processor", { source: recording, extensions: [include, probeExtension] });
    walk("processor", processor);
    graph = await method(processor, "processor", "load", { path: "main.conf", overrides: { o: "9" } });
    walk("document graph", graph);
  });
  await step("render (graph)", async () => {
    before = await callFree("render", { graph });
    walk("rendered", before);
  });
  await step("parse (text)", async () => {
    walk("syntax", await callFree("parse", { text: "a {\n" }));
  });

  // Edits, then a second render and a diff (changed, added, removed), then a save through a recording writer.
  await step("edits, render, diff", async () => {
    const block = member(member(graph, "document graph", "root"), "document", "block");
    const statements = member(block, "written block", "statements") as readonly unknown[];
    const setPort = statements.find((s) => member(s, "statement", "text") === "set $port 80;");
    const gone = statements.find((s) => member(s, "statement", "text") === "gone 1;");
    method(setPort, "set line", "set", { text: "81" });
    method(gone, "statement", "remove");
    method(block, "written block", "add statements", { text: "added 1;" });
    const after = await callFree("render", { graph });
    walk("rendered", after);
    walk("change", method(before, "rendered", "diff", { after }));
  });
  await step("save (writer)", async () => {
    const writer = port("document writer", {
      write: (list: readonly unknown[]) => {
        writes.push(...list);
        return Promise.resolve();
      },
    });
    await method(graph, "document graph", "save", { writer });
  });
  for (const context of contexts) walk("load context", context);
  for (const use of uses) walk("extension use", use);
  for (const write of writes) walk("file write", write);
}

// --- the checks ----------------------------------------------------------------------------------------------------

function missing(concept: IConcept): string[] {
  const objects = [...(instances.get(concept.name) ?? [])];
  if (objects.length === 0) {
    return [`no ${concept.name} object was reached from the probe${problems.length > 0 ? ` (probe problems: ${problems.join("; ")})` : ""}`];
  }
  const out: string[] = [];
  for (const m of concept.members ?? []) {
    const key = keyOf(m);
    const present = objects.filter((o) => key in o).map((o) => get(o, key));
    // Object.prototype's own members (toString) do not count: the concept must define the member.
    const own = present.filter((v) => !(key in Object.prototype && v === (Object.prototype as Bag)[key]));
    if (own.length === 0 || present.length !== own.length) {
      out.push(`${m.name}: no ${m.member} ${show(key)}`);
    } else if (m.member === "method" && !own.some((v) => typeof v === "function")) {
      out.push(`${m.name}: ${show(key)} is a property; the schema says a method`);
    } else if (m.member === "property" && !own.some((v) => typeof v !== "function")) {
      out.push(`${m.name}: ${show(key)} is a method; the schema says a property`);
    }
  }
  return out;
}

beforeAll(probe);

describe("public names match spec/schema/api.json", () => {
  it.each(SCHEMA.concepts.map((c) => [c.name, c] as const))("concept %s", (_name, concept) => {
    expect(missing(concept)).toEqual([]);
  });

  it.each(SCHEMA["free functions"].filter((f) => f.spell?.ts !== "absent").map((f) => [f.name, f] as const))(
    "free function %s",
    async (_name, f) => {
      const key = keyOf(f);
      const exported = (await module(moduleOf(f)))[key];
      expect(typeof exported, `${show(key)} from ${moduleOf(f)}`).toBe("function");
    },
  );

  it.each(SCHEMA["error groups"].map((g) => [g.name, g] as const))("error group %s", async (_name, g) => {
    const root = await module("villanelle");
    const classOf = (group: IErrorGroup): unknown => {
      const key = keyOf({ name: group.name, spell: { ts: group.ts } });
      return key in globalThis ? (globalThis as unknown as Bag)[key] : root[key];
    };
    const cls = classOf(g);
    expect(typeof cls, `${g.ts} exported from villanelle`).toBe("function");
    const parent = SCHEMA["error groups"].find((p) => p.name === g.parent);
    const prototype = (cls as { readonly prototype?: unknown }).prototype;
    expect(prototype instanceof Error, `${g.ts} is an Error`).toBe(true);
    if (parent !== undefined) {
      const parentClass = classOf(parent) as new () => unknown;
      expect(prototype instanceof parentClass, `${g.ts} extends ${parent.ts}`).toBe(true);
    }
  });
});
