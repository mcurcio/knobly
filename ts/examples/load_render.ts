// Sample "load_render" (examples/samples.json): a processor with the file source and the include extension; which
// files a load read; the nodes of the rendered tree, each with where it was written. ts/examples/examples.test.ts runs
// this file and compares what it prints with examples/expected/load_render.txt.
// --8<-- [start:main]
import { WalkControl } from "villanelle";
import { villanelle } from "villanelle/written";
import { render } from "villanelle/rendered";
import { include } from "villanelle/include";
import { fileSource } from "villanelle/node";

// --8<-- [start:processor]
const config = villanelle({ source: fileSource(), extensions: [include()] });
const graph = await config.load("main.conf");
for (const path of graph.documents.keys()) console.log(`read ${path}`);
// --8<-- [end:processor]

// --8<-- [start:walk]
render(graph).block.walk((directive) => {
  if (directive.name === "node") {
    const values = directive.values.map((value) => value.text).join(" ");
    console.log(`node ${values} (${String(directive.origin.place)})`);
  }
  return directive.name === "graph" ? undefined : WalkControl.Skip;
});
// --8<-- [end:walk]
// --8<-- [end:main]
