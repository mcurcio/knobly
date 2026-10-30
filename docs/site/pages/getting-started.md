# Getting started

This page is for a program that reads knobly config: it makes a processor, loads a file, renders it, and reads
the values it wants. Problems in the config are reported, never thrown; the few things that do throw are at the end.

The samples read [`fixtures/rasl/split`](https://github.com/mcurcio/knobly/tree/main/fixtures/rasl/split), the
config of rasl, the light controller knobly was built for. `main.conf` sets two variables and includes
`sink.conf` twice, at lines 19 and 24, each time with its own `$name` and `$host`:

```conf
--8<-- "fixtures/rasl/split/main.conf"
```

`sink.conf` is one sink:

```conf
--8<-- "fixtures/rasl/split/sink.conf"
```

## A processor, loading and rendering

A **processor** is made once, with two things: the **document source** (where files come from) and the
**extensions** (such as include). Loading is its only operation, so two loads are always read the same way.
`load(path)` reads the root file and every file it splices in, each once however many places include it, and gives
back the **document graph**: the files as written. `render(graph)`, in the rendered layer, builds the **rendered
tree** from the graph: the directives a program reads, with `@set`, `@snippet`, `@use` and `@include` lines worked
out (they never appear; what they produce does, in their place).

The file source reads files from disk; `include()` turns on the `@include` statement (without it, `@include` is a
problem, E3008). The sample prints each file the load read, then walks the rendered tree and prints each `node`
with the place it was written:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/load_render.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/load_render.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/load_render.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/load_render.txt"
```

A walk visits every directive depth first, in written order. This one goes into `graph` only and passes over every
other directive's block. Both sinks say `sink.conf:2:1`: a file included twice renders as two directives with the
same origin. [Walking, addresses and reloads](walking.md) has the rest.

`render` reads no file, so it can be called again after an edit, and two calls never disagree about the same texts.
A rendered tree is a snapshot: an edit made after `render` does not change it; render again to see the edit.

## Reading values

A directive has a `name`, its `values`, and its `block` (the directives inside it, absent when written without a
block). Each value has a `kind` (word, string, list, slice or index), a canonical `text`, an `origin`, and
**readers**, one per type a program wants. A file of one directive per kind:

```conf
--8<-- "examples/fixtures/values/values.conf"
```

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/read_values.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/read_values.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/read_values.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/read_values.txt"
```

There is no reader that guesses a value's kind: `8080` and `true` are words until a program reads them as a number
or a boolean, and quoting means text (`"8080"` is a string; the number reader on it is a problem, E4002). A
single-quoted string is raw, so `'C:\new'` is the text `C:\new`. A reader that meets the wrong value throws a
diagnostic error placed on that value (below). Every reader, and what each refuses, is in [Walking, addresses and
reloads](walking.md#readers).

### Canonical text

`text` is the same in every binding, and two values are the same exactly when their texts are equal:

- a word as written;
- a string in double quotes, with `\` `"` newline tab and carriage return escaped (`'single'` becomes `"single"`,
  and a raw `'C:\new'` becomes `"C:\\new"`);
- a slice `name[start~end]` with either side empty when absent, an index `name[i]`, in decimal, `name` being the
  word its slice name holds (`$src[0~3]` with `$src` holding `leds` is `leds[0~3]`);
- a list `[` + its items' texts joined by `, ` + `]`, with comments, line breaks and a trailing comma dropped
  (`[1, # warm` / `'two',` / `[3,4,],]` is `[1, "two", [3, 4]]`);
- a value from a variable has the value's text, never `$name`.

## Overrides from the program

An **override** is a value the program gives a variable when it loads a file, without editing the file (rasl's
`--set leds_host=...`). It is config text, made with `quote` (a program's string, written as a knobly string) or
`text` (text already written in knobly syntax: `text("8080 443")` is two values). An override wins over every
`@set` of its name, at any depth and in every included file, so a `@set` acts as the default; it never wins over a
snippet parameter ([`spec/expansion.md`](https://github.com/mcurcio/knobly/blob/main/spec/expansion.md) 6 has the
whole precedence table).

The sample loads the split config twice with one processor, without and with `leds_host`:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/overrides.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/overrides.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/overrides.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/overrides.txt"
```

Only `leds` changes: its `$host` comes from `$leds_host`, while `porch` sets its own. The low level can also change
an override later without a reload ([Variables, snippets and includes](variables.md#overrides)).

## Problems are diagnostics

A file with problems still loads. Every problem is a **located diagnostic**: a `code` (the stable part, such as
`E5001`), a `message` for people (which may differ between bindings), the `place` it is about, and `via`, the steps
that brought it there (an include line, a snippet's use, a variable). The rest of the file is read, and a broken line
stays in place as unreadable, so it never hides its neighbours. Diagnostics come in order: each file's syntax
problems, files in the order they were first read, then the load's problems in the order the load met them.

`main.conf` has a missing `;`, an unknown variable, and includes `part.conf`, which has another:

```conf title="main.conf"
--8<-- "examples/fixtures/broken/main.conf"
```

```conf title="part.conf"
--8<-- "examples/fixtures/broken/part.conf"
```

`format_diagnostic(d, graph)` prints one for people: the place counted from 1, the code and message, the source line,
a caret line under the span, and one line per step:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/diagnostics.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/diagnostics.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/diagnostics.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/diagnostics.txt"
```

`graph.diagnostics` lists the problems the low level finds; `render(graph).diagnostics` adds the ones only rendering
finds (an unknown variable, a bad value, a wrong count of snippet values), so a program prints the render's. Every
code is listed in [Diagnostics and your own checks](diagnostics.md#error-codes).

## Exceptions

What is wrong in the config is a diagnostic. An exception means the program cannot go on as written, and there are
two sorts ([`spec/spec.md`](https://github.com/mcurcio/knobly/blob/main/spec/spec.md) 2.8):

- **Expected outcomes** extend one base class, the knobly error, so one `catch` handles them all and never hides
  a bug: a root file that cannot be read (a read error, with the root path in `paths`), a reader on the wrong kind of
  value (a diagnostic error, carrying the located diagnostic), an edit's text refused (a bad text error), and a
  writer that failed (a save error, and its lost update error).
- **Program bugs** are outside it: a handle whose text an edit removed, a value of the wrong type where text is
  taken, a bad name, an index out of range.

`missing.conf` does not exist; `main.conf` holds `fps fast;`:

```conf
--8<-- "examples/fixtures/errors/main.conf"
```

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/errors.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/errors.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/errors.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/errors.txt"
```

A load fails only when the source cannot give the root file (or an override is bad: see [Variables, snippets and
includes](variables.md#overrides)); a file that includes a missing file still loads, with E3001 at the include
line. To record a reader's error instead of stopping, run the read through a sink ([Diagnostics and your own
checks](diagnostics.md)).

Every error, per binding:

<!-- generated: members: errors (tools/gen-api.py docs) -->
| Error | TypeScript | Python | C++ | When |
|---|---|---|---|---|
| the text is not what the edit takes | `BadTextError` (`diagnostics`) | `BadTextError` (`diagnostics`) | `bad_text_error` (`diagnostics()`) | an edit ([Editing and saving](editing.md#named-edits-and-a-refused-edit)) |
| a file changed since it was read (`paths`: the conflicting files) | `LostUpdateError` (`paths`) | `LostUpdateError` (`paths`) | `lost_update_error` (`paths()`) | `save` ([Saving](editing.md#saving)) |
| the writer failed | `SaveError` (`paths`, `cause`) | `SaveError` (`paths`, `__cause__`) | `save_error` (`paths()`, `std::nested_exception (std::rethrow_if_nested)`) | `save` ([Saving](editing.md#saving)) |
| the root file cannot be read | `ReadError` (`paths`, `cause`) | `ReadError` (`paths`, `__cause__`) | `read_error` (`paths()`, `std::nested_exception (std::rethrow_if_nested)`) | `load` |
| the handle's tokens are gone (a bug) | `DetachedError` | `DetachedError` | `detached_error` | [Handles](editing.md#handles) |
| knobly text was not given (a bug) | `TypeError` | `TypeError` | `argument_type_error` | a number, `null` / `None` or anything else where text is taken |
| a bad name (a bug) | `MisuseError` | `ValueError` | `misuse_error` | `rename`, `setOverride`, an override `load` takes |
| an index outside the block (a bug) | `RangeError` | `IndexError` | `index_out_of_range` | `insertStatements` |
<!-- end generated -->

A lost update error is a save error. In TypeScript and Python a detached error is a `ReferenceError`; in C++ the
program bugs derive `std::logic_error`, and a save or read error nests its cause (`std::rethrow_if_nested`). There is
no error for a `set` on a parameter or an override: those kinds have no `set` member.
