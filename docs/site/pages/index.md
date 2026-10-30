# Quickstart

villanelle is a small configuration language: directives ended by `;`, `{ }` blocks, lists, slices, `#` comments,
and variables and snippets written as `@` statements. It has one grammar and three bindings, TypeScript, Python and
C++, with the same parts under each language's own names. Every sample on this site has a tab per language; pick
one and every page follows it.

A program can work at three layers, each built on the one below:

- **the syntax tree**: `parse(text)` reads one text into tokens and a tree, every character in exactly one token
  ([The syntax tree](syntax.md));
- **the files as written** (the low level): `load(path)` reads a file and every file it includes into a document
  graph, which shows the variables and include lines, takes edits and saves them back with comments and layout
  kept ([Editing and saving](editing.md));
- **the rendered tree**: `render(graph)` works out variables, snippets and included files into the directives a
  program reads, each value with the place it was written ([Getting started](getting-started.md)).

## Get it

villanelle depends on nothing but each language's standard library (and, in TypeScript and Python, the ANTLR
runtime their generated parsers use). Nothing is installed system-wide: each release on
[GitHub](https://github.com/mcurcio/villanelle/releases) carries one file per language that goes into your project.

=== "TypeScript"

    The `npm pack` tarball of each release, for Node 24 or later (it is not on npm):

    ```bash
    npm install https://github.com/mcurcio/villanelle/releases/download/v<version>/villanelle-<version>.tgz
    ```

    Each layer is its own import path: `villanelle`, `villanelle/syntax`, `villanelle/written`,
    `villanelle/rendered`, `villanelle/include`, and `villanelle/node` for files on disk.

=== "Python"

    The wheel of each release, for Python 3.11 or later (it is not on PyPI):

    ```bash
    pip install https://github.com/mcurcio/villanelle/releases/download/v<version>/villanelle-<version>-py3-none-any.whl
    ```

    Each layer is its own module: `villanelle`, `villanelle.syntax`, `villanelle.written`, `villanelle.rendered`,
    `villanelle.include`, and `villanelle.files` for files on disk.

=== "C++"

    A C++20 compiler and nothing else. Either copy the single header `villanelle.hpp` from the release into your
    project and `#include "villanelle.hpp"`, or let CMake 3.24 or later fetch the release's source archive
    (`villanelle-cpp-<version>.tar.gz`, which carries the generated headers) into your build folder:

    ```cmake
    --8<-- "cpp/tests/consumer/CMakeLists.txt:fetchcontent"
    ```

    `VILLANELLE_RELEASE_URL` and `VILLANELLE_RELEASE_SHA256` are the archive's URL and SHA-256 from the release
    (write them in, or set them). `add_subdirectory` of the extracted archive, or of a copy in your repository,
    works the same way. No Python and no install step is needed by any route; compiled mode and versions are in
    [`cpp/README.md`](https://github.com/mcurcio/villanelle/blob/main/cpp/README.md#using-it).

!!! note
    No release has been made yet. Until then, build the packages from a checkout as the
    [README](https://github.com/mcurcio/villanelle/blob/main/README.md#build-and-test) says.

## Hello

A file, `hello.conf`:

```conf
--8<-- "examples/fixtures/hello/hello.conf"
```

The program makes a processor that reads files from disk, loads the file, renders it, and reads the one value as a
string:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/hello.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/hello.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/hello.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/hello.txt"
```

## A real file

`app.conf` sets a variable and uses it in a `server` block:

```conf
--8<-- "examples/fixtures/quickstart/app.conf"
```

The program reads three settings, each with the reader for the type it wants. `port` is written `$port`; the
rendered tree has already put the variable's value there, so the integer reader reads `8080`. `debug` is a word
until the boolean reader reads it. Problems in a file are never thrown: they are the render's `diagnostics`, here
none.

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/quickstart.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/quickstart.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/quickstart.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/quickstart.txt"
```

## Where next

- [Getting started](getting-started.md): processors and extensions, reading values, overrides, problems and
  exceptions.
- [The language](language.md): what a villanelle file may say.
- Advanced usage: [editing and saving](editing.md), [variables, snippets and
  includes](variables.md), [your own checks](diagnostics.md), [walking and
  reloads](walking.md), [sources and extensions](sources.md), [the syntax
  tree](syntax.md).
- [How the bindings differ](differences.md).

The language-neutral rules every binding follows are in
[`spec/`](https://github.com/mcurcio/villanelle/blob/main/spec/README.md), which wins where this guide differs; the
words are defined in [`spec/glossary.md`](https://github.com/mcurcio/villanelle/blob/main/spec/glossary.md).
