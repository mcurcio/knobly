/**
 * The layer check bites (frozen-m1.md section 4): ts/eslint.config.js applies the core rule no-restricted-imports to
 * every module but the rendered layer, the package entry and tests, and that rule refuses a planted type-only import
 * of the rendered layer from the low level. `pnpm lint` runs the rule over the real tree.
 */
import { ESLint, Linter } from "eslint";
import tseslint from "typescript-eslint";
import { describe, expect, it } from "vitest";

const ROOT = new URL("..", import.meta.url).pathname;

/** The no-restricted-imports setting ESLint uses for a file of this package. */
async function ruleFor(path: string): Promise<Linter.RuleEntry | undefined> {
  const config = (await new ESLint({ cwd: ROOT }).calculateConfigForFile(path)) as Linter.Config;
  return config.rules?.["no-restricted-imports"];
}

/** What the rule reports for `code` as a TypeScript file of src/written/. */
function lint(code: string, rule: Linter.RuleEntry): (string | null)[] {
  const config: Linter.Config = { files: ["**/*.ts"], languageOptions: { parser: tseslint.parser }, rules: { "no-restricted-imports": rule } };
  return new Linter().verify(code, [config], "src/written/planted.ts").map((m) => m.ruleId);
}

const PLANTED = 'import type { IRendered } from "../rendered/model.js";\nexport type Leak = IRendered;\n';

describe("layer direction (spec 5)", () => {
  it("applies the rule to the low level and shared modules, not to the rendered layer or the entry", async () => {
    for (const path of ["src/written/graph.ts", "src/value.ts", "src/include.ts", "src/written/planted.ts"]) {
      expect(await ruleFor(path), path).toBeDefined();
    }
    for (const path of ["src/rendered/render.ts", "src/index.ts"]) expect(await ruleFor(path), path).toBeUndefined();
  });

  it("refuses a planted type-only import of the rendered layer from src/written/", async () => {
    const rule = await ruleFor("src/written/planted.ts");
    if (rule === undefined) throw new Error("no layer rule for src/written/");
    expect(lint(PLANTED, rule)).toEqual(["no-restricted-imports"]);
    expect(lint('export type { IRendered } from "../rendered/index.js";\n', rule)).toEqual(["no-restricted-imports"]);
    expect(lint('import type { IDocumentGraph } from "./model.js";\nexport type Fine = IDocumentGraph;\n', rule)).toEqual([]);
  });
});
