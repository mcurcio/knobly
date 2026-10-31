# Sources and extensions

The core does no input or output. Where files come from is a **document source**, where saved files go is a
**writer** ([Editing and saving](editing.md#saving)), and what an `@name` statement splices in is an **extension**.
A processor is made with a source and its extensions, and everything else follows from them:

<!-- generated: members: processor (tools/gen-api.py docs) -->
|  | TypeScript | Python | C++ |
|---|---|---|---|
| make | `knobly({ source, extensions? })` from `knobly/written` | `Processor(source=..., extensions=None)` from `knobly.written` | `processor({.source, .extensions})` from `knobly::written` |
| load the files as written | `processor.load(path, { overrides? })` | `processor.load(path, overrides=None)` | `processor.load(path, {.overrides})` |
| read files an edit added | `graph.read()` | `graph.read()` | `graph.read()` |
| render | `render(graph)` from `knobly/rendered` | `render(graph)` from `knobly.rendered` | `render(graph)` from `knobly::rendered` |
| compare | `before.diff(after, { key? })` | `before.diff(after, key=None)` | `before.diff(after, {.key})` |
<!-- end generated -->

## Document sources

A document source has two methods: `resolve(spec, context)` gives the paths a spec names (a path, or a glob with `*`
and `?` in its last part; none means not found: E3001 for a path, the warning W3005 for a glob), and `read(path)` gives a file's text. If either throws, the
render reports E3004 at the include line (for the root file, `load` throws a read error). In TypeScript both return
promises; in Python and C++ both are plain calls.

<!-- generated: members: sources (tools/gen-api.py docs) -->
| Source | TypeScript | Python | C++ |
|---|---|---|---|
| texts held in memory (tests, editors) | `memorySource(files)` from `knobly` | `memory_source(files)` from `knobly` | `memory_source(files)` from `knobly` |
| the filesystem | `fileSource()` from `knobly/node` | `file_source()` from `knobly.files` | `file_source()` from `knobly::files` |
| `fetch` (paths are URLs) | `fetchSource(fetch)` from `knobly/browser` | none | none |
<!-- end generated -->

A **memory source** reads the map it was given at every call, so a memory writer over the same map saves into what
the next load reads: tests and editors use the pair to work without a disk. The file source resolves an include
against its parent's directory; the paths it gives are the keys of `documents` and the paths in every message (how
they are spelled differs per binding: [How the bindings differ](differences.md#paths)). The fetch source never fetches
in `resolve`, so a missing remote file is E3004 (the read fails), not E3001, and a glob resolves to nothing (W3005).

A program can write its own source, for example to record which files a load read. `main.conf` includes
`sink.conf` twice; the source sees one read of each file:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/custom_source.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/custom_source.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/custom_source.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/custom_source.txt"
```

`load` resolves its `path` through the source as an include spec is resolved (with an empty parent path), so the
root has one path however it is written.

## The include extension

`include()` is the one extension knobly ships: it owns `@include "path";` and names the files to splice in.
The extension only names files: knobly resolves and reads them through the source, reads each file once per load,
applies the line's block of `@set` lines, and checks loops and limits. What a config may write with it is in [the
language](language.md#including-files-an-extension).

## Writing an extension

An **extension** owns one statement name and turns each use of it into specs of files to splice in its place. It has
`directive` (its name, without `@`) and `specs(use)`, where `use` has the line's `values` (expanded values, the same
type a rendered directive's values are; the low level never hands an extension a rendered type) and its `origin`.
`specs` returns a list of texts. In Python an extension is any object with a `directive` attribute and a `specs(use)`
method, and a bare `str` returned is refused as E3006 (Python would read it as a list of letters); in C++ it derives
`knobly::written::extension`.

To refuse a use at a place, throw a diagnostic error from a value's or the use's `error(message, code)`; it is
recorded as thrown. Anything else thrown becomes E3006 at the line, and so does a diagnostic error whose code is a
warning (`W3005`): a warning is never thrown, so throwing one is the extension's mistake. An extension's statement is written with `@`, so
its name is never reserved for directives: `include "f.conf";` is a directive named `include`, and an `@name` no
registered extension owns is E3008. Every binding refuses an extension named `set`, `snippet` or `use`, or two
extensions with one name, when the processor is made (a misuse error).

## The files behind a render

A render's `graph` is the document graph it was rendered from: `root`, `documents` (each file read, by path, root
first, then in first-read order, with its text and syntax tree), `edges()` (one per place an extension line is read:
the line, the specs it gave and the paths it spliced, empty when resolving or reading failed), the variables, and the
edits and save of [the low level](editing.md#the-document-graph). `render` takes any object with the document graph's
public members ([`spec/spec.md`](https://github.com/mcurcio/knobly/blob/main/spec/spec.md) 7.0), and a render's
`diff` takes any other render.
