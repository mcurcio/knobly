# Sample "diagnostics" (examples/samples.json): print every problem rendering found, for people. The user guide
# includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it
# prints with examples/expected/diagnostics.txt.
# --8<-- [start:main]
from villanelle import rendered, written
from villanelle.files import file_source
from villanelle.include import include

graph = written.Processor(source=file_source(), extensions=[include()]).load("main.conf")
tree = rendered.render(graph)
# --8<-- [start:print]
for diagnostic in tree.diagnostics:
    print(written.format_diagnostic(diagnostic, graph))
# --8<-- [end:print]
# --8<-- [end:main]
