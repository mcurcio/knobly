# Sample "load_render" (examples/samples.json): load a file and the files it includes, then walk the rendered tree.
# The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and
# compares what it prints with examples/expected/load_render.txt.
# --8<-- [start:main]
from knobly import rendered, written
from knobly.files import file_source
from knobly.include import include

# --8<-- [start:processor]
config = written.Processor(source=file_source(), extensions=[include()])
graph = config.load("main.conf")
# --8<-- [end:processor]
for path in graph.documents:
    print(f"read {path}")

tree = rendered.render(graph)
# --8<-- [start:walk]
for directive in tree.block.walk(descend=lambda d: d.name == "graph"):
    if directive.name == "node":
        values = " ".join(value.text for value in directive.values)
        print(f"node {values} ({directive.origin.place})")
# --8<-- [end:walk]
# --8<-- [end:main]
