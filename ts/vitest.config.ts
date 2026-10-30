// The samples of the user guide (examples/samples.json) import the package as a program does ("villanelle/written");
// in the tests those names resolve to the source, by the package's own export map: each export's "./dist/<x>.js"
// becomes "./src/<x>.ts", so the map stays the one list of entry points.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

interface Manifest {
  readonly name: string;
  readonly exports: Readonly<Record<string, { readonly import: string }>>;
}

const manifest = JSON.parse(readFileSync(new URL("package.json", import.meta.url), "utf8")) as Manifest;
const alias = Object.entries(manifest.exports).map(([entry, target]) => ({
  find: new RegExp(`^${(manifest.name + entry.slice(1)).replaceAll("/", "\\/")}$`),
  replacement: fileURLToPath(new URL(target.import.replace(/^\.\/dist\//, "./src/").replace(/\.js$/, ".ts"), import.meta.url)),
}));

export default defineConfig({ resolve: { alias } });
