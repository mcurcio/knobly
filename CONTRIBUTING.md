# Contributing to knobly

Thanks for helping. This page explains how the repository fits together, how to build and test it, and how
changes land. If you are an AI coding agent, read [AGENTS.md](AGENTS.md) first; it points back here.

## Reporting a bug or asking for something

Open an [issue](https://github.com/mcurcio/knobly/issues). For a bug, include the smallest config text that shows
it, which language you used (TypeScript, Python or C++), and what you expected. Because all three bindings must
behave the same, a bug in one is usually a missing conformance case for all of them.

## How the pieces fit

knobly is one language with three bindings. Everything flows from two sources:

- **The grammar, [`grammar/Knobly.g4`](grammar/Knobly.g4) (ANTLR4), is the language.** ANTLR generates the
  TypeScript and Python parsers from it; knobly's own parser generator ([`tools/parser/gen.py`](tools/parser/gen.py))
  generates the C++ one. Change the language only there. [`grammar/knobly.ebnf`](grammar/knobly.ebnf) is the same
  grammar in W3C EBNF, kept by hand as a readable view.
- **The spec, [`spec/`](spec/README.md), is the API.** It describes, language-neutrally, what every binding offers:
  the layers, one word per concept ([`spec/glossary.md`](spec/glossary.md)), and a schema
  ([`spec/schema/`](spec/schema/)) from which each binding's public declarations are generated
  ([`spec/codegen.md`](spec/codegen.md)). Where a binding's code and the spec disagree, the spec wins and the code
  has a bug.

[`spec/expansion.md`](spec/expansion.md) holds the rules for what a `$name`, a `@use` and an included file reach.
The [conformance cases](spec/conformance.md) are the shared tests every binding must pass, run by one driver.

### Layout

| Path | What it is |
|---|---|
| `grammar/` | The grammar (`Knobly.g4`) and its EBNF view |
| `spec/` | The language-neutral API spec and its schema |
| `ts/` | The TypeScript package ([`ts/README.md`](ts/README.md)) |
| `py/` | The Python package ([`py/README.md`](py/README.md)) |
| `cpp/` | The header-only C++ library, CMake target `knobly::knobly` ([`cpp/README.md`](cpp/README.md)) |
| `conformance/` | The shared test cases, their expected output, and the driver that runs them against each binding ([`spec/conformance.md`](spec/conformance.md)) |
| `examples/` | The user guide's samples: the table (`samples.json`), each sample's expected output and fixtures. Each binding's sample programs live in its own `examples/` |
| `docs/site/` | The user guide (MkDocs Material); pages in `docs/site/pages/`, the logo in `docs/site/pages/assets/` |
| `tools/` | The grammar checks (`check.sh`), the parser generator (`gen.sh`), the API generator (`gen-api.py`), the kind lint (`lint/`) and the logo generator (`logo.py`) |
| `fixtures/rasl/` | Real config files from [rasl](https://github.com/mcurcio/rasl), which the tests load |
| `design/` | The design record ([`design/RECORD.md`](design/RECORD.md)) and older plans |
| `reference/` | The code knobly started from, copied from rasl as source material |
| `.beads/` | The issue tracker the maintainers' agents use (`bd`) |

## Building and testing

You need Node 24 (run `nvm use`; it reads `.nvmrc`), Python 3.11 or later with [uv](https://docs.astral.sh/uv/),
Java 11 or later and `curl` (to generate the TypeScript and Python parsers), `bison` (for the grammar check), and
for C++, CMake 3.24 or later and a C++20 compiler.

Generated code is never committed. Every build and test regenerates the parsers and API declarations first, into
git-ignored folders (`ts/src/gen/`, `py/src/knobly/_gen/` and `_api/`, and the generated C++ headers). The ANTLR
jar is downloaded once, checked against its pinned sha256, and cached in `$ANTLR_JAR_DIR` (default
`~/.cache/antlr`).

From the repository root, run the checks for each part you change:

```bash
bash tools/check.sh                       # the grammar and API schema checks; must exit 0
```

```bash
corepack pnpm -C ts install               # TypeScript
corepack pnpm -C ts test
corepack pnpm -C ts typecheck
corepack pnpm -C ts lint
```

```bash
cd py                                     # Python
uv run pytest
uv run ruff check && uv run ruff format --check && uv run mypy
```

```bash
cmake -S cpp -B build && cmake --build build && ctest --test-dir build   # C++
```

```bash
cd docs/site && uv run --locked mkdocs serve   # the user guide, live at http://127.0.0.1:8000
```

The package READMEs ([TypeScript](ts/README.md#build-and-test), [Python](py/README.md#build-and-test),
[C++](cpp/README.md#build-and-test)) list every check. CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))
runs all of them on every push and pull request, on several compilers and Python versions, so you only need to
run the ones for the parts you touched.

### What the grammar check proves

`tools/check.sh` makes sure every valid file has exactly one parse:

- it translates the grammar's parser rules to Bison and requires 0 conflicts;
- it checks that no two token kinds can match the same text;
- it checks the API schema, renders every binding's declarations, and checks the generated tables in the docs are
  current;
- it runs knobly's own parser generator over the grammar;
- and it confirms each of those checks still catches the deliberately broken grammars and schemas in
  `tools/planted/` and `tools/planted-parser/`, so a check cannot quietly stop working.

Because of this, the grammar may not use ANTLR actions, semantic predicates, lexer commands or modes: they could
hide an ambiguity. Whitespace, comments and line breaks are ordinary tokens, so the syntax tree keeps every
character.

## Writing docs

- The user guide's pages are in [`docs/site/pages/`](docs/site/pages/). Every code sample is included from a real
  program in `ts/examples/`, `py/examples/` or `cpp/examples/`, listed in
  [`examples/samples.json`](examples/samples.json), which each binding's tests run and compare with the expected
  output. A new sample needs all three languages; the docs build fails otherwise.
- Tables between `<!-- generated: ... -->` markers are generated from the API schema. Don't edit them by hand:
  run `python3 tools/gen-api.py docs`.
- The logo is drawn by [`tools/logo.py`](tools/logo.py); change it there and run `python3 tools/logo.py`.
- knobly code goes in ` ```knobly ` blocks. They are highlighted by
  [`docs/site/lexer/`](docs/site/lexer/src/knobly_pygments/__init__.py), which lexes with the token rules of
  `grammar/Knobly.g4` itself; it only says how each token kind looks. A new token kind needs a style there, and a
  block the grammar cannot lex fails the docs build.

## Landing a change

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`,
  `refactor!:` for a breaking change). Releases are made from them.
- Renames and changes of behaviour are discussed first in an issue: knobly does not keep old names or
  compatibility paths.

## Releases

A push to `main` that passes CI runs semantic-release, which takes the next version from the Conventional Commits
since the last release. It builds the npm tarball of `ts/`, the Python wheel and sdist of `py/`, and the C++ source
archive and single header of `cpp/` ([`.github/release-build.sh`](.github/release-build.sh)), and attaches them to a
GitHub Release. The version is stamped into the manifests only for the build. Nothing is published to npm or PyPI.

Releases stay in dry-run (the version is computed and the assets built, but nothing is tagged) until the
repository variable `RELEASE_ENABLED` is `true`.
