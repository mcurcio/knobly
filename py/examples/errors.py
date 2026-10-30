# Sample "errors" (examples/samples.json): the two errors a program catches, a file it cannot read and a value of the
# wrong kind. The user guide includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file
# and compares what it prints with examples/expected/errors.txt.
# --8<-- [start:main]
import knobly as vl
from knobly import rendered, written
from knobly.files import file_source

config = written.Processor(source=file_source())
# --8<-- [start:read_error]
try:
    config.load("missing.conf")
except vl.ReadError as error:
    print(f"cannot read: {', '.join(error.paths)}")
# --8<-- [end:read_error]

tree = rendered.render(config.load("main.conf"))
# --8<-- [start:diagnostic_error]
try:
    fps = tree.block.directives("fps")[0].values[0].number()
except vl.DiagnosticError as error:
    print(f"bad value: {error.diagnostic.code} at {error.diagnostic.place}")
else:
    print(f"fps {fps}")
# --8<-- [end:diagnostic_error]
# --8<-- [end:main]
