/**
 * The TypeScript binding's conformance adapter (spec/conformance.md): it speaks the adapter protocol on standard input
 * and output, one JSON request per line and one JSON response per line, for the shared driver. Every object it dumps
 * gets an id; it finds no target, converts no position and compares nothing: the driver does all three.
 * Run it with `corepack pnpm build && corepack pnpm conformance`. Node 24 runs it as is (type stripping, so erasable
 * syntax only). It uses the built package's public entry points (one per layer); its types come from the same entry
 * points' sources, type-only, so it typechecks and lints without a build. Its requests, results and dumps are typed by
 * the generated shapes (./shapes.ts, spec/conformance.md 6), members are spelled by the generated `SPELLING` and thrown
 * errors are named by the generated `ERROR_GROUP_OF_CLASS`.
 */
import { createInterface } from "node:readline";

import type * as Knobly from "../src/index.js";
import type * as Include from "../src/include.js";
import type * as Rendered from "../src/rendered/index.js";
import type * as Syntax from "../src/syntax/index.js";
import type * as Written from "../src/written/index.js";
import {
  type AddressDump,
  type BlockDump,
  type ChangeDump,
  type CopyDump,
  type DirectiveDump,
  ERROR_GROUP_OF_CLASS,
  type ExpandedValueDump,
  type GraphDump,
  type Json,
  type KeyRuleDump,
  type LocatedDiagnosticDump,
  type OriginDump,
  type OverrideDump,
  type PlaceDump,
  PROTOCOL,
  type Position,
  type ReaderResultDump,
  type RenderDump,
  type RequestParams,
  type RequestResults,
  type ResolutionDump,
  SPELLING,
  type StatementDump,
  type StepDump,
  type SyntaxDiagnosticDump,
  type SyntaxDump,
  type VariableReferenceDump,
  type WrittenValueDump,
} from "./shapes.ts";

const dist = new URL("../dist/", import.meta.url);
const load = async <T>(path: string): Promise<T> => (await import(new URL(path, dist).href)) as T;
const vl = await load<typeof Knobly>("index.js");
const syntaxLayer = await load<typeof Syntax>("syntax/index.js");
const written = await load<typeof Written>("written/index.js");
const renderedLayer = await load<typeof Rendered>("rendered/index.js");
const { include } = await load<typeof Include>("include.js");
const { PlaceKind } = vl;
const { StatementKind, ValueKind, VariableKind } = written;

const handles: unknown[] = [];
const ref = (o: unknown): string => String(handles.push(o) - 1);
const get = <T>(id: string): T => handles[Number(id)] as T;

const pos = (p: Knobly.SourcePosition): Position => [p.line, p.column, p.offset];
const place = (p: Knobly.Place | Knobly.Override): PlaceDump | OverrideDump =>
  p.kind === PlaceKind.File ? { id: ref(p), path: p.resolvedPath, start: pos(p.span.start), end: pos(p.span.end) } : { id: ref(p), override: p.variable };
const filePlace = (p: Knobly.Place): PlaceDump => ({ id: ref(p), path: p.resolvedPath, start: pos(p.span.start), end: pos(p.span.end) });
const steps = (via: readonly Knobly.Step[]): StepDump[] => via.map((s) => ({ id: ref(s), kind: s.kind, name: s.name, place: filePlace(s.place) }));
const origin = (o: Knobly.Origin): OriginDump => ({ place: place(o.place), via: steps(o.via) });
const diagnostic = (d: Knobly.Diagnostic): SyntaxDiagnosticDump => ({ id: ref(d), code: d.code, severity: d.severity, message: d.message, start: pos(d.span.start), end: pos(d.span.end) });
const located = (d: Knobly.LocatedDiagnostic): LocatedDiagnosticDump => ({ id: ref(d), code: d.code, severity: d.severity, message: d.message, ...origin(d) });

function syntax(s: Syntax.Syntax): SyntaxDump {
  const node = (n: Syntax.Node): SyntaxDump["root"] => [n.kind, n.start, n.end, n.children.map(node)];
  return {
    tokens: s.tokens.map((t) => [t.kind, t.text, pos(t.span.start), pos(t.span.end)]),
    root: node(s.root),
    diagnostics: s.diagnostics.map(diagnostic),
  };
}

const variable = (v: Written.Variable | undefined): VariableReferenceDump | null =>
  v === undefined ? null : { id: ref(v), name: v.name, kind: v.kind, place: v.kind === VariableKind.Override ? null : filePlace(v.place) };
const resolution = (r: Written.ReferenceResolution): ResolutionDump => ({
  reference: { id: ref(r.reference), place: filePlace(r.reference.place) },
  via: steps(r.copy.via),
  winner: variable(r.winner),
  shadowed: r.shadowed.map(variable).filter((v) => v !== null),
});

