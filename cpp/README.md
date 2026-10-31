# knobly for C++

A header-only C++20 library: one include directory and one CMake target, `knobly::knobly`, with no
dependency beyond the standard library (owner, 2026-10-25: "I don't want villanelle dependent on third party
libraries"). It has the three layers TypeScript and Python have, with the same names in snake_case. The user guide,
with every sample in TypeScript, Python and C++, is [https://mcurcio.github.io/knobly/](https://mcurcio.github.io/knobly/) (source:
[`docs/site/pages/`](../docs/site/pages/)); every C++ sample is a program `ctest` builds and runs (`examples/`).

| Header | Namespace | What it holds |
|---|---|---|
| `<knobly/syntax.hpp>` | `knobly::syntax` | `parse`, the lossless syntax tree |
| `<knobly/written.hpp>` | `knobly::written` | the low level: `processor`, `load`, the document graph you edit and `save` back |
| `<knobly/rendered.hpp>` | `knobly::rendered` | `render(graph)`: the tree after variables, snippets and includes |
| `<knobly/files.hpp>` | `knobly::files` | `file_source()`, `file_writer()`: files on disk |
| `<knobly/extensions.hpp>` | `knobly::extensions` | `include()`: the include extension |

```cpp
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

const vw::processor config({.source = vl::files::file_source(), .extensions = {vl::extensions::include()}});
const vw::document_graph graph = config.load("main.conf");
for (const vl::located_diagnostic& d : graph.diagnostics()) {
    std::cerr << vw::format_diagnostic(d, graph) << '\n';  // the line, a caret under the span, and the steps
}
const vr::rendered tree = vr::render(graph);
for (const vr::directive& d : tree.block().walk()) {
    if (d.name() == "fps") {
        std::cout << d.values().at(0).integer() << '\n';  // a wrong kind throws vl::diagnostic_error, placed
    }
}
for (vw::variable v : graph.variables("pixels")) {      // the written layer: edit, then save
    if (auto set = v.as<vw::set_variable>()) set->set(vl::text("2400"));
}
graph.save(vl::files::file_writer());                   // vl::lost_update_error if a file changed on disk
```

The design's three programs are in `tests/programs/` as a user writes them, built with `-Wsign-conversion` (and
`-Wdangling` on Clang) and run by `ctest` against fixtures with expected output: `sinks.cpp` (an app reading every
sink of a config with includes and `name=value` overrides), `editor.cpp` (edit and save with lost-update protection)
and `lint.cpp` (a third-party tool checking its own schema and reporting diagnostics with places).

**Namespaces: alias them, never a using-directive.** Types and their accessors share names (`place place()`,
`origin origin()`), and the written layer has a `string` and a `list`. So `using namespace knobly::written;`
beside `using namespace std;` makes `string` and `list` ambiguous, and a class
member `vl::place place;` that then names the type hits GCC's "declaration changes meaning". Write
`namespace vw = knobly::written;` and qualify, as every example here does.

**Formatting.** `<knobly/format.hpp>` is opt-in (no other header includes it): it gives every type with a people
form (`place`, `located_diagnostic`, `rendered::address`, each kind list, `diagnostic_code`, ...) an `operator<<` and
a `std::formatter`, both writing exactly its `to_string`. The formatter takes a string's format spec, so width, fill
and alignment work: `std::format("[{:>8}]", vl::value_kind::word)` is `[    word]`. Which types it covers is read from
the schema, so the header is generated whole.

```cpp
#include <knobly/format.hpp>
std::cerr << std::format("{}: skipped ({})\n", u.origin().place(), u.reason());  // lb.conf:11:1: skipped (expansion)
```

**Handles.** Every object a layer returns (a graph, a statement, a rendered directive) is a small handle: copying it
shares the graph or render it belongs to, which lives while any handle of it does, so nothing returned can dangle (a
rendered directive keeps its render and the graph alive). Two handles are equal when they show the same object.
Every list is a `knobly::sequence<T>` and every map a `knobly::ordered_map<K, V>` (insertion order): copying
one shares it, and elements come back by value. A loop over a block, or a `walk()`, reads a snapshot, so editing
during it is allowed. A statement an edit removed is detached: its `kind()` still works and every other member
throws `knobly::detached_error`. **Memory:** every object of a graph lives until the graph dies, detached ones
included, so each edit grows the graph by what it re-parses (about 20 KB for a 50-line document replaced whole):
a process that keeps one graph for a long run of edits should load a fresh graph from time to time.

