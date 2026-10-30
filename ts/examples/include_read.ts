// Sample "include_read" (examples/samples.json): an include line added by an edit is unread until read() reads it.
// ts/examples/examples.test.ts runs this file and compares what it prints with examples/expected/include_read.txt.
// --8<-- [start:main]
import { memorySource, text } from "knobly";
import { knobly, type DocumentGraph } from "knobly/written";
import { render } from "knobly/rendered";
import { include } from "knobly/include";

const source = memorySource({ "main.conf": "name main;\n", "extra.conf": "name extra;\n" });
const graph = await knobly({ source, extensions: [include()] }).load("main.conf");

function showUnread(graph: DocumentGraph): void {
  const names = render(graph).block.directives("name").map((directive) => directive.values[0]?.text);
  console.log(`unread ${graph.unread().length}: ${names.join(", ")}`);
}

graph.root.block.addStatements(text('@include "extra.conf";'));
showUnread(graph);
for (const diagnostic of render(graph).diagnostics) console.log(String(diagnostic));
await graph.read();
showUnread(graph);
// --8<-- [end:main]
