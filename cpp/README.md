# villanelle for C++

A header-only C++20 library: one include directory and one CMake target, `villanelle::villanelle`, with no
dependency beyond the standard library (owner, 2026-10-25: "I don't want villanelle dependent on third party
libraries"). Milestone 1 has the syntax tree; the low level and the rendered tree come in later milestones.

```cpp
#include <villanelle/syntax.hpp>

villanelle::syntax::syntax parsed = villanelle::syntax::parse("node leds { max_count 3; }\n");
for (const villanelle::diagnostic& d : parsed.diagnostics()) {
    std::cerr << villanelle::to_string(d) << '\n';  // such as 1:3: E2004: unmatched bracket: "]"
}
std::string all = villanelle::syntax::text_of(parsed, parsed.root());  // the input, exactly
```

`parse` is total: it never throws (but `std::bad_alloc`), and problems are diagnostics. Positions count bytes of
UTF-8 (`line` and `column` from 0). `span_of` and `text_of` throw `villanelle::index_out_of_range` for a token range
outside the parse. Every list is a `villanelle::sequence<T>`: copying one shares it, and its elements come back by
value, so nothing returned can dangle.

## Using it

```cmake
add_subdirectory(villanelle/cpp)   # or FetchContent
target_link_libraries(my_program PRIVATE villanelle::villanelle)
```

- **Header-only** (the default): every definition is inline in the headers.
- **Compiled mode** (`-DVILLANELLE_COMPILED=ON`, or `VILLANELLE_HEADER_ONLY=0` for the whole program): the headers
  hold declarations only, and exactly one file of the program includes `<villanelle/implementation.hpp>`.
- The syntax layer builds with `-fno-exceptions -fno-rtti`; without exceptions, a thrown error is written to
  standard error and `std::abort()` is called instead.
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

`ctest` runs the unit tests (`tests/unit/`, Catch2), the generated contract of each implemented layer (a
declaration without a definition fails to link) and the shared conformance driver against the adapter
(`conformance/adapter.cpp`, which claims level 0 with byte positions). Building also compiles every header
together, each layer's header against the layers it may not import, the generated parser against its hooks, and
the syntax layer with exceptions and RTTI off. `VILLANELLE_BUILD_TESTS` is on when this is the top-level project.

Format the hand-written files with the pinned clang-format (its one pin is `CLANG_FORMAT` in
`tools/api/emit_cpp.py`):

```bash
git ls-files 'cpp/*.hpp' 'cpp/*.cpp' | xargs uv tool run --from clang-format==21.1.8 clang-format -i --style=file:cpp/.clang-format
```

The design is `.claude/design/cpp/design.md`; milestone 1's frozen plan is `.claude/design/cpp/frozen-m1.md`.
