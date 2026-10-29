/**
 * The TypeScript binding's conformance adapter (spec/conformance.md): it speaks the adapter protocol on standard input
 * and output, one JSON request per line and one JSON response per line, for the shared driver. Every object it dumps
 * gets an id; it finds no target, converts no position and compares nothing: the driver does all three.
 * Run it with `corepack pnpm build && corepack pnpm conformance`. Node 24 runs it as is (type stripping, so erasable syntax only). It uses the built package's public entry points;
 * its types come from the same entry points' sources, type-only, so it typechecks and lints without a build.
 */
import { createInterface } from "node:readline";

import type * as Villanelle from "../src/index.js";
import type * as Include from "../src/include.js";

const dist = new URL("../dist/", import.meta.url);
const vl = (await import(new URL("index.js", dist).href)) as typeof Villanelle;
const { include } = (await import(new URL("include.js", dist).href)) as typeof Include;

type Json = null | boolean | number | string | readonly Json[] | { readonly [key: string]: Json };
type KeyData = { readonly directive: string; readonly parent?: string; readonly key: readonly ["value", number] | readonly ["join", string] };
type Params = Record<string, unknown> & {
  readonly text: string; readonly files: Record<string, string>; readonly root: string; readonly extensions: readonly string[];
  readonly overrides?: Record<string, string>; readonly key?: readonly KeyData[]; readonly graph: string; readonly before: string;
  readonly after: string; readonly target: string; readonly member: string; readonly args: readonly Json[]; readonly value: string;
  readonly reader: string; readonly diagnostic: string; readonly start: number; readonly end: number;
  readonly disk?: Record<string, string>;
};

const handles: unknown[] = [];
const ref = (o: unknown): string => String(handles.push(o) - 1);
const get = <T>(id: string): T => handles[Number(id)] as T;

const pos = (p: Villanelle.ISourcePosition): Json => [p.line, p.column, p.offset];
const place = (p: Villanelle.IPlace | Villanelle.IOverride): Json =>
  p.kind === "file" ? { id: ref(p), path: p.resolvedPath, start: pos(p.span.start), end: pos(p.span.end) } : { id: ref(p), override: p.variable };
const steps = (via: readonly Villanelle.IStep[]): Json[] => via.map((s) => ({ id: ref(s), kind: s.kind, name: s.name, place: place(s.place) }));
const origin = (o: Villanelle.IOrigin): { place: Json; via: Json } => ({ place: place(o.place), via: steps(o.via) });
const diagnostic = (d: Villanelle.IDiagnostic): Json => ({ id: ref(d), code: d.code, message: d.message, start: pos(d.span.start), end: pos(d.span.end) });
const located = (d: Villanelle.ILocatedDiagnostic): Json => ({ id: ref(d), code: d.code, message: d.message, ...origin(d) });

function syntax(s: Villanelle.ISyntax): Json {
  const node = (n: Villanelle.INode): Json => [n.kind, n.start, n.end, n.children.map(node)];
  return {
    tokens: s.tokens.map((t) => [t.kind, t.text, pos(t.span.start), pos(t.span.end)]),
    root: node(s.root),
    diagnostics: s.diagnostics.map(diagnostic),
  };
}

const variable = (v: Villanelle.Variable | undefined): Json =>
  v === undefined ? null : { id: ref(v), name: v.name, kind: v.kind, place: v.kind === "override" ? null : place(v.place) };
const resolution = (r: Villanelle.IReferenceResolution): Json => ({
  reference: { id: ref(r.reference), place: place(r.reference.place) },
  via: steps(r.copy.via),
  winner: variable(r.winner),
  shadowed: r.shadowed.map(variable),
});

function value(v: Villanelle.WrittenValue): Json {
  const out: Record<string, Json> = { id: ref(v), kind: v.kind, place: place(v.place), text: v.text };
  if (v.kind === "list") out.items = v.items.map(value);
  if (v.kind === "slice") Object.assign(out, { start: v.start === undefined ? null : value(v.start), end: v.end === undefined ? null : value(v.end) });
  if (v.kind === "index") out.index = value(v.index);
  if (v.kind === "reference") Object.assign(out, { declaration: variable(v.declaration), resolutions: v.resolutions().map(resolution) });
  return out;
}