function value(v: Written.WrittenValue): WrittenValueDump {
  const base = { id: ref(v), place: filePlace(v.place), text: v.text };
  switch (v.kind) {
    case ValueKind.List:
      return { ...base, kind: v.kind, items: v.items.map(value) };
    case ValueKind.Slice:
      return { ...base, kind: v.kind, name: value(v.name), start: v.start === undefined ? null : value(v.start), end: v.end === undefined ? null : value(v.end) };
    case ValueKind.Index:
      return { ...base, kind: v.kind, name: value(v.name), index: value(v.index) };
    case ValueKind.Reference:
      return { ...base, kind: v.kind, declaration: variable(v.declaration), resolutions: v.resolutions().map(resolution) };
    default:
      return { ...base, kind: v.kind };
  }
}

function statement(s: Written.Statement): StatementDump {
  const base = { id: ref(s), place: filePlace(s.place), text: s.text };
  const inner = (b: Written.WrittenBlock | undefined): BlockDump | null => (b === undefined ? null : block(b));
  switch (s.kind) {
    case StatementKind.Directive:
    case StatementKind.Extension:
      return { ...base, kind: s.kind, values: s.values.map(value), block: inner(s.block) };
    case StatementKind.Set:
    case StatementKind.Use:
      return { ...base, kind: s.kind, values: s.values.map(value) };
    case StatementKind.Snippet:
      return { ...base, kind: s.kind, block: inner(s.block) };
    default:
      return { ...base, kind: s.kind };
  }
}
const block = (b: Written.WrittenBlock): BlockDump => ({ id: ref(b), statements: [...b].map(statement) });
const copy = (c: Written.Copy): CopyDump => ({ place: filePlace(c.statement.place), via: steps(c.via) });

const graph = (g: Written.DocumentGraph): GraphDump => ({
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
  variables: g.variables().map((v) => ({
    id: ref(v),
    name: v.name,
    kind: v.kind,
    place: v.kind === VariableKind.Override ? null : filePlace(v.place),
    wins: v.wins().map(resolution),
    shadowedAt: v.shadowedAt().map(resolution),
  })),
  diagnostics: g.diagnostics.map(located),
});

/** A key rule from its data (spec/conformance.md 4.3): the first rule naming the directive (and its parent, if given). */
function keyOptions(rules: readonly KeyRuleDump[] | undefined): Rendered.KeyOptions {
  if (rules === undefined) return {};
  return {
    key: (d) => {
      const rule = rules.find((r) => r.directive === d.name && (r.parent == null || d.parent?.name === r.parent));
      if (rule === undefined) return undefined;
      const [how, arg] = rule.key;
      return how === "value" ? d.values[arg]?.text : d.values.map((a) => a.text).join(arg);
    },
  };
}

const address = (a: Rendered.Address | undefined): AddressDump => {
  if (a === undefined) throw new Error("a directive without an address");
  return { text: a.text, people: String(a) };
};

function rendered(r: Rendered.Rendered, rules: readonly KeyRuleDump[] | undefined): RenderDump {
  const addresses = r.addresses(keyOptions(rules));
  const unreadable = (u: Written.UnreadableExpansion): RenderDump["unreadable"][number] => ({ reason: u.reason, origin: origin(u.origin) });
  const expanded = (a: Written.ExpandedValue): ExpandedValueDump => ({
    id: ref(a),
    kind: a.kind,
    text: a.text,
    origin: origin(a.origin),
    definition: a.definition === undefined ? null : filePlace(a.definition.place),
    chain: a.chain.map(resolution),
  });
  const directive = (d: Rendered.Directive): DirectiveDump => ({
    id: ref(d),
    name: d.name,
    address: address(addresses.get(d)),
    origin: origin(d.origin),
    values: d.values.map(expanded),
    block: d.block === undefined ? null : [...d.block].map(directive),
    unreadable: d.unreadable.map(unreadable),
  });
  return { id: ref(r), block: [...r.block].map(directive), unreadable: r.unreadable.map(unreadable), diagnostics: r.diagnostics.map(located) };
}

type ReaderResult = boolean | string | number | Written.SliceValue | Written.IndexValue | readonly Written.ExpandedValue[];
const isList = (x: ReaderResult): x is readonly Written.ExpandedValue[] => Array.isArray(x);

/** A reader's result, neutral (spec/conformance.md, `read`): a list only from the `list` reader, its items by text. */
function result(x: ReaderResult): ReaderResultDump {
  if (typeof x === "boolean") return { boolean: x };
  if (typeof x === "string") return { text: x };
  if (typeof x === "number") return { number: Object.is(x, -0) ? "-0" : x };
  if (isList(x)) return { list: x.map((item) => ({ value: item.text })) };
  if (x.kind === ValueKind.Index) return { index: [x.name, x.index] };
  return { slice: [x.name, x.start ?? null, x.end ?? null] };
}

/** The position of each edit member's config text parameter (names, such as `rename`'s, stay plain text). */
const TEXT_PARAMETER: Readonly<Record<string, number>> = {
  set: 0,
  "replace with text": 0,
  "insert statements": 1,
  "add statements": 0,
  "insert before": 0,
  "insert after": 0,
  "set override": 1,
};

/** A member of a dumped object by its spec name, spelled by the generated casing table, called on it. */
function call(target: string, member: string, args: unknown[]): unknown {
  const object = get<Record<string, unknown>>(target);
  const spelled = SPELLING[member];
  const fn = spelled === undefined ? undefined : object[spelled];
  if (typeof fn !== "function") throw new Error(`no member ${JSON.stringify(member)}`);
  return (fn as (...a: unknown[]) => unknown).apply(object, args);
}

