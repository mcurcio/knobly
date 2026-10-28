# Round 11 handoff: the low-level consumer API

Overnight run of 2026-10-28. Branch `feat/consumer-api-low-level`, PR
https://github.com/mcurcio/villanelle/pull/3 (open, into `main`; the owner merges).

## What landed

| Commit | Step | What |
|--------|------|------|
| 3cf7460 | architect | Frozen interfaces for the low-level API, TypeScript and Python |
| 20b763d | architect | Slice pages (`slices.md`), decisions, design record |
| 4d55efe | S1 (vil-9ze.4) | Grammar: variables (`$name`), slice bounds from variables, lone `$` is E1004; syntax corpus `conformance/variables.json`; 24 load cases in `conformance/load/`; rasl fixtures in `fixtures/rasl/`; TypeScript tracer for `load` |
| 08e0ff9 | S3 (vil-stq.4) | Python low-level API: expansion rules 1-12, readers, addresses and key rule, diff, diagnostics sink, `memory_source`/`file_source`, `include` |
| f69dda9 | S2 (vil-stq.3) | TypeScript low-level API: the same, plus `createFileSource`/`createFetchSource`; old facade and graph code deleted |
| b660737 | S4 (vil-9vn.1) | `docs/language.md`, `docs/low-level-api.md`, `design/RECORD.md`, the three READMEs |
| 5405aad | fix round 1 | One variable lookup rule, one root path, E5012 kind, reserved extension names, E3005 placement and Python-only fixes (F1-01..F1-09); 6 new load cases (30 total) |
| 9db43f2 | close | `.beads/issues.jsonl` snapshot |

What a program can now do, in both languages: load a config with variables, snippets and
`include`; hand in values that win over the file; walk directives and read typed values with
located errors; get a stable address per directive under the program's key rule; diff two
loads (added, removed, changed, unknown); read the include graph; collect and format
diagnostics. rasl's real configs (`fixtures/rasl/`) load through both.

## Decisions taken overnight

All in `decisions.md` (S1-01..S1-18, S2-01..S2-09, S3-01..S3-16, S4-01..S4-07, F1-01..F1-11),
one line each with reason and the alternative. The ones that change behaviour a program sees:

- F1-01: nearest `set` or snippet parameter binds; an include block's value wins over every
  `set` inside the files it splices; a handed-in value wins over every `set`; neither replaces
  a snippet parameter.
- S3-01 / S2-02: a snippet body sees its defining block's live scope (lexical).
- F1-04: `load(path)` resolves the root through the document source first, so a file has one
  identity and is read once.
- F1-02 / S3-07: an E5012 statement is unreadable with kind `extension`, error on the name.
- S2-01 / F1-03: an extension may not be named `set`, `snippet` or `use`, and names are unique.

## Open for the owner

- F1-10 (also S1-18): a file with its own top-level `set`, included twice in one block, gives
  E5002. That seems to clash with R21 "Allowed, per place" and R22 "each instance of the file
  would have its own bindings". Either fix changes a frozen rule, so it is his call.
- Python uses a `Processor` object (jinja2 style), where the design chose a plain function
  (`ast` style). Reason: one key rule tied to both loads in a diff. He has not seen this.
- F1-04 rewords the §2 root rule and `ILoadContext.parentPath` locally; `slices.md` should be
  re-cut to match.
- `slices.md` S1 acceptance 1's probe cannot fail (S1-01, F1-11); the rule is held only by the
  `var-slice-base` corpus case.

## Residuals not changed (F1-11)

- Message wording differs between the languages (E5007, E5008, E4002, handed-in texts).
- The E3xxx-E5xxx message table lives in `syntax/recovery`; tier-1 `diagnostics` imports a
  load-layer type.
- Small duplications: Python's two `error()` bodies; TS `reasonOf`/`place`; `include` builds
  E3005 by hand.
- TS file source returns absolute paths, Python relative ones.
- For the sugar bead vil-xlo: its E6xxx codes must go in core's registry; round 10's include
  depth option is gone.
- No load case yet for E5007 depth, E5008, handed-in or list-held slice bounds, or E5003 for a
  snippet whose definition is not visible.
- AGENTS.md still says to push directly to main; RECORD's NOT RUN list is stale.

## Checks

- CI on 5405aad: green (runs 40653604043 push, 40653608815 pull_request): grammar soundness,
  Python 3.11 and 3.13, TypeScript on Node 24. Release skipped, as expected on a PR branch.
- Locally at 5405aad: TS test 428 passed, typecheck and lint exit 0; Python 494 passed, ruff,
  format and mypy exit 0; `tools/check.sh` exit 0. Each fix has a test seen to fail on b660737.

NOT RUN:
- CI on 9db43f2 (beads snapshot and this file only; no code changed).
- TS branch coverage (c8 download was denied).
- `createFetchSource` against a real server.
- The Python 3.11 leg locally (CI ran it).
- jscpd duplication scan (denied); duplication was checked by reading.
- Docs examples were checked by script, not line by line.

## How to resume

1. Work in `/Volumes/Dock/Home/Code/villanelle/.claude/worktrees/consumer-api-build` on
   `feat/consumer-api-low-level`; Node 24.14.1 (`nvm use 24.14.1`), caches under
   `/Volumes/Dock/Home/.cache`.
2. Read the owner's PR comment replies, then this file's "Open for the owner".
3. For F1-10, change rule 7 or L2 per his answer, update `load-include-exports`, add a load case.
4. Checks: `bash tools/check.sh`; `corepack pnpm -C ts test|typecheck|lint`;
   `(cd py && uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy)`.
5. Gate bead vil-9vn stays open until the owner reviews the PR.
