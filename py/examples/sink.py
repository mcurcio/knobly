# Sample "sink" (examples/samples.json): collect a program's own problems with villanelle's, in one list. The user
# guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it
# prints with examples/expected/sink.txt.
# --8<-- [start:main]
import villanelle as vl
from villanelle import rendered, written

files = {"main.conf": "port eighty;\nnode Mystery m;\nfps $x;\n"}
tree = rendered.render(written.Processor(source=vl.memory_source(files)).load("main.conf"))
problems = vl.Diagnostics(tree.diagnostics)

# --8<-- [start:collect]
port: int | None = None
with problems.collecting():
    port = tree.block.directives("port")[0].values[0].integer()
if port is None:
    print("port unset")
# --8<-- [end:collect]
# --8<-- [start:report]
for node in tree.block.directives("node"):
    problems.report(node, f"unknown node type {node.values[0].text}", code="app/unknown-node")
# --8<-- [end:report]
for problem in problems:
    print(problem)
# --8<-- [end:main]
