# How the bindings differ

The three bindings have the same parts, generated from one schema
([`spec/schema/api.json`](https://github.com/mcurcio/knobly/blob/main/spec/schema/api.json)), and pass the same
conformance cases. Where they differ, it is by design: each follows its own language's way.

## Names and imports

| | TypeScript | Python | C++ |
|---|---|---|---|
| member names | `camelCase` (`replaceWithText`, `shadowedAt`) | `snake_case` | `snake_case` |
| type names | `DocumentGraph`, `Rendered` | `DocumentGraph`, `Rendered` | `document_graph`, `rendered` |
| a property | `graph.root` | `graph.root` | `graph.root()` |
| make a processor | `knobly({ source, extensions })` | `Processor(source=..., extensions=...)` | `processor({.source, .extensions})` |
| options | an object, `{ key }` | a keyword argument, `key=` | a designated initializer, `{.key = ...}` |
| each layer | an import path (`knobly/written`) | a module (`knobly.written`) | a header and a namespace (`<knobly/written.hpp>`, `knobly::written`) |
| files on disk | `knobly/node` | `knobly.files` | `knobly::files` |
| absent | `undefined` | `None` | `std::optional` (`std::nullopt`) |
| a kind | a union narrowed by `kind` | a class per kind, narrowed by `match` | `as<T>()`, an `std::optional` of the kind's handle |

In C++, alias the namespaces (`namespace vl = knobly;`, `vw`, `vr`) and never write a using-directive: types and
their accessors share names (`place place()`), and the written layer has a `string` and a `list`
([`cpp/README.md`](https://github.com/mcurcio/knobly/blob/main/cpp/README.md)).

## Blocks and walks

Every block is a sequence in every binding: TypeScript's is an `Iterable` with `length` and `at(i)` (undefined out of
range), Python's a `Sequence` (`block[0]`, `len(block)`), C++'s a range with `size()` and `at(i)`. A walk takes a
callback returning `WalkControl.Skip` or `WalkControl.Stop` in TypeScript, is a generator with `descend=` in Python,
and a range with a `descend` predicate in C++.

## Async

TypeScript's `load`, `graph.read()`, `graph.save(writer)`, document sources and writers are async (promises).
Python's and C++'s are plain calls. `render` and `diff` are plain calls in every binding.

## Positions

Lines and columns count from 0 in the API, and from 1 in the people forms and `format_diagnostic`. What a column and
an offset count differs:

| TypeScript | Python | C++ |
|---|---|---|
| UTF-16 code units, JavaScript's string unit (`text.slice(start.offset, end.offset)` is the spanned text) | UTF-16 code units too, so an offset is not a `str` index once a character outside the Basic Multilingual Plane comes before it | bytes of UTF-8 |

## Paths

TypeScript's file source makes paths absolute; Python's and C++'s stay as written, joined lexically with the
including file's directory (a relative root stays relative). The "It prints" blocks on this site show the relative
form: run as it is, a TypeScript sample prints `/home/me/proj/main.conf` where the block shows `main.conf` (its test
cuts the run folder from what it prints before comparing).

## Errors

The error groups are the same in every binding (the table is in [Getting started](getting-started.md#exceptions)):
expected outcomes extend the knobly error, program bugs do not.

| | TypeScript | Python | C++ |
|---|---|---|---|
| a bad name | `MisuseError` | `ValueError` | `misuse_error` |
| an index outside a block | `RangeError` | `IndexError` | `index_out_of_range` |
| not text where text is taken | `TypeError` | `TypeError` | a compile error |
| a save or read error's cause | `cause` | `__cause__` | a nested exception (`std::rethrow_if_nested`) |
| the base of program bugs | the language's own errors (`DetachedError` is a `ReferenceError`) | the language's own errors (`DetachedError` is a `ReferenceError`) | `std::logic_error` |

## Refused at compile time in C++

What TypeScript and Python refuse at run time, C++ refuses when the program compiles: `render` of a document instead
of a graph, a `std::string` where config text is taken, a program code without `/`, a key rule that returns
something other than an optional string, `report()` on a written statement, and `view()` of a temporary. Each has a
compile-fail test in `cpp/tests/compile_fail/`.

## Threads and memory

- **TypeScript and Python** objects are garbage-collected; the bindings make no promise about threads.
- **C++**: every object a layer returns is a small handle that shares ownership of the graph or render it belongs
  to, which lives while any handle of it does, so nothing returned can dangle. Copying a handle or destroying one on
  another thread is safe (the count is atomic); nothing else is, not even reading one graph from two threads through
  `const`. Every object of a graph lives until the graph dies, detached ones included, so a process that keeps one
  graph for a long run of edits should load a fresh graph from time to time.

## What each binding has

Python and C++ have no fetch source or fetch writer (`knobly/browser` is TypeScript only). The C++ syntax and
written layers also build with `-fno-exceptions -fno-rtti`, where a thrown error is written to standard error and
`std::abort()` is called instead.
