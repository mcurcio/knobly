// Sample "quickstart" (examples/samples.json): load app.conf, render it, read three typed settings. The user guide
// includes the regions between the --8<-- markers; ts/examples/examples.test.ts runs this file and compares what it
// prints with examples/expected/quickstart.txt.
// --8<-- [start:main]
import { villanelle, type ExpandedValue } from "villanelle/written";
import { render } from "villanelle/rendered";
import { fileSource } from "villanelle/node";

// --8<-- [start:load]
const config = villanelle({ source: fileSource() });
const tree = render(await config.load("app.conf"));
// --8<-- [end:load]

// --8<-- [start:read]
const server = tree.block.directives("server")[0]?.block;
const setting = (name: string): ExpandedValue | undefined => server?.directives(name)[0]?.values[0];
console.log(`host ${setting("host")?.string()}`);
console.log(`port ${setting("port")?.integer()}`);
console.log(`debug ${setting("debug")?.boolean()}`);
console.log(`problems ${tree.diagnostics.length}`);
// --8<-- [end:read]
// --8<-- [end:main]
