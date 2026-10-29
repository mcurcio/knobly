/**
 * Values going in (spec 6.9, frozen-m1.md section 3): every member that takes villanelle text refuses anything else
 * with a TypeError naming the member and the parameter, before it changes anything; and the one check of an override
 * (spec 6.3) refuses the same texts from `load` and `setOverride`. No conformance case can carry a non-string, so
 * these are this binding's own tests.
 */
import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { memorySource } from "../source.js";
import { type ConfigText, quote, text } from "../text.js";
import { BadTextError, DetachedError, MisuseError } from "../errors.js";
import type { IDocumentGraph, ISetLine, IWrittenDirective, IUseLine } from "./model.js";
import { villanelle } from "./processor.js";

const MAIN = '@set $port 80;\n@snippet s $a { x $a; }\n@use s 1;\nserver "web" [1, 2] {\n  listen $port;\n}\n';

async function load(): Promise<IDocumentGraph> {
  return await villanelle({ source: memorySource({ "main.conf": MAIN }), extensions: [include()] }).load("main.conf", { overrides: { o: text("1") } });
}

/** A value of each wrong type: a number, null, undefined and (TypeScript) an array. */
const WRONG: readonly [string, unknown][] = [
  ["number", 2400],
  ["null", null],
  ["undefined", undefined],
  ["array", ["2400"]],
];

/** The argument type error's exact text (spec/schema/api.json, "argument type error message"). */
function message(member: string, parameter: string, got: string): string {
  return `${member}(): argument "${parameter}" must be a string, not ${got}; villanelle edits take config text: quote() a program string, text() one already written as villanelle text, String() a number first`;
}

/** Call `edit` with `value` where text goes, as a JavaScript caller or a cast could. */
function misuse(edit: (value: never) => unknown, value: unknown): () => unknown {
  return () => edit(value as never);
}

describe("text-only edits (spec 6.9)", () => {
  it.each(WRONG)("each member refuses a %s with a TypeError naming it, and changes nothing", async (got, value) => {
    const graph = await load();
    const doc = graph.root;
    const [setPort, , use, server] = doc.block.statements as [ISetLine, unknown, IUseLine, IWrittenDirective];
    const before = doc.text;
    const cases: [string, string, () => unknown][] = [
      ["set", "text", misuse((v) => server.set(v), value)],
      ["set", "text", misuse((v) => setPort.set(v), value)],
      ["set", "text", misuse((v) => use.set(v), value)],
      ["set", "text", misuse((v) => setPort.variable.set(v), value)],
      ["replaceWithText", "text", misuse((v) => server.replaceWithText(v), value)],
      ["replaceWithText", "text", misuse((v) => server.values[0]?.replaceWithText(v), value)],
      ["replaceWithText", "text", misuse((v) => doc.replaceWithText(v), value)],
      ["insertStatements", "text", misuse((v) => doc.block.insertStatements(0, v), value)],
      ["addStatements", "text", misuse((v) => server.block?.addStatements(v), value)],
      ["rename", "name", misuse((v) => server.rename(v), value)],
      ["rename", "name", misuse((v) => setPort.variable.rename(v), value)],
      ["quote", "text", misuse((v) => quote(v), value)],
      ["text", "raw", misuse((v) => text(v), value)],
      ["set", "text", misuse((v) => server.values[0]?.set(v), value)],
    ];
    if (value !== undefined) cases.push(["setOverride", "text", misuse((v) => graph.setOverride("o", v), value)]);
    cases.push(["setOverride", "name", misuse((v) => graph.setOverride(v, text("1")), value)]);
    for (const [member, parameter, call] of cases) {
      expect(call, `${member} ${parameter}`).toThrow(new TypeError(message(member, parameter, got)));
    }
    expect(doc.text).toBe(before);
    expect([...graph.overrides]).toEqual([["o", "1"]]);
  });

  it("takes undefined as setOverride's text: it removes the override", async () => {
    const graph = await load();
    graph.setOverride("o", undefined);
    expect([...graph.overrides]).toEqual([]);
  });

  it("refuses a load override that is not text, naming it as overrides[name]", async () => {
    for (const [got, value] of WRONG) {
      const processor = villanelle({ source: memorySource({ "main.conf": "a;\n" }) });
      const overrides = { port: value } as unknown as Record<string, ConfigText>;
      await expect(processor.load("main.conf", { overrides }), got).rejects.toThrow(new TypeError(message("load", 'overrides["port"]', got)));
    }
  });

  it("checks a detached handle first: DetachedError, not TypeError", async () => {
    const graph = await load();
    const [, , , server] = graph.root.block.statements as [unknown, unknown, unknown, IWrittenDirective];
    server.remove();
    expect(misuse((v) => server.set(v), 2400)).toThrow(DetachedError);
  });

  it("shows quote() as the way to write a program string", async () => {
    const graph = await load();
    const [, , , server] = graph.root.block.statements as [unknown, unknown, unknown, IWrittenDirective];
    server.set(quote("my host"));
    expect(server.text.split("\n")[0]).toBe('server "my host" {');
  });
});

describe("the check of an override (spec 6.3): one check for load and setOverride", () => {
  /** What the check refused, as [code, line, column] per diagnostic, or "ok". */
  function outcome(error: unknown): unknown {
    if (!(error instanceof BadTextError)) throw error;
    return error.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]);
  }

  async function fromLoad(given: string): Promise<unknown> {
    const processor = villanelle({ source: memorySource({ "main.conf": "a $v;\n" }) });
    try {
      await processor.load("main.conf", { overrides: { v: text(given) } });
      return "ok";
    } catch (error) {
      return outcome(error);
    }
  }

  async function fromSetOverride(given: string): Promise<unknown> {
    const graph = await villanelle({ source: memorySource({ "main.conf": "a $v;\n" }) }).load("main.conf");
    try {
      graph.setOverride("v", text(given));
      return "ok";
    } catch (error) {
      return outcome(error);
    }
  }

  it('refuses "1;" from load as from setOverride: E2001 at 0:1', async () => {
    expect(await fromLoad("1;")).toEqual([["E2001", 0, 1]]);
    expect(await fromSetOverride("1;")).toEqual([["E2001", 0, 1]]);
  });

  it('accepts "1\\n2" from load as from setOverride: a line break is whitespace, so it is two values', async () => {
    expect(await fromLoad("1\n2")).toEqual("ok");
    expect(await fromSetOverride("1\n2")).toEqual("ok");
  });

  it.each(["1", "8080 443", '"x" [1, 2]', "", "   ", "$x", "a { b; }", '"\\q"', "c[x]", '"open', "1;", "a; b", "1\n2", "1 // c\n"])("agrees on %j", async (given) => {
    expect(await fromLoad(given)).toEqual(await fromSetOverride(given));
  });

  it("refuses a bad name with a MisuseError from both, as a variable's rename does (one name check)", async () => {
    const processor = villanelle({ source: memorySource({ "main.conf": "@set $a 1;\n" }) });
    await expect(processor.load("main.conf", { overrides: { "a-b": text("1") } })).rejects.toThrow(MisuseError);
    const graph = await processor.load("main.conf");
    expect(() => graph.setOverride("a-b", text("1"))).toThrow(MisuseError);
    const [set] = graph.root.block.statements;
    expect(() => (set?.kind === "set" ? set.variable.rename("a-b") : undefined)).toThrow(MisuseError);
  });
});
