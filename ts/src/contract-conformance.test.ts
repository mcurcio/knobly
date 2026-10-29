/**
 * The contract conformance runner (conformance/contract/format.md; spec/contract.md): number readers, positions in
 * this binding's string unit (UTF-16 code units, so no conversion is needed before a span is compared), people forms
 * and `formatDiagnostic`. Each case's expected result is inline; a difference fails the case, naming it.
 */
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { DiagnosticError } from "./errors.js";
import type { IOverride, IPlace, IStep } from "./origin.js";
import { render } from "./rendered/render.js";
import type { IRendered } from "./rendered/model.js";
import { memorySource } from "./source.js";
import { formatDiagnostic, type IDocumentGraph, villanelle } from "./written/index.js";

const CONTRACT = new URL("../../conformance/contract/", import.meta.url);

type Target =
  | readonly ["argument", number, number, "place"]
  | readonly ["argument", number, number, "step", number]
  | readonly ["diagnostic", number]
  | readonly ["syntax diagnostic", string, number];

interface ILoaded {
  readonly files: Readonly<Record<string, string>>;
  readonly root: string;
  readonly overrides?: Readonly<Record<string, string>>;
  readonly target: Target;
}

type Case =
  | { readonly name: string; readonly kind: "reader"; readonly value: string; readonly reader: string; readonly expect: readonly [string, string] }
  | (ILoaded & { readonly name: string; readonly kind: "position"; readonly expect: { readonly span: readonly number[]; readonly slice: string } })
  | (ILoaded & { readonly name: string; readonly kind: "print"; readonly expect: string | Readonly<Record<string, string>> })
  | (ILoaded & { readonly name: string; readonly kind: "format"; readonly expect: readonly string[] });

const CASES = JSON.parse(readFileSync(new URL("cases.json", CONTRACT), "utf8")) as Case[];

/** This binding's string unit, as the cases name it. */
const UNIT = "utf-16";

async function load(c: ILoaded): Promise<{ readonly graph: IDocumentGraph; readonly rendered: IRendered }> {
  const graph = await villanelle({ source: memorySource(c.files) }).load(c.root, c.overrides === undefined ? undefined : { overrides: c.overrides });
  return { graph, rendered: render(graph) };
}

/** The target of a case: a place, an override, a step, or a diagnostic. */
function find(graph: IDocumentGraph, rendered: IRendered, target: Target): unknown {
  switch (target[0]) {
    case "argument": {
      const argument = rendered.block[target[1]]?.values[target[2]];
      if (argument === undefined) throw new Error(`no argument ${JSON.stringify(target)}`);
      return target[3] === "place" ? argument.origin.place : argument.origin.via[target[4]];
    }
    case "diagnostic":
      return rendered.diagnostics[target[1]];
    case "syntax diagnostic":
      return graph.documents.get(target[1])?.syntax.diagnostics[target[2]];
  }
}

/** The number rule of format.md: an integer type in decimal, a double as ECMAScript writes it (here both are `String`). */
function numberText(n: number): string {
  if (Object.is(n, -0)) throw new Error("a reader returned negative zero");
  return String(n);
}

function readerResult(c: Extract<Case, { kind: "reader" }>, rendered: IRendered): readonly [string, string] {
  const value = rendered.block[0]?.values[0];
  if (value === undefined) throw new Error(`${c.name}: no value`);
  const reader = (value as unknown as Record<string, () => unknown>)[c.reader];
  if (typeof reader !== "function") throw new Error(`${c.name}: no reader ${c.reader}`);
  let result: unknown;
  try {
    result = reader.call(value);
  } catch (error) {
    if (error instanceof DiagnosticError) return ["error", error.diagnostic.code];
    throw error;
  }
  if (typeof result === "boolean") return ["boolean", String(result)];
  if (typeof result === "string") return ["text", result];
  if (typeof result === "number") return [c.reader === "integer" ? "integer" : "number", numberText(result)];
  throw new Error(`${c.name}: a ${typeof result} result`);
}

function withMessage(text: string, message: string): string {
  return text.replaceAll("{message}", message);
}

describe("contract conformance (conformance/contract/cases.json)", () => {
  it.each(CASES.map((c) => [c.name, c] as const))("%s", async (_name, c) => {
    if (c.kind === "reader") {
      const { rendered } = await load({ files: { "main.conf": `x ${c.value};\n` }, root: "main.conf", target: ["diagnostic", 0] });
      expect(readerResult(c, rendered)).toEqual(c.expect);
      return;
    }
    const { graph, rendered } = await load(c);
    const target = find(graph, rendered, c.target);
    if (target === undefined) throw new Error(`${c.name}: no target ${JSON.stringify(c.target)}`);
    const message = (target as { readonly message?: string }).message ?? "";
    switch (c.kind) {
      case "position": {
        const place = target as IPlace;
        const { start, end } = place.span;
        const text = graph.documents.get(place.resolvedPath)?.text ?? "";
        // TypeScript's unit is the corpus's (UTF-16): the span is compared as it is.
        expect([start.line, start.column, end.line, end.column]).toEqual(c.expect.span);
        expect(text.slice(start.offset, end.offset)).toBe(c.expect.slice);
        return;
      }
      case "print": {
        const expected = typeof c.expect === "string" ? c.expect : c.expect[UNIT];
        if (expected === undefined) throw new Error(`${c.name}: no expectation for ${UNIT}`);
        expect(String(target as IPlace | IOverride | IStep)).toBe(withMessage(expected, message));
        return;
      }
      case "format": {
        const formatted = formatDiagnostic(target as Parameters<typeof formatDiagnostic>[0], graph);
        expect(formatted.split("\n")).toEqual(c.expect.map((line) => withMessage(line, message)));
        return;
      }
    }
  });
});
