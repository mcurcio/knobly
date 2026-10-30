# C++ binding milestone 3 (the rendered layer's remainder: format.hpp, programs 4.1 and 4.3, compile-fail tests, the docs' C++ column), frozen for the slices

This page is what slices P and D build in milestone 3 of the C++ binding. It is frozen: a slice that finds it wrong
appends the finding to `.claude/errata.md` and does not diverge silently. `spec/` is canonical; where this page and
`spec/` differ, `spec/` wins and the difference is an erratum. Where this page and `design.md` differ, this page wins
for milestone 3 (section 8). `frozen-m1.md` and `frozen-m2.md` stay the records of milestones 1 and 2.

## 0. What this rests on

The owner's words, quoted, not widened (`answers.md` has the dates):

- 2026-10-28: "clean, easy to comprehend API design", "idiomatic in each language", "consistent across layers", codegen
  "so we dont have to maintain n languages by hand".
- 2026-10-25: "I don't want villanelle dependent on third party libraries".
- 2026-10-29: C++ header-only "but with as much auto codegen as possible to unify with typescript and python".
- 2026-10-30: expected errors throw exceptions mirroring the error tree; handles share ownership of the graph
  (reference counted, never dangle); pinned formatters on generated code.
- 2026-10-30 (tonight): "run an overnight build and deliver me 1 evolving PR". He is asleep: every open choice takes
  design.md's recommended default and is listed in section 6 as a choice made overnight.
- 2026-10-23: "Don't commit the generated code, just the source".

**Already landed in milestone 2** (frozen-m2.md choice 1, commit `9ea9ef6`), so not rebuilt here: `render` built only
on the written layer's public objects, rendered directives and blocks, `walk` with `descend`, `closest`, `addresses`
with key rules (`conformance/keys.json`), `diff`, the adapter's level 3. The freeze re-ran it: the shared driver
passes all 380 cases (L0 168, L1 60, L2 123, L3 24; "claimed L3 extensions: holds") in header-only mode, and `ctest`
is 24/24 green (section 7 has the evidence).

**Milestone 3 delivers** what design.md section 7, slice 3, lists and milestone 2 left: `<villanelle/format.hpp>`;
design programs 4.1 (the sinks app) and 4.3 (the upstream lint) compiled with `-Wsign-conversion` and `-Wdangling`
and run as tests against fixtures with expected output; compile-fail tests (design.md finding F1 and 2.6: what C++
refuses at compile time that the dynamically typed bindings refuse at run time); the full 380-case run re-proven in
header-only (ASan and UBSan) and compiled mode; `emit_docs.py` renders the C++ column in every documentation table that
has per-language columns (today those tables are hand-written with TypeScript and Python only).

**Not in milestone 3:** packaging, install, the single header and the versioned release archive (design.md slice 4),
MSVC (errata T5), `spec/binding-guide.md`'s tables (choice 5), any change to a rule every binding follows.

## 1. Order and ownership

```text
freeze (landed: this commit) --> wave 1:  Slice P (C++: format tests, programs 4.1 and 4.3, compile-fail tests, 380 in both modes)
                                          Slice D (docs: generated per-language tables with the C++ column)          [parallel]
```

One wave. P and D run **at the same time in this one checkout**; their paths are disjoint and neither needs the other's
work. A compile error or a stale table in a file another slice owns is theirs: wait and retry, never edit it.

### 1.1 Owned paths (exact)

| Owner | Paths (generated outputs and build trees count as owned) |
|---|---|
| **P** | `cpp/tests/programs/` (all of it: the new `sinks.cpp`, `lint.cpp`, their fixture and expected folders, the runner script, and the existing editor files if the runner is shared); `cpp/tests/unit/format.cpp`; `cpp/tests/compile_fail/` (new); `cpp/CMakeLists.txt`; `cpp/README.md`; `cpp/include/villanelle/detail/` and `cpp/include/villanelle/support/` (only to fix a bug a P test finds); `cpp/conformance/adapter.cpp`, `cpp/conformance/json.hpp` (same); the `cpp` job of `.github/workflows/ci.yml` (only if a new test needs a CI step; none is expected); build trees `/Volumes/Dock/tmp/vil-cpp-build-P*` |
| **D** | `tools/api/emit_docs.py`, `tools/api/loader.py`, `tools/api/stub.py`, `tools/gen-api.py`, and the `LANGUAGE` blocks of `tools/api/emit_ts.py`, `emit_py.py`, `emit_cpp.py` (only to add a documentation fact, section 5); `spec/schema/api.json` (only if a table needs a schema fact; an erratum first); the new `docs/tables.json`; `docs/rendered-tree.md`, `docs/low-level-api.md`, `README.md` (root), `spec/codegen.md`, and every table region `python3 tools/gen-api.py docs` rewrites (`spec/*.md`, `docs/*.md`); temp renders under `/Volumes/Dock/tmp/vil-docs-D*` |
| every slice | `.claude/errata.md`, append only |

