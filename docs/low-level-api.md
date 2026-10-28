# The low-level API (TypeScript and Python)

This page is for a program that reads villanelle files. It covers the load layer: one call reads a root file and
everything it includes, expands variables and snippets, and gives back directives with values a program can read,
the place each one was written, an identity that survives edits, and a list of what changed between two loads.
The language itself is described in [language.md](language.md).

The two packages have the same parts under each language's own names. Each section shows TypeScript first, then
Python.

**About the examples.** Every example is copied from a test that passes, named under it. The tests import from the
package's source files (`./processor.js`, `../include.js`); the examples write the imports a program would write
(`villanelle`, `villanelle/include`, `villanelle/node`). "Excerpt" means lines were left out; nothing else was
changed.

There is a tier below this one: `parse(text)` gives the lossless syntax tree of one text, with every character in
exactly one token. A program that edits files works at that level; this page does not cover it.

## Worked example: how rasl reads its config and reloads it

rasl is the program villanelle was built for. Its config has a `graph` block of `node` directives, each named by
its second value (`node DdpSink leds { ... }`). It wants: every node, the place of every problem, and, when a file
changes while it runs, the list of what changed, with each node keeping its identity when lines move.

TypeScript:

```ts
import { fileURLToPath } from "node:url";

import { type IDirective, type ILoaded, type KeyRule, villanelle } from "villanelle";
import { include } from "villanelle/include";
import { createFileSource } from "villanelle/node";

/** The "rasl" key rule of conformance/load/format.md. */
const RASL_KEY: KeyRule = (d) => {
  if (d.name === "node" && d.parent?.name === "graph") return d.args[1]?.text;
  if (d.name === "connect") return d.args.map((a) => a.text).join(" ");
  if (d.name === "fill") return d.args[0]?.text;
  return undefined;
};

function nodeIds(loaded: ILoaded): string[] {
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.args[1]?.text ?? "");
  });
  return ids;
}

const HANDED = { leds_host: '"10.0.70.1"' };

    const processor = villanelle({ source: files, extensions: [include()], key: RASL_KEY });
    const path = fileURLToPath(new URL(name, FIXTURES));
    const options = { variables: HANDED };
    const first = await processor.load(path, options);
    expect(first.diagnostics).toEqual(expected.diagnostics);
    expect(nodeIds(first)).toEqual(expected.nodes);
    edit();
    const second = await processor.load(path, options);
    expect(processor.diff(first, second).map((c) => [c.kind, c.address.toString()])).toEqual(expected.changes);
```

Excerpt of `ts/src/load/rasl.test.ts`, test "%s loads with the expected nodes and reload changes" (run once per
fixture). `files` is the file source from `createFileSource()`, wrapped so that `edit()` makes the next read say
`set $pixels 2400;` instead of `2284`.

Python:

```python
import villanelle as vl
from villanelle.files import file_source
from villanelle.include import include


def rasl_key(d: vl.KeyInput) -> str | None:
    """The "rasl" key rule of conformance/load/format.md."""
    if d.name == "node" and d.parent is not None and d.parent.name == "graph":
        return d.args[1].text if len(d.args) > 1 else None
    if d.name == "connect":
        return " ".join(a.text for a in d.args)
    if d.name == "fill":
        return d.args[0].text if d.args else None
    return None


def node_ids(loaded: vl.Loaded) -> list[str]:
    graph = next(d for d in loaded.body if d.name == "graph")
    return [d.args[1].text for d in graph.body or () if d.name == "node"]


    processor = vl.Processor(source=file_source(), extensions=[include()], key=rasl_key)
    variables = {"leds_host": '"10.0.0.9"'} if handed else None
    first = processor.load(str(root), variables=variables)
    expected = EXPECTED[name]
    assert expected["diagnostics"] == []
    assert first.diagnostics == ()
    assert node_ids(first) == expected["nodes"]
    text = root.read_text(encoding="utf-8")
    assert text.count("set $pixels 2284;") == 1
    root.write_text(text.replace("set $pixels 2284;", "set $pixels 2400;"), encoding="utf-8")
    second = processor.load(str(root), variables=variables)
    assert [[type(c).__name__.lower(), str(c.address)] for c in processor.diff(first, second)] == expected["changes"]
```

Excerpt of `py/tests/test_rasl.py`, `test_a_rasl_fixture_loads_and_reloads_as_expected`.

