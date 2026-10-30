# Variables, snippets and includes

The low level shows what the rendered tree works out: which files were read and from where, every variable, and
which definition each `$name` reads at each place. The rules themselves (which `@set` a `$name` reaches, and which
definition wins) are taught in [the language](language.md) and specified, with one precedence table, in
[`spec/expansion.md`](https://github.com/mcurcio/knobly/blob/main/spec/expansion.md).

## Which files were read, and where each variable wins

The split config again ([Getting started](getting-started.md) shows its files): `main.conf` sets `$pixels` and
`$leds_host`, and includes `sink.conf` at lines 19 and 24, each with its own `$name` and `$host`. The program gives
`leds_host` as an override, which wins over the file's default:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/variables.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/variables.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/variables.cpp:main"
    ```

It prints (TypeScript prints each path absolute, starting with the folder it ran in: see [Paths](differences.md#paths)):

```text
--8<-- "examples/expected/variables.txt"
```

Read the table this way: `$pixels` is set at `main.conf:4` and wins at `sink.conf:6` twice, once per include line
(`wins()`). The file's `$leds_host` (`main.conf:5`) is shadowed at `main.conf:21` (`shadowed_at()`) by the override,
which wins there.

A **variable** is a `@set` line's `$name`, a snippet's parameter, or an override the program gives. Its `kind` is
`set`, `parameter` or `override`, and each kind is its own type with only the members that can succeed on it
(`SetVariable`, `Parameter`, `OverrideVariable`; C++ `set_variable`, `parameter`, `override_variable`). Narrow it
before using them:

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

## What each `$name` reads

A **reference** is one `$name` written as a value. It has two answers to "which variable is this?":

- `declaration`, by where it is written, in its own file only: nearest first, block by block outward, the `@set` of
  that name above it in that block, then the parameter of that name when the block is a snippet's body. Absent when
  there is none: a `$name` in an included file that the including line's block sets is free in its own file.
- `resolutions()`, one per copy of its line: at that copy, the `winner` (the variable it reads there, or absent when
  nothing of that name is visible, which rendering reports as E5001), `shadowed` (every other variable of that name
  visible there, the next one to win first), and `values` (the winner's values: its `@set` line's, or for a parameter
  the `@use` line's values bound to it; empty for an override or when nothing wins).

The winner is the language's rule, unchanged: the nearest `@set` or parameter; a `@set` in an include line's block
wins over every `@set` inside the files it splices in; an override wins over every `@set`, never over a parameter.
When `main.conf` is `@include "f.conf" { @set $a 2; }`, `f.conf` is `@set $a 1;` then `x $a;`, and `a` is an
override, the `$a` on `x` reads the override, and its `shadowed` lists `main.conf`'s `@set $a 2;` first, then
`f.conf`'s `@set $a 1;` (shared case `shadowed-next-first`).

A `@use` line has the same pair for its snippet: `snippet` by where it is written, `snippets()` per copy.

## Overrides

An **override** is a value the program gives a variable without editing a file ([Getting
started](getting-started.md#overrides-from-the-program) loads with one). `graph.overrides` holds them, by name, as
config text. `set_override(name, text)` adds or changes one, and `set_override(name, absent)` (TypeScript
`undefined`, Python `None`, C++ `std::nullopt`) removes it, without a reload. An override has one variable object per
name for the graph's life, so a program can hold on to it. Overrides are never saved.

`load` and `set_override` run the same check of an override
([`spec/spec.md`](https://github.com/mcurcio/knobly/blob/main/spec/spec.md) 6.3), so they refuse the same texts
with the same errors. The text is parsed with the grammar's `valuesText` rule: one or more values without a `$name`,
over any number of lines (`"1\n2"` is two values), not ending in a comment. Anything else is a bad text error located
in the text, and nothing changes: `1;` is E2001 at its `;`, `1 $b` is E2001 at the `$b`, and the empty text is E2001
at 0:0. A name that is not letters, digits and `_` is a misuse error, the same as for a variable's `rename`.

## Snippets and their copies

A snippet is a named block of directives with parameters; `@use` puts a copy of its body where the line is. Each
copy of a body directive renders with the place it was written and the `@use` step that brought it:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/snippets.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/snippets.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/snippets.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/snippets.txt"
```

Both nodes' `seed` is written once, at `main.conf:2:5`; the step says which `@use` it came through. A problem inside
a body is reported at each use of it, with the same steps.

Every directive, value, unreadable statement and diagnostic carries an **origin**: `place`, where the text was
written (a file and a span, or an override), and `via`, the steps that brought it to where it is read, innermost
first. A step is a `variable`, a `use` or an `extension` (an include line), with its name and the place of the
reference. In the split config, the `leds` sink's `target` comes from the override `leds_host`, through `$host` in
the include block, through the include line, so its value's `via` is `variable leds_host`, `variable host`,
`extension include`, and its `place` is the override.

Lines and columns are counted from 0 in the API; the people forms (`String(place)`, `str(place)`,
`to_string(place)`) and `format_diagnostic` count from 1. What a column counts differs per binding ([How the
bindings differ](differences.md#positions)).

## An include an edit added

An edit can add an include line, or change one to name another file. Until that file is read, the graph lists the
include copy in `graph.unread()`, and `render` shows it as an unreadable statement with reason `unread` at the
include line, with E3007 in `diagnostics`, so a change list calls what it held `unknown`, not removed.
`graph.read()` (a promise in TypeScript) reads what is missing, through the source the graph was loaded with,
repeating until nothing new is named, and returns the paths it read. Every unsaved text stays, and no file is read
twice:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/include_read.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/include_read.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/include_read.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/include_read.txt"
```

A file that could not be found or read stays that way for the graph: `read()` does not try it again. Load again for
a fresh look.

The include extension's own rules (one quoted path, globs, the `@set`-only block, a file read once per load) are in
[the language](language.md#including-files-an-extension); writing an extension of your own is in [Sources and
extensions](sources.md).