function statement(s: Villanelle.Statement): Json {
  const out: Record<string, Json> = { id: ref(s), kind: s.kind, place: place(s.place), text: s.text };
  if ("values" in s) out.values = s.values.map(value);
  if ("block" in s) out.block = s.block === undefined ? null : block(s.block);
  return out;
}
const block = (b: Villanelle.IWrittenBlock): Json => ({ id: ref(b), statements: b.statements.map(statement) });
const copy = (c: Villanelle.ICopy): Json => ({ place: place(c.statement.place), via: steps(c.via) });

const graph = (g: Villanelle.IDocumentGraph): Json => ({
  id: ref(g),
  documents: [...g.documents.values()].map((d) => ({
    id: ref(d),
    path: d.resolvedPath,
    text: d.text,
    savedText: d.savedText,
    syntax: syntax(d.syntax),
    block: block(d.block),
    includedBy: d.includedBy().map((e) => copy(e.copy)),
  })),
  edges: g.edges().map((e) => ({ copy: copy(e.copy), specs: [...e.specs], targets: [...e.targets] })),
  variables: g.variables().map((v) => ({ id: ref(v), name: v.name, kind: v.kind, place: v.kind === "override" ? null : place(v.place), wins: v.wins().map(resolution), shadowedAt: v.shadowedAt().map(resolution) })),
  diagnostics: g.diagnostics.map(located),
});

/** A key rule from its data (spec/conformance.md 4.3): the first rule naming the directive (and its parent, if given). */
function keyOptions(rules: readonly KeyData[] | undefined): Villanelle.IKeyOptions {
  if (rules === undefined) return {};
  return {
    key: (d) => {
      const rule = rules.find((r) => r.directive === d.name && (r.parent === undefined || d.parent?.name === r.parent));
      if (rule === undefined) return undefined;
      const [how, arg] = rule.key;
      return how === "value" ? d.values[arg]?.text : d.values.map((a) => a.text).join(arg);
    },
  };
}

const address = (a: Villanelle.IAddress | undefined): Json => (a === undefined ? null : { text: a.text, people: String(a) });

function rendered(r: Villanelle.IRendered, rules: readonly KeyData[] | undefined): Json {
  const addresses = r.addresses(keyOptions(rules));
  const unreadable = (u: Villanelle.IUnreadableExpansion): Json => ({ reason: u.reason, origin: origin(u.origin) });
  const expanded = (a: Villanelle.ExpandedValue): Json => ({
    id: ref(a),
    kind: a.kind,
    text: a.text,
    origin: origin(a.origin),
    definition: a.definition === undefined ? null : place(a.definition.place),
    chain: a.chain.map(resolution),
  });
  const directive = (d: Villanelle.IDirective): Json => ({
    id: ref(d),
    name: d.name,
    address: address(addresses.get(d)),
    origin: origin(d.origin),
    values: d.values.map(expanded),
    block: d.block === undefined ? null : d.block.map(directive),
    unreadable: d.unreadable.map(unreadable),
  });
  return { id: ref(r), block: r.block.map(directive), unreadable: r.unreadable.map(unreadable), diagnostics: r.diagnostics.map(located) };
}

type ReaderResult = Villanelle.PlainValue | Villanelle.ExpandedValue | readonly ReaderResult[];
const isList = (x: ReaderResult): x is readonly ReaderResult[] => Array.isArray(x);

/** A reader's result, neutral (spec/conformance.md, `read`). */
function result(x: ReaderResult): Json {
  if (typeof x === "boolean") return { boolean: x };
  if (typeof x === "string") return { text: x };
  if (typeof x === "number") return { number: Object.is(x, -0) ? "-0" : x };
  if (isList(x)) return { list: x.map(result) };
  if ("origin" in x) return { value: x.text };
  if (x.kind === "index") return { index: [x.name, x.index] };
  return { slice: [x.name, x.start ?? null, x.end ?? null] };
}

const camel = (spec: string): string => spec.replace(/ ([a-z])/g, (_m, c: string) => c.toUpperCase());

