# Sample "hello" (examples/samples.json): load one file, render it, read one string. The user guide includes the
# region between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it prints with
# examples/expected/hello.txt.
# --8<-- [start:main]
from villanelle import rendered, written
from villanelle.files import file_source

config = written.Processor(source=file_source())
tree = rendered.render(config.load("hello.conf"))
greeting = tree.block.directives("greeting")[0].values[0]
print(greeting.string())
# --8<-- [end:main]
