/**
 * The written-layer conformance runner (conformance/written/format.md): every case, byte for byte with its expected
 * output, none skipped (slices.md B1). Through the public API only.
 */

import { readdirSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { include } from "./include.js";
import type { IOrigin, IPlace, IStep } from "./load/origin.js";
import { villanelle } from "./load/processor.js";
import { memorySource } from "./load/source.js";
import { originText, placeText } from "./load/testing.js";
import { TokenKind } from "./syntax/tokens.js";
import { BadTextError, EditError } from "./written/errors.js";
import type {
  IDocument,
  IDocumentGraph,
  IDocumentWriter,
  IFileWrite,
  IVariable,
  IWrittenBlock,
  Statement,
  WrittenValue,
} from "./written/model.js";
import { quote, save } from "./written/save.js";

const WRITTEN = new URL("../../conformance/written/", import.meta.url);
const EXPECTED = new URL("expected/", WRITTEN);
const FIXTURES = new URL("../../fixtures/", import.meta.url);

/** The `needs` tokens this runner implements: all of format.md's (slices.md §3). */
const FEATURES: ReadonlySet<string> = new Set([
  "include",
  "snippet",
  "values",
  "save",
  "quote",
  "statements",
  "directive-values",
  "blocks",
  "rename",
  "document",
  "handed",
]);

type Step = readonly [string, ...unknown[]];

/** format.md "Case". */
interface ICase {
  readonly name: string;
  readonly needs: readonly string[];
  readonly files?: Readonly<Record<string, string>>;
  readonly fixture?: string;
  readonly root: string;
  readonly variables?: Readonly<Record<string, string>>;
  readonly extensions?: readonly "include"[];
  readonly steps: readonly Step[];
}

const CASES = JSON.parse(readFileSync(new URL("cases.json", WRITTEN), "utf8")) as ICase[];

/** A fixture directory's `*.conf` files, by path relative to it. */
function fixtureFiles(directory: string): Record<string, string> {
  const url = new URL(`${directory}/`, FIXTURES);
  const files: Record<string, string> = {};
  for (const name of readdirSync(url).filter((n) => n.endsWith(".conf")).sort()) files[name] = readFileSync(new URL(name, url), "utf8");
  return files;
}

function bytes(value: unknown): string {
  const json = JSON.stringify(value).replace(/[\u0080-￿]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return `${json}\n`;
}

/** The copy text of format.md: the load-conformance origin text of `{written, via}`. */
function copyText(written: IPlace, via: readonly IStep[]): string {
  return originText({ written, via });
}

function variableText(variable: IVariable | undefined): string | null {
  if (variable === undefined) return null;
  return variable.place === undefined ? `handed ${variable.name}` : placeText(variable.place);
}

function origin(o: IOrigin): string {
  return originText(o);
}

/** Every statement of a block, depth first in text order. */
function statementsOf(block: IWrittenBlock): Statement[] {
  return block.statements.flatMap((s) => [s, ...("block" in s && s.block !== undefined ? statementsOf(s.block) : [])]);
}

function valuesOf(statement: Statement): WrittenValue[] {
  const all: WrittenValue[] = [];
  const add = (v: WrittenValue): void => {
    all.push(v);
    if (v.kind === "list") v.items.forEach(add);
    if (v.kind === "slice") [v.start, v.end].forEach((b) => b !== undefined && add(b));
    if (v.kind === "index") add(v.index);
  };
  if ("values" in statement) statement.values.forEach(add);
  return all;
}

/** The statement whose name token starts at line:col: the first token of its place that is not a comment or space. */
function nameAt(doc: IDocument, statement: Statement): [number, number] {
  const offset = statement.place.span.start.offset;
  const token = doc.syntax.tokens.find(
    (t) => t.span.start.offset >= offset && t.kind !== TokenKind.Comment && t.kind !== TokenKind.Space && t.kind !== TokenKind.Newline,
  );
  return [token?.span.start.line ?? -1, token?.span.start.column ?? -1];
}

function at(place: IPlace, line: number, col: number): boolean {
  return place.span.start.line === line && place.span.start.column === col;
}

class Runner {
  private previous: unknown;
  private returned: unknown;
  private readonly batches: IFileWrite[][] = [];
  private readonly writer: IDocumentWriter = {
    write: (files) => {
      this.batches.push([...files]);
      return Promise.resolve();
    },
  };

  constructor(
    private readonly processor: ReturnType<typeof villanelle>,
    private readonly graph: IDocumentGraph,
  ) {}

  private doc(path: unknown): IDocument {
    const doc = this.graph.documents.get(path as string);
    if (doc === undefined) throw new Error(`no document ${String(path)}`);
    return doc;
  }

  private statement(path: unknown, line: unknown, col: unknown): Statement {
    const doc = this.doc(path);
    const found = statementsOf(doc.body).find((s) => {
      const [l, c] = nameAt(doc, s);
      return l === line && c === col;
    });
    if (found === undefined) throw new Error(`no statement at ${String(path)}:${String(line)}:${String(col)}`);
    return found;
  }

  private target(target: readonly unknown[]): unknown {
    const [kind, ...rest] = target;
    switch (kind) {
      case "document":
        return this.doc(rest[0]);
      case "statement":
        return this.statement(rest[0], rest[1], rest[2]);
      case "block": {
        if (rest.length === 1) return this.doc(rest[0]).body;
        const statement = this.statement(rest[0], rest[1], rest[2]);
        return "block" in statement ? statement.block : undefined;
      }
      case "value": {
        const doc = this.doc(rest[0]);
        const found = statementsOf(doc.body)
          .flatMap(valuesOf)
          .find((v) => at(v.place, rest[1] as number, rest[2] as number));
        if (found === undefined) throw new Error(`no value at ${JSON.stringify(rest)}`);
        return found;
      }
      case "variable":
        return this.graph.variables().find((v) => v.place !== undefined && v.place.resolvedPath === rest[0] && at(v.place, rest[1] as number, rest[2] as number));
      case "handed":
        return this.graph.variables().find((v) => v.kind === "handed" && v.name === rest[0]);
      case "graph":
        return this.graph;
      case "previous":
        return this.previous;
      case "returned":
        return this.returned;
      case "rendered": {
        const [address, arg, step, which] = rest as [string, number, number, "winner" | "reference"];
        const rendered = this.processor.render(this.graph);
        let found;
        for (const [d, at] of rendered.addresses()) {
          if (at.toString() === address) found = d.args[arg]?.resolutions[step]?.[which];
        }
        return found;
      }
      default:
        throw new Error(`unknown target ${String(kind)}`);
    }
  }

  private edit(target: readonly unknown[], op: string, args: readonly unknown[]): unknown {
    const handle = this.target(target) as Record<string, (...a: unknown[]) => unknown>;
    this.previous = handle;
    try {
      const method = handle[op];
      if (typeof method !== "function") throw new Error(`no ${op} on ${JSON.stringify(target)}`);
      // JSON has no undefined: `["setHanded", name, null]` removes the value.
      const result = method.apply(handle, args.map((a) => (a === null ? undefined : a)));
      if (Array.isArray(result)) {
        this.returned = result[0];
        return ["ok", (result as { text: string }[]).map((h) => h.text)];
      }
      return ["ok"];
    } catch (error) {
      if (!(error instanceof EditError)) throw error;
      const diagnostics = error instanceof BadTextError ? error.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]) : [];
      return ["error", error.name, diagnostics];
    }
  }

  private list(): unknown {
    const g = this.graph;
    return {
      files: [...g.documents.values()].map((d) => [d.resolvedPath, d.includedBy().map((e) => copyText(e.copy.statement.place, e.copy.via))]),
      edges: g.edges().map((e) => [copyText(e.copy.statement.place, e.copy.via), e.specs, e.targets]),
      variables: g
        .variables()
        .map((v) => [
          v.name,
          v.kind,
          v.place === undefined ? "handed" : placeText(v.place),
          v.reaches().map((r) => copyText(r.reference.place, r.copy.via)),
          v.overridden().map((r) => [copyText(r.reference.place, r.copy.via), variableText(r.winner)]),
        ]),
      diagnostics: g.diagnostics().map((d) => [d.code, origin({ written: d.at, via: d.via })]),
    };
  }

  private references(): unknown {
    return [...this.graph.documents.values()].flatMap((doc) =>
      statementsOf(doc.body)
        .flatMap(valuesOf)
        .filter((v) => v.kind === "reference")
        .map((r) => [
          placeText(r.place),
          variableText(r.declaration),
          r.resolutions().map((x) => [copyText(r.place, x.copy.via), variableText(x.winner), x.overridden.map(variableText)]),
        ]),
    );
  }

  private render(): unknown {
    const rendered = this.processor.render(this.graph);
    const directives: unknown[] = [];
    const unreadable: unknown[] = rendered.unreadable.map((u) => ["", u.kind, origin(u.origin)]);
    const named = rendered.addresses();
    rendered.walk((d) => {
      const address = named.get(d)?.toString();
      directives.push([
        address,
        d.body !== undefined,
        origin(d.origin),
        d.args.map((a) => [
          a.text,
          origin(a.origin),
          a.written === undefined ? null : placeText(a.written.place),
          a.resolutions.map((r) => [copyText(r.reference.place, r.copy.via), variableText(r.winner)]),
        ]),
      ]);
      for (const u of d.unreadable) unreadable.push([address, u.kind, origin(u.origin)]);
    });
    return { directives, unreadable, diagnostics: rendered.diagnostics.map((d) => [d.code, origin({ written: d.at, via: d.via })]) };
  }

  async step(step: Step): Promise<unknown> {
    const [kind, ...args] = step;
    switch (kind) {
      case "list":
        return this.list();
      case "references":
        return this.references();
      case "render":
        return this.render();
      case "texts":
        return [...this.graph.documents.values()].filter((d) => d.text !== d.source).map((d) => [d.resolvedPath, d.text]);
      case "save": {
        const before = this.batches.length;
        await save(this.graph, this.writer);
        const batch = this.batches.length > before ? (this.batches.at(-1) ?? []) : [];
        return batch.map((f) => [f.resolvedPath, f.text]);
      }
      case "edit":
        return this.edit(args[0] as unknown[], args[1] as string, args.slice(2));
      case "quote":
        return quote(args[0] as string);
      default:
        throw new Error(`unknown step ${kind}`);
    }
  }
}

describe("written conformance (conformance/written/)", () => {
  it("has an expected file for every case and a case for every expected file", () => {
    const expected = readdirSync(EXPECTED).filter((n) => n.endsWith(".json")).map((n) => n.slice(0, -5)).sort();
    expect(expected).toEqual(CASES.map((c) => c.name).sort());
  });

  it("implements every feature a case needs, so no case is skipped", () => {
    expect(CASES.flatMap((c) => c.needs.filter((need) => !FEATURES.has(need)).map((need) => `${c.name}: ${need}`))).toEqual([]);
  });

  it.each(CASES.map((c) => [c.name, c] as const))("%s", async (name, c) => {
    const files = c.fixture === undefined ? (c.files ?? {}) : fixtureFiles(c.fixture);
    const processor = villanelle({
      source: memorySource(files),
      ...(c.extensions?.includes("include") === true ? { extensions: [include()] } : {}),
    });
    const graph = await processor.load(c.root, c.variables === undefined ? undefined : { variables: c.variables });
    const runner = new Runner(processor, graph);
    const out: unknown[] = [];
    for (const step of c.steps) out.push(await runner.step(step));
    expect(bytes(out)).toBe(readFileSync(new URL(`${name}.json`, EXPECTED), "utf8"));
  });
});