**The emitter rule.** Only D edits a file under `tools/` or `spec/schema/`. D's change must leave every binding's
generated code byte-identical (section 5's acceptance checks it), so P's build never sees it. P configures with
`-DVILLANELLE_REGENERATE=OFF` and never runs `tools/gen.sh` or `tools/gen-api.py`; the generated headers, `format.hpp`
included, are already in the tree from the freeze's `python3 tools/gen-api.py cpp` (run it once yourself, before
starting, only if `cpp/include/villanelle/format.hpp` is missing). A P test that needs a generated-header change appends
an erratum and reports it; it does not edit `tools/`. Generated files are never committed (`git status` shows none).

## 2. What the freeze committed (all green)

| Path | State |
|---|---|
| `tools/api/emit_cpp.py` | `format_header(model)`: renders `cpp/include/villanelle/format.hpp` **whole** (section 3.1); listed in the module docstring; wired into `render_with_hands`. No other C++ output changes; TypeScript, Python and docs output unchanged |
| `spec/codegen.md` | the C++ header table gains the `format.hpp` row |
| `cpp/tests/compile/headers.cpp` | includes `<villanelle/format.hpp>`, so the compile check builds it with `-Wall -Wextra -Werror` (CI also compiles every public header alone) |
| `.claude/design/cpp/frozen-m3.md` | this page |

The freeze compiled design programs 4.1 and 4.3 **verbatim** (from design.md, unchanged) against the current headers with
`-std=c++20 -Wall -Wextra -Werror -Wsign-conversion -Wdangling`, linked them header-only and ran them on scratch fixtures:
both give the output design.md shows (4.3's three `lb/...` diagnostics with source lines and carets; 4.1's sinks,
the `20hz` E4004 once per include copy, `via extension include at main.conf:4:5`, exit 1). So no public signature
changes in this milestone; P's work is tests, fixtures and the compile-fail harness.

## 3. Frozen interfaces

### 3.1 `<villanelle/format.hpp>` (generated whole by `emit_cpp.format_header`)

Opt-in (design.md 3.5): no other header includes it. Which types it covers is a schema fact, so nothing in it is hand
code. Today's schema gives (the list is the generator's, not this page's):

```cpp
#include <format>
#include <ostream>
#include <string_view>
#include <villanelle/rendered.hpp>    // the header of each layer holding a people form
#include <villanelle/villanelle.hpp>

namespace villanelle::detail {
template <class T>
struct people_formatter : std::formatter<std::string_view, char> {   // width, fill, alignment as for a string
    template <class Context> auto format(const T& value, Context& context) const;   // formats to_string(value)
};
}

namespace villanelle {   // (inside the versioned inline namespace, VILLANELLE_NAMESPACE_BEGIN)
std::ostream& operator<<(std::ostream&, const place&);              // every concept with a people form:
std::ostream& operator<<(std::ostream&, const override&);           //   place, override, step, diagnostic,
std::ostream& operator<<(std::ostream&, const step&);               //   located_diagnostic (shared)
std::ostream& operator<<(std::ostream&, const diagnostic&);
std::ostream& operator<<(std::ostream&, const located_diagnostic&);
std::ostream& operator<<(std::ostream&, const token_kind&);         // every kind list: token_kind, node_kind,
// ... node_kind, statement_kind, value_kind, variable_kind, step_kind, place_kind, unreadable_reason, change_kind
std::ostream& operator<<(std::ostream&, const diagnostic_code&);    // "E4004"
}
namespace villanelle::rendered {
std::ostream& operator<<(std::ostream&, const address&);            // graph > node "leds" > max_count
}

template <> struct std::formatter<::villanelle::place, char> : ::villanelle::detail::people_formatter<::villanelle::place> {};
// ... one specialization per type above
```

Each `operator<<` is `inline` and sits in its type's namespace (found by argument-dependent lookup); each formatter
and each `operator<<` gives exactly `to_string(value)`. A schema concept that gains a people form, or a new kind list,
appears here with no hand edit.

