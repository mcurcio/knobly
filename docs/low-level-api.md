# The low level (TypeScript and Python)

This page is for a program that works with villanelle config **as written**: which files were read, what variables
exist, where each one is overridden, and changes to any of it written back to the files. Comments and layout are
kept: an edit changes only the text it names.

villanelle has three layers. Each one is built on the one below, and a program can work at any of them:

| Layer | What it is | Where it is described |
|---|---|---|
| the syntax tree | `parse(text)`: one text, every character in exactly one token | [`ts/README.md`](../ts/README.md), [`py/README.md`](../py/README.md) |
| the low level | `load(path)`: the files as written, with the variables and include lines in them, editable and saved back | this page |
| the rendered tree | `render(graph)`: what the files say once variables, snippets and includes are worked out | [rendered-tree.md](rendered-tree.md) |

The language itself is described in [language.md](language.md). The two packages have the same parts under each
language's own names; each section shows TypeScript first, then Python.

**About the examples.** Every code example is copied from a test that passes, named under it. The tests import
from the package's source files (`../load/processor.js`, `./save.js`); the examples write the imports a program
would write (`villanelle`, `villanelle/include`). "Excerpt" means lines were left out; nothing else was changed.
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

(Excerpt of [`fixtures/rasl/split/sink.conf`](../fixtures/rasl/split/sink.conf).) The program hands in its own
`leds_host`, which wins over the file's default.

### Which files were read, what variables exist, where each is overridden

TypeScript:

```ts
import { readFileSync } from "node:fs";

import { type IDirective, type IDocumentWriter, type IFileWrite, type IPlace, type IRendered, memorySource, save, villanelle } from "villanelle";
import { include } from "villanelle/include";

/** 1-based `file:line`, as design.md §1 prints it. */
const lineOf = (place: IPlace): string => `${place.resolvedPath}:${String(place.span.start.line + 1)}`;

  const config = villanelle({ source: memorySource(FILES), extensions: [include()] });
  const graph = await config.load("main.conf", { variables: { leds_host: '"10.0.70.1"' } });

    expect([...graph.documents.values()].map((doc) => [doc.resolvedPath, doc.includedBy().map((e) => lineOf(e.copy.statement.place))])).toEqual([
      ["main.conf", []],
      ["sink.conf", ["main.conf:19", "main.conf:24"]],
    ]);
    const table = graph.variables().map((v) => [
      v.name,
      v.kind,
      v.place === undefined ? "handed in" : lineOf(v.place),
      v.reaches().map((r) => lineOf(r.reference.place)),
      v.overridden().map((r) => [lineOf(r.reference.place), r.winner?.kind]),
    ]);
    expect(table).toEqual([
      ["pixels", "set", "main.conf:4", ["sink.conf:6", "sink.conf:6"], []],
      ["leds_host", "set", "main.conf:5", [], [["main.conf:21", "handed"]]],
      ["name", "set", "main.conf:20", ["sink.conf:2"], []],
      ["host", "set", "main.conf:21", ["sink.conf:3"], []],
      ["name", "set", "main.conf:25", ["sink.conf:2"], []],
      ["host", "set", "main.conf:26", ["sink.conf:3"], []],
      ["leds_host", "handed", "handed in", ["main.conf:21"], []],
    ]);
```

Excerpt of `ts/src/written/tracer.test.ts`, test "lists files, variables and overrides, then changes $pixels itself
(2) and saves only main.conf". `FILES` holds the two fixture files.

Read the table this way: `$pixels` is set at main.conf:4 and used at sink.conf:6 twice, once per include line.
The file's `$leds_host` (main.conf:5) is overridden at main.conf:21 by the handed-in value, which is used there.

Python:

```python
    config = vl.Processor(source=vl.memory_source(FILES), extensions=[include()])
    return config, config.load("main.conf", variables={"leds_host": '"10.0.70.1"'})

    files = [
        (doc.resolved_path, [line_of(e.copy.statement.place) for e in doc.included_by()])
        for doc in graph.documents.values()
    ]
    assert files == [("main.conf", []), ("sink.conf", ["main.conf:19", "main.conf:24"])]
    table = [
        (
            v.name,
            v.kind,
            "handed in" if v.place is None else line_of(v.place),
            [line_of(r.reference.place) for r in v.reaches()],
            [(line_of(r.reference.place), None if r.winner is None else r.winner.kind) for r in v.overridden()],
        )
        for v in graph.variables()
    ]
```

