# The low level (TypeScript and Python)

This page is for a program that works with villanelle config **as written**: which files were read, what variables
exist, which `set` line wins where, and changes to any of it written back to the files. Comments and layout are
kept: an edit changes only the text it names.

> The language-neutral rules every binding follows are in [`spec/`](../spec/README.md), which wins
> where this page differs; the words are in [`spec/glossary.md`](../spec/glossary.md).

villanelle has three layers. Each one is built on the one below, and a program can work at any of them:

| Layer | What it is | Where it is described |
|---|---|---|
| the syntax tree | `parse(text)`: one text, every character in exactly one token | [`ts/README.md`](../ts/README.md), [`py/README.md`](../py/README.md) |
| the low level | `load(path)`: the files as written, with the variables and include lines in them, editable and saved back | this page |
| the rendered tree | `render(graph)`: what the files say once variables, snippets and includes are worked out | [rendered-tree.md](rendered-tree.md) |

The language itself is described in [language.md](language.md). The two packages have the same parts under each
language's own names; each section shows TypeScript first, then Python.

**About the examples.** Every code example is copied from a test that passes, named under it. The tests import
from the package's source files (`./processor.js`, `../rendered/render.js`); the examples write the imports a
program would write (`villanelle`, `villanelle/written`, `villanelle/rendered`, `villanelle/include`; in Python
`import villanelle as vl` and `from villanelle import rendered, written`). "Excerpt" means lines were left out; nothing else was changed.
Config texts in prose come from the tests or from the shared cases in
[`conformance/written/`](../conformance/written/), which both packages must pass byte for byte.

## User code first

The example config is [`fixtures/rasl/split`](../fixtures/rasl/split/): `main.conf` sets `$pixels` and
`$leds_host`, and includes `sink.conf` twice, at lines 19 and 24, each time with its own `$name` and `$host`.
`sink.conf` is one sink:

```conf
node DdpSink $name {
    target $host;
    fps 20hz;
    input_port pixels;
    max_count $pixels;

    connect crossfade_rgb pixels;
}
```

(Excerpt of [`fixtures/rasl/split/sink.conf`](../fixtures/rasl/split/sink.conf).) The program gives its own
`leds_host` as an override, which wins over the file's default.

### Which files were read, what variables exist, where each one wins

TypeScript:

```ts
import { readFileSync } from "node:fs";

import { type DocumentWriter, type FileWrite, type Place, memorySource, quote, text } from "villanelle";
import { type Directive, type Rendered, render } from "villanelle/rendered";
import { villanelle } from "villanelle/written";
import { include } from "villanelle/include";

/** 1-based `file:line`, as design.md §1 prints it. */
const lineOf = (place: Place): string => `${place.resolvedPath}:${String(place.span.start.line + 1)}`;

  const config = villanelle({ source: memorySource(FILES), extensions: [include()] });
  const graph = await config.load("main.conf", { overrides: { leds_host: quote("10.0.70.1") } });

    expect([...graph.documents.values()].map((doc) => [doc.resolvedPath, doc.includedBy().map((e) => lineOf(e.copy.statement.place))])).toEqual([
      ["main.conf", []],
      ["sink.conf", ["main.conf:19", "main.conf:24"]],
    ]);
    const table = graph.variables().map((v) => [
      v.name,
      v.kind,
      v.kind === "override" ? "an override" : lineOf(v.place),
      v.wins().map((r) => lineOf(r.reference.place)),
      v.shadowedAt().map((r) => [lineOf(r.reference.place), r.winner?.kind]),
    ]);
    expect(table).toEqual([
      ["pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []],
      ["leds_host", "set", "main.conf:5", [], [["main.conf:21", "override"]]],
      ["name", "set", "main.conf:20", ["sink.conf:2"], []],
      ["host", "set", "main.conf:21", ["sink.conf:3"], []],
      ["name", "set", "main.conf:25", ["sink.conf:2"], []],
      ["host", "set", "main.conf:26", ["sink.conf:3"], []],
      ["leds_host", "override", "an override", ["main.conf:21"], []],
    ]);
```

Excerpt of `ts/src/written/tracer.test.ts`, test "lists files, variables and overrides, then changes $pixels itself
(2) and saves only main.conf". `FILES` holds the two fixture files.

Read the table this way: `$pixels` is set at main.conf:4 and wins at sink.conf:6 twice, once per include line
(`wins()`). The file's `$leds_host` (main.conf:5) is shadowed at main.conf:21 (`shadowedAt()`) by the override,
which wins there.

Python:

```python
    config = written.Processor(source=vl.memory_source(FILES), extensions=[include()])
    return config.load("main.conf", overrides={"leds_host": vl.quote("10.0.70.1")})

    files = [
        (doc.resolved_path, [line_of(e.copy.statement.place) for e in doc.included_by()])
        for doc in graph.documents.values()
    ]
    assert files == [("main.conf", []), ("sink.conf", ["main.conf:19", "main.conf:24"])]
    table = [
        (
            v.name,
            v.kind,
            "override" if isinstance(v, written.OverrideVariable) else line_of(v.place),
            [line_of(r.reference.place) for r in v.wins()],
            [(line_of(r.reference.place), None if r.winner is None else r.winner.kind) for r in v.shadowed_at()],
        )
        for v in graph.variables()
    ]
```

Excerpt of `open_split` and `test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf`,
`py/tests/test_tracer.py` (the table it checks is the one above, with `"override"` where TypeScript prints
`"an override"`).

### Change `$pixels` itself, or change `max_count` to no longer use it

Both kinds of change start from a rendered value. Its `chain[0]` says what the `$name` on its own line reads at
this place: `winner` is the variable (here `@set $pixels 2284;`), `reference` is the `$pixels` written on the
`max_count` line.