For [`family_room.conf`](../fixtures/rasl/family_room.conf), the change list after the `$pixels` edit is exactly the
two directives that use `$pixels` ([`fixtures/rasl/expected.json`](../fixtures/rasl/expected.json)):

```
changed  graph > node "leds" > max_count
changed  graph > node "leds" > connect "crossfade_rgb pixels" > repeat_until
```

The rest of this page goes through each part used above.

## Making a processor and loading

A **processor** is made once, with three things: the **document source** (where files come from), the
**extensions** (such as include), and the **key rule** (how to name a directive among its siblings). Every load and
every comparison goes through it, so two loads are always read the same way.

| | TypeScript | Python |
|---|---|---|
| make | `villanelle({ source, extensions?, key? })` | `Processor(source=..., extensions=(), key=None)` |
| load | `await processor.load(path, { variables? })` | `processor.load(path, variables=None)` |
| compare | `processor.diff(before, after)` | `processor.diff(before, after)` |

`load` reads the root file at `path` through the source, then everything it splices in. Each file is read once per
load, however many places include it. A load never fails because of what a file says: every problem becomes a
diagnostic and the rest is read. It fails only when:

- the source cannot read the root file: a `DiagnosticError` with code E3004, placed at the root file at line 0,
  column 0 (test "rejects the load with a DiagnosticError E3004 at the root file when the source cannot read it",
  `ts/src/load/rules.test.ts`; `test_a_root_the_source_cannot_read_raises_e3004_at_the_root`, `py/tests/test_load.py`);
- a handed-in variable has a bad name or a text that is not one run of values (TypeError in TypeScript, ValueError in
  Python);
- the key rule throws: the load ends with what it threw (a bug in the program, not in the config).

**Handed-in variables** are texts read as values: `{ ports: '8080 443 "x" [1, 2]' }` gives `$ports` four values.
They win over every `set` of the same name.

What a load gives back (`ILoaded` / `Loaded`):

| Field | What it is |
|---|---|
| `body` | the top-level directives, expanded |
| `unreadable` | top-level statements that could not be read, in place |
| `diagnostics` | every problem: each file's syntax problems, then the load's, in order |
| `graph` | the files read, and one edge per include line (below) |
| `origin` | the root file at 0:0, where a problem of the whole file is placed |
| `walk(...)`, `error(...)` | see "Walking" and "Problems" |

## Walking the directives

A directive (`IDirective` / `Directive`) has `name`, `args` (its values), `body` (the directives of its block, or
undefined/None when written without a block), `unreadable`, `parent`, `address`, `origin` and `node` (its node in the
syntax tree). `set`, `snippet`, `use` and include lines never appear: what they produce does, in their place.

TypeScript walks with a callback. Return `"skip"` to pass over a directive's block, `"stop"` to end the walk:

```ts
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.args[1]?.text ?? "");
  });
  return ids;
```

Excerpt of `nodeIds` in `ts/src/load/rasl.test.ts`.

Python walks with a generator. `descend` returning False passes over a block; `break` ends the walk:

```python
    skipped = [d.name for d in vl.walk(loaded, descend=lambda d: d.name != "server")]
    assert skipped == ["http", "server", "server", "events"]
```

Excerpt of `test_walk_is_depth_first_in_written_order_and_descend_false_passes_over_a_block`,
`py/tests/test_load.py`.

Both walk depth-first in written order, from the load or from one directive. `closest(predicate)` gives this
directive or the nearest enclosing one that matches. Python directives and values also take part in `match`:

```python
    match graph.body[0]:
        case vl.Directive("node", [kind, node_id, *rest], body):
            assert (kind.text, node_id.text, [r.text for r in rest]) == ("DdpSink", "leds", ["1"])
```

Excerpt of `test_directive_matches_by_name_args_and_body`, `py/tests/test_load.py`.

### Unreadable statements

A statement that could not be read stays in its block's `unreadable` list, with its `kind`, its `origin` and its
syntax node. It has no name and no address: what it would have been is unknown.

