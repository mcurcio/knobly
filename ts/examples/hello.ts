// Sample "hello" (examples/samples.json): load one file, render it, read one string. The user guide includes the
// region between the --8<-- markers; ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/hello.txt.
// --8<-- [start:main]
import { render } from "knobly/rendered";
import { fileSource } from "knobly/node";
import { knobly } from "knobly/written";

const config = knobly({ source: fileSource() });
const tree = render(await config.load("hello.conf"));
const greeting = tree.block.directives("greeting")[0]?.values[0];
console.log(greeting?.string());
// --8<-- [end:main]
