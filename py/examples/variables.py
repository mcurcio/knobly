# Sample "variables" (examples/samples.json): which file includes which, and where each variable wins or is shadowed.
# The user guide includes the region between the --8<-- markers; py/tests/test_examples.py runs this file and compares
# what it prints with examples/expected/variables.txt.
# --8<-- [start:main]
import villanelle as vl
from villanelle import written
from villanelle.files import file_source
from villanelle.include import include


def line(place: vl.Place) -> str:
    return f"{place.resolved_path}:{place.span.start.line + 1}"


config = written.Processor(source=file_source(), extensions=[include()])
graph = config.load("main.conf", overrides={"leds_host": vl.quote("10.0.70.1")})
for document in graph.documents.values():
    includers = ", ".join(line(edge.copy.statement.place) for edge in document.included_by())
    print(f"file {document.resolved_path} included at [{includers}]")
for variable in graph.variables():
    match variable:
        case written.OverrideVariable():
            where = "override"
        case written.SetVariable() | written.Parameter():
            where = line(variable.place)
    wins = ", ".join(line(r.reference.place) for r in variable.wins())
    shadowed = ", ".join(line(r.reference.place) for r in variable.shadowed_at())
    print(f"${variable.name} {variable.kind} {where} wins at [{wins}] shadowed at [{shadowed}]")
# --8<-- [end:main]