| Kind | Why |
|---|---|
| `syntax` | the parser could not read it |
| `expansion` | a variable, `set`, `snippet` or `use` failed (unknown name, wrong count, loop, limits) |
| `value` | a value broke a rule checked at load (E4001, E4003) |
| `extension` | an include line (or another extension's line) failed |

```ts
    const loaded = await loadText("a {\n  b 1;\n  : x;\n  c $nope { d $nope2; }\n  e;\n}\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E2001", "main.conf:2:2"],
      ["E5001", "main.conf:3:4"],
    ]);
    const a = only(loaded.body);
    expect(a.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([
      ["syntax", "main.conf:2:2"],
      ["expansion", "main.conf:3:2"],
    ]);
    expect(addresses(loaded)).toEqual(["a", "a > b", "a > e"]);
```

`ts/src/load/rules.test.ts`, test "keeps a bad line in its place without its block expanded, siblings kept". The
`$nope2` inside the broken line's block is not reported.

## Reading values

Each value (`IArgument` / `Argument`) has a `kind` (word, string, list, slice, index), a canonical `text`, an
`origin`, and readers. A reader that meets the wrong value throws a `DiagnosticError` placed on that value.

| Reads | TypeScript | Python | Error |
|---|---|---|---|
| a bare word | `word()` | `as_word()` | E4002 |
| a word or a string, decoded | `string()` | `as_str()` | E4002 |
| a number (JSON's number syntax: `8080`, `0.5`, `-2E-2`; not `20hz`, `01`, `.5`) | `number()` | `as_number()` | E4004, E4002 |
| a whole number within ±(2^53-1) (`1.0` is not one) | `integer()` | `as_int()` | E4005, E4002 |
| `true` or `false` only (`on`, `yes` are not) | `boolean()` | `as_bool()` | E4006, E4002 |
| a list's items, each with its own origin | `items()` | `as_list()` | E4002 |
| a slice or an index | `slice()` | `as_slice()` | E4002 |
| anything, by one rule | `plain()` | `plain()` | never |

`plain()` reads a string as its text, a word as a number when it spells one, `true`/`false` as booleans, any other
word as its text, a list item by item, a slice or index as itself:

```ts
    const read = await values('"8080" 8080 true "true" on [1, "a", [false]] c[1:2] c[3] 20hz');
    expect(read.map((a) => a.plain())).toEqual([
      "8080",
      8080,
      true,
      "true",
      "on",
      [1, "a", [false]],
      { kind: "slice", name: "c", start: 1, end: 2 },
      { kind: "index", name: "c", index: 3 },
      "20hz",
    ]);
```

`ts/src/load/readers.test.ts`, test "plain: one rule for every value; quoting means text".

```python
    assert arg("hyperhdr_color[144:152]").as_slice() == vl.SliceValue("hyperhdr_color", 144, 152)
    assert arg("c[144:]").as_slice() == vl.SliceValue("c", 144, None)
    assert arg("c[:-2]").as_slice() == vl.SliceValue("c", None, -2)
    assert arg("foo[1]").as_slice() == vl.IndexValue("foo", 1)
```

Excerpt of `test_as_slice_gives_slices_with_an_absent_side_none_and_indexes`, `py/tests/test_readers.py`. In
TypeScript an absent side is left out of the object (`{ kind: "slice", name: "c", start: 144 }`).

### Canonical text

`text` is the same in both languages, and two values are the same exactly when their texts are equal:

- a word as written;
- a string in double quotes, with `\` `"` newline tab and carriage return escaped (`'single'` becomes `"single"`);
- a slice `name[start:end]` with either side empty when absent, an index `name[i]`, in decimal;
- a list `[` + its items' texts joined by `, ` + `]`, with comments, line breaks and a trailing comma dropped;
- a value from a variable has the value's text, never `$name`.

```ts
    const arg = await value("[1, # warm\n  'two',\n  [3,4,],\n]");
    expect(arg.text).toBe('[1, "two", [3, 4]]');
```

`ts/src/load/readers.test.ts`, test "drops comments, line breaks and a trailing comma from a list".

## Origins: where each value was written

Every directive, value, unreadable statement and diagnostic carries an **origin**: `written`, the place the text was
written (a file and a span, or a handed-in variable), and `via`, the steps that brought it to where it is read,
innermost first. A step is a `variable`, a `use` or an `extension` (an include line), with its name and the place of
the reference.

So a value from a variable says both where it was set and where the `$name` was used:

```python
    value = next(d for d in vl.walk(loaded) if d.name == "max_count").args[0]
    assert value.text == "2284"
    assert isinstance(value.origin.written, vl.Place)
    assert value.origin.written.span.start == vl.SourcePosition(12, 0, 12)
    [step] = value.origin.via
    assert (step.kind, step.name, step.at.span.start.line, step.at.span.start.column) == ("variable", "pixels", 2, 32)
```

Excerpt of `test_a_variable_value_has_its_set_place_and_the_variable_step`, `py/tests/test_load.py`
(`set $pixels 2284;` on line 0, `max_count $pixels;` on line 2).

A handed-in value has `written` = the handed-in variable, and its steps say how it got there. In the split rasl
fixture, the `leds` sink's `target` comes from `--set leds_host`, through `$host` in the include block, through the
include line:

```python
    leds_target = next(d for d in vl.walk(handed) if d.name == "target")
    assert leds_target.args[0].origin.written == vl.Handed("leds_host")
    assert [(s.kind, s.name) for s in leds_target.args[0].origin.via] == [
        ("variable", "leds_host"),
        ("variable", "host"),
        ("extension", "include"),
    ]
```

Excerpt of `test_the_split_fixtures_sinks_take_their_include_blocks_values_and_the_handed_host_wins`,
`py/tests/test_rasl.py`.

Lines and columns are 0-based and columns count UTF-16 code units, in both languages. `formatDiagnostic` prints them
1-based for people.

## Addresses and the key rule

An **address** is a directive's identity across loads of one processor: from the top level down, each step is the
directive's name, its key (what the key rule returned, or none), and its occurrence among earlier siblings with the
same name and key (counting from 0). It is unique within one load. A file included at two places, or a snippet used
twice, lands at two addresses.

| | TypeScript | Python |
|---|---|---|
| for people | `address.toString()`: `graph > node "leds" > max_count` | `str(address)` |
| as a map key | `address.text` (JSON, the same bytes in both languages) | `address.text`, or the `Address` itself (hashable) |
| enclosing | `address.parent` | `address.parent` |

The **key rule** is the program's: it sees each directive's name, its expanded values, whether it has a block, and
its parent's key input, parents first, and returns a key or nothing. Without a key rule, a directive is named by its
position among same-name siblings, so moving a line changes addresses. With rasl's rule, a node keeps its address
when it moves:

```ts
    const text = (first: string, second: string): string => `graph {\n  ${first}\n  ${second}\n}\n`;
    const one = "node A one { x 1; }";
    const two = "node B two { x 2; }";
    expect(await changes(text(one, two), text(two, one), RASL_KEY)).toEqual([]);
    expect(await changes(text(one, two), text(two, one))).toEqual([
      ["changed", "graph > node"],
      ["changed", "graph > node > x"],
      ["changed", "graph > node #1"],
      ["changed", "graph > node #1 > x"],
    ]);
```

`ts/src/load/diff.test.ts`, test "follows a keyed node that moved: no change". `RASL_KEY` there is
`(d) => (d.name === "node" && d.parent?.name === "graph" ? d.args[1]?.text : undefined)`.

The key rule runs only for directives that could be read. A key rule that reads values from variables makes identity
follow config edits; that is the program's choice.

## What changed: diff

`processor.diff(before, after)` compares two loads of the same processor by address. Each change carries its address
and its directives (`before`, `after`, or both):

| Change | When |
|---|---|
| added | only in `after` |
| removed | only in `before`, and its block in `after` has no unreadable statement |
| unknown | only in `before`, but its block in `after` (or the top level) holds an unreadable statement: the broken line may be it |
| changed | in both, and its own values (by canonical text) or whether it has a block differ |

An added, removed or unknown directive is listed alone, never with the directives inside it. A changed or unchanged
directive's block is compared at its own addresses. Order: removed and unknown in `before`'s walk order, then added
and changed in `after`'s. Loads with diagnostics can be compared. Loads of another processor are refused (TypeError
in TypeScript, ValueError in Python).

In TypeScript a change has `kind` (`"added"`, `"removed"`, `"changed"`, `"unknown"`). In Python each kind is its own
class (`Added`, `Removed`, `Changed`, `Unknown`); test with `isinstance` or `match`.

```python
def test_a_directive_missing_beside_an_unreadable_statement_is_unknown_not_removed() -> None:
    assert changes("g {\n  a 1;\n  b 2;\n}\nz;\n", 'g {\n  a 1;\n  b x"y";\n}\n') == [
        ("unknown", "g > b"),
        ("removed", "z"),
    ]
    assert changes("a;\nb;\n", 'a;\nb x"y";\n') == [("unknown", "b")]
```

`py/tests/test_load.py`. `changes` loads the first text, then the second, through one processor.

A comment or a quote style is no change; a number's spelling is (`0.5` to `0.50`), because values compare by text
(test "compares canonical texts: a comment or a quote style is no change, a number's spelling is",
`ts/src/load/diff.test.ts`). To group changes by its own unit (a rasl node), a program uses `directive.closest(...)` or
`address.parent`.

## Problems: diagnostics, program errors and the sink

A **located diagnostic** (`ILocatedDiagnostic` / `LocatedDiagnostic`) has a `code`, a `message` (for people; not
part of the contract between the languages), `at` (a place in a file) and `via` (the steps). A problem with a
handed-in value is placed on the `$name` that used it.

A program places its own problems on what it read. Every directive, value and the load itself has
`error(message, code)` (Python: `error(message, code=...)`), which returns a `DiagnosticError` to throw or record. A
program's code is `<namespace>/<name>`, such as `rasl/unknown-node`; both parts must be there (TypeError /
ValueError otherwise), so a program's code never looks like villanelle's.

