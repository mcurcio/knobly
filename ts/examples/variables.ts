// Sample "variables" (examples/samples.json): which files were read and where each includes them; every variable,
// where it is set, where it wins and where another one wins. ts/examples/examples.test.ts runs this file and compares
// what it prints with examples/expected/variables.txt.
// --8<-- [start:main]
import { quote, type Place } from "knobly";
import { knobly, VariableKind, type ReferenceResolution } from "knobly/written";
import { include } from "knobly/include";
import { fileSource } from "knobly/node";

const config = knobly({ source: fileSource(), extensions: [include()] });
const graph = await config.load("main.conf", { overrides: { leds_host: quote("10.0.70.1") } });

const lineOf = (place: Place): string => `${place.resolvedPath}:${place.span.start.line + 1}`;
const places = (resolutions: readonly ReferenceResolution[]): string =>
  resolutions.map((resolution) => lineOf(resolution.reference.place)).join(", ");

for (const document of graph.documents.values()) {
  const includers = document.includedBy().map((edge) => lineOf(edge.copy.statement.place));
  console.log(`file ${document.resolvedPath} included at [${includers.join(", ")}]`);
}
for (const variable of graph.variables()) {
  const where = variable.kind === VariableKind.Override ? "override" : lineOf(variable.place);
  const wins = places(variable.wins());
  const shadowed = places(variable.shadowedAt());
  console.log(`$${variable.name} ${variable.kind} ${where} wins at [${wins}] shadowed at [${shadowed}]`);
}
// --8<-- [end:main]