Change the variable itself with `set(text)` (the edit that replaces values; not the language's `@set` statement, and
it takes config text only: `quote()` a program string, `text()` one already written as villanelle text): main.conf:4 changes, so every place that reads it changes
(both sinks read 2400), and `graph.save(writer)` hands the writer only main.conf:

```ts
    const rendered = render(graph);
    const maxCount = nodeNamed(rendered, "leds").block?.find((d) => d.name === "max_count")?.values[0];
    const read = maxCount?.chain[0];
    const winner = read?.winner;
    if (winner?.kind !== "set") throw new Error("the winner is not a set line's variable");
    winner.set(text("2400"));
    const writer = recorder();
    expect(await graph.save(writer)).toEqual(["main.conf"]);
    expect(writer.batches).toHaveLength(1);
    const [written] = writer.batches[0] ?? [];
    expect(written?.text).toBe(FILES["main.conf"].replace("@set $pixels 2284;", "@set $pixels 2400;"));
    expect(maxCounts(render(graph))).toEqual([
      ["2400", "main.conf:4:13", 1],
      ["2400", "main.conf:4:13", 1],
    ]);
    // The rendered tree from before the edit is a snapshot: it still reads 2284.
    expect(maxCount?.text).toBe("2284");
```

Excerpt of the same test. `nodeNamed` walks the rendered tree for a `node` by its id; `recorder()` is the test's
writer that keeps each batch it is handed (a program passes `memoryWriter(files)` or `fileWriter()`, under
"Saving"); `maxCounts` lists each `max_count` value's text, where its `definition` is written
and how long its `chain` is.

Change the line instead: `max_count $pixels;` becomes `max_count 2400;` in sink.conf, `$pixels` wins nowhere,
and `graph.save(writer)` hands over only sink.conf:

```ts
    const read = nodeNamed(render(graph), "leds").block?.find((d) => d.name === "max_count")?.values[0]?.chain[0];
    const reference = read?.reference;
    expect(reference?.text).toBe("$pixels");
    reference?.replaceWithText(text("2400"));
    const writer = recorder();
    expect(await graph.save(writer)).toEqual(["sink.conf"]);
    expect(writer.batches[0]?.[0]?.text).toBe(FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;"));
    expect(graph.variables("pixels")[0]?.wins()).toEqual([]);
```

Excerpt of `ts/src/written/tracer.test.ts`, test "changes max_count to no longer use the variable (3): only
sink.conf, and $pixels wins nowhere".

The same in Python:

```python
    read = max_count.chain[0]
    assert isinstance(read.winner, written.SetVariable)
    read.winner.set(vl.text("2400"))  # (2)
    writer = Recorder()
    assert graph.save(writer) == ["main.conf"]
    [[written]] = writer.batches
    assert written.text == FILES["main.conf"].replace("@set $pixels 2284;", "@set $pixels 2400;")
    assert graph.save(writer) == []  # (5): saving twice writes once
```

```python
    read = next(d for d in leds.block or () if d.name == "max_count").values[0].chain[0]
    assert read.reference.text == "$pixels"
    read.reference.replace_with_text(vl.text("2400"))  # (3)
```

Excerpts of `test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf` and
`test_changes_max_count_to_no_longer_use_the_variable_only_sink_conf_and_pixels_wins_nothing`,
`py/tests/test_tracer.py`. `Recorder` is the test's writer that keeps each batch, as `recorder()` above.

An edit lands on the written line, so every place that reads that line sees it. sink.conf is read at two places:
replacing `$pixels` there changes the `porch` sink as well as `leds` (a rendered value's `written` is that one
shared line, not a per-copy line). `statement.copies()` says how many places read
a line before a program edits it. For a value that came through a snippet parameter, the variable is the
parameter, and its value is on the `use` line: `read.values[0].replaceWithText(...)` edits that.

### Edit a directive inside the included file, and undo

