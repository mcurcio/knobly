// Sample "edit_save" (examples/samples.json): change a variable where it is set, save the change to disk, and render
// again. ts/examples/examples.test.ts runs this file and compares what it prints with examples/expected/edit_save.txt.
// --8<-- [start:main]
import { readFileSync } from "node:fs";

import { text } from "villanelle";
import { villanelle, VariableKind } from "villanelle/written";
import { render } from "villanelle/rendered";
import { include } from "villanelle/include";
import { fileSource, fileWriter } from "villanelle/node";

const graph = await villanelle({ source: fileSource(), extensions: [include()] }).load("main.conf");

// --8<-- [start:edit]
for (const variable of graph.variables("pixels")) {
  if (variable.kind === VariableKind.Set) variable.set(text("2400"));
}
// --8<-- [end:edit]

// --8<-- [start:save]
const saved = await graph.save(fileWriter());
console.log(`saved ${saved.join(", ")}`);
// --8<-- [end:save]
console.log(readFileSync("main.conf", "utf8").split("\n").find((line) => line.includes("$pixels")));

render(graph).block.walk((directive) => {
  if (directive.name === "max_count") {
    console.log(`${directive.parent?.values[1]?.text} max_count ${directive.values[0]?.integer()}`);
  }
});
// --8<-- [end:main]
