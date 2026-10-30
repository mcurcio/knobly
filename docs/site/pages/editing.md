# Editing and saving

This page is for a program that changes knobly config **as written** and writes it back: an editor, a settings
screen, a tool that bumps a value. It works on the low level, the document graph that `load` returns. Comments and
layout are kept: an edit changes only the text it names. There is no formatter.

## Config text: `quote` and `text`

New values and statements are written as **config text**, a type of its own (a branded string in TypeScript, a
`NewType` in Python, a class in C++), made only two ways:

- `quote(s)` writes a string the program holds as a knobly string, the same text an expanded string has, with
  backslash, quote, newline, tab and carriage return escaped: `quote('10.0.60.31 "x"\n')` is
  `"10.0.60.31 \"x\"\n"`;
- `text(raw)` takes text already written in knobly syntax (`text("8080 udp")`, `text("[1, 2]")`) unchanged, and
  the edit it is given checks it.

So passing a plain string where config text is taken is refused before the program runs: a type error in
TypeScript and Python's type checker, a compile error in C++. In TypeScript and Python every edit also refuses, at
run time, anything that is not text (a number, `null` / `None`) with the language's type error, naming the member
and the parameter, before it changes anything. To write a number, convert it first (`text(String(n))`, `vl.text(str(n))`,
`vl::text(std::to_string(n))`). A value's or statement's `text` is plain text, so writing it into another edit takes
`text(value.text)`.

## Named edits, and a refused edit

The sample edits a file held in memory: it sets `host` to a quoted string, sets the port's one value, inserts a
statement into the block, and renames the directive. Then it tries a text that is not one value, which is refused
and changes nothing, and saves through a memory writer:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/edit_statements.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/edit_statements.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/edit_statements.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/edit_statements.txt"
```

The comment `# the port` stays with `port`, and the inserted line takes the block's indentation. `text` differs from
`saved_text` exactly when the document has unsaved changes.

| Edit | On | Takes |
|---|---|---|
| `set(text)` | a directive, an include line, a `set` line, a `use` line, a `set` variable | values |
| `set(text)` | a value | exactly one value; keeps the handle |
| `replace_with_text(text)` | a value | values (in a list: items) |
| `remove()` | a value | nothing |
| `replace_with_text(text)` | a statement | zero or more statements |
| `remove()` | a statement | nothing |
| `insert_statements(index, text)`, `add_statements(text)` | a block (a document's or a statement's) | zero or more statements |
| `rename(name)` | a directive; a variable (its `$name` only) | one name |
| `replace_with_text(text)` | a document | any text |
| `set_override(name, text)` | the graph | values without a `$name` |

(TypeScript spells them `replaceWithText`, `insertStatements`, `addStatements`, `setOverride`.) A statement's `set`
is the edit that replaces its values, not the language's `@set` statement.

Every edit except a document's `replace_with_text` checks its text first, and **a refused edit changes nothing**:

- A values text is parsed with the grammar's entry rule for it
  ([`spec/spec.md`](https://github.com/mcurcio/knobly/blob/main/spec/spec.md) 2.8): `valuesText` for a line's
  values, `itemsText` for a list item, `valueText` for a value's `set` (exactly one value), `boundText` for a slice
  bound, `sliceNameText` for a slice's name. A statement's `set` given no value must be given `""` (which clears the
  values). Its first syntax error is the diagnostic; a `;` or a block in it is E2001 at that token. A line break is
  whitespace, so a values text may span lines. A comment the text ends in is E2001 at the text's end (`port 1 #
  note;` would let the comment swallow the `;`).
- A name (`rename`, `set_override`) that is not well formed is a misuse error, not a bad text error: a directive name
  is one word that starts with a letter or `_ . / * ?` (`use` and `include` are allowed); a variable name is letters,
  digits and `_`.
- A statements text is read as a file; its syntax errors keep their codes. An empty text is zero statements.
- Then the rules a file alone must keep are checked on the block the edit would make: a second `@set` of a name in
  one block (E5002), a second snippet of a name (E5005), a malformed `@set`, `@snippet` or `@use` (E5009 to E5011).
  A `@set` line left with no value is E5009.
- An edit that adds an include line is allowed; its file is not read until `graph.read()` ([Variables, snippets and
  includes](variables.md#an-include-an-edit-added)).

A refused text throws a **bad text error**. Its `diagnostics` are placed in the text the edit was given (line and
column from 0, as `parse` places them), with the same codes a load gives.

## Change a variable, then save

Changing a `@set` line's variable changes every place that reads it. In the split config, `$pixels` is set once in
`main.conf` and read by both sinks in `sink.conf`; setting it to `2400` changes one line of one file, and the save
writes only that file:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/edit_save.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/edit_save.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/edit_save.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/edit_save.txt"
```

A program can instead change one use: a rendered value's `chain[0].reference` is the `$pixels` written on its own
line, and replacing it with `2400` writes `max_count 2400;` into `sink.conf`, after which `$pixels` wins nowhere
([Walking, addresses and reloads](walking.md#from-a-rendered-value-to-what-is-written)). An edit lands on the
written line, so every place that reads that line sees it: `sink.conf` is read at two places, so replacing `$pixels`
there changes the `porch` sink as well as `leds`. `statement.copies()` says how many places read a line before a
program edits it.

## Saving

`graph.save(writer)` hands every document whose `text` differs from its `saved_text` to the writer, in one batch,
and returns their paths. With nothing changed it does not call the writer and returns an empty list, so saving twice
writes once. When the writer succeeds, each written document's `saved_text` becomes the text handed over; an edit
made while the writer ran stays unsaved.

The core does no input or output: the **writer** is the program's. It has one method, `write(files)` (a promise in
TypeScript, a plain call in Python and C++), given the batch. Each file in it has its path, `text` (what to write)
and `saved_text` (what was read or last saved, to compare with the disk). If the writer fails, `save` throws a save
error with the `paths` and the writer's error as its cause, and no `saved_text` changes.

<!-- generated: members: writers (tools/gen-api.py docs) -->
| Writer | TypeScript | Python | C++ |
|---|---|---|---|
| memory | `memoryWriter(files)` from `knobly` | `memory_writer(files)` from `knobly` | `memory_writer(files)` from `knobly` |
| the filesystem | `fileWriter()` from `knobly/node` | `file_writer()` from `knobly.files` | `file_writer()` from `knobly::files` |
| `fetch` | `fetchWriter(fetch, options?)` from `knobly/browser` | none | none |
<!-- end generated -->

### Lost updates

Every writer first runs the one lost-update check, `check_lost_updates(files, current)` (TypeScript
`checkLostUpdates`), with each file's text in its medium now: if a file no longer holds its `saved_text` (someone
else changed it), it writes nothing and throws a **lost update error** whose `paths` are exactly those files. A
writer of your own calls it too. Then the file writer writes each text to a temporary file beside its target and
renames them over the targets, so a failure while staging replaces nothing. A missing file holds the empty text, so
a new file (`saved_text` "") is written.

The sample changes `app.conf` behind the graph's back, then saves an edit:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/lost_update.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/lost_update.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/lost_update.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/lost_update.txt"
```

A failure while renaming can leave the files renamed before it replaced while their `saved_text` stays the old
text, so the next save refuses them as lost updates until you load again. The fetch writer (TypeScript only), per
file, `GET`s the URL, runs the same check on the body, then sends the text with `If-Match` on the `GET`'s ETag, so a
server that keeps ETags refuses a change made in between (`412`). It stops at the first file that fails, so it is not
all-or-nothing.

## The document graph

`load` gives back the **document graph**. Loading is the processor's only operation; everything after it is a
member of the graph, or the rendered layer's `render(graph)`.

<!-- generated: members: graph members (tools/gen-api.py docs) -->
| Member | TypeScript | Python | C++ | What it is |
|---|---|---|---|---|
| the root file | `root` | `root` | `root()` | the file `load` was given |
| every file read | `documents` | `documents` | `documents()` | by path: the root, then in first-read order; never shrinks |
| overrides | `overrides` | `overrides` | `overrides()` | by name, each as config text; never saved |
| change an override | `setOverride(name, text)` | `set_override(name, text)` | `set_override(name, text)` | see [Overrides](variables.md#overrides) |
| every place an include line is read | `edges()` | `edges()` | `edges()` | the line, the specs it gave, the files it matched |
| what is not read yet | `unread()` | `unread()` | `unread()` | the edges naming a file not read yet ([An include an edit added](variables.md#an-include-an-edit-added)) |
| variables | `variables(name?)` | `variables(name=None)` | `variables([name])` | every `set` line's and snippet parameter's `$name`, then the overrides |
| problems | `diagnostics` | `diagnostics` | `diagnostics()` | a property: each file's syntax problems, then the include, `set` and `snippet` problems found |
| read what is unread | `read()` | `read()` | `read()` | see [An include an edit added](variables.md#an-include-an-edit-added) |
| write the changes back | `save(writer)` | `save(writer)` | `save(writer)` | `save` ([Saving](editing.md#saving)) |
<!-- end generated -->

`graph.diagnostics` leaves out the problems only rendering finds (bad values E4xxx, an unknown variable E5001, an
unknown snippet E5003, a wrong count E5004, too many directives E5008); `render(graph).diagnostics` has every one.

### Documents

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

A document's `replace_with_text` takes any text, broken or not (an undo, a formatter's output), leaves `saved_text`
alone, and detaches every handle into the document (below).

### Statements

A document's `block`, and every statement's block, holds **statements**, in order. Each statement has a `kind`:

| Kind | What it is | Its own members |
|---|---|---|
| `directive` | a directive | `name`, `values`, `block`, `rename(name)`, `set(text)` |
| `extension` | a line a registered extension owns, written `@` and its name: `@include "f.conf";` | `name` (`include`, without `@`), `values` (the path), `block` (its `@set` lines), `set(text)`; no `rename` (the extension owns the name) |
| `set` | `@set $name value...;` | `variable`, `values`, `set(text)` |
| `snippet` | `@snippet name $param... { ... }` | `name`, `parameters`, `block` |
| `use` | `@use name value...;` | `snippet_name`, `snippet`, `snippets()`, `values`, `set(text)` |
| `unreadable` | a line that does not parse, a malformed `@set`, `@snippet` or `@use`, a second `@set` (or `@snippet`) of one name in one block, or an `@name` no extension owns (E3008) | none |

The first token decides the kind: a statement whose name starts with `@` is one of the last five, and any other is a
directive, whatever its name (`use epoll;` is a directive named `use`). Each kind has only the members that can
succeed on it: narrow by `kind` in TypeScript (a union), with `match` in Python (a class per kind), with
`as<T>()` in C++ (an `std::optional` of the kind's handle).

Every statement has `document`, `parent` (the statement whose block holds it), `place`, `text`, `copies()`,
`replace_with_text(text)` and `remove()`. A block is the sequence of its statements, in every layer: iterate it,
count it, index it, then `directives(name)`, `walk(...)` (every statement at any depth), `insert_statements(index,
text)` and `add_statements(text)`.

### Values

A statement's `values` are **written values**, each with a `kind`:

| Kind | Written | Its own members |
|---|---|---|
| `word` | `20hz` | none |
| `string` | `"10.0.60.31"` | none |
| `list` | `[1, 2]` | `items` |
| `slice` | `c[1~2]`, `$src[0~3]` | `name` (a word or a reference), `start`, `end` (a word or a reference; absent when not written) |
| `index` | `c[0]` | `name` (a word or a reference), `index` |
| `reference` | `$pixels` | `name`, `declaration`, `resolutions()` |

Every value has `text` (exactly as written), `place`, `statement`, `list` (the list it is an item of, if any),
`set(text)`, `replace_with_text(text)` and `remove()`. `set(text)` replaces it with exactly one value and keeps the
handle: the same object stays in its statement, with the new text, and takes the new value's kind (`80` set to
`[1, 2]` is a list afterwards). `replace_with_text(text)` may write several values, and detaches the handle.

### Copies: every place a line is read

A line can be read at several places: a file included twice, a snippet used twice. Each place is a **copy**:
`copy.statement` is the line, `copy.via` the include and `use` steps that bring it there, innermost first (empty at
the root). `statement.copies()` lists every copy in the order rendering meets them; it is empty for a line nothing
reaches (a snippet never used, a file no include reaches any more). `graph.edges()` lists every copy of every
include line, with the `specs` the extension gave there and the `targets` it matched; `document.included_by()` is the
edges that splice that document in.

## Where new text goes

- `set` replaces the values from the first to the last, comments between them included. On a line with no values
  it puts one space, then the text, after the name (on a `@set` line, after its `$name`). An empty text removes the
  values and the space before them.
- A value's `remove()` deletes it and the space before it; in a list, the item and its comma (the one after it, else
  the one before it). Comments and line breaks between the item and that comma stay; a line left empty goes.
- Inserted statements take the indentation of the block's statements. In an empty block they take the parent
  line's indentation plus the file's indentation step (the leading spaces of its first indented line, else four
  spaces). Inner lines keep their own indentation relative to the first. Line breaks are the file's own (`\r\n` or
  `\n`). An empty block is opened over lines; in a block holding only comments, the statements go just before its
  `}` line.
- Statements inserted before a statement go before the comments it owns.

### The comments a statement owns

A statement owns the comment lines directly above it (with no blank line between) when it starts its line, and a
comment after its last token on the same line. Its `text` and `place` run from the first comment it owns to the last.
`remove()` and `replace_with_text` take the comments with it, and a line left empty goes too. In `# far` / blank /
`# near` / `b 2; # end`, `b`'s text is `# near` through `# end`, and removing `b` leaves `# far`. For `a; b; # c`
the trailing comment is `b`'s.

## Renaming

`rename` on a directive changes its name and keeps the handle and its values. `rename` on a variable changes only
the `$name` on its `@set` or `@snippet` line; the `$name`s that read it are left as written, so a program that wants
them renamed too edits each of `variable.references()`. A new variable name must not make a second `@set` of that
name in its block (E5002).

## Handles

Every statement, value and variable is a **handle**: one object per written thing for the graph's life, so identity
(`===`, `is`, `==` in C++) holds across edits. A handle follows its tokens: an edit elsewhere in the file leaves it
pointing at the same text, at its new place. In C++ a handle shares ownership of its graph, so it never dangles.

A handle whose tokens an edit removed is **detached**: every member but `kind` throws a detached error, so a program
never reads stale text by mistake.

- `set` and `rename` keep the handle they are called on (only its values or its name change).
- `replace_with_text` and `remove()` detach the handle they are called on, and any handle inside what they replaced.
  `replace_with_text` returns the new handles.
- A document's `replace_with_text` detaches every handle into that document; the document's own handle stays.

## What is stored and what is worked out

The graph stores only the texts (and each `saved_text`), the overrides, and which files were read. Everything else
(copies, edges, variables, resolutions, the problems found, the rendered tree) is worked out from those when asked,
and worked out again after any edit. The lists those members return are snapshots of one moment; the statements,
values and variables in them are live handles.

Orders: `documents` is the root, then first-read order. `copies()`, `edges()`, `wins()`, `shadowed_at()`,
`resolutions()` and `snippets()` are in the order rendering meets them. `variables()` is each document in order, and
in it each `$name` of a `@set` or `@snippet` line in text order, then the overrides in `overrides` order (a new name
goes at the end).

Not part of this layer: creating or deleting files, several root files in one graph, identities that outlive the
process, and a whole-file formatter.
