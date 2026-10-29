# Contract conformance format, v0

The cases for the edge contract ([`spec/contract.md`](../../spec/contract.md)): number readers, positions in each
binding's string unit, people forms and `format diagnostic`. Added in milestone 2 (bead vil-0vz). The expected
results were derived by hand from the contract, not produced by an implementation; a runner that disagrees has found
a bug in itself or in the contract, never a reason to change a case.

Each case holds its expected result inline (`expect`): every case checks one value, so a separate expected file per
case would hold one short line. The shared driver of milestone 3 may move them; until then each binding's runner
reads this file directly.

## Input

`conformance/contract/cases.json`: a JSON array of cases. Every case has `name` (unique) and `kind`.

### `reader`

`{"name", "kind": "reader", "value", "reader", "expect"}`

The runner loads `main.conf` holding `x <value>;\n` from a `memory source`, renders it (`render (graph)`), takes
`block[0].values[0]` and calls the reader named (`word`, `string`, `number`, `integer`, `boolean`, `list`, `slice`,
`plain`; spec 2.9, in the binding's spelling). `expect` is one of:

- `["integer", decimal]`: an `integer` result, written in decimal;
- `["number", text]`: a number (from `number`, or from `plain` reading a number), written by the number rule below;
- `["text", text]`: text (from `string`, `word`, or `plain` reading text);
- `["boolean", "true" | "false"]`;
- `["error", code]`: the reader raised a `diagnostic error` with that code.

**The number rule:** a whole number within plus or minus 2^53-1 that the binding holds as an integer type is written
in decimal; a double is written as ECMAScript's `Number::toString` writes it (shortest round trip, `1e+21` from
10^21 up). Negative zero has no spelling here: the contract says no reader returns it (section 3), so a runner that
gets one fails the case.

### `position`

`{"name", "kind": "position", "files", "root", "overrides"?, "target", "expect": {"span", "slice"}}`

The runner loads `root` from `files` (and `overrides`), renders, and finds the `target` (below), a `place`. Then:

- `span`: `[start line, start column, end line, end column]` of the place's span, 0-based, in **UTF-16 units**
  (the runner converts its binding's unit with the document's text, `spec/contract.md` 1);
- `slice`: the document's text cut at the place's own `start.offset` and `end.offset`, unconverted, in the
  binding's own string type. This is the check that the binding's unit is its language's: it gives the token's text
  only when it is.

### `print`

`{"name", "kind": "print", "files", "root", "overrides"?, "target", "expect"}`

The runner loads and renders as above, finds the `target` and converts it to text with the language's to-text
conversion (`String(x)` in TypeScript, `str(x)` in Python): its `people form`. `expect` is the text, or an object
by unit (`"utf-16"`, `"code point"`, `"byte"`) when the column depends on it; the runner takes its binding's unit.
`{message}` stands for the diagnostic's own `message` (messages are not part of the contract, spec 2.3).

### `format`

`{"name", "kind": "format", "files", "root", "target", "expect"}`

The runner loads and renders, finds the `target` (a located diagnostic) and calls `format diagnostic (diagnostic,
graph)` with the loaded graph. `expect` is the result split at `"\n"`, `{message}` as above.

### Targets

- `["argument", d, v, "place"]`: `rendered.block[d].values[v].origin.place`;
- `["argument", d, v, "step", i]`: `rendered.block[d].values[v].origin.via[i]`;
- `["diagnostic", i]`: `rendered.diagnostics[i]`;
- `["syntax diagnostic", path, i]`: `graph.documents[path].syntax.diagnostics[i]`.

## Output

A runner prints nothing and writes no file: it compares each case's result with `expect` and fails the case on a
difference, naming the case.
