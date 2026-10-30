# Sample "include_read" (examples/samples.json): an edit adds an include line, and graph.read() reads the file it
# names. The user guide includes the region between the --8<-- markers; py/tests/test_examples.py runs this file and
# compares what it prints with examples/expected/include_read.txt.
# --8<-- [start:main]
import villanelle as vl
from villanelle import rendered, written
from villanelle.include import include

files = {"main.conf": "name main;\n", "extra.conf": "name extra;\n"}
graph = written.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf")
graph.root.block.add_statements(vl.text('@include "extra.conf";'))


def print_unread(tree: rendered.Rendered) -> None:
    names = ", ".join(name.values[0].text for name in tree.block.directives("name"))
    print(f"unread {len(graph.unread())}: {names}")


tree = rendered.render(graph)
print_unread(tree)
for diagnostic in tree.diagnostics:
    print(diagnostic)
graph.read()
print_unread(rendered.render(graph))
# --8<-- [end:main]
