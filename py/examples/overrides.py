# Sample "overrides" (examples/samples.json): load one config twice, the second time with a variable handed in by the
# program. The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and
# compares what it prints with examples/expected/overrides.txt.
# --8<-- [start:main]
import knobly as vl
from knobly import rendered, written
from knobly.files import file_source
from knobly.include import include

config = written.Processor(source=file_source(), extensions=[include()])
for overrides in (None, {"leds_host": vl.quote("10.0.70.1")}):
    # --8<-- [start:load]
    graph = config.load("main.conf", overrides=overrides)
    # --8<-- [end:load]
    print(f"overrides: {', '.join(graph.overrides) or 'none'}")
    for directive in rendered.render(graph).block.walk(descend=lambda d: d.name == "graph"):
        match directive:
            case rendered.Directive("node", [_, node_id, *_], block) if block is not None:
                for target in block.directives("target"):
                    print(f"  {node_id.text} -> {target.values[0].string()}")
# --8<-- [end:main]
