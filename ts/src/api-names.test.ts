/**
 * Every public name, per import path, is the generated `PUBLIC_NAMES` (spec/schema/api.json through the casing rule;
 * binding guide rules 1, 2 and 9), both ways: each entry's run-time exports equal its `values`, and the exports the
 * type checker sees as types equal its `types`. A name the schema lacks (a removed one, an internal one that leaked)
 * fails as surely as a missing one; nothing else here lists a name.
 */

import ts from "typescript";
import { describe, expect, it } from "vitest";

import { PUBLIC_NAMES } from "./gen/api/names.js";

/** Each import path's entry module (package.json "exports"), relative to this directory. */
const ENTRY: Readonly<Record<keyof typeof PUBLIC_NAMES, string>> = {
  villanelle: "./index.ts",
  "villanelle/browser": "./browser.ts",
  "villanelle/include": "./include.ts",
  "villanelle/node": "./node.ts",
  "villanelle/rendered": "./rendered/index.ts",
  "villanelle/syntax": "./syntax/index.ts",
  "villanelle/written": "./written/index.ts",
};

const paths = Object.keys(PUBLIC_NAMES) as (keyof typeof PUBLIC_NAMES)[];
const files = paths.map((path) => new URL(ENTRY[path], import.meta.url).pathname);
const program = ts.createProgram(files, { module: ts.ModuleKind.NodeNext, moduleResolution: ts.ModuleResolutionKind.NodeNext, strict: true });
const checker = program.getTypeChecker();

/** The names an entry exports that have a type meaning (interfaces, type aliases, classes, as-const lists). */
function typeExports(file: string): string[] {
  const source = program.getSourceFile(file);
  const module = source === undefined ? undefined : checker.getSymbolAtLocation(source);
  if (module === undefined) throw new Error(`no module symbol for ${file}`);
  return checker
    .getExportsOfModule(module)
    .filter((symbol) => {
      const target = symbol.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(symbol) : symbol;
      return (target.flags & ts.SymbolFlags.Type) !== 0;
    })
    .map((symbol) => symbol.name);
}

describe("public names are the generated PUBLIC_NAMES (spec/schema/api.json)", () => {
  it.each(paths.map((path, i) => [path, files[i] ?? ""] as const))("%s", async (path, file) => {
    const { values, types } = PUBLIC_NAMES[path];
    const module = (await import(file)) as Record<string, unknown>;
    expect(Object.keys(module).sort()).toEqual([...values].sort());
    expect(typeExports(file).sort()).toEqual([...types].sort());
  });
});
