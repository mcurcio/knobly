# Sample "snippets" (examples/samples.json): a snippet used twice, and where each rendered directive came from. The
# user guide includes the region between the --8<-- markers; py/tests/test_examples.py runs this file and compares
# what it prints with examples/expected/snippets.txt.
# --8<-- [start:main]
import knobly as vl
from knobly import rendered, written

files = {
    "main.conf": (
        "@snippet twinkle $source {\n"
        "    seed 11337;\n"
        "    connect $source;\n"
        "}\n"
        "\n"
        "node TwinkleEffect twinkle { @use twinkle rgb_150; }\n"
        "node TwinkleEffect white_twinkle { @use twinkle white_150; }\n"
    )
}
tree = rendered.render(written.Processor(source=vl.memory_source(files)).load("main.conf"))
for node in tree.block.directives("node"):
    for directive in node.block or ():
        values = " ".join(value.text for value in directive.values)
        via = "; ".join(str(step) for step in directive.origin.via)
        print(f"{node.values[1].text}: {directive.name} {values} (written at {directive.origin.place}, via {via})")
# --8<-- [end:main]
