# Walking, addresses and reloads

This page is for a program that keeps running while its config changes. rasl is one: its config has a `graph` block
of `node` directives, each named by its second value (`node DdpSink leds { ... }`), and when a file changes it wants
the list of what changed, with each node keeping its identity when lines move.

## Walking the directives

A rendered directive has `name`, `values`, `block` (absent when written without a block), `unreadable`, `parent`,
`origin` and `written` (the directive as written, on the low level: the line to edit). Every block has one shape in
every layer: iterate it, count it, index it, ask `directives(name)`, or `walk` it.

A walk visits every directive below a block, depth first in written order. Each binding passes over a directive's
block in its own way:

- TypeScript walks with a callback: return `WalkControl.Skip` to pass over the directive's block,
  `WalkControl.Stop` to end the walk;
- Python's `walk` is a generator: `descend=` returning `False` passes over a block, and `break` ends the walk;
- C++'s `walk` is a range for a range-for: a `descend` predicate passes over a block, and `break` ends the loop.
  The range reads a snapshot, so editing during it is allowed.

[Getting started](getting-started.md#a-processor-loading-and-rendering) walks into `graph` only.
`closest(predicate)` gives this directive or the nearest enclosing one that matches. A line read at two places (a
file included twice, a snippet used twice) renders as two directives with the same `written` object, so an edit to it
shows in both.

### Unreadable statements

A statement that could not be read stays in its block's `unreadable` list, with its `reason`, its `origin` and
`written` (the statement as written). It has no name and no address: what it would have been is unknown. Its block
is not expanded, so problems inside it are not reported.

| Reason | Why |
|---|---|
| `syntax` | the parser could not read it |
| `expansion` | a variable, `@set`, `@snippet` or `@use` failed (unknown name, wrong count, loop, limits) |
| `value` | a value broke a rule checked when expanding (E4001) |
| `extension` | an include line (or another extension's line) failed |
| `unread` | an include line's files are not read yet: an edit added or changed it, and `graph.read()` has not run (E3007) |

## Readers

Each value is an **expanded value**, the low level's own object, the one an extension's use holds too: a `kind`
(word, string, list, slice, index; never reference), a canonical `text`, an `origin`, and readers. A reader that
meets the wrong value throws a diagnostic error placed on that value. [Getting started](getting-started.md#reading-values)
reads one of each.

<!-- generated: members: readers (tools/gen-api.py docs) -->
| Reads | TypeScript | Python | C++ | Error |
|---|---|---|---|---|
| a bare word | `word()` | `word()` | `word()` | E4002 |
| a word or a string, decoded | `string()` | `string()` | `string()` | E4002 |
| a number (JSON's number syntax: `8080`, `0.5`, `-2E-2`; not `20hz`, `01`, `.5`) | `number()` | `number()` | `number()` | E4004, E4002 |
| a whole number within ±(2^53-1) (`1.0` is not one) | `integer()` | `integer()` | `integer()` | E4005, E4002 |
| `true` or `false` only (`on`, `yes` are not) | `boolean()` | `boolean()` | `boolean()` | E4006, E4002 |
| a list's items, each with its own origin | `list()` | `list()` | `list()` | E4002 |
| a slice or an index | `slice()` | `slice()` | `slice()` | E4002 |
<!-- end generated -->

A slice reader gives a slice (`name`, `start`, `end`, a side absent when not written) or an index (`name`,
`index`). Two expanded values are equal when their texts are equal (Python `==`, C++ `==` and `std::hash`).

### From a rendered value to what is written

Three members lead from a rendered value back to the low level, where it can be edited:

- `written`: the written value on the same line, the line of the statement the value is read in: for
  `max_count $pixels;`, the `$pixels` there; for a value written where it is read, the value itself. Never absent.
  Editing it edits that one line, which every copy of the line shares. A value's `set(text)` keeps the handle, so a
  loop that sets every directive's `written` value meets the shared handle twice and both calls succeed.
- `definition`: the written value at the end of its chain (for `max_count $pixels;`, the `2284` of
  `@set $pixels 2284;`); absent for an override. Editing it changes every use.
- `chain`: one reference resolution per `$name` the value came through, starting with the `$name` written on the
  directive's own line. Each says which variable won at this place, and which it shadowed. Empty for a value written
  where it is read.

So `chain[0].winner` is the variable to change for every place that reads it ([Editing and
saving](editing.md#change-a-variable-then-save)), and `chain[0].reference` (the same handle as `written`) is the
`$name` on this line, to replace with a value of its own. To change one copy of an included file only, edit what that
copy is given (its include block's `@set` line, at the include step of `chain`).

## Addresses and the key rule

An **address** is a directive's identity across renders: from the top level down, each step is the directive's
name, its key (what the key rule returned, or none), and its occurrence among earlier siblings with the same name and
key (counting from 0). It is unique within one render. A file included at two places, or a snippet used twice, lands
at two addresses.

The **key rule** is the program's, given where addresses are asked for: to `addresses` and to `diff`. It is called
once per readable directive, parents first, with the rendered directive, and returns a key or nothing. What it
throws comes out of `addresses` or `diff` unchanged (a bug in the program, not in the config). Without a key rule a
directive is named by its position among same-name siblings, so moving a line changes addresses; with rasl's rule a
node keeps its address when it moves:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/addresses.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/addresses.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/addresses.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/addresses.txt"
```

<!-- generated: members: addresses (tools/gen-api.py docs) -->
|  | TypeScript | Python | C++ |
|---|---|---|---|
| every directive's address, a map from directive to address | `rendered.addresses({ key? })` | `rendered.addresses(key=None)` | `rendered.addresses({.key})` |
| for people: `graph > node "leds" > max_count` | `address.toString()` | `str(address)` | `to_string(address)` |
| as a map key (JSON, the same bytes in every language) | `address.text` | `address.text`, or the `Address` itself (hashable) | `address.text()` |
| enclosing | `address.parent` | `address.parent` | `address.parent()` |
<!-- end generated -->

A key rule that reads values from variables makes identity follow config edits; that is the program's choice.

## What changed between two loads

`before.diff(after, key)` compares two renders by address, under the key rule given. The sample renders the split
config, rewrites `main.conf` on disk (sets `$pixels` to `2400` and deletes the `hue_ramp` node), loads and renders
again:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/diff_reload.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/diff_reload.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/diff_reload.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/diff_reload.txt"
```

Each change carries its address and its directives (`before`, `after`, or both):

| Change | When |
|---|---|
| added | only in `after` |
| removed | only in `before`, and its block in `after` has no unreadable statement |
| unknown | only in `before`, but its block in `after` (or the top level) holds an unreadable statement: the broken line may be it |
| changed | in both, and its own values (by canonical text) or whether it has a block differ |

An added, removed or unknown directive is listed alone, never with the directives inside it. A changed or unchanged
directive's block is compared at its own addresses. Order: removed and unknown in `before`'s walk order, then added
and changed in `after`'s. Renders with diagnostics can be compared. A comment or a quote style is no change; a
number's spelling is (`0.5` to `0.50`), because values compare by text. To group changes by its own unit (a rasl
node), a program uses `directive.closest(...)` or `address.parent`.

A change's `kind` is one of `added`, `removed`, `changed` and `unknown` in every binding.
