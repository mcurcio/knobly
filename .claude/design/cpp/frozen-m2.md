# C++ binding milestone 2 (the written layer, with render and include), frozen for the slices

This page is what slices W, F and R build in milestone 2 of the C++ binding. It is frozen: a slice that finds it wrong
appends the finding to `.claude/errata.md` and does not diverge silently. `spec/` is canonical; where this page and
`spec/` differ, `spec/` wins and the difference is an erratum. Where this page and `design.md` differ, this page wins
for milestone 2 (section 9 lists each difference and why). `frozen-m1.md` stays the record of milestone 1.

## 0. What this rests on

The owner's words, quoted, not widened (`answers.md` has the dates and the question numbering):

- 2026-10-28: "clean, easy to comprehend API design", "idiomatic in each language", "consistent across layers", codegen
  "so we dont have to maintain n languages by hand".
- 2026-10-25: "I don't want villanelle dependent on third party libraries".
- 2026-10-29: C++ header-only "but with as much auto codegen as possible to unify with typescript and python".
- 2026-10-30: Q1 A (expected errors throw exceptions mirroring the error tree, as TypeScript and Python do); Q2, "Are
  you asking about ref counting? Ok" (handles share ownership of the graph, reference counted, never dangle); Q3 A
  (pinned formatters on generated code).
- 2026-10-30 (tonight): "run an overnight build and deliver me 1 evolving PR". He is asleep: every open choice below
  takes design.md's recommended default and is listed in section 7 as a choice made overnight.
- 2026-10-23: "Don't commit the generated code, just the source".

**Milestone 2 delivers** (design.md section 7, slice 2, plus what the conformance levels need; section 7, choice 1):
the written layer whole (processor and load through any `document_source`, `memory_source` and `memory_writer`, the
graph, documents, statements, values, variables, resolutions, the expansion and expanded values with their readers,
every edit with the strong exception guarantee, `save` with lost-update checking, iteration snapshots, `diagnostics`
and `collect`, `format_diagnostic`, the people forms); `file_source` and `file_writer`; the include extension; the
rendered layer (`render`, rendered directives and blocks, `walk` with `descend`, `closest`, `addresses` with key
rules, `diff`); design program 4.2 as a compiled test; explicit instantiation in compiled mode; a per-request timeout
in the shared driver (bead kno-p5x). The adapter claims **level 3**, and every one of the 380 cases (L0 168, L1 60,
L2 123, L3 24) passes in header-only and compiled mode under ASan and UBSan. `tools/check.sh`, TypeScript and Python
stay green, and their behaviour does not change.

**Not in milestone 2:** `format.hpp` (the `std::formatter` header), programs 4.1 and 4.3, the compile-fail tests
(F1), install and packaging, the single-header file, MSVC (errata T5), the compile-time budget as a gate (it is
reported, not gated).

## 1. Order and ownership

```text
freeze (landed: this commit) --> wave 1:  Slice W (written layer, shared, io, support, adapter L1, emitter)
                                          Slice F (files adapters, include extension, driver timeout, CI)   [parallel]
                             --> wave 2:  Slice R (rendered layer, adapter L2 and L3, program 4.2, docs, cleanup)
```

W and F run **at the same time in this one checkout**. Their paths are disjoint, and neither needs the other's code to
build or pass its own acceptance (the freeze defined whole the two helpers both call, section 3.4). The checkout is
shared: a compile error in a file another slice owns is theirs; wait and retry, never edit it. Build only your own
targets (each unit-test file is its own program, section 2) in your own build tree. R starts when W and F have both
landed, and owns everything they owned but the emitter (one slice only changes the emitter: W).

### 1.1 Owned paths (exact)

