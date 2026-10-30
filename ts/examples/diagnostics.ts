// Sample "diagnostics" (examples/samples.json): problems in the config are diagnostics, never exceptions; print each
// for people. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/diagnostics.txt.
// --8<-- [start:main]
import { formatDiagnostic, knobly } from "knobly/written";
import { render } from "knobly/rendered";
import { include } from "knobly/include";
import { fileSource } from "knobly/node";

const config = knobly({ source: fileSource(), extensions: [include()] });
const graph = await config.load("main.conf");
const tree = render(graph);
// --8<-- [start:print]
for (const diagnostic of tree.diagnostics) console.log(formatDiagnostic(diagnostic, graph));
// --8<-- [end:print]
// --8<-- [end:main]
