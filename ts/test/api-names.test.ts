/**
 * Every public name, per import path, is the generated `PUBLIC_NAMES` (spec/schema/api.json through the casing rule;
 * binding guide rules 1, 2 and 9), both ways: each entry's run-time exports equal its `values`, and the exports the
 * type checker sees as types equal its `types`. A name the schema lacks (a removed one, an internal one that leaked)
 * fails as surely as a missing one; nothing else here lists a name.
 */

import ts from "typescript";
import { describe, expect, it } from "vitest";

import { PUBLIC_NAMES } from "./api-contract.ts";

/** Each import path's entry module (package.json "exports"), relative to this directory. */
const ENTRY: Readonly<Record<keyof typeof PUBLIC_NAMES, string>> = {
  knobly: "../src/index.ts",
  "knobly/browser": "../src/browser.ts",
  "knobly/include": "../src/include.ts",
  "knobly/node": "../src/node.ts",
  "knobly/rendered": "../src/rendered/index.ts",
  "knobly/syntax": "../src/syntax/index.ts",
  "knobly/written": "../src/written/index.ts",
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

/** What a public doc may not carry (spec/codegen.md section 3, "Docs and rationale"): it belongs in a `//` comment. */
const HISTORY = /\bkno-[a-z0-9]{3}(\.[0-9]+)*\b|\bmilestone [0-9]|\bowner, [0-9]{4}-|\bgen\/api\b|\.test\.ts\b/;

/** Every JSDoc a program sees on hover: each export of each entry, and each member of an exported class or interface. */
function publicDocs(): [string, string][] {
  const out: [string, string][] = [];
  const text = (node: ts.Node): string =>
    ts
      .getJSDocCommentsAndTags(node)
      .map((d) => d.getText())
      .join("\n");
  for (const [i, file] of files.entries()) {
    const source = program.getSourceFile(file);
    const module = source === undefined ? undefined : checker.getSymbolAtLocation(source);
    if (module === undefined) throw new Error(`no module symbol for ${file}`);
    for (const exported of checker.getExportsOfModule(module)) {
      const symbol = exported.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(exported) : exported;
      for (const decl of symbol.declarations ?? []) {
        out.push([`${paths[i] ?? file}.${exported.name}`, text(decl)]);
        if (ts.isClassDeclaration(decl) || ts.isInterfaceDeclaration(decl)) {
          for (const member of decl.members) out.push([`${paths[i] ?? file}.${exported.name}.${member.name?.getText() ?? "?"}`, text(member)]);
        }
      }
    }
  }
  return out;
}

describe("public docs carry no maintainer history", () => {
  it("has none", () => {
    expect(publicDocs().filter(([, doc]) => HISTORY.test(doc)).map(([where, doc]) => `${where}: ${HISTORY.exec(doc)?.[0] ?? ""}`)).toEqual([]);
  });
});

/**
 * What a program sees on hover is the schema's doc (spec/codegen.md section 3): every export of every entry has a doc,
 * on its declaration or, for a function or constructor, on its call or construct signature; and every member of an
 * exported interface has one. A declaration the schema leaves undocumented, or a public function typed by hand
 * instead of by its generated signature, fails here.
 */
function undocumented(): string[] {
  const out: string[] = [];
  const docOf = (symbol: ts.Symbol): string => ts.displayPartsToString(symbol.getDocumentationComment(checker));
  for (const [i, file] of files.entries()) {
    const source = program.getSourceFile(file);
    const module = source === undefined ? undefined : checker.getSymbolAtLocation(source);
    if (module === undefined) throw new Error(`no module symbol for ${file}`);
    for (const exported of checker.getExportsOfModule(module)) {
      const where = `${paths[i] ?? file}.${exported.name}`;
      const symbol = exported.flags & ts.SymbolFlags.Alias ? checker.getAliasedSymbol(exported) : exported;
      let doc = docOf(symbol);
      if (symbol.flags & ts.SymbolFlags.Value && doc === "") {
        const type = checker.getTypeOfSymbol(symbol);
        const signatures = [...type.getCallSignatures(), ...type.getConstructSignatures()];
        doc = signatures.map((s) => ts.displayPartsToString(s.getDocumentationComment(checker))).join("");
      }
      if (doc === "") out.push(where);
      for (const decl of symbol.declarations ?? []) {
        if (!ts.isInterfaceDeclaration(decl)) continue;
        for (const member of checker.getPropertiesOfType(checker.getDeclaredTypeOfSymbol(symbol))) {
          if (docOf(member) === "") out.push(`${where}.${member.name}`);
        }
      }
    }
  }
  return out;
}

describe("public declarations carry the schema's docs", () => {
  it("every export and every interface member has a doc", () => {
    expect(undocumented()).toEqual([]);
  });
});
