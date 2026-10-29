// Lint rules from reference/rasl-config-ts/STYLE.md, enforced with typescript-eslint's type-aware rules.
import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

import { KIND_RULE } from "../tools/lint/kind-rule.mjs";

/** The rendered layer, as an import pattern; exported so src/layers.test.ts can plant a violation against it. */
export const LAYER_RULE = {
  group: ["**/rendered", "**/rendered/**", "**/gen/api/rendered.js"],
  message: "Only the rendered layer and the package entry import the rendered layer (spec 5, Layer direction).",
};

/** The rendered layer reaches the low level only through its public entry; exported for src/layers.test.ts. */
export const PUBLIC_RULE = {
  group: ["**/written/*", "!**/written/index.js"],
  message: "The rendered layer builds only on the low level's public API: import ../written/index.js (spec 7.0).",
};

/** No cast that could reach past the low level's public types; exported for src/layers.test.ts. */
export const NO_CAST_RULE = [
  { selector: "TSAsExpression[typeAnnotation.type='TSUnknownKeyword']", message: "No cast through unknown in the rendered layer (spec 7.0)." },
  { selector: "TSAsExpression > TSAsExpression", message: "No double cast in the rendered layer (spec 7.0)." },
];

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
  // The kind lint (spec 2.10; owner, 2026-10-29, "Yes, generate both"): a .kind, .reason or .code is compared with a
  // generated member, never a string literal. src/layers.test.ts plants each form to show the rule bites.
  {
    files: ["src/**/*.ts", "conformance/*.ts"],
    rules: {
      "no-restricted-syntax": ["error", ...KIND_RULE],
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
  // The rendered layer builds only on the low level's public objects (owner, 2026-10-29: "The middle layer of objects
  // can build on the lower layer domains"): it imports ../written/index.js and nothing else under written/, and casts
  // nothing through unknown. src/layers.test.ts plants each pattern to show the rules bite.
  {
    files: ["src/rendered/**/*.ts"],
    ignores: ["src/**/*.test.ts"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [PUBLIC_RULE] }],
      "no-restricted-syntax": ["error", ...NO_CAST_RULE, ...KIND_RULE],
    },
  },
);
