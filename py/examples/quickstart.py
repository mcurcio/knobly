# Sample "quickstart" (examples/samples.json): load a file, render it, read typed values. The user guide includes the
# regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it prints with
# examples/expected/quickstart.txt.
# --8<-- [start:main]
from knobly import rendered, written
from knobly.files import file_source

# --8<-- [start:load]
config = written.Processor(source=file_source())
tree = rendered.render(config.load("app.conf"))
# --8<-- [end:load]

# --8<-- [start:read]
server = tree.block.directives("server")[0].block
assert server is not None  # server { ... } has a block
host = server.directives("host")[0].values[0].string()
port = server.directives("port")[0].values[0].integer()
debug = server.directives("debug")[0].values[0].boolean()
# --8<-- [end:read]
print(f"host {host}")
print(f"port {port}")
print(f"debug {str(debug).lower()}")
print(f"problems {len(tree.diagnostics)}")
# --8<-- [end:main]
