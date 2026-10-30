# Sample "addresses" (examples/samples.json): each directive's address, by position and by a key rule. The user guide
# includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it
# prints with examples/expected/addresses.txt.
# --8<-- [start:main]
from knobly import rendered, written
from knobly.files import file_source
from knobly.include import include


# --8<-- [start:key]
def node_id(directive: rendered.Directive) -> str | None:
    """rasl's key rule: a node is named by its id, so it keeps its address when it moves."""
    if directive.name == "node" and len(directive.values) > 1:
        return directive.values[1].text
    return None


# --8<-- [end:key]
graph = written.Processor(source=file_source(), extensions=[include()]).load("main.conf")
tree = rendered.render(graph)
for title, key in (("by position:", None), ("by node id:", node_id)):
    print(title)
    for directive, address in tree.addresses(key=key).items():
        if directive.name == "target":
            print(f"  {address} = {directive.values[0].text}")
# --8<-- [end:main]
