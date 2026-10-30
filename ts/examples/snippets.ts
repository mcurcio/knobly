// Sample "snippets" (examples/samples.json): a snippet used twice; each copy of its lines says where it was written
// and which use brought it. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/snippets.txt.
// --8<-- [start:main]
import { memorySource } from "villanelle";
import { villanelle } from "villanelle/written";
import { render } from "villanelle/rendered";

const main = [
  "@snippet twinkle $source {",
  "    seed 11337;",
  "    connect $source;",
  "}",
  "",
  "node TwinkleEffect twinkle { @use twinkle rgb_150; }",
  "node TwinkleEffect white_twinkle { @use twinkle white_150; }",
  "",
].join("\n");
const tree = render(await villanelle({ source: memorySource({ "main.conf": main }) }).load("main.conf"));

for (const node of tree.block.directives("node")) {
  for (const directive of node.block ?? []) {
    const values = directive.values.map((value) => value.text).join(" ");
    const { place, via } = directive.origin;
    console.log(`${node.values[1]?.text}: ${directive.name} ${values} (written at ${String(place)}, via ${via.join("; ")})`);
  }
}
// --8<-- [end:main]