```python
    node = node_named(rendered.render(graph), "porch").written  # (4): `node DdpSink $name {` in sink.conf
    assert node is node_named(rendered.render(graph), "leds").written
    assert len(node.copies()) == 2
    doc = node.document
    kept = doc.text
    block = node.block
    assert block is not None
    [fps] = block.directives("fps")
    fps.set(vl.text("30hz"))
    block.insert_statements(list(block).index(fps) + 1, vl.text("brightness 0.8;"))
    assert "    fps 30hz;\n    brightness 0.8;\n    input_port pixels;" in doc.text
```

```python
    doc.replace_with_text(vl.text(kept))  # undo: `saved_text` is untouched; every handle into it detaches
    assert doc.text == doc.saved_text
    with pytest.raises(vl.DetachedError):
        _ = node.text
    assert graph.save(Recorder()) == []
```

Excerpts of `test_edits_a_directive_inside_the_included_file_and_undoes_it`, `py/tests/test_tracer.py`.

The rest of this page goes through each part used above.

## Loading: the document graph

`await processor.load(path, { overrides })` (Python: `processor.load(path, overrides=...)`) reads the root file and
every file its include lines name, once each, and gives back the **document graph**. Loading is the processor's
only operation; everything after it is a method on the graph (`read()`, `save(writer)`) or, for the rendered tree,
the rendered layer's `render(graph)`. Each override goes through the check of an override (see "Overrides"), so
`load` raises `BadTextError` for override text that check refuses. Making a processor, document
sources, extensions, and the one way `load` fails (`ReadError`, E3004 at the root path) are the same as for the
rendered tree: see [rendered-tree.md](rendered-tree.md#making-a-processor-loading-and-rendering).

<!-- generated: members: graph members (tools/gen-api.py docs) -->
| Member | TypeScript | Python | C++ | What it is |
|---|---|---|---|---|
| the root file | `root` | `root` | `root()` | the file `load` was given |
| every file read | `documents` | `documents` | `documents()` | by path: the root, then in first-read order; never shrinks |
| overrides | `overrides` | `overrides` | `overrides()` | by name, each as config text; never saved |
| change an override | `setOverride(name, text)` | `set_override(name, text)` | `set_override(name, text)` | see "Overrides" |
| every place an include line is read | `edges()` | `edges()` | `edges()` | the line, the specs it gave, the files it matched |
| what is not read yet | `unread()` | `unread()` | `unread()` | the edges naming a file not read yet (see "Reading files an edit added") |
| variables | `variables(name?)` | `variables(name=None)` | `variables([name])` | every `set` line's and snippet parameter's `$name`, then the overrides |
| problems | `diagnostics` | `diagnostics` | `diagnostics()` | a property: each file's syntax problems, then the include, `set` and `snippet` problems found |
| read what is unread | `read()` | `read()` | `read()` | see "Reading files an edit added" |
| write the changes back | `save(writer)` | `save(writer)` | `save(writer)` | see "Saving" |
<!-- end generated -->

`graph.diagnostics` leaves out the problems only rendering finds (bad values E4xxx, an unknown variable E5001, an
unknown snippet E5003, a wrong count E5004, too many directives E5008); `render(graph).diagnostics` has every one.

## Documents

A **document** is one file as written:

<!-- generated: members: document members (tools/gen-api.py docs) -->
| Member | TypeScript | Python | C++ |
|---|---|---|---|
| its path | `resolvedPath` | `resolved_path` | `resolved_path()` |
| the text as read, or as last saved | `savedText` | `saved_text` | `saved_text()` |
| the text now | `text` | `text` | `text()` |
| its syntax tree | `syntax` | `syntax` | `syntax()` |
| its top-level statements | `block` | `block` | `block()` |
| the include copies that splice it in | `includedBy()` | `included_by()` | `included_by()` |
| replace the whole text | `replaceWithText(text)` | `replace_with_text(text)` | `replace_with_text(text)` |
<!-- end generated -->

`text` differs from `savedText` exactly when the document has unsaved changes. `replaceWithText` takes any text,
broken or not (an undo, a formatter's output), leaves `savedText` alone, and detaches every handle into the document
(see "Handles").

## Statements

A document's `block`, and every statement's block, holds **statements**, in order. Each statement has a `kind`:

| Kind | What it is | Its own members |
|---|---|---|
| `directive` | a directive | `name`, `values`, `block`, `rename(name)`, `set(text)` |
| `extension` | a line a registered extension owns, written `@` and its name: `@include "f.conf";` | `name` (`include`, without `@`), `values`, `block`, `set(text)`, but no `rename` (the extension owns the name); its `values` are the path, its `block` its `@set` lines |
| `set` | `@set $name value...;` | `variable`, `values`, `set(text)` |
| `snippet` | `@snippet name $param... { ... }` | `name`, `parameters`, `block` |
| `use` | `@use name value...;` | `snippetName`, `snippet`, `snippets()`, `values`, `set(text)` |
| `unreadable` | a line that does not parse, a malformed `@set`, `@snippet` or `@use`, a second `@set` (or `@snippet`) of one name in one block, or an `@name` no extension owns (E3008) | none |

The first token decides the kind: a statement whose name starts with `@` is one of the last five, and any other is a
directive, whatever its name (`use epoll;` is a directive named `use`).

Every statement has `document`, `parent` (the statement whose block holds it), `place`, `text`, `copies()`,
`replaceWithText(text)` and `remove()`. A block is itself the sequence of its statements, in both languages (one
block shape in every layer, spec 2.11): `for (const s of block)` / `for s in block`, `block.length` / `len(block)`,
`block.at(i)` / `block[i]`, then `directives(name?)`, `walk(...)` (every statement at any depth),
`insertStatements(index, text)` and `addStatements(text)`. In Python the names are `snake_case`, and each kind is its
own class, so `match` narrows it:

```python
def describe(statement: written.Statement) -> str:
    match statement:
        case written.WrittenDirective(name, values, block):
            return f"directive {name} {len(values)} {block is not None}"
        case written.ExtensionLine(name, values, _):
            return f"extension {name} {values[0].text}"
        case written.SetLine(variable, values):
            return f"set ${variable.name} {len(values)}"
        case written.SnippetLine(name, parameters, block):
            return f"snippet {name} {len(parameters)} {len(block)}"
        case written.UseLine(snippet_name, values):
            return f"use {snippet_name} {len(values)}"
        case written.UnreadableLine(text):
            return f"unreadable {text}"
        case _:
            assert_never(statement)
```

`py/tests/test_written.py`, used by `test_match_narrows_every_kind_and_a_block_is_a_sequence_of_the_same_handles`.
In TypeScript, `kind` is the tag of a union type, so a `switch` on it narrows the same way.

## Values

A statement's `values` are **written values**, each with a `kind`:

| Kind | Written | Its own members |
|---|---|---|
| `word` | `20hz` | none |
| `string` | `"10.0.60.31"` | none |
| `list` | `[1, 2]` | `items` |
| `slice` | `c[1~2]`, `$src[0~3]` | `name` (the slice name: a word or a reference), `start`, `end` (a word or a reference; absent when not written) |
| `index` | `c[0]` | `name` (a word or a reference), `index` |
| `reference` | `$pixels` | `name`, `declaration`, `resolutions()` |

Every value has `text` (exactly as written), `place`, `statement`, `list` (the list it is an item of, if any),
`set(text)`, `replaceWithText(text)` and `remove()`. `set(text)` replaces it with exactly one value and keeps the
handle: the same object stays in its statement, now with the new text, and takes the new value's kind (`80` set to
`[1, 2]` is a list afterwards; in Python its class changes too). `replaceWithText(text)` may write several values,
and detaches the handle.

```python
def value_kind(value: written.WrittenValue) -> str:
    match value:
        case written.Word(text) | written.String(text):
            return f"{value.kind} {text}"
        case written.List(items):
            return f"list of {len(items)}"
        case written.Slice(name, start, end):
            return f"slice {name.text} {start is not None} {end is not None}"
        case written.Index(name, index):
            return f"index {name.text}[{index.text}]"
        case written.Reference(name):
            return f"reference {name}"
        case _:
            assert_never(value)
```

`py/tests/test_written.py`, used by the same test, which reads `x w "s" [1, 2] c[1~2] c[0] $a;` as word w, string
"s", list of 2, slice c, index c[0], reference a. The written value classes come from `villanelle.written` only
(`from villanelle import written`), so `from villanelle import *` never replaces `typing.List`.

## Copies: every place a line is read

A line can be read at several places: a file included twice, a snippet used twice. Each place is a **copy**:
`copy.statement` is the line, `copy.via` the include and `use` steps that bring it there, innermost first (empty at
the root). `statement.copies()` lists every copy in the order rendering meets them; it is empty for a line nothing
reaches (a snippet never used, a file no include reaches any more).

`graph.edges()` lists every copy of every include line, with the `specs` the extension gave there and the
`targets` it matched (several for a glob; empty when it failed or is not read yet). `document.includedBy()` is the
edges that splice that document in.

## Variables and what each `$name` reads

A **variable** is a `set` line's `$name`, a snippet's parameter, or an override the program gives. Its `kind` is
`set`, `parameter` or `override`, and each kind is its own type (TypeScript: `SetVariable`, `Parameter`,
`OverrideVariable`, the union `Variable`; Python: `SetVariable`, `Parameter`, `OverrideVariable`), with only the
members that can succeed on it. Narrow by `kind` (TypeScript) or with `match` / `isinstance` (Python) before using
them:

<!-- generated: members: variable members (tools/gen-api.py docs) -->
| Member | TypeScript | Python | C++ | On | What it is |
|---|---|---|---|---|---|
|  | `kind`, `name` | `kind`, `name` | `kind()`, `name()` | every kind | the name without `$` |
| where its `$name` is written | `place` | `place` | `place()` | `set`, `parameter` | an override has none |
| its line | `line` | `line` | `line()` | `set`, `parameter` | the `set` or `snippet` line |
| the `$name`s declared by it | `references()` | `references()` | `references()` | every kind | lexical only: the `$name`s in its own file whose `declaration` it is, reached or not; empty for an override. A use in an included file has no declaration, so it is only in `wins()` and `shadowedAt()` |
| where it wins | `wins()` | `wins()` | `wins()` | every kind | one resolution per place it wins: every use, per copy |
| where another one wins | `shadowedAt()` | `shadowed_at()` | `shadowed_at()` | every kind | one resolution per place it is shadowed |
| rename its `$name` | `rename(name)` | `rename(name)` | `rename(name)` | `set`, `parameter` | only the `$name` on its line; the references are not changed |
| change its value | `set(text)` | `set(text)` | `set(text)` | `set` | its `set` line's values. A parameter's value is on the `use` line; an override's changes with `setOverride` |
<!-- end generated -->

A **reference** is one `$name` written as a value. It has two answers to "which variable is this?":

- `declaration`, by where it is written, in its own file only: nearest first, block by block outward, the `set` of
  that name above it in that block, then the parameter of that name when the block is a snippet's body. So a `set`
  in a block inside a snippet's body wins over the snippet's parameter, as it does at every copy. Undefined (None)
  when there is none: a `$name` in an included file that the including line's block sets is free in its own file.
- `resolutions()`, one per copy of its line: at that copy, the `winner` (the variable it reads there, or undefined
  when nothing of that name is visible, which rendering reports as E5001), `shadowed` (every other variable of
  that name visible there, the next one to win first), and `values` (the winner's values: its `set` line's, or for
  a parameter the `use` line's values bound to it; empty for an override or when nothing wins).

The winner is the language's rule, unchanged ([language.md](language.md)): the nearest `set` or parameter; a `set`
in an include line's block wins over every `set` inside the files it splices in; an override wins over every
`set`, never over a parameter. In the shared case `shadowed-next-first`, `main.conf` is

```conf
@include "f.conf" {
    @set $a 2;
}
```

`f.conf` is `@set $a 1;` then `x $a;`, and `a` is an override: the `$a` on `x` reads the override, and its
`shadowed` lists main.conf's `@set $a 2;` first, then f.conf's `@set $a 1;`.

A `use` line has the same pair for its snippet: `snippet` by where it is written, `snippets()` per copy.

## Overrides

An **override** is a value the program gives a variable without editing a file. `graph.overrides` holds them, by
name, as config text. `setOverride(name, text)` (Python: `set_override`) adds or changes one, and
`setOverride(name, undefined)` (Python: `None`) removes it, without a reload. An override has one variable object
per name for the graph's life, so a program can hold on to it:

```ts
    const { source, reads } = countingSource({ "main.conf": "@set $a 0;\nx $a;\n" });
    const processor = villanelle({ source });
    const graph = await processor.load("main.conf", { overrides: { a: text("1") } });
    const override = graph.variables("a").find((v) => v.kind === "override");
    graph.setOverride("a", text("2 3"));
    expect(render(graph).block[0]?.values.map((v) => v.text)).toEqual(["2", "3"]);
    graph.setOverride("a", undefined);
    expect([...graph.overrides.keys()]).toEqual([]);
    expect(graph.variables("a").map((v) => v.kind)).toEqual(["set"]);
    expect(render(graph).block[0]?.values.map((v) => v.text)).toEqual(["0"]);
    graph.setOverride("b", text("9"));
    graph.setOverride("a", text("4"));
    expect([...graph.overrides.keys()]).toEqual(["b", "a"]);
    expect(graph.variables("a").find((v) => v.kind === "override")).toBe(override);
    expect(override?.wins()).toHaveLength(1);
    expect(reads.get("main.conf")).toBe(1);
```

`ts/src/written/edits.test.ts`, test "changes resolutions and render without a reload, one variable per name for
the graph's life (B5, D28)". `countingSource` is a memory source that counts each file's reads.

`load` and `setOverride` run the same check of an override (spec 6.3), so they refuse the same texts with the same
errors. The text is parsed with the grammar's `valuesText` rule: one or more values without a `$name`, over any
number of lines (`"1\n2"` is two values), not ending in a comment (`"1 # note"` is refused at its end). Anything else
is a `BadTextError` located in the text, and nothing changes; a text that is not a string is a `TypeError`, and a
name that is not letters, digits and `_` is a misuse error (`MisuseError` in TypeScript, `ValueError` in Python),
the same as for a variable's `rename` (milestone 4):

```ts
    expect(refused("1;")).toEqual([["E2001", 0, 1]]);
    expect(refused("1 $b")).toEqual([["E2001", 0, 2]]);
    expect(refused('"\\q"')).toEqual([["E1005", 0, 0]]);
    expect(refused("")).toEqual([["E2001", 0, 0]]);
    expect(() => graph.setOverride("a-b", text("1"))).toThrow(MisuseError);
    expect(graph.overrides.get("a")).toBe("1");
```

Excerpt of `ts/src/written/edits.test.ts`, test "refuses a text that is not values without a $name, and a bad name,
changing nothing". `refused` calls `setOverride("a", text)` and gives each diagnostic's code, line and column.

## Edits and their errors

New values and statements are written as **config text**, a type of its own (`ConfigText`: a branded string in
TypeScript, a `NewType` in Python), made only by `quote(text)` and `text(raw)` (below). So `statement.set("8080")`
is a type error the checker reports; write `statement.set(text("8080"))`. At run time every edit below raises the
language's own `TypeError` for anything that is not a string (a number, `null` / `None`, an array), naming the
member and the parameter, before it changes anything. To write a number, convert it first (`text(String(n))`,
Python `vl.text(str(n))`).

| Edit | On | Takes |
|---|---|---|
| `set(text)` | a directive, an include line, a `set` line, a `use` line, a `set` variable | values |
| `set(text)` | a value | exactly one value; keeps the handle |
| `replaceWithText(text)` | a value | values (in a list: items) |
| `remove()` | a value | nothing |
| `replaceWithText(text)` | a statement | zero or more statements |
| `remove()` | a statement | nothing |
| `insertStatements(index, text)`, `addStatements(text)` | a block (a document's or a statement's) | zero or more statements |
| `rename(name)` | a directive; a variable (its `$name` only) | one name |
| `replaceWithText(text)` | a document | any text |
| `setOverride(name, text)` | the graph | values without a `$name` |

Every edit except a document's `replaceWithText` checks its text first, and **a refused edit changes nothing**:

- A values text is parsed with the grammar's entry rule for it (spec 2.8): `valuesText` for a line's values,
  `itemsText` for a list item (items separated by `,`), `valueText` for a value's `set` (exactly one value),
  `boundText` for a slice bound (one whole number or `$name`), `sliceNameText` for a slice's name. A statement's
  `set` given a text with no value must be given `""` (which clears the values): `set(text("# note\n"))` is E2001 at
  0:0. Its first syntax error is the diagnostic; a `;` or a block in it is E2001 at that token. A line break is
  whitespace, so a values text may span lines. A comment the text ends in is E2001 at the text's end
  (`set("1 # note")` would write `port 1 # note;`, and the comment would swallow the `;`).
- A name (`rename`, `setOverride`) that is not well formed is a misuse error, not a `BadTextError`: a directive name
  must be one word that starts with a letter or `_ . / * ?` (never a digit, `-` or `@`); any such word is allowed,
  `use` and `include` among them; a variable name is letters, digits and `_`.
- A statements text is read as a file; its syntax errors keep their codes. An empty text is zero statements.
- Then the rules a file alone must keep are checked on the block the edit would make: a second `set` of a name in
  one block (E5002), a second snippet of a name (E5005), a malformed `@set`, `@snippet` or `@use` (E5009 to E5011).
  A `set` line left with no value, by `remove()` or `set(text(""))`, is E5009.
- `rename` takes one word; an include line has no `rename`. A variable's new name must be letters, digits and `_`,
  and must not make a second `set` of that name in its block (E5002).
- An edit that adds an include line is allowed; its file is not read until `graph.read()` (below).

A refused text throws **`BadTextError`**. Its `diagnostics` are placed in the text the edit was given (0-based line
and column, as `parse` places them), with the same codes a load gives:

```ts
    const graph = await load({ "main.conf": "@set $a 1;\n" });
    const [set] = graph.root.block;
    if (set?.kind !== "set") throw new Error("not a set line");
    for (const given of ["1; x", "{", "", "\"open"]) {
      expect(() => set.set(text(given)), given).toThrow(BadTextError);
      expect(graph.root.text).toBe("@set $a 1;\n");
    }
    expect(set.text).toBe("@set $a 1;");
```

`ts/src/written/written.test.ts`, test "changes nothing when an edit's text is refused".

<!-- generated: members: errors (tools/gen-api.py docs) -->
| Error | TypeScript | Python | C++ | When |
|---|---|---|---|---|
| the text is not what the edit takes | `BadTextError` (`diagnostics`) | `BadTextError` (`diagnostics`) | `bad_text_error` (`diagnostics()`) | above |
| a file changed since it was read (`paths`: the conflicting files) | `LostUpdateError` (`paths`) | `LostUpdateError` (`paths`) | `lost_update_error` (`paths()`) | see "Saving" |
| the writer failed | `SaveError` (`paths`, `cause`) | `SaveError` (`paths`, `__cause__`) | `save_error` (`paths()`, `std::nested_exception (std::rethrow_if_nested)`) | see "Saving" |
| the root file cannot be read | `ReadError` (`paths`, `cause`) | `ReadError` (`paths`, `__cause__`) | `read_error` (`paths()`, `std::nested_exception (std::rethrow_if_nested)`) | `load` |
| the handle's tokens are gone (a bug) | `DetachedError` | `DetachedError` | `detached_error` | see "Handles" |
| villanelle text was not given (a bug) | `TypeError` | `TypeError` | `argument_type_error` | a number, `null` / `None` or anything else where text is taken |
| a bad name (a bug) | `MisuseError` | `ValueError` | `misuse_error` | `rename`, `setOverride`, an override `load` takes |
| an index outside the block (a bug) | `RangeError` | `IndexError` | `index_out_of_range` | `insertStatements` |
<!-- end generated -->

Expected outcomes (the first four rows) extend `VillanelleError`; `LostUpdateError` is a `SaveError`. The program
bugs do not: `catch (e) { if (e instanceof VillanelleError) ... }` never hides a bug. `DetachedError` is a
`ReferenceError` in both languages. There is no `EditError` (milestone 4) and no error for a `set` on a parameter
or an override: those kinds have no `set` member.

### Where new text goes

villanelle keeps the file's own layout; there is no formatter.

- `set` replaces the values from the first to the last, comments between them included. On a line with no
  values it puts one space, then the text, after the name (on a `set` line, after its `$name`). An empty text
  removes the values and the space before them.
- A value's `remove()` deletes it and the space before it; in a list, the item and its comma (the one after it, else
  the one before it). Comments and line breaks between the item and that comma stay; a line left empty goes.
- Inserted statements take the indentation of the block's statements. In an empty block they take the parent
  line's indentation plus the file's indentation step (the leading spaces of its first indented line, else four
  spaces). Inner lines keep their own indentation relative to the first. Line breaks are the file's own (`\r\n` or
  `\n`). An empty block (`{}`, or only spaces and line breaks between the braces) is opened over lines; in a block
  holding only comments, the statements go just before its `}` line.
- Statements inserted before a statement go before the comments it owns.

```ts
    const graph = await villanelle({ source: memorySource({ "main.conf": "b {\n    a 1;\n    # about c\n    c 3;\n}\n" }) }).load("main.conf");
    const [b] = [...graph.root.block] as [WrittenDirective];
    const block = b.block;
    if (block === undefined) throw new Error("no block");
    const [a, c] = block;
    const made = block.insertStatements(1, text("x 1;\ny 2;"));
    expect(made.map((s) => s.text)).toEqual(["x 1;", "y 2;"]);
    expect(graph.root.text).toBe("b {\n    a 1;\n    x 1;\n    y 2;\n    # about c\n    c 3;\n}\n");
    expect([...block]).toEqual([a, ...made, c]);
    expect(c?.text).toBe("# about c\n    c 3;");
    expect(() => block.insertStatements(9, text("z;"))).toThrow(RangeError);
    expect(() => block.insertStatements(0, text("z {"))).toThrow(BadTextError);
    expect(block.insertStatements(0, text("  "))).toEqual([]);
```

`ts/src/written/edits.test.ts`, test "inserts before a statement and its comments, at an index, keeping other
handles".

### Renaming

`rename` on a directive changes its name and keeps the handle and its values. `rename` on a variable changes only
the `$name` on its `set` or `snippet` line; the `$name`s that read it are left as written, so a program that wants
them renamed too edits each of `variable.references()`:

```ts
    const graph = await villanelle({ source: memorySource({ "main.conf": "@set $a 1;\n@snippet s $p { x $p; }\ny $a;\n" }) }).load("main.conf");
    const [set, snippet] = [...graph.root.block];
    if (set?.kind !== StatementKind.Set || snippet?.kind !== StatementKind.Snippet) throw new Error("unexpected body");
    const variable = set.variable;
    const [parameter] = snippet.parameters;
    variable.rename("b");
    parameter?.rename("q");
    expect(graph.root.text).toBe("@set $b 1;\n@snippet s $q { x $p; }\ny $a;\n");
    expect(set.variable).toBe(variable);
    expect(snippet.parameters[0]).toBe(parameter);
```

Excerpt of `ts/src/written/edits.test.ts`, test "renames a set line's and a parameter's $name only, keeping the
variable".

## Handles

Every statement, value and variable is a **handle**: one object per written thing for the graph's life, so `===`
(Python `is`) holds across edits. A handle follows its tokens: an edit elsewhere in the file leaves it pointing at
the same text, at its new place.

```ts
    const graph = await load({ "main.conf": "@set $a 1;\nb 2 3;\nc { d 4; }\n" });
    const body = graph.root.block;
    const [set, b, c] = [...body];
    if (set?.kind !== StatementKind.Set || b?.kind !== StatementKind.Directive || c?.kind !== StatementKind.Directive) throw new Error("unexpected body");
    const [two, three] = b.values;
    const d = c.block?.at(0);
    set.set(text("100 200"));
    expect(graph.root.text).toBe("@set $a 100 200;\nb 2 3;\nc { d 4; }\n");
    expect(body.at(0)).toBe(set);
    expect(body.at(1)).toBe(b);
    expect(b.values[0]).toBe(two);
    expect(b.values[1]).toBe(three);
    expect(c.block?.at(0)).toBe(d);
```

Excerpt of `ts/src/written/written.test.ts`, test "keeps one handle per statement and value across an edit
elsewhere in the file (===)".

A handle whose tokens an edit removed is **detached**: every member but `kind` throws `DetachedError`, so a program
never reads stale text by mistake.

- `set` and `rename` keep the handle they are called on (only its values or its name change).
- `replaceWithText` and `remove()` detach the handle they are called on, and any handle inside what they replaced.
  `replaceWithText` returns the new handles.
- A document's `replaceWithText` detaches every handle into that document; the document's own handle stays.

```ts
    const graph = await load({ "main.conf": "x 1;\n" });
    const [value] = graph.root.block.directives()[0]?.values ?? [];
    if (value === undefined) throw new Error("no value");
    const [made] = value.replaceWithText(text("2"));
    expect(made?.text).toBe("2");
    expect(value.kind).toBe("word");
    expect(() => value.text).toThrow(DetachedError);
    expect(() => value.replaceWithText(text("3"))).toThrow(DetachedError);
```

Excerpt of `ts/src/written/written.test.ts`, test "detaches a replaced value: every member but kind throws
DetachedError".

## The comments a statement owns

A statement owns the comment lines directly above it (with no blank line between) when it starts its line, and a
comment after its last token on the same line. Its `text` and `place` run from the first comment it owns to the
last; `text` leaves out the indentation before it and the line break after it. `remove()` and `replaceWithText`
take the comments with it, and a line left empty goes too:

```ts
    const graph = await load({ "main.conf": "# far\n\n# near\n  b 2; # end\nc;\n" });
    const [b] = graph.root.block;
    expect(b?.text).toBe("# near\n  b 2; # end");
    expect(b?.place.span.start).toMatchObject({ line: 2, column: 0 });
    b?.remove();
    expect(graph.root.text).toBe("# far\n\nc;\n");
```

`ts/src/written/written.test.ts`, test "owns the comment lines directly above a statement and its trailing comment".
For `a; b; # c` the trailing comment is `b`'s.

## Reading files an edit added

An edit can add an include line, or change one to name another file. Until that file is read, the graph lists the
include copy in `graph.unread()`, and `render` shows it as an unreadable statement with reason `unread` at the
include line, with E3007 in `diagnostics` (so a change list calls what it held `unknown`, not removed; written case
`render-unread-include`). `await graph.read()` (Python:
`graph.read()`) reads what is missing, repeating until nothing new is named, and returns the paths it read.
Every unsaved text stays, and no file is read twice:

```ts
    const { source, reads } = countingSource({ "main.conf": MAIN, "part.conf": "p 1;\n", "other.conf": "o 1;\n" });
    const processor = villanelle({ source, extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [a] = [...graph.root.block] as [WrittenDirective];
    a.set(text("2"));
    const [line] = graph.root.block.addStatements(text('@include "part.conf";'));
    expect(line?.kind).toBe("extension");
    expect(graph.unread()).toHaveLength(1);
    expect(render(graph).block.map((d) => d.name)).toEqual(["a"]);
    expect(render(graph).unreadable.map((u) => u.reason)).toEqual(["unread"]);
    expect(reads.get("part.conf")).toBeUndefined();

    expect(await graph.read()).toEqual(["part.conf"]);
    expect(graph.unread()).toEqual([]);
    expect(graph.root.text).toBe('a 2;\n@include "part.conf";\n');
```

Excerpt of `ts/src/written/edits.test.ts`, test "reads an include line an edit added once, keeps every unsaved
text, and render then splices it (B3)". `MAIN` is `a;`.

A file that could not be found or read stays that way for the graph: `read` does not try it again (test "keeps a
rejection: a missing file is not resolved again", same file). Load again for a fresh look.

## Saving

`graph.save(writer)` hands every document whose `text` differs from its `savedText` to the writer, in one batch,
and returns their paths. With nothing changed it does not call the writer and returns an empty list, so saving
twice writes once. When the writer succeeds, each written document's `savedText` becomes the text handed over; an
edit made while the writer ran stays unsaved.

```ts
    const graph = await load({ "main.conf": '@include "p.conf";\nx 1;\n', "p.conf": "y 2;\n" });
    const writer = recorder();
    expect(await graph.save(writer)).toEqual([]);
    expect(writer.batches).toEqual([]);
    const p = graph.documents.get("p.conf");
    p?.block.directives()[0]?.values[0]?.replaceWithText(text("3"));
    expect(await graph.save(writer)).toEqual(["p.conf"]);
    expect(writer.batches).toEqual([[{ resolvedPath: "p.conf", text: "y 3;\n", savedText: "y 2;\n" }]]);
    expect(p?.savedText).toBe("y 3;\n");
    expect(await graph.save(writer)).toEqual([]);
    expect(writer.batches).toHaveLength(1);
```

`ts/src/written/written.test.ts`, test "hands only changed files to the writer in one call, then updates source;
nothing changed: no call". `recorder()` is the test's writer that keeps each batch.

The core does no input or output: the **writer** is the program's. It has one method, `write(files)` (a promise in
TypeScript, a plain call in Python and C++), given the batch. Each file in it has `resolvedPath`, `text` (what to write)
and `savedText` (what was read or last saved, to compare with the disk). If the writer fails, `save` throws
`SaveError` with the `paths` and the writer's error as its cause, and no `savedText` changes. The writer and the
file write are I/O ports, beside the document source (`villanelle` exports them in every binding).

<!-- generated: members: writers (tools/gen-api.py docs) -->
| Writer | TypeScript | Python | C++ |
|---|---|---|---|
| memory | `memoryWriter(files)` from `villanelle` | `memory_writer(files)` from `villanelle` | `memory_writer(files)` from `villanelle` |
| the filesystem | `fileWriter()` from `villanelle/node` | `file_writer()` from `villanelle.files` | `file_writer()` from `villanelle::files` |
| `fetch` | `fetchWriter(fetch, options?)` from `villanelle/browser` | none | none |
<!-- end generated -->

Every writer first runs the one lost-update check, `checkLostUpdates(files, current)` (Python
`check_lost_updates`), with each file's text in its medium now: if a file no longer holds its `savedText` (someone
else changed it), it writes nothing and raises `LostUpdateError` whose `paths` are exactly those files (written
cases `save-lost-update`, `save-lost-update-paths`). A writer of your own calls it too. Then it writes each text to a temporary file beside its
target and renames them over the targets, so a failure while staging replaces nothing. A missing file holds the
empty text, so a new file (`savedText` "") is written. A failure while renaming can leave the files renamed before it
replaced while their `savedText` stays the old text, so the next save refuses them as lost updates until you load again:

```python
def test_file_writer_refuses_a_lost_update_writing_nothing(tmp_path: Path) -> None:
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("a 1;\n")
    b.write_text("changed by someone else;\n")
    with pytest.raises(vl.LostUpdateError, match=r"b\.conf"):
        file_writer().write([vl.FileWrite(str(a), "a 2;\n", "a 1;\n"), vl.FileWrite(str(b), "b 2;\n", "b 1;\n")])
    assert a.read_text() == "a 1;\n"
    assert b.read_text() == "changed by someone else;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf", "b.conf"]
```

`py/tests/test_files.py`. The TypeScript writer does the same (test "refuses a lost update, writing nothing, and
names the file", `ts/src/node.test.ts`). The fetch writer, per file, `GET`s the URL, runs the same check on the
body, then sends the text with `If-Match` on the `GET`'s ETag, so a server that keeps ETags refuses a change made in
between (`412`, a lost update). It stops at the first file that fails, so it is not all-or-nothing.

## Making config text: `quote` and `text`

New values are config text. `quote(text)` writes a string a program holds as a villanelle string, the same string
text an expanded value has, with backslash, quote, newline, tab and carriage return escaped; `text(raw)` takes text
already written in villanelle syntax (`text("8080 udp")`, `text("[1, 2]")`) as config text, unchanged, and the edit
it is given checks it:

```ts
    expect(quote('10.0.60.31 "x"\n')).toBe('"10.0.60.31 \\"x\\"\\n"');
```

`ts/src/written/written.test.ts`, test "quotes a plain string as the canonical villanelle string". In Python,
`vl.quote` (`test_quote_writes_a_plain_string_as_the_canonical_villanelle_string`). `quote` and `text` take text
only too: a number is a `TypeError`. Nothing else makes config text: a value's or statement's `text` is plain text,
so writing it into another edit takes `text(value.text)`.

## What is stored and what is worked out

The graph stores only the texts (and each `savedText`), the overrides, and which files were read: for each
include spec, the paths it resolved to or why it failed; for each path, the document or why it could not be read.
Everything else (copies, edges, variables, resolutions, the problems found, the rendered tree) is worked out from
those when asked, and worked out again after any edit. The lists those methods return (`copies()`,
`resolutions()`, `edges()` and so on) are snapshots of one moment; the statements, values and variables in them are
live handles.

Orders: `documents` is the root, then first-read order. `copies()`, `edges()`, `wins()`, `shadowedAt()`,
`resolutions()` and `snippets()` are in the order rendering meets them. `variables()` is each document in order, and
in it each `$name` of a `set` or `snippet` line in text order, then the overrides in `overrides` order (a new
name goes at the end).

## How the two languages differ

By design (each language's own way):

- TypeScript's `load`, `read`, `save` and writers are async (promises); Python's are plain calls.
- Python names are `snake_case` (`replace_with_text`, `insert_statements`, `included_by`, `set_override`,
  `shadowed_at`, `saved_text`); a block is a `Sequence` (`block[0]`, `len(block)`, `list(block).index(fps)`) where
  TypeScript's is an `Iterable` with `length` and `at(i)`; each statement and value kind is its own class for
  `match`; absent is `None`, not `undefined`.
- Each layer is its own import path (milestone 6): `villanelle` (config text, the ports, the memory adapters, the
  error classes), `villanelle/written` / `villanelle.written` (this page), `villanelle/rendered` /
  `villanelle.rendered`, `villanelle/syntax` / `villanelle.syntax`. Type names are the same in both languages.
- An index outside a block is RangeError in TypeScript and IndexError in Python. A bad name is MisuseError in
  TypeScript and ValueError in Python; `BadTextError` is not a `ValueError` (milestone 4).
- `SaveError` keeps the writer's error as `cause` in TypeScript and as `__cause__` in Python.
- Places and the diagnostics of a refused edit count UTF-16 code units in both, so a Python offset is not a `str`
  index once a character outside the Basic Multilingual Plane comes before it (Python has no public helper for the
  conversion yet: positions per language are the edge contract's question, a later milestone).
- Python has no fetch source or fetch writer.

## Not covered here

Creating or deleting files, several root files in one graph, and identities that outlive the process are not part
of this layer. There is no whole-file formatter. A rendered tree read after an edit shows the old text; render again.
