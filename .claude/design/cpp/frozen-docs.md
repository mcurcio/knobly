# Frozen page: the user guide (PR 8)

The user guide for all three bindings, and the no-install change to the C++ binding. This page is the contract the
wave 1 and wave 2 slices build against. The skeleton (this page's commit and the one after it) already holds the
site, one sample in each language, the three runners, the shared sample table with every expected output, and the CI
jobs. Every slice below adds to it; none changes what this page fixes without reporting it.

## 0. What the owner asked, and what he picked

Owner, 2026-10-30, on PR 8: "the PR needs to include C++ user guide documentation. Every language binding needs its
own version of a 'quickstart' doc and a 'getting started' and 'advanced usage' style docs. OR, we could have a unified
version of those docs where the language of the code samples is selectable -- that would be really slick".

Owner, 2026-10-30: "i dont want to 'install' villanelle for it to be usable. im not a fan of having to 'install' c++
dependnencies on my filesystem before using them".

His picks, relayed by the orchestrator on 2026-10-30 (not his own words here, so a revisable choice, never a
requirement beyond them):

- One shared set of guides. Every code sample has TypeScript / Python / C++ tabs, synced across the whole site and
  remembered.
- A static site, built by CI on every pull request, deployed to GitHub Pages from `main` only.
- Every sample is pulled from a file that CI compiles and runs, so a sample cannot silently rot.
- The docs tool is a build-time tool only, never a dependency of any package.
- `docs/language.md`, `docs/low-level-api.md` and `docs/rendered-tree.md` fold into the guides; what moves is deleted.
- No install step for C++: no `cmake --install`, no `find_package`, no package config. Two routes: copy the single
  header into your project, or CMake `FetchContent` of the release archive into the build folder (it carries the
  generated headers: no Python, nothing system-wide). `add_subdirectory` of the archive or a vendored copy works the
  same way.

## 1. The docs tool: MkDocs with Material for MkDocs

Prior art compared: Starlight (Astro; `<Tabs syncKey>`), Docusaurus (React; `<Tabs groupId>`), MkDocs with Material
(Python; `content.tabs.link`). All three sync tabs site-wide and remember the choice in the browser. Only MkDocs has
a mature, maintained way to include a named region of a real file: `pymdownx.snippets` sections
(`--8<-- "py/examples/hello.py:main"` includes the lines between `--8<-- [start:main]` and `--8<-- [end:main]`
comments, in any language's comment syntax, dedented), and with `check_paths: true` a missing file or region fails
the build. Starlight and Docusaurus need a hand-written remark plugin or MDX component to cut regions out of a raw
import, which is code to maintain for each. The repo already runs uv for `py/`, so MkDocs adds no new toolchain; a
Node site would add a second pnpm project with a few hundred packages. So: **MkDocs 1.6.1, mkdocs-material 9.7.7,
pymdown-extensions 12.2**, exact pins in `docs/site/pyproject.toml`, every transitive version in
`docs/site/uv.lock`, built with `uv run --locked mkdocs build --strict` from `docs/site/`.

Costs. MkDocs 1.x is in maintenance, and MkDocs 2.0 (in development) drops the plugin and theme system Material
needs; the Material team's own successor, Zensical, reads the same `mkdocs.yml` and Python-Markdown extensions but is
at 0.0.x. The pins hold the site on 1.6.1; moving to Zensical once it reaches 1.0 is a follow-up, and every page is
plain Markdown plus `pymdownx` syntax, so the move is configuration, not a rewrite. mkdocs-material 9.8.0 is newer
but under two weeks old, so 9.7.7.

## 2. Layout (fixed by the skeleton)

| Path | What it is |
|---|---|
| `docs/site/mkdocs.yml` | the site: theme, extensions, `nav`. `pymdownx.snippets` `base_path` is the repository root |
| `docs/site/pyproject.toml`, `docs/site/uv.lock` | the pinned tool (not a package: `[tool.uv] package = false`) |
| `docs/site/pages/*.md` | the pages (`docs_dir: pages`); `build/` and `.venv/` are ignored |
| `examples/samples.json` | **the sample table**: each sample id and the fixture folder it runs in (`null`: an empty folder) |
| `examples/expected/<id>.txt` | what the sample prints, byte for byte, in every language (committed by the skeleton) |
| `examples/fixtures/<name>/` | config files the samples read; samples also use `fixtures/rasl/split/` |
| `ts/examples/<id>.ts` | the TypeScript sample; imports the package as a program does (`villanelle/written`) |
| `py/examples/<id>.py` | the Python sample, run as a program |
| `cpp/examples/<id>.cpp` | the C++ sample, one executable each |
| `ts/examples/examples.test.ts` | runs every `ts/examples/*.ts` (vitest; `pnpm test`) |
| `ts/vitest.config.ts`, `ts/examples/tsconfig.json` | resolve `villanelle/...` to `src/` in the tests and the type check (`pnpm typecheck` runs `tsc -p examples`) |
| `py/tests/test_examples.py` | runs every `py/examples/*.py` (`pytest`); mypy checks `examples/` |
| `cpp/examples/CMakeLists.txt`, `cpp/examples/run_example.cmake` | builds every `cpp/examples/*.cpp` and adds ctest `examples_<id>` |

**The runner rule, the same in all three.** For each sample file the binding has: its id must be in
`examples/samples.json`; copy the fixture folder to a fresh temporary folder; run the sample with that folder as the
working directory; it must exit 0; cut `<run folder>/` from what it printed; the rest must equal
`examples/expected/<id>.txt` byte for byte. The cut exists because TypeScript's `fileSource()` makes paths absolute,
while Python's and C++'s stay relative; for those two it is a no-op. Samples print with `console.log`, `print` and
`std::cout << ... << '\n'` only, and never print a message the spec leaves to each binding beyond what the expected
file shows (if a binding's message differs, report it: section 7).

**A sample file's shape.** A header comment naming the sample and its expected file, then region `main` (every line
a reader copies: imports and code), then nothing else. TypeScript and Python samples are top-level programs; C++ has
`int main()`. Extra named regions (section 4, "Regions") sit inside `main`; a page shows `main` unless the outline
names a region. Markers are comments: `// --8<-- [start:name]` (TS, C++), `# --8<-- [start:name]` (Python). Each
language's sample does the same steps in the same order with that language's idiomatic API
(`for...of` / generator / range-for, `match` where Python narrows, `std::optional` and exceptions in C++), aliases
`namespace vl = villanelle;`, `vw`, `vr` in C++ (cpp/README.md, "Namespaces"), and passes the binding's lint, type
check and formatter (TS: eslint with the type-aware rules, `noUncheckedIndexedAccess`; Python: ruff, ruff format,
mypy strict; C++: the tests' `-Wall -Wextra -Werror`, the pinned clang-format).

**How a page shows a sample** (copy this shape):

````markdown
=== "TypeScript"

    ```ts
    --8<-- "ts/examples/<id>.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/<id>.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/<id>.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/<id>.txt"
```
````

Tab labels are exactly `TypeScript`, `Python`, `C++` everywhere (the link between tabs is the label). Config files
are shown whole from their fixture (` ```conf ` around `--8<-- "examples/fixtures/<name>/<file>"`).

## 3. Pages

`nav` order. Each page: its outline, and the samples it shows (ids from section 4).

1. **Quickstart** (`index.md`)
   - What villanelle is (three layers in one paragraph: syntax tree, the files as written, the rendered tree).
   - Get it, one tab per language. TypeScript: the `npm pack` tarball from the GitHub release. Python: the wheel from
     the release. C++: copy the single header `villanelle.hpp`, or `FetchContent` of the release archive: the CMake
     shown is a region of the file the C++ package job configures (section 6, packaging), so it cannot rot.
   - Hello: `hello.conf` and sample `hello`.
   - A real file: `app.conf` and sample `quickstart` (a variable, three typed reads, no problems).
   - Where next: links to Getting started and the language reference.
2. **Getting started** (`getting-started.md`)
   - A processor, its source and extensions (`file_source`, `include`); load and render: `load_render`.
   - Reading values: kinds and typed readers; a word is untyped until read: `read_values`.
   - Overrides from the program: `overrides`.
   - Problems in the config are diagnostics, never exceptions; printing them: `diagnostics`.
   - Exceptions: what throws (a root that cannot be read; a reader on a wrong kind), the error tree per language
     (generated table `members: errors`): `errors`.
3. **Advanced usage** (a nav section of six pages)
   1. **Editing and saving** (`editing.md`): config text (`quote`, `text`); named edits and a refused edit
     changing nothing: `edit_statements`; changing a variable at its definition, then save through a writer:
     `edit_save`; lost updates: `lost_update`. Where new text goes; renaming; handles and detaching (prose, from
     `low-level-api.md`). Generated tables `members: graph members`, `members: document members`,
     `members: writers`.
   2. **Variables, snippets and includes** (`variables.md`): which files were read and where each variable wins:
     `variables`; snippet copies and their origins: `snippets`; an include added by an edit is unread until
     `read()`: `include_read`. Generated table `members: variable members`. Overrides as a variable kind (prose).
   3. **Diagnostics and your own checks** (`diagnostics.md`): the sink, `collect`, `report`, program codes
     `<namespace>/<name>`: `sink`; formatting (`format_diagnostic`, people forms; C++ `format.hpp`). The generated
     error code table (`error codes`) moves here.
   4. **Walking, addresses and reloads** (`walking.md`): walking with descend / skip; addresses and the key rule:
     `addresses`; what changed between two loads: `diff_reload`. Generated tables `members: addresses`,
     `members: readers`. A custom schema is checked by walking and reporting (links `sink`).
   5. **Sources and extensions** (`sources.md`): your own document source: `custom_source`; memory sources and
     writers; the include extension's rules; writing an extension (prose only). Generated tables `members: processor`,
     `members: sources`.
   6. **The syntax tree** (`syntax.md`): `parse`, tokens, nodes, losslessness, syntax diagnostics: `syntax_tree`.
4. **Language reference** (`language.md`): `docs/language.md` moved whole and adjusted (links, "both languages" to
   "every binding"); its config examples stay as they are (they cite load cases and fixtures).
5. **How the bindings differ** (`differences.md`): the "How the two languages differ" sections of the two old pages,
   with a C++ column: names, positions (UTF-16 code units, code points, bytes), paths (absolute in TS), async, errors,
   compile-time refusals (cpp/README.md, compile-fail tests), threads, memory.

Every `<!-- generated: ... -->` table of the old pages moves with its section, and its `file` in `docs/tables.json`
names the new page; `python3 tools/gen-api.py docs` rewrites them and `tools/gen-api.py --check` (tools/check.sh)
stays green.

## 4. The sample table

Every sample exists in all three languages, doing the same steps, printing its expected file. Files:
`ts/examples/<id>.ts`, `py/examples/<id>.py`, `cpp/examples/<id>.cpp`. Expected: `examples/expected/<id>.txt`
(committed; computed with TypeScript on 2026-10-30, and the Python output checked for `diagnostics`). Regions: every
sample has `main`; the extra regions listed must exist in all three files.

| id | Page | What it shows (the steps, in order) | Fixture | Extra regions |
|---|---|---|---|---|
| `hello` | Quickstart | processor with the file source; load `hello.conf`; render; print the `greeting` value read with the string reader | `examples/fixtures/hello` | none |
| `quickstart` | Quickstart | load `app.conf`, render; take the first `server` directive; print `host` (string reader), `port` (integer reader: `$port` is 8080), `debug` (boolean reader, printed `true`/`false`), then `problems <count of render diagnostics>` | `examples/fixtures/quickstart` | `load`, `read` |
| `load_render` | Getting started | processor with the file source and the include extension; load `main.conf`; print `read <path>` per document in order; render; walk, descending only into `graph`, and print `node <values joined by space> (<origin place>)` per `node` | `fixtures/rasl/split` | `processor`, `walk` |
| `read_values` | Getting started | load and render `values.conf`; print each directive's name and its first value through one reader: word, string, string (raw `'C:\new'`), number, integer, boolean, the list's items as numbers joined by spaces, then the slice reader on `leds[144~152]` (`slice <name> <start>~<end>`) and on `leds[0]` (`index <name> <index>`) | `examples/fixtures/values` | none |
| `overrides` | Getting started | one processor (file source, include); load twice: no overrides, then `leds_host` = `quote("10.0.70.1")`; each time print `overrides: <names joined by ", " or none>` and, for every `target` in a `node` block under `graph`, `  <node id> -> <target as string>` | `fixtures/rasl/split` | `load` |
| `diagnostics` | Getting started | load `main.conf` (file source, include), render; print `format_diagnostic(d, graph)` for each render diagnostic, in order | `examples/fixtures/broken` | `print` |
| `errors` | Getting started | load `missing.conf`: catch the read error, print `cannot read: <paths joined by ", ">`; load `main.conf`, render, read `fps` with the number reader: catch the diagnostic error, print `bad value: <code> at <place>` | `examples/fixtures/errors` | `read_error`, `diagnostic_error` |
| `edit_statements` | Editing and saving | memory source over `{"main.conf": "server {\n    host a;\n    # the port\n    port 80;\n}\n"}`; `host.set(quote("10.0.60.31"))`; port's first value `set(text("8080"))`; `insert_statements(1, text("timeout 30s;"))` on the server block; `rename("listener")`; `host.set(text("1; x"))` is refused: print `refused: <code> (line <l+1>, column <c+1>)` per diagnostic; print the root text; `unsaved <text differs from saved text>`; save to a memory writer over the same files, print `saved <paths>`; `unsaved false` | none | `edit`, `refused` |
| `edit_save` | Editing and saving | load `main.conf` (file source, include); the `set` variable `pixels`: `set(text("2400"))`; save with the file writer, print `saved <paths>`; print the line of `main.conf` on disk holding `$pixels`; render, print `<node id> max_count <integer>` per `max_count` in walk order | `fixtures/rasl/split` | `edit`, `save` |
| `lost_update` | Editing and saving | load `app.conf`; change the file on disk behind the graph (`debug false` to `debug true`); set `server`'s `host` to `quote("0.0.0.0")`; save: catch the lost update error, print `changed on disk: <paths>`; load again, make the same edit, save, print `saved <paths>`, print the file | `examples/fixtures/quickstart` | `conflict` |
| `variables` | Variables, snippets and includes | load `main.conf` with override `leds_host` = `quote("10.0.70.1")`; per document `file <path> included at [<place of each includer's copy statement, path:line 1-based>]`; per variable `$<name> <kind> <path:line or override> wins at [...] shadowed at [...]` | `fixtures/rasl/split` | none |
| `snippets` | Variables, snippets and includes | memory source: a `twinkle $source` snippet (`seed 11337; connect $source;`) used by two `node TwinkleEffect` directives; render; per node, per directive in its block: `<node id>: <name> <values> (written at <origin place>, via <steps joined by "; ">)` | none | none |
| `include_read` | Variables, snippets and includes | memory source `main.conf` = `name main;\n`, `extra.conf` = `name extra;\n`, include extension; `add_statements(text('@include "extra.conf";'))` on the root block; print `unread <count>: <rendered name values>`; print each render diagnostic's people form; `read()`; print the unread line again | none | none |
| `sink` | Diagnostics and your own checks | memory source `port eighty;\nnode Mystery m;\nfps $x;\n`; render; a sink started with the render's diagnostics; `collect` the integer read of `port` (absent: print `port unset`); `report` each `node` with message `unknown node type <type>` and code `app/unknown-node`; print every sink diagnostic's people form | none | `collect`, `report` |
| `addresses` | Walking, addresses and reloads | load and render `main.conf`; twice, without a key rule (`by position:`) and with rasl's node-id rule (`by node id:`): per `target` in walk order, `  <address> = <first value's text>` | `fixtures/rasl/split` | `key` |
| `diff_reload` | Walking, addresses and reloads | one processor; render `main.conf`; rewrite the file on disk (`@set $pixels 2284;` to `2400`, and delete the `node Waveform hue_ramp { ... }` block and the blank line after it); load and render again; print `<change kind> <address>` per change of `before.diff(after)` under the node-id key rule | `fixtures/rasl/split` | `diff` |
| `custom_source` | Sources and extensions | a document source of the program's own that wraps a memory source and records each `read` path; `main.conf` includes `sink.conf` twice with `@set $name a;` / `b;`; render; print `sinks <values>` and `reads <paths>` (each file read once) | none | `source` |
| `syntax_tree` | The syntax tree | `parse("server {\n    port 8080; # the port\n}\n")`; print `tokens <n>, problems <n>`; print the tree depth first, two spaces per level: `<node kind> tokens <start>-<end> from <first token kind> "<first token text>"`; `comment <text of the COMMENT tokens>`; `lossless true`; parse `a 1;\nb "open;\nc 3;\n` and print `<code> at line <l+1>, column <c+1>` per diagnostic | none | `parse`, `tree` |

The fixtures: `examples/fixtures/hello/hello.conf`, `quickstart/app.conf`, `values/values.conf`,
`broken/main.conf` and `broken/part.conf`, `errors/main.conf` (all committed), and `fixtures/rasl/split/`.

## 5. What the skeleton committed

- `docs/site/` with the Quickstart page holding the `hello` sample in three linked tabs and its output; it builds
  with `uv run --locked mkdocs build --strict`, and a missing region fails it (checked by planting one).
- `hello` in all three languages; each runner passes it and fails on a planted wrong expected file (checked).
- `examples/samples.json`, every `examples/expected/<id>.txt`, every fixture.
- CI: job `docs` (every push and pull request: build, then `actions/upload-pages-artifact` v5.0.0) and job
  `docs-deploy` (`needs: docs`, only on push to `main`; `permissions: pages: write, id-token: write`; environment
  `github-pages`; `actions/deploy-pages` v5.0.1), both pinned by commit sha.

## 6. The waves

### Wave 1 (four slices at the same time; owned paths are disjoint)

**ts-samples.** Owns `ts/examples/**` except `examples.test.ts` and `tsconfig.json` (the runner; change them only to
fix a bug, and report it). Task: write `ts/examples/<id>.ts` for every id of section 4 but `hello` (done), each with
regions `main` and its extra regions, each printing its expected file. Done when `corepack pnpm test`,
`corepack pnpm typecheck`, `corepack pnpm lint` and `corepack pnpm build` pass in `ts/` under Node 24.

**py-samples.** Owns `py/examples/**`. Task: write `py/examples/<id>.py` for every id but `hello`, same rules, using
`match` where Python narrows a kind. Done when, in `py/`, `uv run --locked pytest -q`, `ruff check`,
`ruff format --check` and `mypy` pass.

**cpp-samples.** Owns `cpp/examples/**` (`CMakeLists.txt` and `run_example.cmake` are the runner; change them only
to fix a bug, and report it). Task: write `cpp/examples/<id>.cpp` for every id but `hello`, same rules. Done when a
build tree under `/Volumes/Dock/tmp/vil-cpp-build-cpp-samples` (configure with `-DVILLANELLE_SANITIZE=ON`) builds
and `ctest -R examples_` passes, once more in compiled mode (`-DVILLANELLE_COMPILED=ON -DCMAKE_CXX_STANDARD=23`), and
the pinned clang-format (`tools/api/emit_cpp.py` `CLANG_FORMAT`) leaves the files unchanged.

Shared by the three: `examples/**` (the table, the expected files, the fixtures) is frozen. A sample that cannot
print its expected file without breaking the spec or its binding's idiom is a finding: append it to
`.claude/errata.md` and report it; do not edit `examples/**`. If one binding's messages differ from the expected
text (a diagnostic's message is "for people and may differ between bindings"), report it with both texts: the end
review decides whether the expected file or the binding changes.

**packaging.** Owns `cpp/CMakeLists.txt` except the `add_subdirectory(examples)` block, `cpp/tests/consumer/**`,
`cpp/tests/consumer-*/**` (new), `.github/release-cpp.sh`, `.github/release-build.sh`, `tools/amalgamate.py`, the
`cpp-package` job of `.github/workflows/ci.yml` (only that job), the "Using it" and "Build and test" sections of
`cpp/README.md`, and the C++ paragraph of `README.md`. Task:

1. Delete the install: option `VILLANELLE_INSTALL`, `include(GNUInstallDirs)`, `$<INSTALL_INTERFACE:...>`, the
   `install(...)` rules, `CMakePackageConfigHelpers` and the version file. The target stays
   `villanelle::villanelle` (an `ALIAS` of an `INTERFACE` library); the version still comes from
   `support/config.hpp`. No alias, shim or message for the removed option.
2. The routes, each tested in the `cpp-package` job with `python`, `python3`, `uv` and `curl` stubbed to fail and
   nothing installed anywhere:
   - `FetchContent` of the release archive built by `.github/release-cpp.sh` (a `file://` URL with its `URL_HASH`)
     into the consumer's build folder, then `target_link_libraries(... villanelle::villanelle)`, in header-only and
     compiled mode (`VILLANELLE_COMPILED=ON` as a cache option of the subproject, or the program defining
     `VILLANELLE_HEADER_ONLY=0` and compiling `<villanelle/implementation.hpp>` once);
   - `add_subdirectory` of the extracted archive;
   - the single header alone (as today);
   - every route builds and runs `cpp/tests/consumer/consumer.cpp` and checks the stamped inline namespace (`nm`).
3. The Quickstart's C++ CMake snippet is a region of a file the job configures: put region `fetchcontent` (the
   `include(FetchContent)`, `FetchContent_Declare` and `FetchContent_MakeAvailable` lines, and
   `target_link_libraries`) in the consumer's `CMakeLists.txt`, written so the region reads as a user writes it (the
   URL and hash come in as variables the test sets; name them so the page can say "the release's URL and SHA-256").
4. `cpp/README.md` "Using it": the two routes and `add_subdirectory`, compiled mode, versions; no install text.
   Root `README.md`: the C++ paragraph says the same in one sentence (drop "`cmake --install` makes
   `find_package(villanelle)` work").
5. Done when the `cpp-package` steps pass locally (archive under `/Volumes/Dock/tmp/vil-cpp-build-packaging`), the
   main C++ build and `ctest` still pass, and `grep -rn "find_package\|cmake --install\|VILLANELLE_INSTALL"` finds
   nothing outside `.claude/design/` and `.beads/`.

### Wave 2 (one slice, after wave 1 lands)

**pages.** Owns `docs/site/pages/**`, `docs/site/mkdocs.yml`, `docs/site/hooks/**` (new), `docs/language.md`,
`docs/low-level-api.md`, `docs/rendered-tree.md` (deleted), `docs/tables.json`, `README.md`, `ts/README.md`,
`py/README.md`, `cpp/README.md` (links and pointers only; packaging's sections stay), `spec/**/*.md` and
`spec/schema/diagnostics.json` (links only), `tools/api/*.py` and `tools/gen-api.py` (comments and the docs paths
only), `.claude/skills/villanelle-binding/SKILL.md` (links). Task:

1. Write every page of section 3 from the old pages' prose (their test-backed examples are the starting material;
   replace each code example by the sample that shows it, in three tabs, with its output). Keep the plain style of the
   old pages: short sentences, every term defined, the spec linked where it wins.
2. Delete `docs/language.md`, `docs/low-level-api.md`, `docs/rendered-tree.md`; move each generated table and set its
   `file` in `docs/tables.json`; run `python3 tools/gen-api.py docs`; `python3 tools/gen-api.py --check` passes.
3. Fix every link to the old pages across the repository (not `.claude/design/` history or `.beads/`): `README.md`,
   the binding READMEs, `spec/`, `tools/`, the skill. Point README.md and each binding README at the guide (the Pages
   URL, `https://mcurcio.github.io/villanelle/`, and the page source under `docs/site/pages/`).
4. Make completeness a build failure: a MkDocs hook (`docs/site/hooks/samples.py`, `hooks:` in `mkdocs.yml`) fails
   the build unless every id in `examples/samples.json` is included on some page from all three of
   `ts/examples/<id>.ts`, `py/examples/<id>.py` and `cpp/examples/<id>.cpp`. Show it bites by planting a missing tab.
5. Done when `uv run --locked mkdocs build --strict` passes in `docs/site/`, `bash tools/check.sh` passes, and
   `grep -rn "low-level-api.md\|rendered-tree.md\|docs/language.md"` finds nothing outside `.claude/design/` and
   `.beads/`.

## 7. Choices made overnight

- MkDocs 1.6.1 + Material 9.7.7 + pymdown-extensions 12.2 (section 1), the site under `docs/site/`, pages under
  `docs/site/pages/`, output `docs/site/build/`.
- The samples' shared parts live at the repository root, `examples/` (table, expected output, fixtures), so the three
  bindings read one copy; each binding's sample files live in its own folder.
- Expected outputs are frozen now, computed by running throwaway TypeScript versions of every sample against the
  built package, so the three sample slices can run at the same time against fixed files.
- Sample ids are snake_case, so a Python sample is a valid module name for mypy.
- The runners cut the run folder from the output, because TypeScript's file source makes paths absolute; the pages
  show the relative form, and `differences.md` says so.
- TypeScript samples are top-level programs run in the vitest process (default `forks` pool, so `process.chdir`
  works) with `console.log` captured; `villanelle/...` resolves to `src/` through `ts/vitest.config.ts`, derived from
  the package's export map, and through `paths` in `ts/examples/tsconfig.json` (one wildcard rule, not a second list).
- Python samples run as programs (`subprocess`, the test's own interpreter); C++ samples are one executable each, built
  with the tests' warnings, run by a CMake script as the design programs are.
- Install commands for TypeScript and Python on the Quickstart are shell lines, not run in CI (nothing to compile);
  the C++ CMake snippet is a region of the consumer test (packaging, step 3).
- The `docs` job uploads the Pages artifact on every run (cheap; it is what the deploy job reads); only the
  `docs-deploy` job is limited to `main`.

## 8. What this leaves out, and costs

- GitHub Pages must be switched to "GitHub Actions" as its source in the repository settings (the owner's setting)
  before the first deploy from `main` works; until then `docs-deploy` fails on `main` only.
- No search index tuning, versioned docs (one site for `main`), or API reference pages generated from the schema
  beyond the existing generated tables.
- Three runners (vitest, pytest, CMake) implement one rule (section 2) in three languages: a small, unavoidable
  per-binding cost; the table and expected files are single copies.
- The expected files fix messages for people that the spec allows to differ between bindings; a binding that words one
  differently fails its sample until the end review picks the expected text or a binding change.