/** A member of a dumped object by its spec name, called on it. */
function call(target: string, member: string, args: unknown[]): unknown {
  const object = get<Record<string, unknown>>(target);
  const fn = object[camel(member)];
  if (typeof fn !== "function") throw new Error(`no member ${JSON.stringify(member)}`);
  return (fn as (...a: unknown[]) => unknown).apply(object, args);
}

const ops: Record<string, (p: Params) => Json | Promise<Json>> = {
  hello: () => ({ protocol: 1, binding: "typescript", unit: "utf-16", level: 3 }),
  parse: (p) => syntax(vl.parse(p.text)),
  load: async (p) => {
    const processor = vl.villanelle({ source: vl.memorySource(p.files), ...(p.extensions.includes("include") ? { extensions: [include()] } : {}) });
    return { graph: ref(await processor.load(p.root, p.overrides === undefined ? undefined : { overrides: p.overrides })) };
  },
  graph: (p) => graph(get(p.graph)),
  render: (p) => rendered(vl.render(get(p.graph)), p.key),
  diff: (p) => get<Villanelle.IRendered>(p.before).diff(get(p.after), keyOptions(p.key)).map((c) => ({ kind: c.kind, address: address(c.address) })),
  edit: (p): Json => {
    const out = call(p.target, p.member, p.args.map((a) => (a === null ? undefined : a)));
    const handles = Array.isArray(out) ? (out as readonly { text: string }[]).map((h) => ({ id: ref(h), text: h.text })) : undefined;
    return handles === undefined ? {} : { handles };
  },
  save: async (p): Promise<Json> => {
    if (p.disk !== undefined) {
      const disk: Record<string, string> = { ...p.disk };
      await get<Villanelle.IDocumentGraph>(p.graph).save(vl.memoryWriter(disk));
      return { files: Object.keys(disk).sort().map((path) => [path, disk[path] ?? ""]) };
    }
    const batches: Json[] = [];
    const write = (files: readonly Villanelle.IFileWrite[]): Promise<void> => (batches.push(files.map((f) => [f.resolvedPath, f.text])), Promise.resolve());
    await get<Villanelle.IDocumentGraph>(p.graph).save({ write });
    return { batches };
  },
  quote: (p) => vl.quote(p.text),
  read: (p) => result(call(p.value, p.reader, []) as ReaderResult),
  print: (p) => String(get(p.target)),
  format: (p) => vl.formatDiagnostic(get(p.diagnostic), p.graph === undefined ? undefined : get(p.graph)),
  cut: (p) => p.text.slice(p.start, p.end),
};

/** Each spec 2.8 error group's class, the most specific first (spec/conformance.md 3), by the group's spec name. */
const GROUPS: readonly (readonly [string, abstract new (...args: never[]) => Error])[] = [
  ["lost update error", vl.LostUpdateError], ["save error", vl.SaveError], ["read error", vl.ReadError],
  ["bad text error", vl.BadTextError], ["diagnostic error", vl.DiagnosticError], ["detached error", vl.DetachedError],
  ["misuse error", vl.MisuseError], ["index out of range", RangeError], ["argument type error", TypeError],
];

/** The error's group by its spec name, with its code, diagnostics or paths; undefined for any other error. */
function group(error: unknown): Json | undefined {
  const found = GROUPS.find(([, type]) => error instanceof type);
  if (found === undefined) return undefined;
  const out: Record<string, Json> = { group: found[0] };
  if (error instanceof vl.DiagnosticError) out.code = error.diagnostic.code;
  if (error instanceof vl.BadTextError) out.diagnostics = error.diagnostics.map(diagnostic);
  if (error instanceof vl.ReadError || error instanceof vl.SaveError) out.paths = [...error.paths];
  return out;
}

for await (const line of createInterface({ input: process.stdin })) {
  const { id, op, ...params } = JSON.parse(line) as Params & { readonly id: Json; readonly op: string };
  let response: Json;
  try {
    const handler = ops[op];
    if (handler === undefined) throw new Error(`unknown op ${JSON.stringify(op)}`);
    response = { id, ok: await handler(params) };
  } catch (error) {
    const thrown = group(error);
    response = thrown === undefined ? { id, fault: String(error) } : { id, thrown };
  }
  process.stdout.write(`${JSON.stringify(response)}\n`);
}