**Errors.** Problems in the config text are never thrown: `load` returns a graph whose `diagnostics()` lists them,
and `render` returns a tree with the same list. Exceptions mirror the error groups of the other bindings: expected
outcomes derive `knobly::knobly_error` (`diagnostic_error`, `read_error`, `bad_text_error`, `save_error` and
its `lost_update_error`; a `save_error` nests the writer's exception, so `std::rethrow_if_nested` gives the cause),
and program bugs derive `std::logic_error` (`detached_error`, `argument_type_error`, `misuse_error`,
`index_out_of_range`). An edit refused with an exception (`bad_text_error`, `detached_error`, `index_out_of_range`, ...) changes nothing;
one cut short by `std::bad_alloc` may leave its graph part edited and unfit for further use, so drop that graph. `parse` never throws (but `std::bad_alloc`).

**Threads.** Copying a handle or destroying one on another thread is safe (the count is atomic); nothing else is,
not even reading one graph from two threads through `const`.

**Positions** count bytes of UTF-8 (`line` and `column` from 0; the people forms, `to_string` and
`format_diagnostic`, count from 1). **Paths** are UTF-8 text with `/`: `file_source` resolves an include against
its parent's directory by a lexical join (`.` and empty segments dropped, `..` popped), so a relative root stays
relative, as in Python (TypeScript makes paths absolute). They are the keys of `documents()` and the paths in every
message. An include follows an absolute path and any number of `..` as written, so it can read any file the process
can (`@include "/etc/hosts";`), and that file's lines come back as directives and in diagnostics: do not load a
config from someone you do not trust with `file_source()` and the include extension. `file_writer()` stages each file
beside the one it replaces and renames it over: a symbolic link's target is replaced (the link stays), and the new
file keeps the old one's permissions.

## Using it

Nothing is installed: knobly goes into your project or its build folder, by one of three routes. None needs Python;
the release assets carry the generated headers.

- **The single header** `knobly.hpp` (on each GitHub release): every header in one file. Copy it into your
  project and `#include "knobly.hpp"`; nothing else is needed. It is header-only mode only, and every file
  including it compiles every layer.
- **`FetchContent`** of the release source archive (`knobly-cpp-<version>.tar.gz`, on each GitHub release), with
  CMake 3.24 or later. CMake downloads and unpacks it into your build folder:

  ```cmake
  include(FetchContent)
  FetchContent_Declare(knobly
    URL https://github.com/mcurcio/knobly/releases/download/v<version>/knobly-cpp-<version>.tar.gz
    URL_HASH SHA256=<the archive's SHA-256>)
  FetchContent_MakeAvailable(knobly)

  target_link_libraries(my_program PRIVATE knobly::knobly)
  ```

- **`add_subdirectory`** of the extracted archive, or of a copy vendored into your repository (or of `cpp/` in a git
  checkout), then the same `target_link_libraries`.

As a subproject it builds no tests (`KNOBLY_BUILD_TESTS` is on only when it is the top-level project). There is
nothing to link: `knobly::knobly` only adds the include path and C++20. A C++20 compiler is needed by every
route. In a git checkout the public headers are generated at configure time ("Generated code" below), which needs
Python 3.9 or later and `uv`.

**Header-only** is the default: every definition is inline in the headers.

**Compiled mode** keeps the definitions out of every file but one, for programs where compile time matters. Define
`KNOBLY_HEADER_ONLY=0` for every file of the program that includes knobly, and include
`<knobly/implementation.hpp>` in exactly one of them:

```cmake
target_compile_definitions(my_program PRIVATE KNOBLY_HEADER_ONLY=0)
target_sources(my_program PRIVATE knobly_implementation.cpp)  # #include <knobly/implementation.hpp>
```

With `FetchContent` or `add_subdirectory`, `-DKNOBLY_COMPILED=ON` (a cache option of the subproject) defines it
for every user of the target instead; the program still compiles `implementation.hpp` once. Compiled mode also instantiates every template the headers spell once, in
`implementation.hpp` (each header declares it `extern`), so other files do not compile them again.

**Versions.** Every name sits in a versioned inline namespace, `knobly::v<major>_<minor>_<patch>` (a program
writes `knobly::written::processor`), so two knobly versions in one program (a library and the app each
bundling its own) get different symbols instead of breaking the one-definition rule. The version's one home is
`KNOBLY_VERSION_MAJOR`, `_MINOR` and `_PATCH` in `include/knobly/support/config.hpp`: 0.0.0 in the
repository, stamped by the release flow into the archive and the single header.

**Exceptions.** Expected errors throw (see "Errors" above). The syntax and written layers also build with
`-fno-exceptions -fno-rtti`; without exceptions, a thrown error is written to standard error and `std::abort()` is
called instead. Exception classes carry default visibility, so a `catch` in one shared library sees a `throw` from
another.

**Invalid UTF-8** (provisional, pending the owner's ruling): a byte that does not decode is one `BAD_CHAR` token with
E1003; a surrogate's three-byte form (WTF-8) decodes. The rule lives in one function, `detail/text_in.hpp`.

## Generated code

Every public header directly in `include/knobly/` is generated from `spec/schema/` by `tools/gen-api.py`, and
`include/knobly/detail/syntax/parser.gen.hpp` from `grammar/Knobly.g4` by knobly's own parser generator
(`tools/parser/gen.py`; no ANTLR, no Java). Neither is committed (owner, 2026-10-23: "Don't commit the generated
code, just the source"): CMake runs `bash tools/gen.sh cpp` at configure time when they are absent, which needs
Python 3.9 or later and `uv` (for the pinned clang-format the generated code is formatted with). The hand-written
code is `include/knobly/support/` (the library types) and `include/knobly/detail/` (the definitions; the
syntax layer's token loop, error codes, recovery and nesting guard are in `detail/syntax/parse.hpp`).

## Build and test

From the repository root, with CMake 3.24 or later and a C++20 compiler:

```bash
cmake -S cpp -B build -DKNOBLY_SANITIZE=ON   # Catch2 v3 is fetched for the tests
cmake --build build
ctest --test-dir build --output-on-failure
```

`ctest` runs:

- the unit tests (`tests/unit/`, one Catch2 program per file: `unit_<name>`, `unit_format` for `format.hpp`);
- the generated contract of each public header (`contract_<header>`: a declaration without a definition fails to
  link);
- the design's programs (`programs_sinks`, `programs_editor`, `programs_lint`): `tests/programs/run_program.cmake`
  runs each once per folder of `tests/programs/<name>_expected/`, in a fresh copy of `tests/programs/<name>/`, with
  that folder's `args` (one per line), and compares standard output, standard error and the exit status with its
  `stdout`, `stderr` and `status` (and, for the editor, the saved files with its `files/`). To add a run, add a folder;
- the compile-fail tests (`compile_fail_<name>`): each `tests/compile_fail/<name>.cpp` holds one line C++ refuses at
  compile time that TypeScript and Python refuse at run time (`render` of a document, a `std::string` where
  `config_text` is taken, a program code without `/`, a key rule returning `int`, `report()` on a written statement,
  `view()` of a temporary). The test builds it and must fail; `compile_fail_<name>_control` builds it with
  `-DKNOBLY_CONTROL`, which swaps in the nearest valid line, and must succeed, so the failure is the refused line
  and not a typo. Both are left out of the default build; a new file is picked up at the next configure;
- the shared conformance driver against the adapter (`conformance`: `conformance/adapter.cpp` claims level 3, every
  case, with byte positions; its own failing source and `throws` extension give the faults of spec/conformance.md
  4.5).

One test at a time: `ctest --test-dir build -R programs_lint --output-on-failure`. Building also compiles every header
together, each layer's header against the layers it may not import, the generated parser against its hooks, and
the syntax layer with exceptions and RTTI off. `KNOBLY_BUILD_TESTS` is on when this is the top-level project.

The routes of "Using it" are checked from the release assets, with nothing installed and Python stubbed out (CI's
C++ package job; `tests/consumer/`):

```bash
bash .github/release-cpp.sh 1.2.3 work/assets && bash cpp/tests/consumer/check.sh 1.2.3 work/assets work
```

Format the hand-written files with the pinned clang-format (its one pin is `CLANG_FORMAT` in
`tools/api/emit_cpp.py`):

```bash
git ls-files 'cpp/*.hpp' 'cpp/*.cpp' | xargs uv tool run --from clang-format==21.1.8 clang-format -i --style=file:cpp/.clang-format
```

The design is `.claude/design/cpp/design.md`; the milestones' frozen plans are `.claude/design/cpp/frozen-m1.md`,
`frozen-m2.md` and `frozen-m3.md`.