/** The test source of spec/conformance.md 4.5: the memory source, but `read` of a path named fails. */
const failingReads = (source: Knobly.DocumentSource, failing: readonly string[] | undefined): Knobly.DocumentSource =>
  failing === undefined
    ? source
    : {
        resolve: (spec, context) => source.resolve(spec, context),
        read: (path) => (failing.includes(path) ? Promise.reject(new Error(`failReads: ${path}`)) : source.read(path)),
      };

/** The extensions a load names: include, or the test extension `throws` (spec/conformance.md 4.5). */
const EXTENSIONS: Readonly<Record<string, () => Written.Extension>> = {
  include,
  throws: () => ({
    directive: "throws",
    specs: () => {
      throw new Error("the throws extension");
    },
  }),
};
const extension = (name: string): Written.Extension => {
  const make = EXTENSIONS[name];
  if (make === undefined) throw new Error(`no extension ${JSON.stringify(name)}`);
  return make();
};

type Handlers = { readonly [K in keyof RequestParams]: (p: RequestParams[K]) => RequestResults[K] | Promise<RequestResults[K]> };

const ops: Handlers = {
  hello: () => ({ protocol: PROTOCOL, binding: "typescript", unit: "utf-16", level: 3 }),
  parse: (p) => syntax(syntaxLayer.parse(p.text)),
  load: async (p) => {
    const processor = written.knobly({ source: failingReads(vl.memorySource(p.files), p.failReads), extensions: p.extensions.map(extension) });
    const overrides = p.overrides === undefined ? undefined : Object.fromEntries(Object.entries(p.overrides).map(([name, text]) => [name, vl.text(text)]));
    return { graph: ref(await processor.load(p.root, overrides === undefined ? undefined : { overrides })) };
  },
  graph: (p) => graph(get(p.graph)),
  render: (p) => rendered(renderedLayer.render(get(p.graph)), p.key),
  diff: (p) => get<Rendered.Rendered>(p.before).diff(get(p.after), keyOptions(p.key)).map((c): ChangeDump => ({ kind: c.kind, address: address(c.address) })),
  edit: (p) => {
    // Every text an edit takes is config text: the driver's texts go through the binding's own `text()` (spec 6.9).
    const textAt = TEXT_PARAMETER[p.member];
    const args = p.args.map((a, i) => (a === null ? undefined : i === textAt && typeof a === "string" ? vl.text(a) : a));
    const out = call(p.target, p.member, args);
    return Array.isArray(out) ? { handles: (out as readonly { text: string }[]).map((h) => ({ id: ref(h), text: h.text })) } : {};
  },
  save: async (p) => {
    if (p.disk !== undefined) {
      const disk: Record<string, string> = { ...p.disk };
      await get<Written.DocumentGraph>(p.graph).save(vl.memoryWriter(disk));
      return { files: Object.keys(disk).sort().map((path) => [path, disk[path] ?? ""] as const) };
    }
    const batches: (readonly (readonly [string, string])[])[] = [];
    const write = (files: readonly Knobly.FileWrite[]): Promise<void> => (batches.push(files.map((f) => [f.resolvedPath, f.text] as const)), Promise.resolve());
    await get<Written.DocumentGraph>(p.graph).save({ write });
    return { batches };
  },
  quote: (p) => vl.quote(p.text),
  read: (p) => result(call(p.value, p.reader, []) as ReaderResult),
  print: (p) => String(get(p.target)),
  format: (p) => written.formatDiagnostic(get(p.diagnostic), p.graph === undefined ? undefined : get(p.graph)),
  cut: (p) => p.text.slice(p.start, p.end),
};

/** The error's group by its spec name (the generated class-to-group table), with its code, diagnostics or paths. */
function group(error: unknown): Json | undefined {
  const name = error instanceof Error ? ERROR_GROUP_OF_CLASS[error.name] : undefined;
  if (name === undefined) return undefined;
  const out: Record<string, Json> = { group: name };
  if (error instanceof vl.DiagnosticError) out.code = error.diagnostic.code;
  if (error instanceof vl.BadTextError) out.diagnostics = error.diagnostics.map(diagnostic);
  if (error instanceof vl.ReadError || error instanceof vl.SaveError) out.paths = [...error.paths];
  return out;
}

const isOp = (op: string): op is keyof RequestParams => Object.hasOwn(ops, op);

for await (const line of createInterface({ input: process.stdin })) {
  const { id, op, ...params } = JSON.parse(line) as { readonly id: Json; readonly op: string };
  let response: Json;
  try {
    if (!isOp(op)) throw new Error(`unknown op ${JSON.stringify(op)}`);
    const handler = ops[op] as (p: unknown) => Json | Promise<Json>;
    response = { id, ok: await handler(params) };
  } catch (error) {
    const thrown = group(error);
    response = thrown === undefined ? { id, fault: String(error) } : { id, thrown };
  }
  process.stdout.write(`${JSON.stringify(response)}\n`);
}
