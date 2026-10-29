// Lint rules from reference/rasl-config-ts/STYLE.md, enforced with typescript-eslint's type-aware rules.
import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

/** The rendered layer, as an import pattern; exported so src/layers.test.ts can plant a violation against it. */
export const LAYER_RULE = {
  group: ["**/rendered", "**/rendered/**"],
  message: "Only the rendered layer and the package entry import the rendered layer (spec 5, Layer direction).",
};

export default defineConfig(
  { ignores: ["dist/", "src/gen/", "node_modules/"] },
  { linterOptions: { reportUnusedDisableDirectives: "error" } },
  js.configs.recommended,
  tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: { allowDefaultProject: ["eslint.config.js"] },
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/explicit-function-return-type": ["error", { allowExpressions: true }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-floating-promises": "error",
    },
  },
  // Layer direction (spec 5; owner, 2026-10-29: "The low level shouldn't "depend on" the middle layer"): only the
  // rendered layer and the package entry import the rendered layer, type-only imports and re-exports included.
  // src/layers.test.ts plants a forbidden import to show the rule bites.
  {
    files: ["src/**/*.ts"],
    ignores: ["src/rendered/**", "src/index.ts", "src/**/*.test.ts"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [LAYER_RULE] }],
    },
  },
);
