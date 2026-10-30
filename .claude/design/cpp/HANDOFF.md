# C++ binding: handoff (2026-10-30, overnight build)

Cold-start notes for whoever picks up the C++ binding next. PR 8 (`feat/cpp-binding` into the
default branch, mcurcio/knobly) holds all of it; the owner reviews and merges.

## State

- All four milestones of design.md section 7 are built. CI is green on every job at 4a127bd
  (six C++ legs: GCC, Clang, AppleClang x header-only, compiled; C++ format; C++ package; grammar
  check; Python 3.11 and 3.13; TypeScript on Node 24).
- The C++ adapter claims level 3 and passes all 380 shared cases (L0 168, L1 60, L2 123, L3 24),
  in header-only with ASan and UBSan and in compiled mode with C++23.
- TypeScript and Python generated code is byte-identical to before tonight. No run-time change
  for them (see the PR body, "Behaviour changes for TypeScript and Python").
- Generated code is never committed: `tools/gen.sh cpp` (or the CMake build with
  `KNOBLY_REGENERATE=ON`) writes the generated headers.

## What was decided, and where

- Design: `design.md` (sections 0-7), owner answers `answers.md`, gate `gate.md`.
- Frozen slice pages: `frozen-m1.md`, `frozen-m2.md`, `frozen-m3.md`. Milestone 4 has none
  (low finding: its choices are listed only in the PR body).