### 3.2 Test names P adds (CTest), frozen so D and the final review can find them

| CTest name | What it runs |
|---|---|
| `unit_format` | `villanelle_unit_format` (Catch2, `cpp/tests/unit/format.cpp`), picked up by the existing per-file loop |
| `programs_sinks` | design program 4.1 (`villanelle_program_sinks`) in a fresh copy of `cpp/tests/programs/sinks/`, three runs (section 4) |
| `programs_lint` | design program 4.3 (`villanelle_program_lint`) in a fresh copy of `cpp/tests/programs/lint/` |
| `programs_editor` | unchanged (milestone 2) |
| `compile_fail_<name>` | for each `cpp/tests/compile_fail/<name>.cpp`: building it must fail (`WILL_FAIL`) |
| `compile_fail_<name>_control` | the same file with `-DVILLANELLE_CONTROL`: building it must succeed, so the failure is the refused line and not a typo |

### 3.3 The generated documentation tables D adds (frozen shape)

- A table with per-language columns becomes a generated region, as the glossary's already are:
  `<!-- generated: members: <table name> (tools/gen-api.py docs) -->` ... `<!-- end generated -->`.
- Its rows live in **`docs/tables.json`** (new, the rows' one home), keyed by table name:
  `{"<table name>": {"file": "docs/low-level-api.md", "first": ["Member"], "last": ["What it is"],
  "rows": [{"what": "the root file", "ref": "document graph.root", "last": ["the file `load` was given"]}, ...]}}`.
  `first` and `last` are the hand columns before and after the language columns; `what` fills the first hand
  column; `last` fills the hand columns after.
- `ref` names a schema thing: `"<concept>.<member>"` (a member: its spelling in each language through the loader's
  `member_spelling` and casing, with `(...)` for a method and bare for a property), `"<concept>"`, `"<free function>"`,
  `"<error group>"`, `"<kind list>"`, `"<module>"` (an adapter module's import path), or `"trait: <trait>"` (codegen.md's
  trait table, from a per-language documentation fact, section 5). A `ref` that does not resolve fails the docs build
  (`SchemaError`), so a renamed member cannot leave a stale row.
- A row the schema cannot spell (prose such as "returns a promise") may carry `"cells": {"<language key>": "<text>"}`
  for that language only; every such hand cell is counted and listed in D's result (each one is a cost).
- The language columns are `langs(model)`, so the third-binding stub (`tools/api/stub.py`) gets a column in every new
  table too, and `gen-api.py --check`'s stub check asserts one of them.

## 4. Slice P: format tests, programs 4.1 and 4.3, compile-fail tests, the full run in both modes

**Build.**
- `cpp/tests/unit/format.cpp` (Catch2): for a `place`, a `located_diagnostic`, a `rendered::address`, a kind
  (`value_kind::word`) and a `diagnostic_code`, `std::format("{}", x) == to_string(x)` and `(std::ostringstream{} << x).str()
  == to_string(x)`; width, fill and alignment (`std::format("[{:>8}]", value_kind::word) == "[    word]"`); a value from a
  real render (an address from `addresses()` of a two-directive tree) so the people forms come from the hand code.
- `cpp/tests/programs/sinks.cpp`: design.md 4.1 **verbatim** (its includes, `sink`, `main`). Fixture
  `cpp/tests/programs/sinks/`: `main.conf` (`@set $pixels 1200;`, `@set $leds_host "10.0.0.5";`, a `graph { ... }` block
  with two `@include "sink.conf" { @set $name <left|right>; }` copies) and `sink.conf` (`node DdpSink $name { target
  $leds_host; fps 20hz; max_count $pixels; }`). The test runs it three times and compares stdout, stderr and the exit
  status with files under `cpp/tests/programs/sinks_expected/`: no argument (two sinks, 1200 leds, the E4004 for `20hz`
  once per copy with its `via extension include` step, exit 1); `pixels=600` (600 leds); `9bad=1` (the usage line, exit 2).
- `cpp/tests/programs/lint.cpp`: design.md 4.3 **verbatim**. Fixture `cpp/tests/programs/lint/lb.conf` with: an upstream
  with a good server, a `[1, 2]` weight, a `-1` weight; an empty `upstream {}`; a top-level `server`; one directive whose
  value cannot be read (so the `unreadable()` line prints through `std::format` of a `place` and an `unreadable_reason`,
  exercising format.hpp). Expected stdout, stderr and exit status 1 under `cpp/tests/programs/lint_expected/`.
- One runner script for every program test (`cpp/tests/programs/run_program.cmake`: copy the fixture to a fresh work
  folder, run with arguments, compare outputs and status; the editor's file comparison as an option), replacing
  `run_editor.cmake` (DRY: one runner, three programs). Each program target gets `-Wsign-conversion` and, on Clang,
  `-Wdangling`, as the editor does (one CMake function for the three).
- `cpp/tests/compile_fail/`: one file per refusal, each with the refused line under `#ifndef VILLANELLE_CONTROL` and the
  nearest valid line under `#else`. At least: `render_not_a_graph.cpp` (`render(document)`: the conformance case
  `render-not-a-graph`, errata R2), `config_text_from_string.cpp` (a `std::string` where `config_text` is taken),
  `program_code_without_slash.cpp` (`report(d, "m", "nodash")`: the consteval check), `key_rule_not_text.cpp` (a key
  rule returning `int`, errata R3), `report_written_statement.cpp` (`report()` on a written statement, which is not
  `locatable`, spec 7.7), `view_of_temporary.cpp` (`text("x").view()`: the deleted `const&&` overload). CMake: each file
  is an `EXCLUDE_FROM_ALL` object library (and its control another), and the test runs `cmake --build <dir> --target
  <it> --config $<CONFIG>`. If a refusal design.md names turns out to compile, that is a finding: append an erratum,
  leave the case out, report it.
- `cpp/README.md`: `format.hpp`, the three programs, the compile-fail tests, how to run them.

**Acceptance (P).** In a header-only build with `-DVILLANELLE_SANITIZE=ON` (`/Volumes/Dock/tmp/vil-cpp-build-P-asan`) and a
compiled-mode build with `-DCMAKE_CXX_STANDARD=23 -DVILLANELLE_COMPILED=ON` (`/Volumes/Dock/tmp/vil-cpp-build-P-compiled`):
`ctest` green, including `unit_format`, `programs_sinks`, `programs_lint`, `programs_editor`, every `compile_fail_*` and its
control, and `conformance`, whose log shows `1..380`, every level `0 failed` and "claimed L3 extensions: holds". The
hand-written files pass the pinned clang-format (`--dry-run --Werror`, as the CI step runs it). `git status` shows no
generated file staged.

**Mutation probes (P).** (1) Change the lint fixture's `-1` to `1`: `programs_lint` must fail on its expected output.
(2) Delete the refused line in `render_not_a_graph.cpp` (leave the file compiling): `compile_fail_render_not_a_graph`
must fail. (3) Put a typo in a control branch: its `_control` test must fail. Revert each.

## 5. Slice D: the C++ column in every per-language documentation table

**Build.**
- `emit_docs.py`: a `members` table kind (section 3.3) rendered from `docs/tables.json` and the loaded model, added to
  `tables(model)` beside the existing ones; `stale()` and `write()` cover it unchanged.
- Convert each hand-written table with TypeScript and Python columns in the user docs to a generated region with a row
  list in `docs/tables.json`: `docs/rendered-tree.md` (the processor/load/render/diff table, the readers table, the
  addresses table, the sources table), `docs/low-level-api.md` (the graph members, document members, variable members,
  errors and writers tables), the root `README.md`'s entry-point table (`ref` to each layer's and module's import path),
  and `spec/codegen.md`'s trait table (`ref: "trait: ..."`). The surrounding prose stays hand-written; where it says "in
  both languages", D may correct it to name the three.
- The trait table needs a per-language fact the `Language` descriptor lacks: add `trait_forms: Dict[str, str]` (each
  trait's documentation text: TypeScript `[Symbol.iterator]()`, Python `__iter__`, C++ `begin()`/`end()` ...) to
  `loader.Language`, filled in each emitter's `LANGUAGE` and the stub's; the loader checks that every trait the schema
  uses has an entry in every language. Read the C++ forms from the generated headers and `support/` (for example
  `walk(descend)` returning a `walk_view`, `collect(read)` returning `std::optional`, `at(i)` throwing
  `index_out_of_range`, `io: true` as a plain call).
- `spec/codegen.md` section on generated tables: name the `members` kind and `docs/tables.json`.

**Acceptance (D).** `python3 tools/gen-api.py docs` writes the tables; `bash tools/check.sh` green (its `--check` fails
on a stale table and asserts the stub's column); every table listed above has a C++ column whose cells match the
generated headers (spot-check five C++ cells against `cpp/include/villanelle/*.hpp`); the TypeScript and Python cells say
what the hand tables said (any change listed in the result, with why). **No binding output changes:** render
`python3 tools/gen-api.py ts`, `py` and `cpp` outputs before and after into `/Volumes/Dock/tmp/vil-docs-D*` (or diff the
in-memory `render()` of each emitter) and show them identical. TypeScript checks (`cd ts && corepack pnpm test &&
corepack pnpm typecheck && corepack pnpm lint && corepack pnpm build`) and Python checks (`cd py && uv run --locked
pytest -q && uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy`) green, since
their emitters' modules changed. The count of hand cells (section 3.3) is in the result.

**Mutation probes (D).** (1) Make `emit_cpp._member_spelling` camelCase a member: `gen-api.py --check` must report the
docs stale. (2) Point one `ref` in `docs/tables.json` at a member that does not exist: `gen-api.py docs` must fail with
the ref named. (3) Drop `"walk"` from C++'s `trait_forms`: the loader must refuse. Revert each.

## 6. Choices made overnight (each revisable)

1. **Milestone 3 is the remainder of design.md slice 3**: the rendered layer, `addresses`, `diff` and the level-3
   adapter landed in milestone 2 (frozen-m2.md choice 1) and are re-proven here, not rebuilt.
2. **`format.hpp` is generated whole** from the schema (which types have a `to_string` is a schema fact), as the union
   members were in milestone 2: no hand code, so a new people form or kind list is formatted with no edit.
3. **The formatter formats the `to_string` as a string**, inheriting `std::formatter<std::string_view>`: width, fill and
   alignment work; no type-specific format spec is invented.
4. **Compile-fail tests are CTest builds of `EXCLUDE_FROM_ALL` targets with `WILL_FAIL`, each with a control build**, the
   common CMake idiom (no `try_compile` at configure time, so configure stays fast and every case is a named test).
5. **`spec/binding-guide.md`'s tables are left as they are**: they record past milestones' choices for TypeScript and
   Python (with "M1:" notes), not the current API per language. A follow-up if the owner wants C++ there.
6. **Documentation rows live in `docs/tables.json`**, one home per table's rows, rendered with every language's column
   by the existing docs emitter; hand cells are allowed only where the schema cannot spell the text, and are counted.
7. **Two slices in one wave**: the C++ tests (P) and the generators and docs (D) share no file; only D touches `tools/`.

## 7. Evidence and NOT RUN by the freeze

Ran: `bash tools/check.sh` (exit 0); `python3 tools/gen-api.py cpp`; a header-only Debug build
(`/Volumes/Dock/tmp/vil-cpp-build-freeze-m3`, AppleClang 21, configure with `-DVILLANELLE_REGENERATE=ON`) and `ctest`: 24/24,
the conformance log `1..380`, L0 168, L1 60, L2 123, L3 24 passed, "claimed L3 extensions: holds"; programs 4.1 and 4.3
verbatim and a `format.hpp` probe (`std::format("[{:>8}] [{}]", value_kind::word, diagnostic_code::not_a_number)` gives
`[    word] [E4004]`) compiled with `-Werror` and run; the pinned clang-format on `tests/compile/headers.cpp`.

NOT RUN: the sanitizer and compiled-mode builds (P's acceptance); GCC (none on this Mac; the CI leg); the TypeScript and
Python checks (no TypeScript or Python path and no emitter they load changed: `emit_cpp.py` is loaded for C++, by
`--check` and by `docs`, and `tools/check.sh` ran green); CI (runs on push).

## 8. Differences from design.md, and why

| design.md | This page | Why |
|---|---|---|
| 7: slice 3 builds render, walk, closest, addresses, diff | already built in milestone 2 | frozen-m2.md choice 1 (the load corpus renders) |
| 3.5: `format.hpp` "for every type with a to_string" (form unstated) | generated whole from the schema, formatter over `string_view` | choices 2 and 3 |
| 2.6: compile-fail cases "a plain string as `config_text`, a literal code without `/`, `view()` on a temporary" | those three plus `render` of a non-graph, a key rule returning non-text, `report()` on a written statement | errata R2 and R3 point here; spec 7.7 |
| 7: "`emit_docs.py` gains the C++ column" | the generated tables already have it; the hand tables become generated ones | the C++ column existed wherever a table was generated; the gap was the hand tables |
