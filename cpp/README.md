# villanelle for C++

A header-only C++20 library: one include directory and one CMake target, `villanelle::villanelle`, with no
dependency beyond the standard library (owner, 2026-10-25: "I don't want villanelle dependent on third party
libraries"). It has the three layers TypeScript and Python have, with the same names in snake_case:

| Header | Namespace | What it holds |
|---|---|---|
| `<villanelle/syntax.hpp>` | `villanelle::syntax` | `parse`, the lossless syntax tree |
| `<villanelle/written.hpp>` | `villanelle::written` | the low level: `processor`, `load`, the document graph you edit and `save` back |
| `<villanelle/rendered.hpp>` | `villanelle::rendered` | `render(graph)`: the tree after variables, snippets and includes |
| `<villanelle/files.hpp>` | `villanelle::files` | `file_source()`, `file_writer()`: files on disk |
| `<villanelle/extensions.hpp>` | `villanelle::extensions` | `include()`: the include extension |

```cpp
#include <villanelle/extensions.hpp>
#include <villanelle/files.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

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

**Formatting.** `<villanelle/format.hpp>` is opt-in (no other header includes it): it gives every type with a people
form (`place`, `located_diagnostic`, `rendered::address`, each kind list, `diagnostic_code`, ...) an `operator<<` and
a `std::formatter`, both writing exactly its `to_string`. The formatter takes a string's format spec, so width, fill
and alignment work: `std::format("[{:>8}]", vl::value_kind::word)` is `[    word]`. Which types it covers is read from
the schema, so the header is generated whole.

```cpp
#include <villanelle/format.hpp>
std::cerr << std::format("{}: skipped ({})\n", u.origin().place(), u.reason());  // lb.conf:11:1: skipped (expansion)
```

**Handles.** Every object a layer returns (a graph, a statement, a rendered directive) is a small handle: copying it
shares the graph or render it belongs to, which lives while any handle of it does, so nothing returned can dangle (a
rendered directive keeps its render and the graph alive). Two handles are equal when they show the same object.
Every list is a `villanelle::sequence<T>` and every map a `villanelle::ordered_map<K, V>` (insertion order): copying
one shares it, and elements come back by value. A loop over a block, or a `walk()`, reads a snapshot, so editing
during it is allowed. A statement an edit removed is detached: its `kind()` still works and every other member
throws `villanelle::detached_error`.

**Errors.** Problems in the config text are never thrown: `load` returns a graph whose `diagnostics()` lists them,
and `render` returns a tree with the same list. Exceptions mirror the error groups of the other bindings: expected
outcomes derive `villanelle::villanelle_error` (`diagnostic_error`, `read_error`, `bad_text_error`, `save_error` and
its `lost_update_error`; a `save_error` nests the writer's exception, so `std::rethrow_if_nested` gives the cause),
and program bugs derive `std::logic_error` (`detached_error`, `argument_type_error`, `misuse_error`,
`index_out_of_range`). An edit that throws changes nothing. `parse` never throws (but `std::bad_alloc`).

**Threads.** Copying a handle or destroying one on another thread is safe (the count is atomic); nothing else is,
not even reading one graph from two threads through `const`.

**Positions** count bytes of UTF-8 (`line` and `column` from 0; the people forms, `to_string` and
`format_diagnostic`, count from 1). **Paths** are UTF-8 text with `/`: `file_source` resolves an include against
its parent's directory by a lexical join (`.` and empty segments dropped, `..` popped), so a relative root stays
relative, as in Python (TypeScript makes paths absolute). They are the keys of `documents()` and the paths in every
message.

## Using it

```cmake
add_subdirectory(villanelle/cpp)   # or FetchContent
target_link_libraries(my_program PRIVATE villanelle::villanelle)
```

- **Header-only** (the default): every definition is inline in the headers.
- **Compiled mode** (`-DVILLANELLE_COMPILED=ON`, or `VILLANELLE_HEADER_ONLY=0` for the whole program): the headers
  hold declarations only, and exactly one file of the program includes `<villanelle/implementation.hpp>`.
- **Compiled mode** instantiates every template the headers spell once, in `implementation.hpp` (each header
  declares it `extern`), so programs do not compile them again.
- The syntax and written layers build with `-fno-exceptions -fno-rtti`; without exceptions, a thrown error is
  written to standard error and `std::abort()` is called instead.
- **Invalid UTF-8** (provisional, pending the owner's ruling): a byte that does not decode is one `BAD_CHAR`
  token with E1003; a surrogate's three-byte form (WTF-8) decodes. The rule lives in one function,
  `detail/text_in.hpp`.

## Generated code

Every public header directly in `include/villanelle/` is generated from `spec/schema/` by `tools/gen-api.py`, and
`include/villanelle/detail/syntax/parser.gen.hpp` from `grammar/Villanelle.g4` by villanelle's own parser generator
(`tools/parser/gen.py`; no ANTLR, no Java). Neither is committed (owner, 2026-10-23: "Don't commit the generated
code, just the source"): CMake runs `bash tools/gen.sh cpp` at configure time when they are absent, which needs
Python 3.9 or later and `uv` (for the pinned clang-format the generated code is formatted with). The hand-written
code is `include/villanelle/support/` (the library types) and `include/villanelle/detail/` (the definitions; the
syntax layer's token loop, error codes, recovery and nesting guard are in `detail/syntax/parse.hpp`).

## Build and test

From the repository root, with CMake 3.24 or later and a C++20 compiler:

```bash
cmake -S cpp -B build -DVILLANELLE_SANITIZE=ON   # Catch2 v3 is fetched for the tests
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
  `-DVILLANELLE_CONTROL`, which swaps in the nearest valid line, and must succeed, so the failure is the refused line
  and not a typo. Both are left out of the default build; a new file is picked up at the next configure;
- the shared conformance driver against the adapter (`conformance`: `conformance/adapter.cpp` claims level 3, every
  case, with byte positions).

One test at a time: `ctest --test-dir build -R programs_lint --output-on-failure`. Building also compiles every header
together, each layer's header against the layers it may not import, the generated parser against its hooks, and
the syntax layer with exceptions and RTTI off. `VILLANELLE_BUILD_TESTS` is on when this is the top-level project.

Format the hand-written files with the pinned clang-format (its one pin is `CLANG_FORMAT` in
`tools/api/emit_cpp.py`):

```bash
git ls-files 'cpp/*.hpp' 'cpp/*.cpp' | xargs uv tool run --from clang-format==21.1.8 clang-format -i --style=file:cpp/.clang-format
```

The design is `.claude/design/cpp/design.md`; the milestones' frozen plans are `.claude/design/cpp/frozen-m1.md`,
`frozen-m2.md` and `frozen-m3.md`.