**The sink** (`Diagnostics`) is the one place problems collect. Start it with the load's problems, report into it,
and run reads through it so a reader's error is recorded instead of ending the program:

```ts
    const loaded = await loadText("port eighty;\n");
    const sink = new Diagnostics();
    const port = only(only(loaded.body).args);
    expect(sink.collect(() => port.integer())).toBeUndefined();
    expect(sink.collect(() => port.word())).toBe("eighty");
    expect(problems(sink)).toEqual([["E4005", "main.conf:0:5"]]);
```

Excerpt of `ts/src/load/report.test.ts`, test "collect records a DiagnosticError and returns undefined; passes
anything else through". Any other exception passes through.

```python
    load = loaded("a $x;\nb 1;\n")
    problems = vl.Diagnostics(load.diagnostics)
    b = load.body[0]
    problems.report(b, "b is not wanted", code="rasl/unwanted")
    problems.add(load.error("no graph", code="rasl/no-graph").diagnostic)
    assert len(problems) == 3
    assert [str(d.code) for d in problems] == ["E5001", "rasl/unwanted", "rasl/no-graph"]
```

Excerpt of `test_report_and_add_record_in_order_after_the_initial_ones`, `py/tests/test_report.py`. Python's
`with problems.collecting():` records a `DiagnosticError` raised inside it and ends the block.