Excerpt of `open_split` and `test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf`,
`py/tests/test_tracer.py` (the table it checks is the one above).

### Change `$pixels` itself, or change `max_count` to no longer use it

Both kinds of change start from a rendered value. Its `resolutions[0]` says what the `$name` on its own line reads
at this place: `winner` is the variable (here `set $pixels 2284;`), `reference` is the `$pixels` written on the
`max_count` line.

Change the variable itself: main.conf:4 changes, so every place that reads it changes (both sinks read 2400), and
`save` hands the writer only main.conf:

```ts
    const rendered = config.render(graph);
    const maxCount = nodeNamed(rendered, "leds").body?.find((d) => d.name === "max_count")?.args[0];
    const read = maxCount?.resolutions[0];
    expect(read?.winner?.kind).toBe("set");
    read?.winner?.setValues("2400");
    const writer = recorder();
    expect(await save(graph, writer)).toEqual(["main.conf"]);
    expect(writer.batches).toHaveLength(1);
    const [written] = writer.batches[0] ?? [];
    expect(written?.text).toBe(FILES["main.conf"].replace("set $pixels 2284;", "set $pixels 2400;"));
    expect(maxCounts(config.render(graph))).toEqual([
      ["2400", "main.conf:4:13", 1],
      ["2400", "main.conf:4:13", 1],
    ]);
    // The rendered tree from before the edit is a snapshot: it still reads 2284.
    expect(maxCount?.text).toBe("2284");
```

Excerpt of the same test. `nodeNamed` walks the rendered tree for a `node` by its id; `recorder()` is a writer that
keeps each batch it is handed; `maxCounts` lists each `max_count` value's text, where it is written and how many
resolutions it has.

Change the line instead: `max_count $pixels;` becomes `max_count 2400;` in sink.conf, `$pixels` reaches nothing,
and `save` hands over only sink.conf:

```ts
    const read = nodeNamed(config.render(graph), "leds").body?.find((d) => d.name === "max_count")?.args[0]?.resolutions[0];
    const reference = read?.reference;
    expect(reference?.text).toBe("$pixels");
    reference?.replaceWithText("2400");
    const writer = recorder();
    expect(await save(graph, writer)).toEqual(["sink.conf"]);
    expect(writer.batches[0]?.[0]?.text).toBe(FILES["sink.conf"].replace("max_count $pixels;", "max_count 2400;"));
    expect(graph.variables("pixels")[0]?.reaches()).toEqual([]);
```

Excerpt of `ts/src/written/tracer.test.ts`, test "changes max_count to no longer use the variable (3): only
sink.conf, and $pixels reaches nothing".

The same in Python:

```python
    read = max_count.resolutions[0]
    assert read.winner is not None and read.winner.kind == "set"
    read.winner.set_values("2400")  # (2)
    writer = Recorder()
    assert vl.save(graph, writer) == ["main.conf"]
    [[written]] = writer.batches
    assert written.text == FILES["main.conf"].replace("set $pixels 2284;", "set $pixels 2400;")
    assert vl.save(graph, writer) == []  # (5): saving twice writes once
```

```python
    read = next(d for d in leds.body or () if d.name == "max_count").args[0].resolutions[0]
    assert read.reference.text == "$pixels"
    read.reference.replace_with_text("2400")  # (3)
```

Excerpts of `test_lists_files_variables_and_overrides_then_changes_pixels_itself_and_saves_only_main_conf` and
`test_changes_max_count_to_no_longer_use_the_variable_only_sink_conf_and_pixels_reaches_nothing`,
`py/tests/test_tracer.py`.

An edit lands on the written line, so every place that reads that line sees it. sink.conf is read at two places:
replacing `$pixels` there changes the `porch` sink as well as `leds`. `statement.copies()` says how many places read
a line before a program edits it. For a value that came through a snippet parameter, the variable is the
parameter, and its value is on the `use` line: `read.values[0].replaceWithText(...)` edits that.

### Edit a directive inside the included file, and undo

