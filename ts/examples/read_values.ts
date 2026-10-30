// Sample "read_values" (examples/samples.json): one typed reader per kind of value; a word stays untyped until a
// reader reads it. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/read_values.txt.
// --8<-- [start:main]
import { knobly, ValueKind, type ExpandedValue, type IndexValue, type SliceValue } from "knobly/written";
import { render } from "knobly/rendered";
import { fileSource } from "knobly/node";

const tree = render(await knobly({ source: fileSource() }).load("values.conf"));

function first(name: string): ExpandedValue {
  const value = tree.block.directives(name)[0]?.values[0];
  if (value === undefined) throw new Error(`values.conf has no ${name}`);
  return value;
}

function describe(part: SliceValue | IndexValue): string {
  return part.kind === ValueKind.Slice
    ? `slice ${part.name} ${part.start ?? ""}~${part.end ?? ""}`
    : `index ${part.name} ${part.index}`;
}

console.log(`name ${first("name").word()}`);
console.log(`host ${first("host").string()}`);
console.log(`path ${first("path").string()}`);
console.log(`fps ${first("fps").number()}`);
console.log(`count ${first("count").integer()}`);
console.log(`enabled ${first("enabled").boolean()}`);
console.log(`gains ${first("gains").list().map((item) => item.number()).join(" ")}`);
console.log(`pixels ${describe(first("pixels").slice())}`);
console.log(`first ${describe(first("first").slice())}`);
// --8<-- [end:main]
