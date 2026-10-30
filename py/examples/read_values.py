# Sample "read_values" (examples/samples.json): read each kind of value with its typed reader. The user guide includes
# the region between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it prints with
# examples/expected/read_values.txt.
# --8<-- [start:main]
from villanelle import rendered, written
from villanelle.files import file_source

tree = rendered.render(written.Processor(source=file_source()).load("values.conf"))
first = {directive.name: directive.values[0] for directive in tree.block}

print("name", first["name"].word())
print("host", first["host"].string())
print("path", first["path"].string())
print("fps", first["fps"].number())
print("count", first["count"].integer())
print("enabled", str(first["enabled"].boolean()).lower())
print("gains", " ".join(str(item.number()) for item in first["gains"].list()))
for name in ("pixels", "first"):
    match first[name].slice():
        case written.SliceValue(sliced, start, end):
            print(f"{name} slice {sliced} {start}~{end}")
        case written.IndexValue(indexed, index):
            print(f"{name} index {indexed} {index}")
# --8<-- [end:main]
