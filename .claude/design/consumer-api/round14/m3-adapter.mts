/**
 * The TypeScript binding's conformance adapter (spec/conformance.md), the proof that the shared driver works for a
 * second binding. The milestone 3 TypeScript lane moves it to ts/conformance/adapter.ts (a .ts file there, since ts/ is a module package), imports "../dist/..." and
 * adds the binding's types (it is written here with `any` so it runs from this folder unchanged).
 *
 *     python3 conformance/driver/run.py -- node .claude/design/consumer-api/round14/m3-adapter.mts
 *
 * Node 24 runs it as is (type stripping). It speaks the adapter protocol on standard input and output: one JSON
 * request per line, one JSON response per line. Every object it dumps gets an id; it finds no target and compares
 * nothing: the driver does both.
 */
import { createInterface } from "node:readline";

import * as vl from "../../../../ts/dist/index.js";
import { include } from "../../../../ts/dist/include.js";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Json = any;

const handles: unknown[] = [];
const ref = (o: unknown): string => String(handles.push(o) - 1);
const get = (id: string): any => handles[Number(id)];

const pos = (p: any): number[] => [p.line, p.column, p.offset];
const place = (p: any): Json =>
  "resolvedPath" in p ? { id: ref(p), path: p.resolvedPath, start: pos(p.span.start), end: pos(p.span.end) } : { id: ref(p), override: p.variable };
const steps = (via: readonly any[]): Json[] => via.map((s) => ({ id: ref(s), kind: s.kind, name: s.name, place: place(s.place) }));
const origin = (o: any): Json => ({ place: place(o.place), via: steps(o.via) });
const diagnostic = (d: any): Json => ({ id: ref(d), code: d.code, message: d.message, start: pos(d.span.start), end: pos(d.span.end) });
const located = (d: any): Json => ({ id: ref(d), code: d.code, message: d.message, ...origin(d) });

function syntax(s: any): Json {
  const node = (n: any): Json => [n.kind, n.start, n.end, n.children.map(node)];
  return {
    tokens: s.tokens.map((t: any) => [t.kind, t.text, pos(t.span.start), pos(t.span.end)]),
    root: node(s.root),
    diagnostics: s.diagnostics.map(diagnostic),
  };
}

const variable = (v: any): Json =>
  v === undefined ? null : { id: ref(v), name: v.name, kind: v.kind, place: v.kind === "override" ? null : place(v.place) };
const resolution = (r: any): Json => ({
  reference: { id: ref(r.reference), place: place(r.reference.place) },
  via: steps(r.copy.via),
  winner: variable(r.winner),
  shadowed: r.shadowed.map(variable),
});

function value(v: any): Json {
  const out: Json = { id: ref(v), kind: v.kind, place: place(v.place), text: v.text };
  if (v.kind === "list") out.items = v.items.map(value);
  if (v.kind === "slice") Object.assign(out, { start: v.start === undefined ? null : value(v.start), end: v.end === undefined ? null : value(v.end) });
  if (v.kind === "index") out.index = value(v.index);
  if (v.kind === "reference") Object.assign(out, { declaration: variable(v.declaration), resolutions: v.resolutions().map(resolution) });
  return out;
}

function statement(s: any): Json {
  const out: Json = { id: ref(s), kind: s.kind, place: place(s.place), text: s.text };
  if ("values" in s) out.values = s.values.map(value);
  if ("block" in s) out.block = s.block === undefined ? null : block(s.block);
  return out;
}
const block = (b: any): Json => ({ id: ref(b), statements: b.statements.map(statement) });
const copy = (c: any): Json => ({ place: place(c.statement.place), via: steps(c.via) });

function graph(g: any): Json {
  return {
    id: ref(g),
    documents: [...g.documents.values()].map((d: any) => ({
      id: ref(d),
      path: d.resolvedPath,
      text: d.text,
      savedText: d.savedText,
      syntax: syntax(d.syntax),
      block: block(d.block),
      includedBy: d.includedBy().map((e: any) => copy(e.copy)),
    })),
    edges: g.edges().map((e: any) => ({ copy: copy(e.copy), specs: [...e.specs], targets: [...e.targets] })),
    variables: g.variables().map((v: any) => ({ ...variable(v), wins: v.wins().map(resolution), shadowedAt: v.shadowedAt().map(resolution) })),
    diagnostics: g.diagnostics.map(located),
  };
}

