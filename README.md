# villanelle

A small configuration language: directives, `{ }` blocks, lists and slices, `#` comments, variables and
snippets, with parsers for TypeScript and Python generated from one grammar.

```conf
set $pixels 2284;

snippet twinkle $source {
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
The language, with every rule the load applies, is described in [docs/language.md](docs/language.md).

## Reading a config from a program

A program makes a processor once, with a document source (where files come from), the include extension if it
wants includes, and a key rule (how to name a directive among its siblings), then loads a root file:

```ts
    const processor = villanelle({ source: files, extensions: [include()], key: RASL_KEY });
    const path = fileURLToPath(new URL(name, FIXTURES));
    const options = { variables: HANDED };
    const first = await processor.load(path, options);
```

```python
    processor = vl.Processor(source=file_source(), extensions=[include()], key=rasl_key)
    variables = {"leds_host": '"10.0.0.9"'} if handed else None
    first = processor.load(str(root), variables=variables)
```

(Excerpts of `ts/src/load/rasl.test.ts` and `py/tests/test_rasl.py`.) The load gives back the directives with
variables, snippets and included files expanded, every value's origin, an address per directive, and every problem
as a located diagnostic; `processor.diff(first, second)` lists what changed between two loads. The reference for
both languages is [docs/low-level-api.md](docs/low-level-api.md).

| Entry point | TypeScript | Python |
|---|---|---|
| the core (no input or output) | `villanelle`: `parse`, `villanelle`, `memorySource`, `Diagnostics`, `formatDiagnostic`, ... | `villanelle`: `parse`, `Processor`, `memory_source`, `Diagnostics`, `format_diagnostic`, `walk`, ... |
| the include extension | `villanelle/include`: `include()` | `villanelle.include`: `include()` |
| files on disk | `villanelle/node`: `createFileSource()`, `createFsWriter()` | `villanelle.files`: `file_source()` |
| files over `fetch` | `villanelle/browser`: `createFetchSource(fetch)`, `createFetchWriter(fetch, options?)` | none |

## The language is defined by one file

[`grammar/Villanelle.g4`](grammar/Villanelle.g4) (ANTLR4) is the specification. ANTLR4
generates the TypeScript and Python parsers from it, so both parsers accept exactly the
grammar's language. [`grammar/villanelle.ebnf`](grammar/villanelle.ebnf) is the same grammar
in W3C EBNF, kept as a readable view.

The grammar is checked to be unambiguous, so every valid file has exactly one parse:

```bash
tools/check.sh
```

The script runs three checks:
- it translates the parser rules to Bison and requires 0 conflicts;
- it checks that no two token kinds can match the same text;
- it confirms that both checks still catch the planted bad grammars in `tools/planted/`.

It needs `python3`, `bison` and `uv`.

## Layout

| Path | What it is |
|---|---|
| `grammar/` | The grammar (`Villanelle.g4`) and its EBNF view |
| `tools/` | The soundness checks (`check.sh`), the planted bad grammars they must catch, and the parser generator script (`gen.sh`) |
| `ts/` | The TypeScript package, npm name `villanelle` ([`ts/README.md`](ts/README.md)) |
| `py/` | The Python package, PyPI name `villanelle` ([`py/README.md`](py/README.md)) |
| `conformance/` | Test cases both packages must pass, and the expected output for each: syntax cases (format in [`conformance/format.md`](conformance/format.md)) and load cases in `conformance/load/` (format in [`conformance/load/format.md`](conformance/load/format.md)) |
| `fixtures/rasl/` | rasl's real config files, which each package's rasl test loads ([`fixtures/rasl/README.md`](fixtures/rasl/README.md)) |
| `docs/` | The language ([`docs/language.md`](docs/language.md)) and the low-level API reference ([`docs/low-level-api.md`](docs/low-level-api.md)) |
| `.github/` | CI and the release build (`workflows/ci.yml`, `release-build.sh`) |
| `package.json`, `.releaserc.json` | Release tooling only (semantic-release); the packages are `ts/` and `py/` |
| `design/` | The design record ([`design/RECORD.md`](design/RECORD.md)), run logs, the older plans, drafts, reviews and experiments |
| `reference/` | The config code copied from mcurcio/rasl, as source material ([`reference/README.md`](reference/README.md)) |
| `.beads/` | The issue tracker (`bd ready` for work) |

## Build and test

The generated parsers are not committed (owner, 2026-10-23: "Don't commit the generated code, just
the source"). `tools/gen.sh ts` and `tools/gen.sh py` write them to `ts/src/gen/` and
`py/src/villanelle/_gen/` (both ignored by git), and every build and test runs it first. It needs
Java 11+ and `curl`: it downloads the ANTLR 4.13.2 jar once, checks its sha256, and caches it in
`$ANTLR_JAR_DIR` (default `~/.cache/antlr`).

From the repository root:

```bash
bash tools/check.sh                       # grammar soundness: needs python3, bison, uv

corepack pnpm -C ts install               # TypeScript: Node 24 (.nvmrc), pnpm through corepack
corepack pnpm -C ts test                  # also: typecheck, lint, build

cd py && uv run pytest                    # Python 3.11 or later, through uv
uv run ruff check && uv run ruff format --check && uv run mypy
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs these on every push and pull
request: the grammar check, the TypeScript checks on Node 24, and the Python checks on Python 3.11
and 3.13.

## Releases

A push to `main` that passes CI runs semantic-release. It takes the next version from the
Conventional Commits since the last release and builds the npm tarball of `ts/` and the Python
wheel and sdist of `py/` with `.github/release-build.sh`. The version is stamped into the
manifests for the build only and never committed. The packages go to GitHub Release assets only;
nothing is published to npm or PyPI.

Releases are dry-run until the repository variable `RELEASE_ENABLED` is `true` (owner, 2026-10-23:
"Dry-run until I enable it"). In dry-run the job still computes the version and builds both
packages, and uploads them as a workflow artifact; it creates no tag and no release. To turn
releases on:

```bash
gh variable set RELEASE_ENABLED --body true -R mcurcio/villanelle
```

## Status

The TypeScript and Python packages are built from the grammar and pass the same syntax and load
conformance cases. Both have the low-level API (the syntax tree and the directive layer); the high-level
API, where a program declares its directives, is deferred (`vil-xlo`). No release has been made yet.
The grammar design was done in [mcurcio/rasl#2](https://github.com/mcurcio/rasl/pull/2), where this
language began as `@rasl/config`.
