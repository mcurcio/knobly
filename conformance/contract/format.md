# Contract conformance format, v0

The cases for the edge contract ([`spec/contract.md`](../../spec/contract.md)) and the readers (spec 2.9): every
reader, positions in each binding's string unit, people forms and `format diagnostic`. Added in milestone 2 (bead
vil-0vz); milestone 3 (bead vil-j80) added the readers other than the number readers and more `format` cases. The
expected results were derived by hand from the contract, not produced by an implementation; an output that disagrees
has found a bug in the binding or in the contract, never a reason to change a case.

Each case holds its expected result inline (`expect`): every case checks one value, so a separate expected file per
case would hold one short line. The shared driver ([spec/conformance.md](../../spec/conformance.md)) compares each
result with `expect` as JSON.

## Input

`conformance/contract/cases.json`: a JSON array of cases. Every case has `name` (unique) and `kind`.

### `reader`

`{"name", "kind": "reader", "value", "reader", "expect"}`

The driver loads `main.conf` holding `x <value>;\n` from a `memory source`, renders it (`render (graph)`), takes
`block[0].values[0]` and asks the adapter to call the reader named (`word`, `string`, `number`, `integer`,
`boolean`, `list`, `slice`; spec 2.9, in the binding's spelling; milestone 5 deleted `plain` and its cases). `expect`
is one of:

- `["integer", decimal]`: an `integer` result, written in decimal;
- `["number", text]`: a number (from `number`), written by the number rule below;
- `["text", text]`: text (from `string` or `word`);
- `["boolean", "true" | "false"]`;
- `["values", [text, ...]]`: the `list` reader's items, each by its canonical text;
- `["slice", name, start | null, end | null]`: a `slice value` (from `slice`);
- `["index", name, index]`: an `index value`;
- `["error", code]`: the reader raised a `diagnostic error` with that code.

**The number rule:** a whole number within plus or minus 2^53-1 that the binding holds as an integer type is written
in decimal; a double is written as ECMAScript's `Number::toString` writes it (shortest round trip, `1e+21` from
10^21 up). Negative zero has no spelling here: the contract says no reader returns it (section 3), so the driver fails a
case that gets one.

### `position`

`{"name", "kind": "position", "files", "root", "overrides"?, "target", "expect": {"span", "slice"}}`

The driver loads `root` from `files` (and `overrides`), renders, and finds the `target` (below), a `place`. Then:

- `span`: `[start line, start column, end line, end column]` of the place's span, 0-based, in **UTF-16 units**
  (the driver converts the binding's unit with the document's text, `spec/contract.md` 1);
- `slice`: the document's text cut at the place's own `start.offset` and `end.offset`, unconverted, in the
  binding's own string type (the adapter's `cut`). This is the check that the binding's unit is its language's: it
  gives the token's text only when it is.

### `print`

`{"name", "kind": "print", "files", "root", "overrides"?, "target", "expect"}`

The driver loads and renders as above, finds the `target`, and the adapter converts it to text with the language's to-text
conversion (`String(x)` in TypeScript, `str(x)` in Python): its `people form`. `expect` is the text, or an object
by unit (`"utf-16"`, `"code point"`, `"byte"`) when the column depends on it; the driver takes the binding's unit.
`{message}` stands for the diagnostic's own `message` (messages are not part of the contract, spec 2.3).

### `format`

`{"name", "kind": "format", "files", "root", "target", "graph"?, "expect"}`

The driver loads and renders, finds the `target` (a located diagnostic), and the adapter calls `format diagnostic
(diagnostic, graph)` with the loaded graph, or without one when the case has `"graph": false`. `expect` is the
result split at `"\n"`, `{message}` as above, or an object of such lists by unit when the column or the carets
depend on it.

### Targets

- `["argument", d, v, "place"]`: `rendered.block[d].values[v].origin.place`;
- `["argument", d, v, "step", i]`: `rendered.block[d].values[v].origin.via[i]`;
- `["diagnostic", i]`: `rendered.diagnostics[i]`;
- `["syntax diagnostic", path, i]`: `graph.documents[path].syntax.diagnostics[i]`.

## Output

The driver prints nothing to a file: it compares each case's result with `expect` and fails the case on a
difference, naming the case.
