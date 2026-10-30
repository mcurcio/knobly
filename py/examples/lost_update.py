# Sample "lost_update" (examples/samples.json): saving refuses to overwrite a file changed on disk since it was read.
# The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and
# compares what it prints with examples/expected/lost_update.txt.
# --8<-- [start:main]
from pathlib import Path

import villanelle as vl
from villanelle import written
from villanelle.files import file_source, file_writer


def set_host(graph: written.DocumentGraph) -> None:
    server = graph.root.block.directives("server")[0]
    assert server.block is not None  # server { ... } has a block
    server.block.directives("host")[0].set(vl.quote("0.0.0.0"))


config = written.Processor(source=file_source())
graph = config.load("app.conf")
app = Path("app.conf")
app.write_text(app.read_text(encoding="utf-8").replace("debug false", "debug true"), encoding="utf-8")
set_host(graph)
# --8<-- [start:conflict]
try:
    graph.save(file_writer())
except vl.LostUpdateError as error:
    print(f"changed on disk: {', '.join(error.paths)}")
    graph = config.load("app.conf")
    set_host(graph)
    print(f"saved {', '.join(graph.save(file_writer()))}")
# --8<-- [end:conflict]
print(app.read_text(encoding="utf-8"), end="")
# --8<-- [end:main]