- Every spec or design contradiction found tonight: `.claude/errata.md`, the sections dated
  2026-10-30 headed "C++ binding" (T1-T5, M2-*, W1-W5, F1, R1-R3, P1-P2, D1-D3, and the review
  fixes' F1-F5).
- Every "choice made overnight" is listed one per line in the PR 8 body, grouped by milestone.

## Commits (oldest first, on top of the milestone 1 work)

| sha | what |
|-----|------|
| b61f437, 164834c, 1e0f314 | milestone 1: C++ API emitter, syntax layer, L0 adapter, CI leg |
| dcd4be7 | milestone 2 freeze: interfaces and stubs |
| 43aa19f, 5408bb0 | slice F: file adapters, include, driver timeout |
| 985441e, e2d8733, 4aa532c, d3ef936, 0bb0176 | slice W: written layer, L1 adapter, unit tests |
| 9ea9ef6, 422c6e9, 33c5bcd | slice R: rendered layer, level 3 adapter, editor program, corpus byte entries |
| 1c57709 | milestone 3 freeze: generated format.hpp |
| f5a5ab3, bf776a7 | slice P: format tests, programs 4.1 and 4.3, compile-fail tests |
| 0002449, a6008e7 | slice D: generated per-language docs tables |
| 93b31fc | GCC 13 fix: one constructor per arm for literal-checked union fields |
| 338d0c2 | milestone 4: install, package config, release archive, single header, CI legs |
| 64429e8, 613930e, 4a127bd | end-review fixes |

## Map of the code

- `tools/api/` (loader, emit_ts, emit_py, emit_cpp, emit_docs) generates every binding's public
  API from `spec/schema/api.json`; `tools/parser/` generates the C++ lexer and parser from
  `grammar/Knobly.g4`; `tools/automaton.py` is the shared code-point automaton.
- `cpp/include/knobly/`: public headers (some generated), `support/` (sequence, view, block,
  ordered_map, config.hpp with the version macros), `detail/<layer>/` hand-written definitions
  (syntax, shared, io, files, extensions, written, rendered), `detail/arena.hpp`,
  `detail/raise.hpp`.
- `cpp/conformance/adapter.cpp`: the stdio adapter for `conformance/driver/run.py`.
- `cpp/tests/`: `unit/` (one Catch2 program per file), `programs/` (design programs 4.1-4.3 and
  `run_program.cmake`, runs read from `<name>_expected/<run>/`), `compile_fail/` (refused plus
  control), `compile/`, `generated/` (layer-boundary checks), `consumer/` (package test).
- `.github/release-cpp.sh` and `tools/amalgamate.py`: release archive and single header.

## How to resume

```bash
cd <worktree on feat/cpp-binding> && git pull --rebase
cmake -S cpp -B /Volumes/Dock/tmp/kno-cpp-build-<name> -DKNOBLY_SANITIZE=ON   # add -DKNOBLY_COMPILED=ON -DCMAKE_CXX_STANDARD=23 for compiled mode
cmake --build /Volumes/Dock/tmp/kno-cpp-build-<name> -j && ctest --test-dir /Volumes/Dock/tmp/kno-cpp-build-<name> -j8
python3 conformance/driver/run.py -- /Volumes/Dock/tmp/kno-cpp-build-<name>/knobly_adapter
bash tools/check.sh
```

- Build trees and scratch go under `/Volumes/Dock/tmp`. GCC is not on the Mac: use Docker
  `gcc:13` to reproduce the CI gcc leg.
- Make on macOS compares file times to the second: a file restored within a second of a build can
  leave a stale object (a false red on a WILL_FAIL test). Touch the file.
- A local TypeScript conformance run needs `pnpm build` first and takes about 13 minutes.
- CI is the full gate; locally run only the checks for what changed.

## Open follow-ups

Owner decisions:
- The inline namespace is `v<major>_<minor>_<patch>` (changes every release), not design D28's
  `v0`. Confirm or revert (`support/config.hpp`).
- Whether `shapes.hpp` should generate the adapter's protocol dump and edit/reader dispatch
  (widens frozen-m1.md 4.2; review findings 16 and 17).
- Review the byte expectations added to `conformance/contract/cases.json` (errata R1).

Spec changes for every binding (not C++'s to make alone):
- Enforce the nesting limit where the parser recurses; C++ overflows the stack on `a { ] ; ` x
  100,000 (parse) and x 10,000 (load plus render). Add the input to `depth.json`.
- A limit on values after expansion; count use and extension lines toward the expansion limit.
- Spec 4.2: file writers follow symbolic links and keep permissions (errata F5).
- Spec 4.3: include follows absolute paths and `..`; consider a root directory on `file_source`.
- `spec/conformance.md` section 3: name the request timeout as a fault (errata F1).
- A corpus "needs" token for run-time type checks (errata R2, R3).
- Whether trailing list fields such as `via` default, in the shared generator (errata P2).
- Add corpus cases: a member on a removed statement; `@include;` with no value.
- One rule for E1003's quoted character (Python escapes it).

C++ only:
- Full strong guarantee for edits: build the handle tree aside, then commit (errata F4).
- Free removed nodes before the graph is dropped; note the memory cost in design 2.3 (errata F3).
- Entry parsing belongs in `detail/syntax` (errata W2).
- clang-tidy: choose checks, pin it (21 line stops at 21.1.6), fix findings, add a CI job.
- Run the conformance adapter through the single header (design 2.5).
- Low review findings: `diagnostic_error` copy can throw; mark `sequence<T>` a borrowed range;
  `insert_statements` index type; document that `diagnostics` and map copies share state; ports'
  `const` overrides; a looping link fails the whole glob; `file_source::read` size and type check;
  deep-tree load time; generate `statement_of_keyword`, `block_traits` declarations,
  `argument_type_message` names, value rules and word kinds; recovery rules as a `.g4`
  annotation.

Docs and generators:
- Update design.md section 3's `located_diagnostic` sketch (one constructor per arm now).
- `spec/binding-guide.md` tables have no C++ column; prose still says "both languages" in places.
- `emit_cpp` `trait_names` gives descriptions where the loader expects type/value/both (errata D3).
- Member-doc assembly is triplicated across emitters; the addresses table's people-form cells are
  hand-typed; people forms are hand-ported per binding.
- Optional: generate Python's expanded-value equality from the schema's `equal by` key.
- Known elsewhere: kno-g8g (TypeScript/Python recovery), kno-9ao, kno-167, kno-a0y (MSVC).

## User guides round (2026-10-30)

Landed on `feat/cpp-binding` (head dbd02a0, CI green): the MkDocs Material guide in `docs/site/`
(plan `frozen-docs.md`), samples in `ts/examples/`, `py/examples/` and `cpp/examples/` listed in
`examples/samples.json` and run by each binding's tests; the no-install C++ routes (single header,
FetchContent of the release archive, `add_subdirectory`; owner, 2026-10-30: "i dont want to
install villanelle for it to be usable"), proved by `cpp/tests/consumer/check.sh`; Python's E3007
message now names the extension. The old `docs/language.md`, `low-level-api.md` and
`rendered-tree.md` are folded into the guide.

Open:
- Owner, once: set the repository's Pages source to "GitHub Actions" (`gh api
  repos/mcurcio/knobly/pages` returned 404); the `docs-deploy` job publishes from `main` only.
- Delete remote `wip/pages` and `wip/py-samples` by hand (refused by the permission system; their
  content is on the branch).
- `design/RECORD.md` lines 128-129 and 168 link the deleted docs (errata W2, user-guide section;
  the id repeats the earlier W2, so renumber one). Errata F5 still open.
- Python hatch build hook running `tools/gen.sh py`; TypeScript `src/` parameter properties block
  `erasableSyntaxOnly`; prettier not enforced in `ts/`; messages are outside the shared contract.