/** A key rule from its data (spec/conformance.md section 3). */
function keyOptions(rules: Json[] | undefined): Json {
  if (rules === undefined) return {};
  return {
    key: (d: any): string | undefined => {
      for (const rule of rules) {
        if (rule.directive !== d.name || (rule.parent !== undefined && d.parent?.name !== rule.parent)) continue;
        const [how, arg] = rule.key;
        return how === "value" ? d.values[arg]?.text : d.values.map((a: any) => a.text).join(arg);
      }
      return undefined;
    },
  };
}

const address = (a: any): Json => ({ text: a.text, people: String(a) });

function rendered(r: any, rules: Json[] | undefined): Json {
  const addresses = r.addresses(keyOptions(rules));
  const unreadable = (u: any): Json => ({ reason: u.reason, origin: origin(u.origin) });
  const argument = (a: any): Json => ({
    id: ref(a),
    kind: a.kind,
    text: a.text,
    origin: origin(a.origin),
    definition: a.definition === undefined ? null : place(a.definition.place),
    chain: a.chain.map(resolution),
  });
  const directive = (d: any): Json => ({
    id: ref(d),
    name: d.name,
    address: address(addresses.get(d)),
    origin: origin(d.origin),
    values: d.values.map(argument),
    block: d.block === undefined ? null : d.block.map(directive),
    unreadable: d.unreadable.map(unreadable),
  });
  return { id: ref(r), block: r.block.map(directive), unreadable: r.unreadable.map(unreadable), diagnostics: r.diagnostics.map(located) };
}

/** A reader's result, neutral (spec/conformance.md, `read`). */
function result(x: any): Json {
  if (typeof x === "boolean") return { boolean: x };
  if (typeof x === "string") return { text: x };
  if (typeof x === "number") return { number: Object.is(x, -0) ? "-0" : x };
  if (Array.isArray(x)) return { list: x.map(result) };
  if ("kind" in x && "origin" in x) return { value: x.text };
  if ("index" in x) return { index: [x.name, x.index] };
  return { slice: [x.name, x.start ?? null, x.end ?? null] };
}

const camel = (spec: string): string => spec.replace(/ ([a-z])/g, (_m, c: string) => c.toUpperCase());

const ops: Record<string, (p: Json) => unknown> = {
  hello: () => ({ protocol: 1, binding: "typescript", unit: "utf-16", level: 3 }),
  parse: (p) => syntax(vl.parse(p.text)),
  load: async (p) => {
    const processor = vl.villanelle({ source: vl.memorySource(p.files), ...(p.extensions.includes("include") ? { extensions: [include()] } : {}) });
    return { graph: ref(await processor.load(p.root, p.overrides === undefined ? undefined : { overrides: p.overrides })) };
  },
  graph: (p) => graph(get(p.graph)),
  render: (p) => rendered(vl.render(get(p.graph)), p.key),
  diff: (p) => get(p.before).diff(get(p.after), keyOptions(p.key)).map((c: any) => ({ kind: c.kind, address: address(c.address) })),
  edit: (p) => {
    const out = get(p.target)[camel(p.member)](...p.args.map((a: Json) => (a === null ? undefined : a)));
    return Array.isArray(out) ? { handles: out.map((h: any) => ({ id: ref(h), text: h.text })) } : {};
  },
  save: async (p) => {
    const batches: Json[] = [];
    await get(p.graph).save({ write: (files: any[]) => (batches.push(files.map((f) => [f.resolvedPath, f.text])), Promise.resolve()) });
    return { batches };
  },
  quote: (p) => vl.quote(p.text),
  read: (p) => result(get(p.value)[p.reader]()),
  print: (p) => String(get(p.target)),
  format: (p) => vl.formatDiagnostic(get(p.diagnostic), p.graph === undefined ? undefined : get(p.graph)),
  cut: (p) => (p.text as string).slice(p.start, p.end),
};

/** The error's group by its spec name (the class name's words), with its code or diagnostics. */
function group(error: any): Json {
  const out: Json = { group: error.constructor.name.replace(/(?<!^)(?=[A-Z])/g, " ").toLowerCase() };
  if (error instanceof vl.DiagnosticError) out.code = error.diagnostic.code;
  if (error instanceof vl.BadTextError) out.diagnostics = error.diagnostics.map(diagnostic);
  return out;
}

for await (const line of createInterface({ input: process.stdin })) {
  const { id, op, ...params } = JSON.parse(line);
  let response: Json;
  try {
    response = { id, ok: await ops[op](params) };
  } catch (error) {
    response = error instanceof vl.VillanelleError ? { id, thrown: group(error) } : { id, fault: String(error) };
  }
  process.stdout.write(`${JSON.stringify(response)}\n`);
}
