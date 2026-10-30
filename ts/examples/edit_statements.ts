// Sample "edit_statements" (examples/samples.json): named edits on the files as written, a refused edit changing
// nothing, and a save. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/edit_statements.txt.
// --8<-- [start:main]
import { BadTextError, memorySource, memoryWriter, quote, text } from "knobly";
import { knobly } from "knobly/written";

const files = { "main.conf": "server {\n    host a;\n    # the port\n    port 80;\n}\n" };
const graph = await knobly({ source: memorySource(files) }).load("main.conf");
const server = graph.root.block.directives("server")[0];
if (server?.block === undefined) throw new Error("main.conf has no server block");
const host = server.block.directives("host")[0];

// --8<-- [start:edit]
host?.set(quote("10.0.60.31"));
server.block.directives("port")[0]?.values[0]?.set(text("8080"));
server.block.insertStatements(1, text("timeout 30s;"));
server.rename("listener");
// --8<-- [end:edit]

// --8<-- [start:refused]
try {
  host?.set(text("1; x"));
} catch (error) {
  if (!(error instanceof BadTextError)) throw error;
  for (const { code, span } of error.diagnostics) {
    console.log(`refused: ${code} (line ${span.start.line + 1}, column ${span.start.column + 1})`);
  }
}
// --8<-- [end:refused]

console.log(graph.root.text.trimEnd());
console.log(`unsaved ${graph.root.text !== graph.root.savedText}`);
const saved = await graph.save(memoryWriter(files));
console.log(`saved ${saved.join(", ")}`);
console.log(`unsaved ${graph.root.text !== graph.root.savedText}`);
// --8<-- [end:main]
