# villanelle

A small configuration language: directives ended by `;` (a line break is a space, as in nginx), `{ }` blocks,
lists and slices (`name[1~3]`), raw single-quoted strings, `#` comments, and variables and snippets written as
`@` statements (`@set`, `@snippet`, `@use`, and an extension's `@include`), with parsers for TypeScript, Python
and C++ generated from one grammar.

```conf
@set $pixels 2284;

@snippet twinkle $source {
    seed 11337;
    mode brightness;
    frequency_hz 0.3;
    attack_ratio 0.33;
    min_speed 1.0;
    max_speed 3.0;

    connect $source;
}
```

(Excerpt of [`fixtures/rasl/family_room.conf`](fixtures/rasl/family_room.conf), which both packages' tests load.)
**The user guide: [https://mcurcio.github.io/villanelle/](https://mcurcio.github.io/villanelle/)** (source: [`docs/site/pages/`](docs/site/pages/)), one set of pages with every
sample in TypeScript, Python and C++. The language is taught in its [language reference](https://mcurcio.github.io/villanelle/language/); its rules
live in the grammar and in
[spec/expansion.md](spec/expansion.md) (which `@set` a `$name` reaches, and which definition wins).

## Using it from a program

villanelle has three layers, each built on the one below; a program can work at any of them.

- **The syntax tree.** `parse(text)` reads one text into tokens and a tree, with every character in exactly one
  token. It never fails: problems are diagnostics.
- **The low level: the files as written.** `processor.load(path)` reads a root file and every file it includes into
  a document graph, and shows which files were read, what variables exist and which `set` line wins where. A
  program can change any of it (`set(text)` on a line, a variable or a value, `setOverride` / `set_override` for an
  override), each edit taking config text made by `quote()` or `text()`, and `graph.save(writer)` writes the changed files back, comments and layout kept; `graph.read()` reads
  files an edit newly includes. The low level knows nothing of the rendered tree. Guide:
  [Editing and saving](https://mcurcio.github.io/villanelle/editing/).
- **The rendered tree.** `render(graph)` works out variables, snippets and included files into the directives a
  program reads, each value with the place it was written. It also gives every directive an address under the
  program's key rule, and `before.diff(after, { key })` (Python: `before.diff(after, key=...)`) lists what changed
  between two renders. Guide: [Getting started](https://mcurcio.github.io/villanelle/getting-started/).

```ts
  // import { memorySource, quote } from "villanelle"; import { villanelle } from "villanelle/written";
  const config = villanelle({ source: memorySource(FILES), extensions: [include()] });
  const graph = await config.load("main.conf", { overrides: { leds_host: quote("10.0.70.1") } });
```

```python
    # import villanelle as vl; from villanelle import written
    config = written.Processor(source=vl.memory_source(FILES), extensions=[include()])
    return config.load("main.conf", overrides={"leds_host": vl.quote("10.0.70.1")})
```

(Excerpts of `ts/src/written/tracer.test.ts` and `py/tests/test_tracer.py`, which go on to list the variables of
[`fixtures/rasl/split`](fixtures/rasl/split/), change `$pixels`, save, and render.) Every sample in the user guide is a file each binding's tests run
([`examples/samples.json`](examples/samples.json)), so a sample cannot rot.

Each layer is its own import path, and every name has exactly one (milestone 6; [spec/binding-guide.md](spec/binding-guide.md)
rule 9). Type names carry no prefix (`DocumentGraph`, `Rendered`), the same in TypeScript and Python; C++ spells them
in snake_case, as its standard library does (`document_graph`), and its import paths are namespaces.

<!-- generated: members: entry points (tools/gen-api.py docs) -->
| Entry point | TypeScript | Python | C++ |
|---|---|---|---|
| what every layer shares, and the ports | `villanelle`: `quote`, `text`, `ConfigText`, `memorySource`, `memoryWriter`, `Diagnostics`, `VillanelleError`, `DocumentSource`, `Place`, ... | `villanelle`: `quote`, `text`, `ConfigText`, `memory_source`, `memory_writer`, `Diagnostics`, `VillanelleError`, `DocumentSource`, `Place`, ... | `villanelle`: `quote`, `text`, `config_text`, `memory_source`, `memory_writer`, `diagnostics`, `villanelle_error`, `document_source`, `place`, ... |
| the syntax tree | `villanelle/syntax`: `parse`, `spanOf`, `textOf`, `Syntax`, `Token`, `Node`, `TokenKind`, ... | `villanelle.syntax`: `parse`, `span_of`, `text_of`, `Syntax`, `Token`, `Node`, `TokenKind`, ... | `villanelle::syntax`: `parse`, `span_of`, `text_of`, `syntax`, `token`, `node`, `token_kind`, ... |
| the low level | `villanelle/written`: `villanelle`, `formatDiagnostic`, `DocumentGraph`, `Statement`, `StatementKind`, ... | `villanelle.written`: `Processor`, `format_diagnostic`, `DocumentGraph`, `Statement`, `StatementKind`, ... | `villanelle::written`: `processor`, `format_diagnostic`, `document_graph`, `statement`, `statement_kind`, ... |
| the rendered tree | `villanelle/rendered`: `render`, `Rendered`, `Directive`, `KeyRule`, ... | `villanelle.rendered`: `render`, `Rendered`, `Directive`, `KeyRule`, ... | `villanelle::rendered`: `render`, `rendered`, `directive`, `key_rule`, ... |
| the include extension | `villanelle/include`: `include`, ... | `villanelle.include`: `include`, ... | `villanelle::extensions`: `include`, ... |
| files on disk | `villanelle/node`: `fileSource`, `fileWriter`, ... | `villanelle.files`: `file_source`, `file_writer`, ... | `villanelle::files`: `file_source`, `file_writer`, ... |
| files over `fetch` | `villanelle/browser`: `fetchSource`, `fetchWriter`, ... | none | none |
<!-- end generated -->

**C++** (milestone 2): a header-only library, the CMake target `villanelle::villanelle`, with the syntax tree
(`<villanelle/syntax.hpp>`), the low level (`<villanelle/written.hpp>`), the rendered tree
(`<villanelle/rendered.hpp>`), files on disk (`<villanelle/files.hpp>`) and the include extension
(`<villanelle/extensions.hpp>`), with names in snake_case from the same schema ([`cpp/README.md`](cpp/README.md)).
Its adapter claims level 3 of the conformance cases. Nothing is installed: copy the single header `villanelle.hpp`
(made by `tools/amalgamate.py`) into your project, or take each release's C++ source archive, which carries the
generated headers, with CMake `FetchContent` or `add_subdirectory` (no Python needed either way).

## The language is defined by one file

[`grammar/Villanelle.g4`](grammar/Villanelle.g4) (ANTLR4) is the specification. ANTLR4
generates the TypeScript and Python parsers from it, and villanelle's own parser generator
([`tools/parser/gen.py`](tools/parser/gen.py), no runtime library) the C++ one, so every parser accepts exactly the
grammar's language. Its entry rules (`statementsText`, `valuesText`, `valueText`, `itemsText`, `boundText`,
`sliceNameText`, `nameText`) also check the shape of every text a program hands to an edit, so no binding keeps a scanner of its own. [`grammar/villanelle.ebnf`](grammar/villanelle.ebnf)
is the same grammar in W3C EBNF, kept by hand as a readable view (whether to derive or retire it is an open question
in `.claude/errata.md`).

The API every language binding offers on top of the parsers is specified, language-neutrally, in
[`spec/`](spec/README.md): the layers, one word per concept ([`spec/glossary.md`](spec/glossary.md)),
and the schema in [`spec/schema/`](spec/schema/), from which each binding's declarations (every public signature,
kind list, error class and diagnostic code) are generated ([`spec/codegen.md`](spec/codegen.md)). The spec wins over either
binding's code (owner, 2026-10-27: "Within villanelle I want the spec to win over a reference
language").

The grammar is checked to be unambiguous, so every valid file has exactly one parse:

```bash
tools/check.sh
```

The script runs these checks:
- it translates the parser rules to Bison and requires 0 conflicts, for the document rule and each entry rule;
- it checks that no two token kinds can match the same text;
- it confirms that both checks still catch the planted bad grammars in `tools/planted/`;
- it checks the API schema (every type resolves, the layer direction, the error tree), renders both bindings'
  declarations, checks the generated docs tables are current, and validates the schema files against their JSON
  Schema, each check also run against planted broken copies;
- it runs the kind lint's and the conformance driver's own tests;
- it runs villanelle's own parser generator over the grammar, which must accept it and refuse every planted grammar
  in `tools/planted-parser/`.

It needs `python3`, `bison` and `uv`.

## Layout

| Path | What it is |
|---|---|
| `grammar/` | The grammar (`Villanelle.g4`) and its EBNF view |
| `tools/` | The soundness checks (`check.sh`), the planted bad grammars they must catch, the parser generator script (`gen.sh`), the API generator (`gen-api.py`: a loader in `api/loader.py` and one emitter per language) and the kind lint (`lint/`) |
| `ts/` | The TypeScript package, npm name `villanelle` ([`ts/README.md`](ts/README.md)) |
| `py/` | The Python package, PyPI name `villanelle` ([`py/README.md`](py/README.md)) |
| `cpp/` | The C++ library, header-only, CMake target `villanelle::villanelle` ([`cpp/README.md`](cpp/README.md)) |
| `conformance/` | Test cases every package must pass, with the expected output for each, and the one driver that runs them against each package's adapter ([`spec/conformance.md`](spec/conformance.md)): syntax cases ([`conformance/format.md`](conformance/format.md)), low-level cases in `conformance/written/`, load cases in `conformance/load/`, addresses and diff order in `conformance/rendered/`, and readers, positions and formatting in `conformance/contract/`; `conformance/corpora.json` lists them |
| `examples/` | The user guide's samples: the table (`samples.json`), each sample's expected output and its fixtures; each binding's sample files are in its own `examples/` |
| `fixtures/rasl/` | rasl's real config files, which each package's rasl test loads ([`fixtures/rasl/README.md`](fixtures/rasl/README.md)) |
| `docs/` | The user guide's site ([`docs/site/`](docs/site/): MkDocs, pages in `docs/site/pages/`, published at [https://mcurcio.github.io/villanelle/](https://mcurcio.github.io/villanelle/)) and `tables.json`, the rows of its generated tables |
| `.github/` | CI and the release build (`workflows/ci.yml`, `release-build.sh`) |
| `package.json`, `.releaserc.json` | Release tooling only (semantic-release); the packages are `ts/` and `py/` |
| `design/` | The design record ([`design/RECORD.md`](design/RECORD.md)), run logs, the older plans, drafts, reviews and experiments |
| `reference/` | The config code copied from mcurcio/rasl, as source material ([`reference/README.md`](reference/README.md)) |
| `.beads/` | The issue tracker (`bd ready` for work) |

## Build and test

The generated parsers and API declarations are not committed (owner, 2026-10-23: "Don't commit the generated
code, just the source"). `tools/gen.sh ts` and `tools/gen.sh py` write them to `ts/src/gen/` (with
`ts/conformance/shapes.ts`) and `py/src/villanelle/_gen/` and `_api/` (with `py/conformance/shapes.py` and
`py/tests/api_contract.py`), all ignored by git, and every build and test runs it first; `tools/gen.sh cpp` writes
the C++ headers into `cpp/` (CMake runs it at configure time; Python and `uv` only, no Java). The generated docs tables are the one committed output
(`python3 tools/gen-api.py docs`; [spec/codegen.md](spec/codegen.md) section 6). It needs
Java 11+ and `curl`: it downloads the ANTLR 4.13.2 jar once, checks its sha256, and caches it in
`$ANTLR_JAR_DIR` (default `~/.cache/antlr`).

From the repository root:

```bash
bash tools/check.sh                       # grammar soundness: needs python3, bison, uv

corepack pnpm -C ts install               # TypeScript: Node 24 (.nvmrc), pnpm through corepack
corepack pnpm -C ts test                  # also: typecheck, lint, build

cd py && uv run pytest                    # Python 3.11 or later, through uv
uv run ruff check && uv run ruff format --check && uv run mypy

cmake -S cpp -B build && cmake --build build && ctest --test-dir build   # C++: CMake 3.24+, a C++20 compiler
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs these on every push and pull
request: the grammar check, the TypeScript checks on Node 24, the Python checks on Python 3.11
and 3.13, the C++ tests (GCC, Clang and AppleClang, each header-only and compiled), the C++ format check,
a C++ package check (a program built from the release archive with `FetchContent` and `add_subdirectory`, and from
the single header alone, with nothing installed), and the user guide's build (`docs/site/`).

## Releases

A push to `main` that passes CI runs semantic-release. It takes the next version from the
Conventional Commits since the last release and builds the npm tarball of `ts/`, the Python
wheel and sdist of `py/`, and the C++ source archive and single header of `cpp/` with
`.github/release-build.sh`. The version is stamped into the
manifests for the build only and never committed. The packages go to GitHub Release assets only;
nothing is published to npm or PyPI.

Releases are dry-run until the repository variable `RELEASE_ENABLED` is `true` (owner, 2026-10-23:
"Dry-run until I enable it"). In dry-run the job still computes the version and builds every
asset, and uploads them as a workflow artifact; it creates no tag and no release. To turn
releases on:

```bash
gh variable set RELEASE_ENABLED --body true -R mcurcio/villanelle
```

## Status

The TypeScript and Python packages are built from the grammar and pass the same conformance cases, run by one
shared driver (`python3 conformance/driver/run.py -- <adapter>`, [`spec/conformance.md`](spec/conformance.md)). Both have the syntax tree, the low level (the files as written, editable and saved back) and the
rendered tree; the high-level API, where a program declares its directives, is deferred (`vil-xlo`). The C++
library has all three (level 3). No release has
been made yet. The grammar design was done in [mcurcio/rasl#2](https://github.com/mcurcio/rasl/pull/2), where this
language began as `@rasl/config`.