**Printing** (`formatDiagnostic(d, graph?)` / `format_diagnostic(d, graph=None)`): the place 1-based, the code and
message, the source line, a caret line under the span, and one line per step. Without the graph, only the first line.

```ts
    const files = { "main.conf": 'include "x.conf";\n', "x.conf": "a 1;\nport c[0:$n];\n" };
    const loaded = await loadFiles(files, { extensions: [include()] });
    expect(formatDiagnostic(only(loaded.diagnostics), loaded.graph)).toBe(
      ["x.conf:2:10: E5001: unknown variable: $n", "port c[0:$n];", "         ^^", "  via extension include at main.conf:1:1"].join("\n"),
    );
```

`ts/src/load/report.test.ts`, test "prints path:line:col: code: message 1-based, the source line, a caret and one via
line per step".

## Document sources: where files come from

The core does no input or output. A **document source** does it, with two methods: `resolve(spec, context)` gives the
paths a spec names (a path, or a glob with `*` and `?` in its last part; none means not found, E3001), and
`read(path)` gives a file's text. If either throws, the load reports E3004 at the include line (or, for the root
file, fails as above). In TypeScript both return promises; in Python both are plain calls.

| Source | TypeScript | Python |
|---|---|---|
| texts held in memory (tests, editors) | `memorySource({ path: text })` | `memory_source({path: text})` |
| the filesystem | `createFileSource()` from `villanelle/node` | `file_source()` from `villanelle.files` |
| `fetch` (paths are URLs) | `createFetchSource(fetch)` from `villanelle/browser` | none |

A program can write its own, for example to count reads:

```python
class _Counting:
    def __init__(self, files: Mapping[str, str], *, resolve_fails: str = "", read_fails: str = "") -> None:
        self.inner = vl.memory_source(files)
        self.reads: list[str] = []
        self.resolve_fails = resolve_fails
        self.read_fails = read_fails

    def resolve(self, spec: str, context: vl.LoadContext, /) -> Sequence[str]:
        if spec == self.resolve_fails:
            raise OSError("resolve failed")
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        if resolved_path == self.read_fails:
            raise OSError("read failed")
        return self.inner.read(resolved_path)
```

