// Sample "lost_update" (examples/samples.json): a save refuses to overwrite a file someone else changed since it was
// read; loading again and redoing the edit saves. ts/examples/examples.test.ts runs this file and compares what it
// prints with examples/expected/lost_update.txt.
// --8<-- [start:main]
import { readFileSync, writeFileSync } from "node:fs";

import { LostUpdateError, quote } from "villanelle";
import { villanelle, type DocumentGraph } from "villanelle/written";
import { fileSource, fileWriter } from "villanelle/node";

const config = villanelle({ source: fileSource() });

function setHost(graph: DocumentGraph): void {
  graph.root.block.directives("server")[0]?.block?.directives("host")[0]?.set(quote("0.0.0.0"));
}

// --8<-- [start:conflict]
const graph = await config.load("app.conf");
writeFileSync("app.conf", readFileSync("app.conf", "utf8").replace("debug false", "debug true"));
setHost(graph);
try {
  await graph.save(fileWriter());
} catch (error) {
  if (!(error instanceof LostUpdateError)) throw error;
  console.log(`changed on disk: ${error.paths.join(", ")}`);
}
// --8<-- [end:conflict]

const fresh = await config.load("app.conf");
setHost(fresh);
const saved = await fresh.save(fileWriter());
console.log(`saved ${saved.join(", ")}`);
console.log(readFileSync("app.conf", "utf8").trimEnd());
// --8<-- [end:main]
