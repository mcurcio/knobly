# AGENTS.md

Instructions for every AI coding agent in this repo. `CLAUDE.md` is a symlink to this file.

## What this repo is

knobly is a configuration language, defined by one formal grammar, with generated TypeScript,
Python and C++ parsers. It began as `@rasl/config` in mcurcio/rasl, and rasl will consume it. It is
an open source project: `README.md` is for users, `CONTRIBUTING.md` for contributors (layout,
build, docs, releases), and this file adds what agents need on top.

## Start here

1. `README.md`: what the language looks like and the three API layers (syntax tree, files as
   written, rendered tree).
2. `CONTRIBUTING.md`: how the grammar, the spec and the three bindings fit, the repo layout, and
   every build and test command.
3. `bd ready`, then `bd show <id>` for the bead you take (see Task tracking below).
4. Before changing any API shape: `.claude/skills/knobly-binding/SKILL.md`, then `spec/`.
5. For design history: `design/RECORD.md` (current choices and the work outline).

## Rules of the repo

- `grammar/Knobly.g4` is the language. Change the language only there, and run
  `tools/check.sh` after every grammar change: it must exit 0.
- The grammar may not use ANTLR actions, semantic predicates, lexer commands or modes. The check
  refuses them because they can hide a conflict.
- Whitespace, comments and newlines are ordinary tokens. Nothing goes on a hidden channel, so the
  parse tree keeps every character.
- The API every binding offers is specified in `spec/` (canonical: it wins over the TypeScript,
  Python and C++ code). Public declarations are generated from `spec/schema/api.json`.
- The older requirement plans are in `design/plans/`. Code carried over from rasl is in
  `reference/` (see `reference/README.md`); it is source material, not part of the build.

## Docs

- `README.md` is user-first: what knobly is, a quickstart, install, and links into the user guide.
  Maintainer detail (layout, checks, releases) belongs in `CONTRIBUTING.md`, not the README.
- The user guide is `docs/site/` (MkDocs Material), published to https://mcurcio.github.io/knobly/.
  Every code sample on it is included from a program in `ts/examples/`, `py/examples/` and
  `cpp/examples/`, listed in `examples/samples.json`; each binding's tests run them, and the docs
  build fails if a language's file is missing.
- Tables between `<!-- generated: ... -->` markers (in `README.md`, `spec/` and the guide) are
  generated: run `python3 tools/gen-api.py docs`, never edit them by hand. `tools/check.sh` fails
  when one is stale.
- The logo (`docs/site/pages/assets/logo.svg`, `logo-dark.svg`, `icon.svg`) is drawn by
  `tools/logo.py`; edit the script and rerun it, never the SVGs.