`py/tests/test_load.py`, used by `test_a_file_included_at_two_places_is_read_once_held_once_and_has_two_edges`,
which shows `p.conf` read once though two places include it.

The fetch source never fetches in `resolve`, so a missing remote file is E3004 (the read fails), not E3001, and a
glob resolves to nothing (test "resolves without fetching, resolves a glob to nothing, and rejects a non-2xx read",
`ts/src/browser.test.ts`).

## Extensions

An **extension** owns one directive name and turns each use of it into specs of files to splice in its place.
`include()` is the one villanelle ships. The extension only names files: the load resolves and reads them through the
source, reads each file once, applies the line's block of `set` lines, and checks loops and limits.

An extension has `directive` (its name) and `specs(use)`, where `use` has the line's expanded `args` and its `origin`.
To refuse a use at a place, throw a `DiagnosticError` from a value's or the use's `error(...)`; anything else thrown
becomes E3006 at the line:

```ts
    const throwing: IExtension = {
      directive: "pull",
      specs: (use) => {
        if (use.args.length === 0) throw new Error("boom");
        throw use.args[0]?.error("bad pull", "test/bad-pull") ?? new Error("no value");
      },
    };
    const loaded = await loadText("pull;\npull x;\n", { extensions: [throwing] });
    expect(problems(loaded.diagnostics)).toEqual([
      ["E3006", "main.conf:0:0"],
      ["test/bad-pull", "main.conf:1:5"],
    ]);
```

Excerpt of `ts/src/load/rules.test.ts`, test "gives E3006 when an extension throws anything but a DiagnosticError,
and records a DiagnosticError as thrown". In Python an extension is any object with a `directive` attribute and a
`specs(use)` method (`test_an_extension_that_raises_something_else_is_e3006`, `py/tests/test_load.py`).

While an extension is registered, its name is reserved at the start of a statement, as `set`, `snippet` and `use` are.

### The file graph

`loaded.graph` holds `root`, `nodes` (each file read, by path, in first-read order, with its text and syntax tree)
and `edges` (one per extension line whose specs were given: its directive name, origin, specs and the paths it
spliced, empty when resolving or reading failed). TypeScript also has `save(graph, writer)` with `createFsWriter()`
(`villanelle/node`) and `createFetchWriter(...)` (`villanelle/browser`) to write files back.

## Error codes

Lines and columns are 0-based in the API. "At" says where the diagnostic is placed. The 1xxx and 2xxx codes come from
the syntax tier, which places them as the cases in [`conformance/`](../conformance/) show; they are listed here so
the table is complete.

