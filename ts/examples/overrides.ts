// Sample "overrides" (examples/samples.json): one processor loads the same files twice, the second time with a value
// from the program that wins over the file's own. ts/examples/examples.test.ts runs this file and compares what it
// prints with examples/expected/overrides.txt.
// --8<-- [start:main]
import { quote } from "villanelle";
import { villanelle } from "villanelle/written";
import { render } from "villanelle/rendered";
import { include } from "villanelle/include";
import { fileSource } from "villanelle/node";

const config = villanelle({ source: fileSource(), extensions: [include()] });
// --8<-- [start:load]
const plain = await config.load("main.conf");
const overridden = await config.load("main.conf", { overrides: { leds_host: quote("10.0.70.1") } });
// --8<-- [end:load]

for (const graph of [plain, overridden]) {
  const names = [...graph.overrides.keys()];
  console.log(`overrides: ${names.length > 0 ? names.join(", ") : "none"}`);
  const nodes = render(graph).block.directives("graph")[0]?.block?.directives("node") ?? [];
  for (const node of nodes) {
    for (const target of node.block?.directives("target") ?? []) {
      console.log(`  ${node.values[1]?.text} -> ${target.values[0]?.string()}`);
    }
  }
}
// --8<-- [end:main]
