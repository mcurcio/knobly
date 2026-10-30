// Sample "custom_source" (examples/samples.json): a document source of the program's own, wrapping a memory source
// and recording each file it reads. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/custom_source.txt.
// --8<-- [start:main]
import { memorySource, type DocumentSource, type LoadContext } from "villanelle";
import { villanelle } from "villanelle/written";
import { render } from "villanelle/rendered";
import { include } from "villanelle/include";

// --8<-- [start:source]
class RecordingSource implements DocumentSource {
  readonly reads: string[] = [];
  private readonly inner: DocumentSource;

  constructor(inner: DocumentSource) {
    this.inner = inner;
  }

  resolve(spec: string, context: LoadContext): Promise<readonly string[]> {
    return this.inner.resolve(spec, context);
  }

  read(resolvedPath: string): Promise<string> {
    this.reads.push(resolvedPath);
    return this.inner.read(resolvedPath);
  }
}
// --8<-- [end:source]

const source = new RecordingSource(
  memorySource({
    "main.conf": '@include "sink.conf" { @set $name a; }\n@include "sink.conf" { @set $name b; }\n',
    "sink.conf": "sink $name;\n",
  }),
);
const tree = render(await villanelle({ source, extensions: [include()] }).load("main.conf"));
console.log(`sinks ${tree.block.directives("sink").map((sink) => sink.values[0]?.text).join(", ")}`);
console.log(`reads ${source.reads.join(", ")}`);
// --8<-- [end:main]