- knobly samples use ` ```knobly ` fences, highlighted by `docs/site/lexer/` from the grammar's own
  token rules. Adding a token kind to `Knobly.g4` needs a style in its `STYLE` table, or the docs build fails.
- When you change behaviour or an API, update the guide page and the package README that describe
  it in the same change.

## Build and test

Run the checks for every package you change, from the repository root:

```bash
bash tools/check.sh                       # after any grammar or schema change; must exit 0
corepack pnpm -C ts install               # ts/: then test, typecheck and lint
corepack pnpm -C ts test
(cd py && uv run pytest)                  # py/: also ruff check, ruff format --check, mypy
cmake -S cpp -B build && cmake --build build && ctest --test-dir build   # cpp/
(cd docs/site && uv run --locked mkdocs build --strict)                  # the user guide
```

`CONTRIBUTING.md` and each package README (`ts/`, `py/`, `cpp/`) give the full lists. CI
(`.github/workflows/ci.yml`) runs all of them on every push and pull request, so run locally only
the checks for what you changed.

Pins:

| What | Version | Where it is set |
|---|---|---|
| Node | 24. Run `nvm use` first: a shell's default Node may be older | `.nvmrc`; `engines` in `ts/package.json` |
| pnpm | 12.15.0, through corepack | `packageManager` in `ts/package.json` and `package.json` |
| Python | 3.11 or later; 3.13 by default; CI runs 3.11 and 3.13 | `requires-python` in `py/pyproject.toml`; `py/.python-version` |
| Java | 11 or later (CI uses 21) | `tools/gen.sh` refuses older |
| ANTLR | 4.13.2: the jar (sha256-pinned) and both runtimes | `tools/gen.sh`; `ts/package.json`; `py/pyproject.toml` |
| C++ | C++20, CMake 3.24 or later; no dependencies beyond the standard library | `cpp/CMakeLists.txt` |
| CI tools | exact versions of Node, Java, uv and bison | the `env` block of `.github/workflows/ci.yml` |

Generated code is never committed (owner, 2026-10-23: "Don't commit the generated code, just
the source"). `tools/gen.sh ts|py|cpp` writes it to git-ignored folders (`ts/src/gen/`,
`py/src/knobly/_gen/` and `_api/`, the C++ headers in `cpp/`); the TS package scripts,
`py/tests/conftest.py` and CMake's configure step run it first, so every build and test
regenerates. It caches the ANTLR jar in `$ANTLR_JAR_DIR` (default `~/.cache/antlr`); on the
owner's Mac, set `ANTLR_JAR_DIR=/Volumes/Dock/Home/.cache/antlr`.

## Landing work

- Push directly to `main`; do not open pull requests yet (owner, 2026-10-22: "Don't open PRs in
  villanelle yet. Just push directly").
- Commits follow Conventional Commits.

## Task tracking: beads

All planned work is tracked in beads (`bd`, prefix `kno-`). Agents manage beads themselves
(owner, 2026-10-21, in rasl: "I want to use beads, and want you to auto manage it"). The beads
were ported from mcurcio/rasl on 2026-10-22; each one's notes say where it came from.

- **Before work:** `bd ready`, `bd show <id>`, `bd update <id> --claim`.
- **During work:** file a bead for every follow-up, bug or open question; record decided rules in
  the bead's design field.
- **After work:** `bd close <id>`; update the rest.
- **Sync to GitHub:** the beads database's Dolt remote is `origin` (`refs/dolt/data`). A
  `Stop` hook in `.claude/settings.json` runs `bd dolt push` after every Claude turn. Agents
  without that hook run `bd dolt push` after changing beads. On a new machine, run
  `bd dolt pull`.
- **Readable snapshot:** `bd export -o .beads/issues.jsonl`, committed with the work.
- Lasting notes about the owner or the project go in Claude memory files, not `bd remember`.

## Collaboration preferences

- **Brainstorming cadence**
  - When we are ideating / brainstorming, keep responses concise and optimize for quick back-and-forth.

- **Opinions vs decisions**
  - Offer **opinions and options**.
  - Do not present choices as "decided" unless the owner explicitly asks you to decide.

- **Specificity & intent**
  - Ask targeted clarifying questions when requirements are ambiguous.
  - Do not guess intentions; when in doubt, present explicit assumptions and ask for confirmation.
  - If a request specifies *interfaces* (ports/config) but leaves *runtime semantics* underspecified (e.g., timing, edge cases, shape rules, default behaviors), **pause implementation** and ask for clarification rather than inventing defaults.

- **No implicit semantic changes**
  - Do not change node semantics, runtime semantics, config semantics, or payload contracts implicitly.
  - If a change might affect behavior (even if tests still pass), call it out **before** implementing and confirm it is wanted.

- **Breaking changes / renames**
  - Confirm renames and behavior changes with the owner before making them.
  - Do not add aliases, deprecated exports, migration messages, or compatibility shims unless explicitly asked.

- **Scope discipline**
  - Keep diffs minimal and tied to the request.
  - Avoid drive-by refactors unless asked; file a bead instead.

- **Config ergonomics**
  - When adding DSL/config sugar:
    - propose exact semantics (including edge cases)
    - avoid ambiguous behavior
    - confirm constraints (e.g., "only supported without slicing") up front

- **Change reporting**
  - After edits, summarize:
    - what changed
    - why
    - any behavior-impacting implications
    - what to run to validate
