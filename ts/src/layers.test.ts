/**
 * The layer checks bite (frozen-m1.md section 4, frozen-m2.md section 4.3). Down: ts/eslint.config.js applies the
 * core rule no-restricted-imports to every module but the rendered layer, the package entry and tests, and that rule
 * refuses a planted type-only import of the rendered layer from the low level. Public: in the rendered layer it
 * refuses an import of a low-level module other than written/index.js, and no-restricted-syntax refuses a cast
 * through unknown and a double cast. Kinds (spec 2.10): no-restricted-syntax refuses a `.kind`, `.reason` or `.code`
 * compared with a string literal everywhere in src/ and conformance/. `pnpm lint` runs the rules over the real tree.
 */
import { ESLint, Linter } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const ROOT = new URL("..", import.meta.url).pathname;

/** The setting of `rule` (default no-restricted-imports) ESLint uses for a file of this package. */
async function ruleFor(path: string, rule = "no-restricted-imports"): Promise<Linter.RuleEntry | undefined> {
  const config = (await new ESLint({ cwd: ROOT }).calculateConfigForFile(path)) as Linter.Config;
  return config.rules?.[rule];
}

/** What the rules report for `code` as a TypeScript file at `path`. */
function lint(code: string, rule: Linter.RuleEntry, path = "src/written/planted.ts", name = "no-restricted-imports"): (string | null)[] {
  const config: Linter.Config = { files: ["**/*.ts"], languageOptions: { parser: tseslint.parser }, rules: { [name]: rule } };
  return new Linter().verify(code, [config], path).map((m) => m.ruleId);
}

const PLANTED = 'import type { Rendered } from "../rendered/tree.js";\nexport type Leak = Rendered;\n';

describe("layer direction (spec 5)", () => {
  it("applies the rule to the low level and shared modules, not to the rendered layer or the entry", async () => {
    for (const path of ["src/written/graph.ts", "src/value.ts", "src/include.ts", "src/written/planted.ts"]) {
      expect(await ruleFor(path), path).toBeDefined();
    }
    expect(await ruleFor("src/index.ts")).toBeUndefined();
    // The rendered layer has its own import rule (below), which does not refuse the rendered layer itself.
    expect(JSON.stringify(await ruleFor("src/rendered/render.ts"))).not.toContain("**/rendered");
  });

  it("refuses a planted type-only import of the rendered layer from src/written/", async () => {
    const rule = await ruleFor("src/written/planted.ts");
    if (rule === undefined) throw new Error("no layer rule for src/written/");
    expect(lint(PLANTED, rule)).toEqual(["no-restricted-imports"]);
    expect(lint('export type { Rendered } from "../rendered/index.js";\n', rule)).toEqual(["no-restricted-imports"]);
    expect(lint('import type { Rendered } from "../gen/api/rendered.js";\nexport type Leak = Rendered;\n', rule)).toEqual(["no-restricted-imports"]);
    expect(lint('import type { DocumentGraph } from "../gen/api/written.js";\nexport type Fine = DocumentGraph;\n', rule)).toEqual([]);
  });
});

describe("the rendered layer on the low level's public API (spec 7.0)", () => {
  const PLANTED_PATH = "src/rendered/planted.ts";

  it("applies the import rule and the cast rule to the rendered layer, testing helpers included, not to its tests", async () => {
    for (const path of ["src/rendered/render.ts", "src/rendered/testing.ts", PLANTED_PATH]) {
      expect(await ruleFor(path), path).toBeDefined();
      expect(await ruleFor(path, "no-restricted-syntax"), path).toBeDefined();
    }
    expect(JSON.stringify(await ruleFor("src/rendered/rules.test.ts", "no-restricted-syntax"))).not.toContain("TSAsExpression");
  });

  it("refuses a planted import of a low-level module other than its public entry", async () => {
    const rule = await ruleFor(PLANTED_PATH);
    if (rule === undefined) throw new Error("no import rule for src/rendered/");
    expect(lint('import { bind } from "../written/bind.js";\nexport const leak = bind;\n', rule, PLANTED_PATH)).toEqual(["no-restricted-imports"]);
    expect(lint('import type { Bound } from "../written/expanded.js";\nexport type Leak = Bound;\n', rule, PLANTED_PATH)).toEqual([
      "no-restricted-imports",
    ]);
    expect(lint('import type { DocumentGraph } from "../written/index.js";\nexport type Fine = DocumentGraph;\n', rule, PLANTED_PATH)).toEqual([]);
  });

  it("refuses a planted cast through unknown and a planted double cast", async () => {
    const rule = await ruleFor(PLANTED_PATH, "no-restricted-syntax");
    if (rule === undefined) throw new Error("no cast rule for src/rendered/");
    const check = (code: string): (string | null)[] => lint(code, rule, PLANTED_PATH, "no-restricted-syntax");
    expect(check("declare const graph: object;\nexport const g: unknown = graph as unknown;\n")).toEqual(["no-restricted-syntax"]);
    expect(check("declare const graph: object;\nexport const g = graph as unknown as { binding(): void };\n")).toEqual([
      "no-restricted-syntax",
      "no-restricted-syntax",
    ]);
    expect(check("declare const x: object;\nexport const y = (x as { a: 1 }) as { a: 1; b: 2 };\n")).toEqual(["no-restricted-syntax"]);
    expect(check("declare const x: object;\nexport const y = x as { a: 1 };\n")).toEqual([]);
  });
});

describe("kinds are compared with generated members (spec 2.10)", () => {
  it("applies the kind rule to every module, tests and the conformance adapter included", async () => {
    for (const path of ["src/written/bind.ts", "src/rendered/render.ts", "src/rendered/rules.test.ts", "conformance/adapter.ts"]) {
      expect(JSON.stringify(await ruleFor(path, "no-restricted-syntax")), path).toContain("(kind|reason|code)");
    }
  });

  it("refuses a planted comparison of .kind, .reason or .code with a string literal, and passes a member", async () => {
    const rule = await ruleFor("src/written/planted.ts", "no-restricted-syntax");
    if (rule === undefined) throw new Error("no kind rule for src/written/");
    const check = (code: string): (string | null)[] => lint(`declare const s: { kind: string; reason: string; code: string };\n${code}`, rule, "src/written/planted.ts", "no-restricted-syntax");
    expect(check('export const a = s.kind === "set";\n')).toEqual(["no-restricted-syntax"]);
    expect(check('export const a = "use" !== s.kind;\n')).toEqual(["no-restricted-syntax"]);
    expect(check('export const a = s.reason == "value";\n')).toEqual(["no-restricted-syntax"]);
    expect(check('switch (s.code) { case "E1001": break; }\n')).toEqual(["no-restricted-syntax"]);
    expect(check('declare const K: { Set: "set" };\nexport const a = s.kind === K.Set;\nswitch (s.kind) { case K.Set: break; }\n')).toEqual([]);
  });
});
