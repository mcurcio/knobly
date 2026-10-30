# Sample "edit_save" (examples/samples.json): change a variable's value and save the file back. The user guide
# includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it
# prints with examples/expected/edit_save.txt.
# --8<-- [start:main]
from pathlib import Path

import knobly as vl
from knobly import rendered, written
from knobly.files import file_source, file_writer
from knobly.include import include

graph = written.Processor(source=file_source(), extensions=[include()]).load("main.conf")
# --8<-- [start:edit]
for variable in graph.variables("pixels"):
    match variable:
        case written.SetVariable():
            variable.set(vl.text("2400"))
# --8<-- [end:edit]
# --8<-- [start:save]
saved = graph.save(file_writer())
print(f"saved {', '.join(saved)}")
# --8<-- [end:save]
print(next(line for line in Path("main.conf").read_text(encoding="utf-8").splitlines() if "$pixels" in line))

for directive in rendered.render(graph).block.walk():
    match directive:
        case rendered.Directive("node", [_, node_id, *_], block) if block is not None:
            for max_count in block.directives("max_count"):
                print(f"{node_id.text} max_count {max_count.values[0].integer()}")
# --8<-- [end:main]
