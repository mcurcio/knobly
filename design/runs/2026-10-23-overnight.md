# Overnight run, 2026-10-23

The M1 (TypeScript) and M2 (Python) parser slices, run as parallel lanes. The run stopped after
two beads were blocked. Main at close-out: `69d5d81`.

## Ledger

| Bead | Outcome | Commits |
|------|---------|---------|
| vil-m8w.7 | Landed, closed: real rasl configs replaced by neutral fixtures | 303107c |
| vil-m8w.6 | Landed, closed: MIT LICENSE (manifest licence fields came later with 6b91b60, e80089d) | 303107c |
| vil-g7n.1 | Epic, open: TS package skeleton and frozen interfaces landed | 6b91b60 |
| vil-g7n.1.1 | Landed, closed: TS tracer, tools/gen.sh, `foo[1]` index form | 086ba17 |
| vil-g7n.1.3 | Landed, closed: directive facade, string values | dc4ea8d |
| vil-g7n.2.1 | Landed, closed: Python tracer and packaging | e80089d |
| (review fix) | Landed: test for the non-integer slice start bound | 69d5d81 |
| vil-g7n.1.2 | Open, blocked: TS recovery built and green except one sibling test | origin/wip/vil-g7n.1.2 (7234335) |
| vil-g7n.1.4 | Open, blocked: include graph built and green, push refused | local only: wip/vil-g7n.1.4 (572d016), lane/ts (7950098) |
| vil-bgz.1 | Open: done inside vil-g7n.1.4, closes with it | 572d016 (local) |
| vil-g7n.2.2 | Not started: waits on vil-g7n.1.2 | |
| vil-g7n.2.3 | Not started: waits on vil-g7n.2.2 | |
| vil-g7n.3 | Not started: run stopped | |
| vil-g7n.1.5 | Not started: run stopped | |

## Blockers

- **vil-g7n.1.2.** `ts/src/ast/ast.test.ts` ("skips error nodes...", from dc4ea8d) expects ANTLR's
  default recovery: for `a {\n b;\n : x;\n c;\n}\nd;\n` it wants top level [a, x, c]. The agreed
  recovery gives top level [a, d], a.body [b, c], walk [a, b, c, d] and one E2001. Fix those
  expectations, rebase the wip commit onto main, check, push. Its edits also sit uncommitted in
  the shared checkout `/Volumes/Dock/Home/Code/villanelle-wt/ts`, which stops `git pull --rebase`
  there.
- **vil-g7n.1.4.** The agent permission system refused the push to main ("Merge Without Review")
  and to a wip branch. 572d016 is based on e80089d; rebase it onto main, rerun the ts checks, push.
  Afterwards local lane/ts (7950098) is redundant.

## Open findings

New beads: vil-6m2 (rasl fixtures handoff, for rasl-8st), vil-pzo (fixture coverage test),
vil-fxo (villanelle.ebnf missing the `foo[1]` form), vil-479 (integer-spelling check untested:
`1e3`, `0x10`, `1.0`, `1_000`), vil-22k (duplicated rules), vil-ngn (pnpm not hash-pinned),
vil-pba (package scripts always regenerate the parser).

Questions for the owner: vil-n1j (negative bounds; `-0` is -0 in TS and 0 in Python),
vil-1g0 (the W1004 warning for unknown escapes), vil-10c (UTF-16 positions in Python),
vil-3pq (Prettier).

Recorded on existing beads instead: Python `parse` docstring says "never raises" but
`nest-1000` raises RecursionError (vil-g7n.2.2); `parseGraph` rejects rather than throws for a
missing loader (vil-g7n.1.4); docs items (vil-g7n.1.5); gen before `uv build` (vil-g7n.3);
moving Python dispatch to M3 (vil-g7n.2.3); `save` cannot be triggered until an edit API
exists (vil-uji). Errata in the lane reports: rec-unclosed-list-eof gives E2001, not the listed
E2004; `deep-ok` is 4 levels, not 100.

## NOT RUN

- CI and release: no `.github/workflows` exist yet (vil-g7n.3), so no CI run and no release.
- Review of unlanded work: vil-g7n.1.4 and the vil-g7n.1.2 recovery edits were not reviewed.
- TS `pnpm` scripts in the shared checkout during slices (they regenerate the parser); slices ran
  vitest, tsc and eslint directly. The reviewer ran the full ts and py checks on an export of e80089d.
- A real browser for `villanelle/browser`.
- The original four mutation probes in review (only the start-bound probe was rerun).

## Next ready beads

P1: vil-g7n.1.2, vil-g7n.1.4 (both just need landing as above), then vil-g7n.2.2, vil-g7n.2.3,
vil-g7n.1.5, vil-g7n.3. Also ready: vil-stq, vil-bzv, vil-bgz and the new P2 beads (`bd ready`).

## Start here (next session)

1. In `/Volumes/Dock/Home/Code/villanelle-wt/ts`, the uncommitted files are vil-g7n.1.2's
   (copy of origin/wip/vil-g7n.1.2). Land 1.2 (fix ast.test.ts first), then rebase and land
   572d016 for vil-g7n.1.4; close vil-g7n.1.2, vil-g7n.1.4, vil-bgz.1.
2. Then vil-g7n.2.2 and 2.3 (Python), vil-g7n.1.5 (docs), vil-g7n.3 (CI and release).
3. Releases: vil-g7n.3 adds semantic-release; to turn publishing on, set the repo variable
   `RELEASE_ENABLED=true` (`gh variable set RELEASE_ENABLED --body true -R mcurcio/villanelle`).
   Until then the release job only dry-runs.
4. M3 cut: vil-9ze (typed argument values), vil-stq (DirectiveDelegator typing and defaults),
   vil-xlo (declarative directive definitions). Cut its slices once M1 and M2 close.
5. The workflow's land step (direct push to main) needs a permission rule for this repo, or a
   PR-based land step; one lane was refused.