| Owner | Paths (generated outputs and build trees count as owned) |
|---|---|
| **W** (wave 1) | `cpp/include/knobly/support/`; `cpp/include/knobly/detail/shared/`, `detail/io/`, `detail/written/`, `detail/raise.hpp`, `detail/text_in.hpp`; `cpp/conformance/adapter.cpp`, `cpp/conformance/json.hpp`; `cpp/tests/compile/`; `cpp/tests/unit/` except `files*.cpp` and `include*.cpp`; `cpp/CMakeLists.txt`; `tools/api/emit_cpp.py`, `tools/api/loader.py`, `tools/gen-api.py`, `spec/schema/api.json` (an erratum's fix only), `spec/codegen.md` and the tables `python3 tools/gen-api.py docs` rewrites (`spec/*.md`, `docs/rendered-tree.md`), only if the emitter or loader changes; the generated `cpp/include/knobly/*.hpp`, `cpp/conformance/shapes.hpp`, `cpp/tests/generated/` (never committed); build trees `/Volumes/Dock/tmp/kno-cpp-build-W*` |
| **F** (wave 1) | `cpp/include/knobly/detail/files/`, `cpp/include/knobly/detail/extensions/`; `cpp/tests/unit/files*.cpp`, `cpp/tests/unit/include*.cpp`; `conformance/driver/adapter.py`, `conformance/driver/test_driver.py`, `conformance/driver/stub_adapter.py`; `.github/workflows/ci.yml`; build trees `/Volumes/Dock/tmp/kno-cpp-build-F*` |
| **R** (wave 2) | `cpp/` except the emitter's generated outputs (so `cpp/include/knobly/detail/` whole, `cpp/include/knobly/support/`, `cpp/conformance/adapter.cpp`, `json.hpp`, `cpp/tests/` but `tests/generated/`, `cpp/CMakeLists.txt`, `cpp/README.md`); `README.md` (root: the C++ line only); build trees `/Volumes/Dock/tmp/kno-cpp-build-R*` |
| every slice | `.claude/errata.md`, append only |

F configures with `-DKNOBLY_REGENERATE=OFF` and never runs `tools/gen.sh` or `tools/gen-api.py`: the generated
headers are W's outputs in wave 1. W regenerates (`python3 tools/gen-api.py cpp`) only after an emitter change.
Generated files are never committed (each slice checks `git status` shows none).

## 2. What the freeze committed (all green)

| Path | State |
|---|---|
| `tools/api/emit_cpp.py` | (1) each union's `as<V>()` and `visit(f)` **generated whole** from the variant list (3.2); (2) a header includes `detail/<layer>/templates.hpp` in both modes for each of its layers with hand member templates or the block shape (3.2); (3) **explicit instantiation**: each header declares `extern template class` in compiled mode for every support or class template specialization it spells first, and `implementation.hpp` instantiates them all once (3.2); (4) the contract now odr-uses `program_code(std::string_view)` (it had no `Hand`); (5) `<type_traits>` among the standard includes. TypeScript, Python and docs output unchanged (`emit_cpp.py` is the only emitter touched; `tools/check.sh` green) |
| `cpp/include/knobly/support/view.hpp` | `view` (members `KNOBLY_API`), `access` (defined), `block_traits<Item>` (declared, its contract in a comment), `bad_kind()` (3.1) |
| `support/block.hpp`, `walk_view.hpp`, `ordered_map.hpp` | unchanged declarations, comments point here; W defines them |
| `detail/not_built.hpp` | **temporary**: `[[noreturn]] void not_built(const char*) noexcept` writes what is missing and aborts; the body of every stub. R deletes it |
| `detail/shared/{definitions,people,values,diagnostics,view,templates}.hpp` | stubs for every shared declaration (W) but `to_string(const diagnostic&)` and `raise_index_out_of_range` (M1, real) |
| `detail/io/{definitions,memory}.hpp` | `memory_source`, `memory_writer` stubs (W) |
| `detail/io/lost_updates.hpp`, `detail/io/paths.hpp` | **defined whole** (3.4): `check_lost_updates`; `detail::io::directory_of`, `normalize`, `join`, `has_glob`, `glob_match` |
| `detail/written/{definitions,processor,graph,document,statements,values,variables,expansion,format,templates}.hpp` | stubs for every written declaration and the two written `block_traits` specializations (W) |
| `detail/rendered/{definitions,templates}.hpp` | stubs for every rendered declaration and `block_traits<rendered::directive>` (R) |
| `detail/files/definitions.hpp`, `detail/extensions/definitions.hpp` | `file_source`, `file_writer`, `include` stubs (F) |
| `cpp/CMakeLists.txt` | every `tests/generated/api_contract_*.cpp` is a program and a test (`contract_<header>`); one Catch2 program per `tests/unit/<name>.cpp` (`knobly_unit_<name>`, test `unit_<name>`, run in the build directory); `conformance` runs the driver at the adapter's claimed level with `TIMEOUT 900`; `tests/compile/unions.cpp` in the compile check |
| `cpp/tests/compile/unions.cpp` | instantiates every union's `as<V>()` for each variant and `visit(f)` (compiled, never run) |

Built and tested at this commit (AppleClang 21): header-only with `-DKNOBLY_SANITIZE=ON`, and
`-DKNOBLY_COMPILED=ON -DCMAKE_CXX_STANDARD=23`: build green, `ctest` green (6 contracts, 3 unit programs, the
driver's 168 L0 cases); `bash tools/check.sh` green.

## 3. Frozen interfaces

### 3.1 Support and the hooks between layers (`support/view.hpp`, `block.hpp`, `walk_view.hpp`, `ordered_map.hpp`)

- **`detail::view`**: one counted pointer to a `detail::node`; copy shares, the last release frees. Equality is
  identity. Members are declared `KNOBLY_API` (W may instead define them inline in `view.hpp` and drop the macro).
  **W defines `struct detail::node`** with a virtual destructor and the count (design.md 2.3: the count may live on the
  graph's core, the node pointing at it; then a view keeps the whole graph alive). R derives its render nodes from it.
  The count is atomic (copying a view on another thread is safe); nothing else is thread-safe (spec 4.1).
- **`detail::access`** (defined): `access::make<T>(view)` builds any generated handle or snapshot; `access::view_of(h)`
  reads its view. The hand code's only way in; the generated `as`/`visit` use it too.
- **`detail::block_traits<Item>`**: the one layer hook of the block shape. `block<Item, Directive>` and
  `walk_view<Item>` are written once over it; each layer specializes it in its `detail/<layer>/templates.hpp`
  (included in both modes), every member `KNOBLY_API static`, defined with the layer's definitions:

  ```cpp
  template <> struct block_traits<Item> {
      using directive = Directive;   // statement -> written_directive; directive_expansion and rendered::directive -> themselves
      KNOBLY_API static sequence<Item> items(const view& block);         // its items in written order: one snapshot
      KNOBLY_API static std::optional<directive> as_directive(const Item& item, std::optional<std::string_view> name);
      KNOBLY_API static std::optional<view> block_of(const Item& item);  // the item's own block; empty: none or detached
  };
  ```

  Specialized (declared in the freeze, stubbed) for `written::statement` and `written::directive_expansion` (W) and
  `rendered::directive` (R).
- **`block<Item, Directive>`** (W defines, in `block.hpp`, every member in the header so compiled mode's explicit
  instantiation covers it): `begin()` takes one `items()` snapshot and the iterator holds it (random access, yields
  `Item` by value); `end()`; `size()`, `at(i)` (`raise_index_out_of_range` past the end) read a fresh snapshot;
  `directives()` and `directives(name)` filter one snapshot through `as_directive`; `walk()` and `walk(descend)`
  return a `walk_view<Item>` holding the block's view and the predicate. `static_assert` that `Directive` is
  `block_traits<Item>::directive`.
- **`walk_view<Item>`** (W defines): an input range, depth first, pre-order. Entering a block takes that block's
  snapshot; after yielding an item it descends into `block_of(item)` when the item has one and `descend(item)` is
  true (no predicate: always). Owns its data (the views and snapshots): an edit never invalidates it, a statement
  detached after its snapshot is still yielded (its `kind()` works, other members raise `detached_error`) and not
  descended, a statement inserted into a block already entered is not visited (design.md 2.3, finding F8).
- **`ordered_map<K, V>`** (W defines): insertion order, copy on write (`insert_or_assign` and `erase` copy the storage
  first when it is shared), lookup by `==` on `K` (it must work for `std::string` and for `rendered::directive`,
  whose `==` is identity), `at` of a missing key raises `index_out_of_range` (through a `detail/raise.hpp` helper
  like `raise_index_out_of_range`, since `support/` cannot name the error class: errata T3), a repeated key in the initializer list keeps its first place and its
  last value.

### 3.2 Generated by `emit_cpp.py` (landed in the freeze; W owns the emitter from here)

- **Union templates.** For each union view class (`statement`, `written_value`, `variable`, `expanded_value`,
  `change`), after every class of the header, in the layer's namespace:
  `as<V>()` is `*this` for `V` the union itself; for a variant, the variant built from the same view when `kind()`
  is that variant's kind (the schema's `kind` of the variant), else `std::nullopt`. `visit(f)` switches on `kind()`
  and calls `f` with the exact variant class (`default: break;` for a union with `except kinds`, such as
  `expanded_value`, which is never a `reference`), then `detail::bad_kind()`. Both read only `kind()`, which works on
  a detached view (contract 4.3), so `as` and `visit` never raise `detached_error` themselves; the variant's members do.
- **Templates in both modes.** `knobly.hpp` includes `detail/shared/templates.hpp` (after `errors.hpp`);
  `written.hpp` includes `detail/written/templates.hpp`; `rendered.hpp` includes `detail/rendered/templates.hpp`; each
  unconditionally, before the compiled-mode externs. The rule (`emit_cpp.template_layers`): a layer of the header
  with a class template's members, a `collect`, a member taking an interface (`report`), or a concept extending the
  block shape. Template members go there: `diagnostics::report`, `diagnostics::collect` (its `try` only under
  `KNOBLY_EXCEPTIONS`; without exceptions a failing read ends the program, design.md 2.2),
  `written::resolution<D>::copy/winner/shadowed` (thin, over non-template `KNOBLY_API` helpers W declares there
  and defines with the definitions), and the `block_traits` specializations.
- **Explicit instantiation (compiled mode).** `emit_cpp.instantiations` reads every specialization of
  `sequence`, `ordered_map`, `block`, `walk_view` and of a generated class template (`resolution`) that a header
  spells (a block adds its `walk_view<Item>` and `sequence<Directive>`), assigns each to the first header that spells
  it, and writes `extern template class ...;` there under `#if !KNOBLY_HEADER_ONLY`; `implementation.hpp` ends
  with `template class ...;` for all 37 of them (6 in `knobly.hpp`, 3 in `syntax.hpp`, 22 in `written.hpp`, 6 in
  `rendered.hpp`). So the support templates' members must be defined in their headers (not in `detail/`), and every
  member must compile for every element type listed (`ordered_map<rendered::directive, rendered::address>`
  included).
- **Contracts.** `api_contract_<header>.cpp` for all six headers now build and run in `ctest`: every hand-defined
  declaration has a definition (a stub until its slice lands).

### 3.3 The public signatures milestone 2 implements

The generated headers are the signatures: `python3 tools/gen-api.py cpp` writes them from `spec/schema/api.json`, and
`api_contract_<header>.cpp` names every hand-defined one. Appendix A lists each hand-defined function and member
(spelled short: `vl::` is `::knobly::`, `w::` `written`, `r::` `rendered`, `s::` `syntax`); everything else in
the headers (records, kinds, codes, limits, errors, matchers, `as`/`visit`) is generated whole. Differences from the
design.md 3 sketches, each from the schema and kept: `written_block::insert_statements(std::int64_t index, ...)`
(schema `integer`; design said `std::size_t`); `processor_options::extensions` is a
`sequence<std::shared_ptr<extension>>` (design: `std::vector`); `diagnostics::add`, `report` and `collect` are `const`
(a `diagnostics` is a handle: const is shallow, design.md 2.3); `diagnostics::size()`/`empty()` and
`unreadable_expansion::reason()` are not `noexcept`.

Rules every definition follows (design.md 2.2 to 2.4, spec 2.8, contract 4.3):

1. **Expected errors throw the generated classes** through `detail::raise` (the library's one `throw`): `read_error`
   (load of an unreadable root), `bad_text_error` (an edit's text does not parse clean or breaks a rule; its
   diagnostics are in the given text's positions), `save_error` (the writer failed: `std::throw_with_nested`, so
   `std::rethrow_if_nested` gives the cause, program 4.2), `lost_update_error` (passes through `save` unchanged),
   `diagnostic_error` (a reader on the wrong kind, an extension's own failure). Program bugs: `detached_error`,
   `misuse_error`, `index_out_of_range`, `argument_type_error`.
2. **Detached handles**: every member but `kind()` raises `detached_error` before any other check. A view never
   dangles: the graph lives while any view of it does.
3. **Stale variant view** (finding F4, D16): after `set` changes a value's kind, `kind()` and `as<V>()` follow the
   node; a member only the old variant has raises `misuse_error`; shared members work.
4. **Strong guarantee for every edit**: compute the new text, parse and check it; on any refusal nothing changes
   (text, handles, caches, saved text). Then re-parse the whole document and reconcile the handles (spec 6.1, as
   `ts/src/written/document.ts` `splice` and `Reconcile`).
5. **Text in**: every `config_text` passes through `detail/text_in.hpp`'s one decode (provisional rule, design.md
   2.4). `quote(s)` of a string that is not UTF-8 raises `misuse_error`; so does a name (`rename`, `set_override`,
   load overrides, `program_code(std::string_view)`) that does not match its pattern.
6. **Ports**: a `document_source` or `document_writer` signals failure by throwing; `load` catches `std::exception`
   from `resolve` and `read` (E3004 at the extension line, a `read_error` for the root), `save` catches it from `write`
   (`save_error` with the cause nested, `lost_update_error` as it is). Paths are UTF-8 text; ordering is byte order
   (code point order, design.md 2.4).
7. **No `throw`, `try` or RTTI in `support/`**, and none outside `detail/raise.hpp` and `collect`'s guarded `try`;
   `tests/compile/no_exceptions.cpp` keeps compiling the syntax layer with `-fno-exceptions -fno-rtti`.

### 3.4 Defined whole in the freeze (both wave-1 slices call them)

- `check_lost_updates(files, current)` (`detail/io/lost_updates.hpp`): `misuse_error` when the lengths differ, before
  any comparison; else `lost_update_error` with every path whose current text (absent read as empty) differs from its
  saved text, in batch order.
- `detail::io` (`detail/io/paths.hpp`): `directory_of(path)`, `normalize(path)` (POSIX: `.` and empty segments dropped,
  `..` pops when it can and is kept otherwise, a leading `/` kept), `join(parent_path, spec)` (a leading `/` as is,
  else joined to `directory_of(parent_path)`; then normalized), `has_glob(spec)`, `glob_match(pattern, name)` (spec
  4.3: `*` any run of code points, `?` exactly one, others themselves; last segment only, the caller compares the
  directory). `memory_source` (W) and `file_source` (F) resolve through these and nothing else.

## 4. Slice W: the written layer (wave 1)

**Build.** Replace every stub under `detail/shared/`, `detail/io/` (`memory.hpp`), `detail/written/` and the view's
members with the definitions, and define `support/block.hpp`, `walk_view.hpp`, `ordered_map.hpp` (3.1). Port the
TypeScript binding's structure (it is the reference; Python is the second): `ts/src/written/document.ts` (documents,
splice, reconcile, the strong guarantee), `statements.ts`, `values.ts`, `value.ts` (expanded values and readers),
`bind.ts` (the one derivation: copies, edges, variables, resolutions, expansion), `read.ts` (the read loop),
`graph.ts`, `override.ts`, `processor.ts`, `expansion.ts`, `shape.ts`, `names.ts`, `format.ts`; and the shared
`ts/src/{anatomy,origin,values,text,people,report,locate,diagnostics,block,source}.ts`, `graph/order.ts`. Suggested
files (W may add more under its directories): `detail/written/core.hpp` (the graph core and nodes deriving
`detail::node`), `shape.hpp`, `bind.hpp`, `names.hpp` beside the stub files; keep `definitions.hpp` the one entry
point. Memory: global `new` (D22). `format_diagnostic` per spec 2.3 / 7.7; the people forms per contract 2 (lines and
columns from 1, columns in bytes).

**Adapter (L1).** `cpp/conformance/adapter.cpp` answers `load`, `graph`, `edit`, `save` and `quote` with the dumps of
spec/conformance.md 4.2 (ids for every dumped object, positions in bytes, member names through
`shapes::spelling`, errors through `shapes::error_group_of`); `load` builds a processor over `memory_source` and
passes `knobly::extensions::include()` when `extensions` holds `"include"` (F's code; L1 has no include case).
`hello` claims level 1. Ops above L1 answer `fault`.

**Compiled mode.** Keep `implementation.hpp`'s explicit instantiations compiling: support template members defined in
their headers, `block_traits` specializations declared in `templates.hpp`.

**Acceptance (W).**
- `python3 conformance/driver/run.py -- <build>/knobly_adapter` exits 0 with level 1 claimed and held: 168 L0 and
  60 L1 cases, in header-only (`-DKNOBLY_SANITIZE=ON`) and compiled mode (`-DKNOBLY_COMPILED=ON
  -DCMAKE_CXX_STANDARD=23`); `ctest` green in both, all six contracts linking.
- Catch2 programs (each its own `tests/unit/<name>.cpp`): `written_iteration` (edit during `for` over a block and
  during a walk: the snapshot rule of 3.1, both directions), `written_detached` (every member of a removed
  statement, value and variable raises `detached_error`, `kind()` works, the graph outlives the last other handle),
  `written_stale_variant` (F4), `written_edits` (each edit's refusal leaves the text and every handle unchanged;
  `bad_text_error` positions), `written_save` (one batch, saved text moves only on success, `lost_update_error`
  passes through, `save_error` nests the writer's exception), `written_readers` (each reader, wrong kinds raise
  `diagnostic_error`, slices and indexes with negative bounds), `shared_diagnostics` (`add`, `report`, `collect` for
  a value and a void read), `support_ordered_map`, `support_block` (iterator category, snapshot, `at` past the end),
  `io_memory` (resolve, globs, missing key, memory writer's lost update).
- `bash tools/check.sh` green; if the emitter or loader changed, TypeScript and Python generated output byte-identical
  (render before and after and compare) and their checks green.
- Every `not_built` under `detail/shared/`, `detail/io/`, `detail/written/` and `support/` gone.

**Mutation probe (W).** Make `written_directive::set` write the new text before checking it: `written_edits` (and the
`*-bad-text` L1 cases) must fail. Make `block::begin` read the items lazily at each `++`: `written_iteration` must
fail. Revert both.

## 5. Slice F: file adapters, include, the driver's timeout, CI (wave 1)

**Build.**
- `detail/files/` (`definitions.hpp` the entry point): `files::file_source()`: `resolve(spec, context)` through
  `detail::io::join` (the one join, shared with `memory_source`), a glob listing `directory_of(path)` with
  `std::filesystem` and keeping regular files whose name `glob_match`es, a plain path returned when it is a regular
  file, empty when not found; `read(path)` reads the bytes whole, throwing on failure (any `std::exception`).
  `files::file_writer()`: `write(files)` reads each file's current text from disk (absent: `std::nullopt`), calls
  `check_lost_updates`, then stages every file as a temporary beside its target and renames each into place; a
  failure while staging removes the temporaries and throws (nothing committed). Port of `py/src/knobly/files.py`
  and `ts/src/node.ts` (spec 4.2, 4.3).
- `detail/extensions/definitions.hpp`: `extensions::include()`: `directive()` is `"include"`; `specs(use)` per spec 5.1
  and `ts/src/written/include.ts`: no value, E3005 at `use.origin()`; a first value that is not a string, or a second
  value, E3005 placed at that value's origin (its text as the message argument); else `{values[0].string()}`. Built on
  the public API and `codes.hpp` only (`located_diagnostic`, `diagnostic_error`, `describe`).
- **kno-p5x**: `conformance/driver/adapter.py` gives each request a timeout (60 s by default, `KNOBLY_DRIVER_TIMEOUT`
  overrides it): a response that does not arrive in time is an `AdapterFault` ("timed out after N s waiting for
  <op>"), the adapter is killed and the run goes on (restart for the next case, as for any fault). Read the pipe
  without blocking forever (a reader thread with a queue, or `selectors` over the raw descriptor with the driver's own
  line buffer; not `select` over the text wrapper, whose buffer hides lines). `stub_adapter.py` gains a mode that
  never answers one op; `test_driver.py` proves the stall becomes a fault within the timeout (set small in the test).
  `.github/workflows/ci.yml`: `timeout-minutes: 30` on the `cpp` job (the ctest `TIMEOUT 900` on `conformance` landed
  in the freeze).
- **Compile-time report** (design.md 2.5 point 4, reported, not gated): one step on the `gcc` leg printing, for each
  public header, the wall time of `-fsyntax-only -O2` on a file that includes only it, in header-only and compiled
  mode.

**Acceptance (F).** Catch2 programs `files` (resolve: plain, `..`, absolute, glob with `*` and `?`, not found; read
of a missing file throws; `file_writer`: writes a batch, refuses a lost update with exactly the conflicting paths and
writes nothing, a staging failure (target directory missing) commits nothing) and `include` (`directive()`; no values
raises `diagnostic_error` with code E3005 placed at the origin given), run in a fresh directory under the build tree;
`python3 -m unittest conformance/driver/test_driver.py` green including the stall test; the driver against the
TypeScript adapter (`cd ts && python3 ../conformance/driver/run.py -- node conformance/adapter.ts`) and the Python
adapter (`cd py && python3 ../conformance/driver/run.py -- uv run --locked python conformance/adapter.py`) both exit
0; the C++ L0 run still green; `bash tools/check.sh` green; `contract_files` and `contract_extensions` run.

**Mutation probe (F).** Remove the timeout (block on `readline`): the stall test must fail (by its own short guard).
Drop the `check_lost_updates` call from `file_writer`: the lost-update test must fail. Revert both.

## 6. Slice R: render, the adapter's L2 and L3, program 4.2 (wave 2)

**Build.**
- `detail/rendered/`: `render(graph)` on the written layer's public objects only (spec 7.0; `graph.expand()`),
  rendered directives (snapshots holding their `directive_expansion`'s objects), `rendered_block` through
  `block_traits<rendered::directive>`, `parent`, `closest`, `error`, `addresses()` and `addresses(key_options)`,
  `diff` (spec 7.4 to 7.6), `change` and its variants, `to_string(const address&)`. Port of
  `ts/src/rendered/{render,tree,diff}.ts`. Render nodes derive `detail::node` (3.1).
- Adapter: `render` (with key rules as data, spec/conformance.md 4.3; a non-graph id calls `render` with that object
  and reports the `argument type error`), `diff`, `read` (each reader, negative zero as `"-0"`), `print` (people
  forms), `format`, `cut` (byte slicing). `hello` claims **level 3**.
- `cpp/tests/programs/editor.cpp`: design program 4.2 verbatim (its includes, `apply`, `main`), compiled with
  `-Wsign-conversion` (and `-Wdangling` on Clang); a CTest runs it in a fresh copy of `cpp/tests/programs/editor/`
  (`main.conf` with `@set $pixels ...;` and two `@include "sink.conf"` copies, `sink.conf` with `fps 20hz;`), then
  compares both files with the expected texts (`$pixels` 2400, `fps 30;`, comments kept).
- Delete `detail/not_built.hpp`; `cpp/README.md` (the written and rendered layers, threads, exceptions, compiled
  mode, the path form, level 3); the root `README.md`'s C++ line.
- R may fix any written, shared, io, files or extensions code an L2 or L3 case finds wrong (it owns them now); an
  emitter change is not R's: append an erratum and report it.

**Acceptance (R).** The driver exits 0 with level 3 claimed and held: all 380 cases, in header-only (ASan and UBSan)
and compiled mode (C++23); `ctest` green in both (contracts, every unit program, `programs_editor`, `conformance`);
Catch2 `rendered` (walk with `descend` skipping a subtree, `closest`, addresses under a key rule, `diff` kinds, a
render kept alive by a directive after the graph handle is gone); no `not_built` anywhere under `cpp/`; `bash
tools/check.sh` green; the CI legs green on the pushed branch.

**Mutation probe (R).** Make a key rule ignore its `parent`: the `keys`/rendered cases using the `rasl` rule must
fail. Swap `changed` and `unknown` in `diff`: the rendered `changes` cases must fail. Revert both.

## 7. Choices made overnight (each revisable)

1. **Milestone 2 takes in the rendered layer and claims level 3.** The ask was L1 and L2 "as spec/conformance.md
   defines them"; L2 there is the load, rendered and contract corpora, which render, diff and read (the rendered
   layer, design.md slice 3), and L3 is the include cases, whose extension is in this milestone's scope. The rendered
   layer is small over `expand()` (TypeScript's is about 230 lines). Left for milestone 3: `format.hpp`, programs 4.1
   and 4.3, compile-fail tests, packaging.
2. **`as<V>()` and `visit(f)` are generated whole** (they are schema facts: each variant's kind), not hand-written.
3. **Template members live in `detail/<layer>/templates.hpp`, included in both modes** (errata A3's first option),
   and the block shape reads its layer through one hook, `detail::block_traits<Item>`.
4. **Explicit instantiation lists are read from what each header spells** (`emit_cpp.instantiations`), so a new
   sequence type in the schema is instantiated without a hand list.
5. **Every declaration has a stub definition from the freeze on**, so all six contracts link and every slice starts
   green; `detail/not_built.hpp` aborts (never throws), and R deletes it.
6. **`check_lost_updates` and the path and glob rules are defined in the freeze**, because both parallel slices call
   them; they have one home (`detail/io/`).
7. **`file_source` resolves through the same POSIX join as `memory_source`** (`detail::io::join`), not design.md
   2.4's `lexically_normal()` spelling: one rule for both sources; the results agree for every relative and absolute
   POSIX path the corpus has (a trailing `/` differs). Windows paths are not handled (no MSVC leg, errata T5).
8. **One Catch2 program per unit-test file**, so parallel slices build only their own.
9. **The driver's request timeout is 60 s, overridable** (`KNOBLY_DRIVER_TIMEOUT`); the CI `cpp` job gets
   `timeout-minutes: 30`; the ctest `conformance` test `TIMEOUT 900` (the L0 run alone takes about 90 s under ASan
   here, because of the driver's quadratic position check, errata T2).

## 8. NOT RUN by the freeze

GCC (none on this Mac: the CI `gcc` leg is the first GCC build of the generated union templates and the explicit
instantiations); the TypeScript and Python checks (no TypeScript or Python path, and no emitter or loader they use,
changed: `emit_cpp.py` is loaded only for C++ and by `--check`, which `tools/check.sh` ran green); CI (runs on push).

## 9. Differences from design.md, and why

| design.md | This page | Why |
|---|---|---|
| 7: slice 2 proves "the `load`, `written` and `variables` cases"; render is slice 3 | M2 builds render and claims L3 | the load corpus renders (L2); the levels are cumulative (choice 1) |
| 3.1: `block` members unspecified in how they reach a layer | `detail::block_traits<Item>` | one block template for three item types (DRY), with a seam each layer fills |
| 2.4: `file_source` joins with `lexically_normal()` | `detail::io::join` (POSIX) | one join for both sources (choice 7) |
| 3.3: `insert_statements(std::size_t, ...)`, `processor_options::extensions` a `std::vector`, non-const `diagnostics::add` | as the schema and emitter give them (3.3) | the generated headers are the signatures; the sketch was an estimate |
| 1.4: `as`/`visit` hand-written | generated | schema facts (choice 2) |

## Appendix A. Every hand-defined declaration (the contracts' list)

Generated from the emitter's model at the freeze (`emit_cpp.render_with_hands`); the headers are the authority.


#### `<knobly/knobly.hpp>`

```text
(free):
    to_string(const vl::place&) -> std::string
    to_string(const vl::override&) -> std::string
    to_string(const vl::step&) -> std::string
    to_string(const vl::diagnostic&) -> std::string
    to_string(const vl::located_diagnostic&) -> std::string
    vl::quote(std::string_view) -> vl::config_text
    vl::text(std::string_view) -> vl::config_text
    vl::memory_source(std::shared_ptr<const vl::ordered_map<std::string, std::string>>) -> std::shared_ptr<vl::document_source>
    vl::memory_writer(std::shared_ptr<vl::ordered_map<std::string, std::string>>) -> std::shared_ptr<vl::document_writer>
    vl::check_lost_updates(vl::sequence<vl::file_write>, vl::sequence<std::optional<std::string>>) -> void
(constructors):
    vl::program_code(std::string_view)
    vl::diagnostics()
    vl::diagnostics(vl::sequence<vl::located_diagnostic>)
vl::diagnostics:
    add(const vl::located_diagnostic&) -> void
    size() -> std::size_t
    empty() -> bool
    begin() -> vl::sequence<vl::located_diagnostic>::iterator
    end() -> vl::sequence<vl::located_diagnostic>::iterator
    operator==
```

#### `<knobly/written.hpp>`

```text
(constructors):
    w::processor(w::processor_options)
w::processor:
    load(std::string_view) -> w::document_graph
    load(std::string_view, w::load_options) -> w::document_graph
    operator==
w::document_graph:
    root() -> w::document
    documents() -> vl::ordered_map<std::string, w::document>
    overrides() -> vl::ordered_map<std::string, vl::config_text>
    set_override(std::string_view, std::optional<vl::config_text>) -> void
    read() -> vl::sequence<std::string>
    save(std::shared_ptr<vl::document_writer>) -> vl::sequence<std::string>
    edges() -> vl::sequence<w::document_edge>
    unread() -> vl::sequence<w::document_edge>
    variables() -> vl::sequence<w::variable>
    variables(std::string_view) -> vl::sequence<w::variable>
    diagnostics() -> vl::sequence<vl::located_diagnostic>
    expand() -> w::expansion
    operator==
w::document:
    resolved_path() -> std::string
    saved_text() -> std::string
    text() -> std::string
    syntax() -> s::syntax
    block() -> w::written_block
    included_by() -> vl::sequence<w::document_edge>
    replace_with_text(vl::config_text) -> void
    operator==
w::document_edge:
    copy() -> w::copy
    specs() -> vl::sequence<std::string>
    targets() -> vl::sequence<std::string>
    operator==
w::copy:
    statement() -> w::statement
    via() -> vl::sequence<vl::step>
    operator==
w::statement:
    kind() -> vl::statement_kind
    document() -> w::document
    parent() -> std::optional<w::statement>
    place() -> vl::place
    text() -> std::string
    copies() -> vl::sequence<w::copy>
    replace_with_text(vl::config_text) -> vl::sequence<w::statement>
    remove() -> void
    insert_before(vl::config_text) -> vl::sequence<w::statement>
    insert_after(vl::config_text) -> vl::sequence<w::statement>
    operator==
w::written_directive:
    name() -> std::string
    values() -> vl::sequence<w::written_value>
    block() -> std::optional<w::written_block>
    rename(std::string_view) -> void
    set(vl::config_text) -> void
w::extension_line:
    name() -> std::string
    values() -> vl::sequence<w::written_value>
    block() -> std::optional<w::written_block>
    set(vl::config_text) -> void
w::set_line:
    variable() -> w::set_variable
    values() -> vl::sequence<w::written_value>
    set(vl::config_text) -> void
w::snippet_line:
    name() -> std::string
    parameters() -> vl::sequence<w::parameter>
    block() -> w::written_block
w::use_line:
    snippet_name() -> std::string
    snippet() -> std::optional<w::snippet_line>
    snippets() -> vl::sequence<w::resolution<w::snippet_line>>
    values() -> vl::sequence<w::written_value>
    set(vl::config_text) -> void
w::written_block:
    insert_statements(std::int64_t, vl::config_text) -> vl::sequence<w::statement>
    add_statements(vl::config_text) -> vl::sequence<w::statement>
w::written_value:
    kind() -> vl::value_kind
    text() -> std::string
    place() -> vl::place
    statement() -> w::statement
    list() -> std::optional<w::list>
    set(vl::config_text) -> void
    replace_with_text(vl::config_text) -> vl::sequence<w::written_value>
    remove() -> void
    operator==
w::list:
    items() -> vl::sequence<w::written_value>
    list_() -> std::optional<w::list>
w::slice:
    name() -> w::written_value
    start() -> std::optional<w::written_value>
    end() -> std::optional<w::written_value>
w::index:
    name() -> w::written_value
    index_() -> w::written_value
w::reference:
    name() -> std::string
    declaration() -> std::optional<w::variable>
    resolutions() -> vl::sequence<w::reference_resolution>
w::variable:
    kind() -> vl::variable_kind
    name() -> std::string
    references() -> vl::sequence<w::reference>
    wins() -> vl::sequence<w::reference_resolution>
    shadowed_at() -> vl::sequence<w::reference_resolution>
    operator==
w::set_variable:
    place() -> vl::place
    line() -> w::set_line
    rename(std::string_view) -> void
    set(vl::config_text) -> void
w::parameter:
    place() -> vl::place
    line() -> w::snippet_line
    rename(std::string_view) -> void
w::reference_resolution:
    reference() -> w::reference
    values() -> vl::sequence<w::written_value>
w::expansion:
    block() -> w::expansion_block
    unreadable() -> vl::sequence<w::unreadable_expansion>
    diagnostics() -> vl::sequence<vl::located_diagnostic>
    operator==
w::directive_expansion:
    written() -> w::written_directive
    origin() -> vl::directive_origin
    values() -> vl::sequence<w::expanded_value>
    block() -> std::optional<w::expansion_block>
    unreadable() -> vl::sequence<w::unreadable_expansion>
    operator==
w::unreadable_expansion:
    written() -> w::statement
    reason() -> vl::unreadable_reason
    origin() -> vl::directive_origin
    operator==
w::expanded_value:
    kind() -> vl::value_kind
    text() -> std::string
    origin() -> vl::origin
    written() -> w::written_value
    definition() -> std::optional<w::written_value>
    chain() -> vl::sequence<w::reference_resolution>
    word() -> std::string
    string() -> std::string
    number() -> double
    integer() -> std::int64_t
    boolean() -> bool
    list() -> vl::sequence<w::expanded_value>
    slice() -> std::variant<w::slice_value, w::index_value>
    error(std::string_view, vl::program_code) -> vl::diagnostic_error
    operator==
w::expanded_list:
    items() -> vl::sequence<w::expanded_value>
w::expanded_slice:
    name() -> std::string
    start() -> std::optional<std::int64_t>
    end() -> std::optional<std::int64_t>
w::expanded_index:
    name() -> std::string
    index() -> std::int64_t
(free):
    w::format_diagnostic(const vl::located_diagnostic&) -> std::string
    w::format_diagnostic(const vl::located_diagnostic&, const w::document_graph&) -> std::string
```

#### `<knobly/rendered.hpp>`

```text
r::rendered:
    block() -> r::rendered_block
    unreadable() -> vl::sequence<w::unreadable_expansion>
    origin() -> vl::directive_origin
    diagnostics() -> vl::sequence<vl::located_diagnostic>
    graph() -> w::document_graph
    error(std::string_view, vl::program_code) -> vl::diagnostic_error
    addresses() -> vl::ordered_map<r::directive, r::address>
    addresses(r::key_options) -> vl::ordered_map<r::directive, r::address>
    diff(const r::rendered&) -> vl::sequence<r::change>
    diff(const r::rendered&, r::key_options) -> vl::sequence<r::change>
    operator==
r::directive:
    name() -> std::string
    values() -> vl::sequence<w::expanded_value>
    block() -> std::optional<r::rendered_block>
    unreadable() -> vl::sequence<w::unreadable_expansion>
    parent() -> std::optional<r::directive>
    origin() -> vl::directive_origin
    written() -> w::written_directive
    closest(std::function<bool(const r::directive&)>) -> std::optional<r::directive>
    error(std::string_view, vl::program_code) -> vl::diagnostic_error
    operator==
(free):
    to_string(const r::address&) -> std::string
    r::render(const w::document_graph&) -> r::rendered
r::change:
    kind() -> vl::change_kind
    address() -> r::address
    operator==
r::added:
    after() -> r::directive
r::removed:
    before() -> r::directive
r::changed:
    before() -> r::directive
    after() -> r::directive
r::unknown:
    before() -> r::directive
```

#### `<knobly/files.hpp>`

```text
(free):
    vl::files::file_source() -> std::shared_ptr<vl::document_source>
    vl::files::file_writer() -> std::shared_ptr<vl::document_writer>
```

#### `<knobly/extensions.hpp>`

```text
(free):
    vl::extensions::include() -> std::shared_ptr<w::extension>
```

Plus, defined by the hand code but not in a contract (templates and hooks): `diagnostics::report`,
`diagnostics::collect`, `written::resolution<D>::copy/winner/shadowed`, the three `detail::block_traits`
specializations' `items`, `as_directive`, `block_of`, `detail::view`'s members, and the members of `block`,
`walk_view` and `ordered_map`.
