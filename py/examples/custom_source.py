# Sample "custom_source" (examples/samples.json): a document source of the program's own, here one that records what
# it reads. The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file
# and compares what it prints with examples/expected/custom_source.txt.
# --8<-- [start:main]
from collections.abc import Mapping

import knobly as vl
from knobly import rendered, written
from knobly.include import include


# --8<-- [start:source]
class RecordingSource:
    """A document source: the files of a memory source, recording each path it reads."""

    def __init__(self, files: Mapping[str, str]) -> None:
        self.inner = vl.memory_source(files)
        self.reads: list[str] = []

    def resolve(self, spec: str, context: vl.LoadContext, /) -> tuple[str, ...]:
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        return self.inner.read(resolved_path)


# --8<-- [end:source]
source = RecordingSource(
    {
        "main.conf": '@include "sink.conf" { @set $name a; }\n@include "sink.conf" { @set $name b; }\n',
        "sink.conf": "sink $name;\n",
    }
)
tree = rendered.render(written.Processor(source=source, extensions=[include()]).load("main.conf"))
print(f"sinks {', '.join(sink.values[0].text for sink in tree.block.directives('sink'))}")
print(f"reads {', '.join(source.reads)}")
# --8<-- [end:main]
