// Sample "sink" (examples/samples.json): one sink collects the render's problems, a reader's error and the program's
// own checks. ts/examples/examples.test.ts runs this file and compares what it prints with examples/expected/sink.txt.
// --8<-- [start:main]
import { Diagnostics, memorySource } from "villanelle";
import { villanelle } from "villanelle/written";
import { render } from "villanelle/rendered";

const source = memorySource({ "main.conf": "port eighty;\nnode Mystery m;\nfps $x;\n" });
const tree = render(await villanelle({ source }).load("main.conf"));
const sink = new Diagnostics(tree.diagnostics);

// --8<-- [start:collect]
const port = sink.collect(() => tree.block.directives("port")[0]?.values[0]?.integer());
if (port === undefined) console.log("port unset");
// --8<-- [end:collect]

// --8<-- [start:report]
for (const node of tree.block.directives("node")) {
  sink.report(node, `unknown node type ${node.values[0]?.text}`, "app/unknown-node");
}
// --8<-- [end:report]

for (const diagnostic of sink) console.log(String(diagnostic));
// --8<-- [end:main]
