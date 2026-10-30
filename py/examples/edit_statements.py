# Sample "edit_statements" (examples/samples.json): edit statements and values in place, see an edit refused, and
# save. The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and
# compares what it prints with examples/expected/edit_statements.txt.
# --8<-- [start:main]
import knobly as vl
from knobly import written

files = {"main.conf": "server {\n    host a;\n    # the port\n    port 80;\n}\n"}
graph = written.Processor(source=vl.memory_source(files)).load("main.conf")
server = graph.root.block.directives("server")[0]
assert server.block is not None  # server { ... } has a block
host = server.block.directives("host")[0]
port = server.block.directives("port")[0]

# --8<-- [start:edit]
host.set(vl.quote("10.0.60.31"))
port.values[0].set(vl.text("8080"))
server.block.insert_statements(1, vl.text("timeout 30s;"))
server.rename("listener")
# --8<-- [end:edit]
# --8<-- [start:refused]
try:
    host.set(vl.text("1; x"))
except vl.BadTextError as error:
    for problem in error.diagnostics:
        start = problem.span.start
        print(f"refused: {problem.code} (line {start.line + 1}, column {start.column + 1})")
# --8<-- [end:refused]

print(graph.root.text, end="")
print(f"unsaved {str(graph.root.text != graph.root.saved_text).lower()}")
saved = graph.save(vl.memory_writer(files))
print(f"saved {', '.join(saved)}")
print(f"unsaved {str(graph.root.text != graph.root.saved_text).lower()}")
# --8<-- [end:main]
