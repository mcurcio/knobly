// Sample "addresses" (examples/samples.json): every target's address, by position and under a key rule that names
// each node by its id. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/addresses.txt.
// --8<-- [start:main]
import { knobly } from "knobly/written";
import { render, type Address, type Directive, type KeyRule } from "knobly/rendered";
import { include } from "knobly/include";
import { fileSource } from "knobly/node";

const tree = render(await knobly({ source: fileSource(), extensions: [include()] }).load("main.conf"));

function showTargets(title: string, addresses: ReadonlyMap<Directive, Address>): void {
  console.log(title);
  tree.block.walk((directive) => {
    if (directive.name === "target") console.log(`  ${String(addresses.get(directive))} = ${directive.values[0]?.text}`);
  });
}

showTargets("by position:", tree.addresses());
// --8<-- [start:key]
const byNodeId: KeyRule = (directive) =>
  directive.name === "node" && directive.parent?.name === "graph" ? directive.values[1]?.text : undefined;
showTargets("by node id:", tree.addresses({ key: byNodeId }));
// --8<-- [end:key]
// --8<-- [end:main]
