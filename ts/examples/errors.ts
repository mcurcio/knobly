// Sample "errors" (examples/samples.json): what throws: a root file that cannot be read, and a reader on a value of
// the wrong kind. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/errors.txt.
// --8<-- [start:main]
import { DiagnosticError, ReadError } from "knobly";
import { knobly } from "knobly/written";
import { render } from "knobly/rendered";
import { fileSource } from "knobly/node";

const config = knobly({ source: fileSource() });

// --8<-- [start:read_error]
try {
  await config.load("missing.conf");
} catch (error) {
  if (!(error instanceof ReadError)) throw error;
  console.log(`cannot read: ${error.paths.join(", ")}`);
}
// --8<-- [end:read_error]

// --8<-- [start:diagnostic_error]
const fps = render(await config.load("main.conf")).block.directives("fps")[0]?.values[0];
try {
  fps?.number();
} catch (error) {
  if (!(error instanceof DiagnosticError)) throw error;
  console.log(`bad value: ${error.diagnostic.code} at ${String(error.diagnostic.place)}`);
}
// --8<-- [end:diagnostic_error]
// --8<-- [end:main]