| Code | TypeScript name | Python name | Meaning | At |
|---|---|---|---|---|
| E1001 | `UnterminatedString` | `UNTERMINATED_STRING` | a string with no closing quote | per `conformance/` |
| E1003 | `UnexpectedCharacter` | `UNEXPECTED_CHARACTER` | a character the language does not use | per `conformance/` |
| E1004 | `LoneDollar` | `LONE_DOLLAR` | `$` not followed by a name | the `$` (case `var-lone-dollar`) |
| E2001 | `UnexpectedToken` | `UNEXPECTED_TOKEN` | a token where it cannot go | per `conformance/` |
| E2003 | `ExpectedClosingBrace` | `EXPECTED_CLOSING_BRACE` | a block with no `}` | per `conformance/` |
| E2004 | `ExpectedClosingBracket` | `EXPECTED_CLOSING_BRACKET` | an unmatched bracket | per `conformance/` |
| E2007 | `BadSlice` | `BAD_SLICE` | a malformed slice (`[:]` among them) | per `conformance/` |
| E2008 | `BraceOnOwnLine` | `BRACE_ON_OWN_LINE` | `{` not on its directive's line | per `conformance/` |
| E2009 | `ValuesTouch` | `VALUES_TOUCH` | two values with no space or comment between | per `conformance/` |
| E2010 | `NestingTooDeep` | `NESTING_TOO_DEEP` | blocks and lists nested deeper than 100 | per `conformance/` |
| E3001 | `IncludeNotFound` | `INCLUDE_NOT_FOUND` | a spec matched no file | the extension line's name |
| E3004 | `IncludeResolverFailed` | `INCLUDE_RESOLVER_FAILED` | the source threw (for the root file the load fails) | the extension line's name; the root file at 0:0 |
| E3005 | `IncludeBadPath` | `INCLUDE_BAD_PATH` | include needs exactly one quoted path | the bad value, or the name when there is none |
| E3006 | `ExtensionFailed` | `EXTENSION_FAILED` | an extension threw something other than a located error | the extension line's name |
| E4001 | `NonIntegerBound` | `NON_INTEGER_BOUND` | a slice or index bound that is not a whole number | the bound (a bound from a variable: the value, via the variable) |
| E4002 | `WrongValueKind` | `WRONG_VALUE_KIND` | a reader met the wrong kind of value | the value |
| E4003 | `BadEscape` | `BAD_ESCAPE` | a string escape other than the six (found at load) | the string |
| E4004 | `NotANumber` | `NOT_A_NUMBER` | `number()` met a word that is not a number | the value |
| E4005 | `NotAnInteger` | `NOT_AN_INTEGER` | `integer()` met a word that is not a whole number | the value |
| E4006 | `NotABoolean` | `NOT_A_BOOLEAN` | `boolean()` met a word other than `true`, `false` | the value |
| E5001 | `UnknownVariable` | `UNKNOWN_VARIABLE` | `$name` with no `set` and nothing handed in | the `$name` |
| E5002 | `VariableSetTwice` | `VARIABLE_SET_TWICE` | two `set` of one name in one block | the second `$name` |
| E5003 | `UnknownSnippet` | `UNKNOWN_SNIPPET` | `use` of a snippet not seen there | the name |
| E5004 | `SnippetArity` | `SNIPPET_ARITY` | wrong number of values for the snippet | `use` |
| E5005 | `SnippetDefinedTwice` | `SNIPPET_DEFINED_TWICE` | two snippets of one name in one block | the second name |
| E5006 | `ExpansionCycle` | `EXPANSION_CYCLE` | a snippet or file reaches itself | the `use` or extension line that closes the loop |
| E5007 | `ExpansionTooDeep` | `EXPANSION_TOO_DEEP` | more than 16 snippets or files open inside each other | the `use` or extension line |
| E5008 | `TooManyDirectives` | `TOO_MANY_DIRECTIVES` | more than 100,000 directives after expansion; expansion stops | the statement that is one too many |
| E5009 | `BadSet` | `BAD_SET` | any other form of `set` | `set` |
| E5010 | `BadSnippet` | `BAD_SNIPPET` | any other form of `snippet` | `snippet` |
| E5011 | `BadUse` | `BAD_USE` | any other form of `use` | `use` |
| E5012 | `ExtensionBlockNotSet` | `EXTENSION_BLOCK_NOT_SET` | an extension line's block holds a line other than `set` | that line |

Codes that are no longer used, and never will be again: **E2006** (the old include path error, replaced by E3005),
**E3002** and **E3003** (the old include loop and depth errors, replaced by E5006 and E5007). E6xxx is kept for the
high-level API, which is not built yet; none is defined.

## How the two languages differ

By design (each language's own way):

- TypeScript's load and document sources are async (promises); Python's are plain calls.
- Readers are `word()`, `integer()`... in TypeScript and `as_word()`, `as_int()`... in Python; `walk` is a callback in
  TypeScript and a generator in Python; change kinds are a `kind` field in TypeScript and classes in Python.
- Misuse by a program is TypeError in TypeScript and ValueError in Python.
- Python has no fetch source and no writers (`save` is TypeScript only).

Found while writing this page, and not yet settled (both are shown by tests; neither is in the shared conformance
cases, so neither language's runner catches it):

- **The kind of an E5012 unreadable statement.** TypeScript keeps it as `expansion` (test "allows only set lines in
  an extension's block (E5012 at the first other line)", `ts/src/load/rules.test.ts`); Python as `extension`
  (`test_an_extension_block_holds_only_set_lines`, `py/tests/test_load.py`). The build's decision S3-07 says
  `extension`.
- **An extension named like a reserved word.** TypeScript's `villanelle()` throws TypeError for an extension named
  `set`, `snippet` or `use`, or for two extensions with one name (test "refuses an extension named like a reserved
  word or like another extension", `ts/src/load/rules.test.ts`). Python's `Processor` has no such check; with two
  extensions of one name, the later one is used.

## What is not tested

Speed on large trees, files that are not UTF-8, and the fetch source against a real server.
