# Sample "diff_reload" (examples/samples.json): reload a changed file and list what changed. The user guide includes
# the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it prints with
# examples/expected/diff_reload.txt.
# --8<-- [start:main]
import re
from pathlib import Path

from villanelle import rendered, written
from villanelle.files import file_source
from villanelle.include import include


def node_id(directive: rendered.Directive) -> str | None:
    if directive.name == "node" and len(directive.values) > 1:
        return directive.values[1].text
    return None


config = written.Processor(source=file_source(), extensions=[include()])
before = rendered.render(config.load("main.conf"))

main = Path("main.conf")
text = main.read_text(encoding="utf-8").replace("@set $pixels 2284;", "@set $pixels 2400;")
main.write_text(re.sub(r"    node Waveform hue_ramp \{.*?\n    \}\n\n", "", text, flags=re.DOTALL), encoding="utf-8")

after = rendered.render(config.load("main.conf"))
# --8<-- [start:diff]
for change in before.diff(after, key=node_id):
    print(f"{change.kind} {change.address}")
# --8<-- [end:diff]
# --8<-- [end:main]
