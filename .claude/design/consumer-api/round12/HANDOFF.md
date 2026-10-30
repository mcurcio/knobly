# Round 12 handoff: the low-level layer (PR #4)

PR: https://github.com/mcurcio/knobly/pull/4 (branch `feat/low-level-layer`, into `main`).
Bead: `kno-e4x` (children `.1`, `.2`, `.3` closed; S4 is `kno-e4x.4`, closed). Written 2026-10-28 at
the end of the overnight run. The owner reviews and merges; nothing here is merged.

## What landed

| Step | Commits | What |
|------|---------|------|
| Architect | 7f964fc, 8e583c0 | Round 12 record, slices and decisions; the interfaces in TS and Python |
| S1 | 52c3b39 | TS core: `load` returns the files as written (a document graph), `render(graph)` builds the rendered tree, handles, comments, edits, save, the split tracer |
| S2 | 3b5204e | TS: every remaining edit (insert, add, rename, values on directive and use lines), `setHanded`, `read(graph)`, the fs writer's lost-update check and staging, the key moved to `addresses()` / `diff` |
| S3 | 49d348f | Python: the same low level, Python idioms, `save`, `quote`, `fs_writer` |
| S4 | 791d485, 95a0ed6 | Docs: new `docs/low-level-api.md`, the old page moved to `docs/rendered-tree.md`, READMEs, RECORD round 12 |
| Fix round 1 | 8d2a6f8 | Review fixes: list item removal keeps comments, edit errors point into the caller's text, parameter rename refused on E5002, `declaration` agrees with the binding, Python caught up with TS in four places, one handed-value reader, binding uses shape.ts |
| Close | 948e69f, this file | Beads snapshot, handoff |

User-visible result: a program can load a config, see which files were read and where each is
included, list every variable and where it is overridden (including by a handed-in value), change
a variable's value or make a line stop using it, and save, which writes only the changed files in
one batch. The same in TypeScript and Python, checked by the 36 shared cases in
`conformance/written/` (27 at first, 9 added in fix round 1) and the 30 in `conformance/load/`.

## Checks

- At 8d2a6f8: TS test (17 files, 495 tests), typecheck, lint, all exit 0. Python pytest (561
  passed), ruff check, ruff format --check, mypy, all exit 0.
- CI on 8d2a6f8: PASS (runs 40789966221 and 40789974362: grammar, Python 3.11 and 3.13,
  TypeScript on Node 24; release skipped as expected on a PR branch).
- Mutation probes A1-A10, B1-B10, C1-C7 each turned their test red (verify review).

## NOT RUN

- CI on 948e69f and on the commit holding this file (beads snapshot and docs only; no code).
- `tools/check.sh` locally (grammar unchanged; CI ran it green).
- jscpd duplicate scan (the npx download was refused; duplicates were searched by hand).
- The fetch writer against a real server (only stubbed); an fs writer failure part-way through
  renaming; concurrent Python threads; a rendered preview of the markdown docs.

## Decisions taken overnight

All in `decisions.md` beside this file, one line each with reason and alternative: D1-D27
(architect), D-S1-1..10, D-S2-1..9, D-S3-1..10, D-S4-1..6, D-F1-1..17. Withdrawn or replaced in
fix round 1: D-S2-1 and D-S3-8 (by D-F1-7 and D-F1-2), D-S3-4 (by D-F1-1). None is the owner's
requirement; only O1-O4 are his answers.

## Open residuals (for the owner or a next round)

1. **The low layer reaches up into the middle layer** (design review, high; D23, D-F1-11). The
   binding imports the rendered tree's `Argument`, `UnreadableKind` and the extension interface,
   and works out render's error codes; design.md §3 says that is render's job. Owner decision:
   move expansion below/into render (shared value module below both layers), or amend §3.
2. **`declaration` is a second walk** (design review, high, partly fixed). It now agrees with the
   binding's winner and a behaviour test checks it, but it is not derived from the binding's
   scope model. slices.md 2.6 states the wrong (parameter-first) rule (D-F1-8).
3. **Writer contract** (D-F1-10). A writer can fail after replacing some files; `save` then keeps
   every `source` old. Fixing it needs an `IDocumentWriter` signature change.
4. **Scope questions:** `render` and `diff` as plain functions rather than processor methods
   (D-F1-12); moving the shared modules out of `ts/src/load/` (D-F1-14).
5. **Duplicated one-per-block claims** (E5002, E5005) between shape.ts and the binding (D-F1-9).
6. **slices.md errata not applied:** A4's probe effect, C2 names the `-inner` case, A10's "in one
   test" wording.
7. RECORD bead outline item 6 still lists `kno-uji` as later work though round 12 built it
   (D-S4-5).
8. pytest writes temporary directories under /private/var/folders on the internal disk.

## How to resume

1. `cd /Volumes/Dock/Home/Code/knobly/.claude/worktrees/low-level-build` (branch
   `feat/low-level-layer`); `git pull`.
2. Node: `source ~/.nvm/nvm.sh && nvm use 24.14.1`; caches on /Volumes/Dock (see the run env in
   the brief). Checks: `corepack pnpm -C ts test|typecheck|lint`;
   `(cd py && uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy)`.
3. Read the owner's PR comments first; residuals 1 and 4 need his answer before code moves.
4. Record new choices in `decisions.md` (append only); track work in beads under `kno-e4x`.