```python
    node = node_named(config.render(graph), "porch").written  # (4): `node DdpSink $name {` in sink.conf
    assert node is node_named(config.render(graph), "leds").written
    assert len(node.copies()) == 2
    doc = node.document
    kept = doc.text
    block = node.block
    assert block is not None
    [fps] = block.directives("fps")
    fps.set_values("30hz")
    block.insert_statements(list(block).index(fps) + 1, "brightness 0.8;")
    assert "    fps 30hz;\n    brightness 0.8;\n    input_port pixels;" in doc.text
```

```python
    doc.replace_with_text(kept)  # undo: `source` is untouched; every handle into it detaches
    assert doc.text == doc.source
    with pytest.raises(vl.DetachedError):
        _ = node.text
    assert vl.save(graph, Recorder()) == []
```

Excerpts of `test_edits_a_directive_inside_the_included_file_and_undoes_it`, `py/tests/test_tracer.py`.

The rest of this page goes through each part used above.

## Loading: the document graph

`await processor.load(path, { variables })` (Python: `processor.load(path, variables=...)`) reads the root file and
every file its include lines name, once each, and gives back the **document graph**. Making a processor, document
sources, extensions, and the one way `load` fails (`ReadError`, E3004 at the root path) are the same as for the
rendered tree: see [rendered-tree.md](rendered-tree.md#making-a-processor-loading-and-rendering).

| Member | TypeScript | Python | What it is |
|---|---|---|---|
| the root file | `root` | `root` | the file `load` was given |
| every file read | `documents` | `documents` | by path: the root, then in first-read order; never shrinks |
| handed-in values | `handed` | `handed` | by name, each as villanelle text; never saved |
| change a handed-in value | `setHanded(name, text)` | `set_handed(name, text)` | see "Handed-in values" |
| every place an include line is read | `edges()` | `edges()` | the line, the specs it gave, the files it matched |
| what is not read yet | `unread()` | `unread()` | the edges naming a file not read yet (see "Reading files an edit added") |
| variables | `variables(name?)` | `variables(name=None)` | every `set` line's and snippet parameter's `$name`, then the handed-in ones |
| problems | `diagnostics()` | `diagnostics()` | each file's syntax problems, then the include, `set` and `snippet` problems found |

`graph.diagnostics()` leaves out the problems only rendering finds (bad values E4xxx, an unknown variable E5001, an
unknown snippet E5003, a wrong count E5004, too many directives E5008); `render(graph).diagnostics` has every one.

## Documents

A **document** is one file as written:

| Member | TypeScript | Python |
|---|---|---|
| its path | `resolvedPath` | `resolved_path` |
| the text as read, or as last saved | `source` | `source` |
| the text now | `text` | `text` |
| its syntax tree | `syntax` | `syntax` |
| its top-level statements | `body` | `body` |
| the include copies that splice it in | `includedBy()` | `included_by()` |
| replace the whole text | `replaceWithText(text)` | `replace_with_text(text)` |

`text` differs from `source` exactly when the document has unsaved changes. `replaceWithText` takes any text,
broken or not (an undo, a formatter's output), leaves `source` alone, and detaches every handle into the document
(see "Handles").

## Statements

A document's `body`, and every block, holds **statements**, in order. Each statement has a `kind`:

| Kind | What it is | Its own members |
|---|---|---|
| `directive` | a directive | `name`, `values`, `block`, `rename(name)`, `setValues(text)` |
| `extension` | a line a registered extension owns: an include line | the same as a directive; its `values` are the path, its `block` its `set` lines |
| `set` | `set $name value...;` | `variable`, `values`, `setValues(text)` |
| `snippet` | `snippet name $param... { ... }` | `name`, `parameters`, `block` |
| `use` | `use name value...;` | `snippetName`, `snippet`, `snippets()`, `values`, `setValues(text)` |
| `unreadable` | a line that does not parse, a malformed `set`, `snippet` or `use`, or a second `set` (or `snippet`) of one name in one block | none |

Every statement has `document`, `parent` (the statement whose block holds it), `place`, `text`, `copies()`,
`replaceWithText(text)` and `remove()`. A block has `statements`, `directives(name?)`, `insertStatements(index,
text)` and `addStatements(text)`. In Python the names are `snake_case`, a block is itself a sequence of its
statements, and each kind is its own class, so `match` narrows it:

```python
def describe(statement: vl.Statement) -> str:
    match statement:
        case vl.WrittenDirective():
            return f"{statement.kind} {statement.name}"
        case vl.SetLine():
            return f"set ${statement.variable.name}"
        case vl.SnippetLine():
            return f"snippet {statement.name}"
        case vl.UseLine():
            return f"use {statement.snippet_name}"
        case vl.UnreadableLine():
            return "unreadable"
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
| `slice` | `c[1:2]` | `name`, `start`, `end` (a word or a reference; absent when not written) |
| `index` | `c[0]` | `name`, `index` |
| `reference` | `$pixels` | `name`, `declaration`, `resolutions()` |

Every value has `text` (exactly as written), `place`, `statement`, `list` (the list it is an item of, if any),
`replaceWithText(text)` and `remove()`.

```python
def value_kind(value: vl.WrittenValue) -> str:
    match value:
        case vl.Word() | vl.String():
            return value.kind
        case vl.List():
            return f"list of {len(value.items)}"
        case vl.Slice():
            return f"slice {value.name}"
        case vl.Index():
            return f"index {value.name}[{value.index.text}]"
        case vl.Reference():
            return f"reference {value.name}"
        case _:
            assert_never(value)
```

`py/tests/test_written.py`, used by the same test, which reads `x w "s" [1, 2] c[1:2] c[0] $a;` as word, string,
list of 2, slice c, index c[0], reference a.

## Copies: every place a line is read

A line can be read at several places: a file included twice, a snippet used twice. Each place is a **copy**:
`copy.statement` is the line, `copy.via` the include and `use` steps that bring it there, innermost first (empty at
the root). `statement.copies()` lists every copy in the order rendering meets them; it is empty for a line nothing
reaches (a snippet never used, a file no include reaches any more).

`graph.edges()` lists every copy of every include line, with the `specs` the extension gave there and the
`targets` it matched (several for a glob; empty when it failed or is not read yet). `document.includedBy()` is the
edges that splice that document in.

## Variables and what each `$name` reads

A **variable** is a `set` line's `$name`, a snippet's parameter, or a value handed in by the program. Its `kind` is
`set`, `parameter` or `handed`.

| Member | TypeScript | Python | What it is |
|---|---|---|---|
| | `kind`, `name` | `kind`, `name` | the name without `$` |
| where its `$name` is written | `place` | `place` | undefined (None) when handed in |
| its line | `line` | `line` | the `set` or `snippet` line; undefined when handed in |
| the `$name`s declared by it | `references()` | `references()` | by where they are written, reached or not |
| where it wins | `reaches()` | `reaches()` | one resolution per place it wins |
| where another one wins | `overridden()` | `overridden()` | one resolution per place it loses |
| rename its `$name` | `rename(name)` | `rename(name)` | only the `$name` on its line; the references are not changed |
| change its value | `setValues(text)` | `set_values(text)` | its `set` line's values; `NoSetLineError` for a parameter or a handed-in value |

A **reference** is one `$name` written as a value. It has two answers to "which variable is this?":

- `declaration`, by where it is written, in its own file only: nearest first, block by block outward, the `set` of
  that name above it in that block, then the parameter of that name when the block is a snippet's body. So a `set`
  in a block inside a snippet's body wins over the snippet's parameter, as it does at every copy. Undefined (None)
  when there is none: a `$name` in an included file that the including line's block sets is free in its own file.
- `resolutions()`, one per copy of its line: at that copy, the `winner` (the variable it reads there, or undefined
  when nothing of that name is visible, which rendering reports as E5001), `overridden` (every other variable of
  that name visible there, the next one to win first), and `values` (the winner's values: its `set` line's, or for
  a parameter the `use` line's values bound to it; empty when handed in or when nothing wins).

The winner is the language's rule, unchanged ([language.md](language.md)): the nearest `set` or parameter; a `set`
in an include line's block wins over every `set` inside the files it splices in; a handed-in value wins over every
`set`, never over a parameter. In the shared case `overridden-next-first`, `main.conf` is

```conf
include "f.conf" {
    set $a 2;
}
```

`f.conf` is `set $a 1;` then `x $a;`, and `a` is handed in: the `$a` on `x` reads the handed-in value, and its
`overridden` lists main.conf's `set $a 2;` first, then f.conf's `set $a 1;`.

A `use` line has the same pair for its snippet: `snippet` by where it is written, `snippets()` per copy.

## Handed-in values

`graph.handed` holds the values the program handed in, by name, as villanelle text. `setHanded(name, text)` adds or
changes one, and `setHanded(name, undefined)` (Python: `None`) removes it, without a reload. A handed-in value has
one variable object per name for the graph's life, so a program can hold on to it:

```ts
    const { source, reads } = countingSource({ "main.conf": "set $a 0;\nx $a;\n" });
    const processor = villanelle({ source });
    const graph = await processor.load("main.conf", { variables: { a: "1" } });
    const handed = graph.variables("a").find((v) => v.kind === "handed");
    graph.setHanded("a", "2 3");
    expect(processor.render(graph).body[0]?.args.map((v) => v.text)).toEqual(["2", "3"]);
    graph.setHanded("a", undefined);
    expect([...graph.handed.keys()]).toEqual([]);
    expect(graph.variables("a").map((v) => v.kind)).toEqual(["set"]);
    expect(processor.render(graph).body[0]?.args.map((v) => v.text)).toEqual(["0"]);
    graph.setHanded("b", "9");
    graph.setHanded("a", "4");
    expect([...graph.handed.keys()]).toEqual(["b", "a"]);
    expect(graph.variables("a").find((v) => v.kind === "handed")).toBe(handed);
    expect(handed?.reaches()).toHaveLength(1);
    expect(reads.get("main.conf")).toBe(1);
```

`ts/src/written/edits.test.ts`, test "changes resolutions and render without a reload, one variable per name for
the graph's life (B5, D28)". `countingSource` is a memory source that counts each file's reads.

The text must be one or more values without a `$name`. Anything else is a `BadTextError` located in the text, and
nothing changes; a name that is not letters, digits and `_` is a TypeError (Python: ValueError):

```ts
    expect(refused("1;")).toEqual([["E2001", 0, 1]]);
    expect(refused("1 $b")).toEqual([["E2001", 0, 2]]);
    expect(refused('"\\q"')).toEqual([["E4003", 0, 0]]);
    expect(refused("")).toEqual([["E2001", 0, 0]]);
    expect(() => graph.setHanded("a-b", "1")).toThrow(TypeError);
    expect(graph.handed.get("a")).toBe("1");
```

Excerpt of `ts/src/written/edits.test.ts`, test "refuses a text that is not values without a $name, and a bad name,
changing nothing". `refused` calls `setHanded("a", text)` and gives each diagnostic's code, line and column.

## Edits and their errors

New values and statements are written as villanelle text. To write a plain string as villanelle text, use
`quote` (below).

| Edit | On | Takes |
|---|---|---|
| `setValues(text)` (Python `set_values`) | a directive, an include line, a `set` line, a `use` line, a `set` variable | values |
| `replaceWithText(text)` | a value | values (in a list: items) |
| `remove()` | a value | nothing |
| `replaceWithText(text)` | a statement | zero or more statements |
| `remove()` | a statement | nothing |
| `insertStatements(index, text)`, `addStatements(text)` | a block or a document's body | zero or more statements |
| `rename(name)` | a directive; a variable (its `$name` only) | one name |
| `replaceWithText(text)` | a document | any text |
| `setHanded(name, text)` | the graph | values without a `$name` |

Every edit except a document's `replaceWithText` checks its text first, and **a refused edit changes nothing**:

- A values text must be values only: its own syntax errors keep their codes; a `;` or a block in it is one E2001 at
  that token. A slice bound takes exactly one word or `$name`.
- A statements text is read as a file; its syntax errors keep their codes. An empty text is zero statements.
- Then the rules a file alone must keep are checked on the block the edit would make: a second `set` of a name in
  one block (E5002), a second snippet of a name (E5005), a malformed `set`, `snippet` or `use` (E5009 to E5011). A
  `set` left with no value, by `remove()` or `setValues("")`, is E5009.
- `rename` takes one word. A name that would change what the line is (`set`, `snippet`, `use`, or a registered
  extension's name), or renaming an include line, is E2001 at 0:0. A variable's new name must be letters, digits and
  `_`, and must not make a second `set` of that name in its block (E5002).
- An edit that adds an include line is allowed; its file is not read until `read(graph)` (below).

A refused text throws **`BadTextError`**. Its `diagnostics` are placed in the text the edit was given (0-based line
and column, as `parse` places them), with the same codes a load gives:

```ts
    const graph = await load({ "main.conf": "set $a 1;\n" });
    const set = graph.root.body.statements[0] as ISetLine;
    for (const text of ["1; x", "{", "", "\"open"]) {
      expect(() => set.setValues(text), text).toThrow(BadTextError);
      expect(graph.root.text).toBe("set $a 1;\n");
    }
    expect(set.text).toBe("set $a 1;");
```

`ts/src/written/written.test.ts`, test "changes nothing when an edit's text is refused".

| Error | TypeScript | Python | When |
|---|---|---|---|
| the text is not what the edit takes | `BadTextError` (`diagnostics`) | `BadTextError` (`diagnostics`) | above |
| the handle's tokens are gone | `DetachedError` | `DetachedError` | see "Handles" |
| no `set` line to edit | `NoSetLineError` | `NoSetLineError` | `setValues` on a parameter (edit the `use` line) or a handed-in value (use `setHanded`); `rename` of a handed-in value |
| an index outside the block | `RangeError` | `IndexError` | `insertStatements` |
| the writer failed | `SaveError` (`files`, `cause`) | `SaveError` (`files`, `__cause__`) | see "Saving" |
| the root file cannot be read | `ReadError` (a `DiagnosticError`, E3004) | `ReadError` | `load` |

`BadTextError`, `DetachedError` and `NoSetLineError` share the base `EditError` (in Python a `ValueError`).

### Where new text goes

villanelle keeps the file's own layout; there is no formatter.

- `setValues` replaces the values from the first to the last, comments between them included. On a line with no
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
    const [b] = graph.root.body.statements as [IWrittenDirective];
    const block = b.block;
    if (block === undefined) throw new Error("no block");
    const [a, c] = block.statements;
    const made = block.insertStatements(1, "x 1;\ny 2;");
    expect(made.map((s) => s.text)).toEqual(["x 1;", "y 2;"]);
    expect(graph.root.text).toBe("b {\n    a 1;\n    x 1;\n    y 2;\n    # about c\n    c 3;\n}\n");
    expect(block.statements).toEqual([a, ...made, c]);
    expect(c?.text).toBe("# about c\n    c 3;");
    expect(() => block.insertStatements(9, "z;")).toThrow(RangeError);
    expect(() => block.insertStatements(0, "z {")).toThrow(BadTextError);
    expect(block.insertStatements(0, "  ")).toEqual([]);
```

`ts/src/written/edits.test.ts`, test "inserts before a statement and its comments, at an index, keeping other
handles".

### Renaming

`rename` on a directive changes its name and keeps the handle and its values. `rename` on a variable changes only
the `$name` on its `set` or `snippet` line; the `$name`s that read it are left as written, so a program that wants
them renamed too edits each of `variable.references()`:

```ts
    const graph = await villanelle({ source: memorySource({ "main.conf": "set $a 1;\nsnippet s $p { x $p; }\ny $a;\n" }) }).load("main.conf");
    const [set, snippet] = graph.root.body.statements as [ISetLine, ISnippetLine];
    const variable = set.variable;
    const [parameter] = snippet.parameters;
    variable.rename("b");
    parameter?.rename("q");
    expect(graph.root.text).toBe("set $b 1;\nsnippet s $q { x $p; }\ny $a;\n");
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
    const graph = await load({ "main.conf": "set $a 1;\nb 2 3;\nc { d 4; }\n" });
    const body = graph.root.body;
    const [set, b, c] = body.statements as [ISetLine, IWrittenDirective, IWrittenDirective];
    const [two, three] = b.values;
    const d = c.block?.statements[0];
    set.setValues("100 200");
    expect(graph.root.text).toBe("set $a 100 200;\nb 2 3;\nc { d 4; }\n");
    expect(body.statements[0]).toBe(set);
    expect(body.statements[1]).toBe(b);
    expect(b.values[0]).toBe(two);
    expect(b.values[1]).toBe(three);
    expect(c.block?.statements[0]).toBe(d);
```

Excerpt of `ts/src/written/written.test.ts`, test "keeps one handle per statement and value across an edit
elsewhere in the file (===)".

A handle whose tokens an edit removed is **detached**: every member but `kind` throws `DetachedError`, so a program
never reads stale text by mistake.

- `setValues` and `rename` keep the handle they are called on (only its values or its name change).
- `replaceWithText` and `remove()` detach the handle they are called on, and any handle inside what they replaced.
  `replaceWithText` returns the new handles.
- A document's `replaceWithText` detaches every handle into that document; the document's own handle stays.

```ts
    const graph = await load({ "main.conf": "x 1;\n" });
    const [value] = (graph.root.body.statements[0] as IWrittenDirective).values;
    if (value === undefined) throw new Error("no value");
    const [made] = value.replaceWithText("2");
    expect(made?.text).toBe("2");
    expect(value.kind).toBe("word");
    expect(() => value.text).toThrow(DetachedError);
    expect(() => value.replaceWithText("3")).toThrow(DetachedError);
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
    const [b] = graph.root.body.statements;
    expect(b?.text).toBe("# near\n  b 2; # end");
    expect(b?.place.span.start).toMatchObject({ line: 2, column: 0 });
    b?.remove();
    expect(graph.root.text).toBe("# far\n\nc;\n");
```

`ts/src/written/written.test.ts`, test "owns the comment lines directly above a statement and its trailing comment".
For `a; b; # c` the trailing comment is `b`'s.

## Reading files an edit added

An edit can add an include line, or change one to name another file. Until that file is read, the graph lists the
include copy in `graph.unread()`, and `render` leaves it out. `await processor.read(graph)` (Python:
`processor.read(graph)`) reads what is missing, repeating until nothing new is named, and returns the paths it read.
Every unsaved text stays, and no file is read twice:

```ts
    const { source, reads } = countingSource({ "main.conf": MAIN, "part.conf": "p 1;\n", "other.conf": "o 1;\n" });
    const processor = villanelle({ source, extensions: [include()] });
    const graph = await processor.load("main.conf");
    const [a] = graph.root.body.statements as [IWrittenDirective];
    a.setValues("2");
    const [line] = graph.root.body.addStatements('include "part.conf";');
    expect(line?.kind).toBe("extension");
    expect(graph.unread()).toHaveLength(1);
    expect(processor.render(graph).body.map((d) => d.name)).toEqual(["a"]);
    expect(reads.get("part.conf")).toBeUndefined();

    expect(await processor.read(graph)).toEqual(["part.conf"]);
    expect(graph.unread()).toEqual([]);
    expect(graph.root.text).toBe('a 2;\ninclude "part.conf";\n');
```

Excerpt of `ts/src/written/edits.test.ts`, test "reads an include line an edit added once, keeps every unsaved
text, and render then splices it (B3)". `MAIN` is `a;`.

A file that could not be found or read stays that way for the graph: `read` does not try it again (test "keeps a
rejection: a missing file is not resolved again", same file). Load again for a fresh look.

## Saving

`save(graph, writer)` hands every document whose `text` differs from its `source` to the writer, in one batch, and
returns their paths. With nothing changed it does not call the writer and returns an empty list, so saving twice
writes once. When the writer succeeds, each written document's `source` becomes the text handed over; an edit made
while the writer ran stays unsaved.

```ts
    const graph = await load({ "main.conf": 'include "p.conf";\nx 1;\n', "p.conf": "y 2;\n" });
    const writer = recorder();
    expect(await save(graph, writer)).toEqual([]);
    expect(writer.batches).toEqual([]);
    const p = graph.documents.get("p.conf");
    (p?.body.statements[0] as IWrittenDirective).values[0]?.replaceWithText("3");
    expect(await save(graph, writer)).toEqual(["p.conf"]);
    expect(writer.batches).toEqual([[{ resolvedPath: "p.conf", text: "y 3;\n", source: "y 2;\n" }]]);
    expect(p?.source).toBe("y 3;\n");
    expect(await save(graph, writer)).toEqual([]);
    expect(writer.batches).toHaveLength(1);
```

`ts/src/written/written.test.ts`, test "hands only changed files to the writer in one call, then updates source;
nothing changed: no call". `recorder()` is a writer that keeps each batch.

The core does no input or output: the **writer** is the program's. It has one method, `write(files)` (a promise in
TypeScript, a plain call in Python), given the batch. Each file in it has `resolvedPath`, `text` (what to write)
and `source` (what was read, to compare with the disk). If the writer fails, `save` throws `SaveError` with the
`files` and the writer's error as its cause, and no `source` changes.

| Writer | TypeScript | Python |
|---|---|---|
| the filesystem | `createFsWriter()` from `villanelle/node` | `fs_writer()` from `villanelle.files` |
| `fetch` | `createFetchWriter(fetch, options?)` from `villanelle/browser` | none |

The filesystem writer first checks that each file on disk still holds its `source`; if any does not (someone else
changed it), it writes nothing and fails, naming the files. Then it writes each text to a temporary file beside its
target and renames them over the targets, so a failure while staging replaces nothing. A missing file holds the
empty text, so a new file (`source` "") is written. A failure while renaming can leave the files renamed before it
replaced while their `source` stays the old text, so the next save refuses them as lost updates until you load again:

```python
def test_fs_writer_refuses_a_lost_update_writing_nothing(tmp_path: Path) -> None:
    a, b = tmp_path / "a.conf", tmp_path / "b.conf"
    a.write_text("a 1;\n")
    b.write_text("changed by someone else;\n")
    with pytest.raises(OSError, match=r"b\.conf"):
        fs_writer().write([vl.FileWrite(str(a), "a 2;\n", "a 1;\n"), vl.FileWrite(str(b), "b 2;\n", "b 1;\n")])
    assert a.read_text() == "a 1;\n"
    assert b.read_text() == "changed by someone else;\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.conf", "b.conf"]
```

`py/tests/test_files.py`. The TypeScript writer does the same (test "refuses a lost update, writing nothing, and
names the file", `ts/src/node.test.ts`). The fetch writer sends one request per file and stops at the first that
fails, so it is not all-or-nothing.

## Writing a plain string: `quote`

New values are villanelle text, so a string a program holds must be quoted first. `quote(text)` gives the same
string text a rendered value has, with backslash, quote, newline, tab and carriage return escaped:

```ts
    expect(quote('10.0.60.31 "x"\n')).toBe('"10.0.60.31 \\"x\\"\\n"');
```

`ts/src/written/written.test.ts`, test "quotes a plain string as the canonical villanelle string". In Python,
`vl.quote` (`test_quote_writes_a_plain_string_as_the_canonical_villanelle_string`).

## What is stored and what is worked out

The graph stores only the texts (and each `source`), the handed-in values, and which files were read: for each
include spec, the paths it resolved to or why it failed; for each path, the document or why it could not be read.
Everything else (copies, edges, variables, resolutions, the problems found, the rendered tree) is worked out from
those when asked, and worked out again after any edit. The lists those methods return (`copies()`,
`resolutions()`, `edges()` and so on) are snapshots of one moment; the statements, values and variables in them are
live handles.

Orders: `documents` is the root, then first-read order. `copies()`, `edges()`, `reaches()`, `overridden()`,
`resolutions()` and `snippets()` are in the order rendering meets them. `variables()` is each document in order, and
in it each `$name` of a `set` or `snippet` line in text order, then the handed-in values in `handed` order (a new
name goes at the end).

## How the two languages differ

By design (each language's own way):

- TypeScript's `load`, `read`, `save` and writers are async (promises); Python's are plain calls.
- Python names are `snake_case` (`set_values`, `replace_with_text`, `insert_statements`, `included_by`,
  `set_handed`); a block is a sequence of its statements (`body[0]`, `len(body)`, `list(block).index(fps)`); each
  statement and value kind is its own class for `match`; absent is `None`, not `undefined`.
- An index outside a block is RangeError in TypeScript and IndexError in Python. A bad name for a handed-in value is
  TypeError in TypeScript and ValueError in Python; the edit errors are `ValueError`s in Python.
- `SaveError` keeps the writer's error as `cause` in TypeScript and as `__cause__` in Python.
- Places and the diagnostics of a refused edit count UTF-16 code units in both, so a Python offset is not a `str`
  index once a character outside the Basic Multilingual Plane comes before it.
- Python has no fetch source or fetch writer.

## Not covered here

Creating or deleting files, several root files in one graph, and identities that outlive the process are not part
of this layer. There is no whole-file formatter. A rendered tree read after an edit shows the old text; render again.
