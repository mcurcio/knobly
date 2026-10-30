// Sample "diff_reload" (examples/samples.json): what changed between two loads of a file edited on disk, with nodes
// keyed by their id. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/diff_reload.txt.
// --8<-- [start:main]
import { readFileSync, writeFileSync } from "node:fs";

import { villanelle } from "villanelle/written";
import { render, type KeyRule } from "villanelle/rendered";
import { include } from "villanelle/include";
import { fileSource } from "villanelle/node";

const config = villanelle({ source: fileSource(), extensions: [include()] });
const before = render(await config.load("main.conf"));

const edited = readFileSync("main.conf", "utf8")
  .replace("@set $pixels 2284;", "@set $pixels 2400;")
  .replace(/ {4}node Waveform hue_ramp \{[^}]*\}\n\n/, "");
writeFileSync("main.conf", edited);
const after = render(await config.load("main.conf"));

// --8<-- [start:diff]
const byNodeId: KeyRule = (directive) =>
  directive.name === "node" && directive.parent?.name === "graph" ? directive.values[1]?.text : undefined;
for (const change of before.diff(after, { key: byNodeId })) {
  console.log(`${change.kind} ${String(change.address)}`);
}
// --8<-- [end:diff]
// --8<-- [end:main]
