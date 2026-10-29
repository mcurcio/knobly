---
name: villanelle-binding
description: Use when adding a new language binding to villanelle (Go, Rust, Java, any language beyond ts/ and py/), or when changing the public API shape of any villanelle binding - renaming or moving a type, member, function, error, kind or module in ts/ or py/, adding an operation, or changing what a layer (syntax, low level / written, rendered tree) exposes. Also use when writing or fixing a conformance runner, or when the TypeScript and Python bindings disagree.
---

# villanelle language bindings

The rules live in `docs/bindings/`. This skill does not repeat them: it says what to read, in what
order, how to work, and what has gone wrong before.

## Read first, in this order

1. `docs/bindings/README.md`: the layers and how the pieces fit.
2. `docs/bindings/spec.md`: what every binding must do. This wins over either binding's code
   (owner, 2026-10-27: "Within villanelle I want the spec to win over a reference language").
3. `docs/bindings/design-guide.md`: the owner's goals, naming rules, allowed differences, the
   concept map, and the new-binding checklist.
4. `docs/bindings/codegen.md` only if the task touches the fixed lists (codes, kinds, limits).
5. For the reasons behind a rule: `.claude/design/consumer-api/requirements.md` (the owner's dated
   words), `.claude/design/consumer-api/round12/decisions.md`, and
   `.claude/design/consumer-api/round13/review.md`.

## Before changing any API shape

API shape changes need the owner's approval. Nothing is locked, but nothing changes without him
(2026-10-27: "Nothing is locked until I see user APIs that I like"). For any rename, move, new
member or removed member:

- Show it as user code first: the first-hour program (design guide rule 7) before and after, in
  every affected language.
- Check the spec name. A concept keeps one word in every layer and binding; a new word goes in the
  spec and is approved.
- A "Proposed (pending owner)" note in the spec is not agreed. Do not build it until the owner
  answers the question it links to.
- No compatibility aliases or deprecated names (repo and global rule).
- Change the spec, both bindings, the reference docs (`docs/low-level-api.md`,
  `docs/rendered-tree.md`) and any affected conformance format in the same change. A change to
  one binding alone is a divergence.

## Workflow: a new binding

Follow the checklist in `docs/bindings/design-guide.md` section 5. In short: pick one model, get the
first-hour program approved, generate the parser, pass the syntax cases, then the written cases,
then the load cases, then write the first-hour program as a test.

## Workflow: changing an existing binding

1. Find the spec section for the concept. If the code and spec disagree, that is a finding: report
   it, do not quietly match either.
2. Make the change in both `ts/` and `py/`.
3. Run both test suites (below), then lint and typecheck for each package you changed.
4. Update the concept map in the design guide if a name changed.

## Running the shared cases

From the repo root (Node from `.nvmrc`; on the owner's Mac set
`ANTLR_JAR_DIR=/Volumes/Dock/Home/.cache/antlr`; Java 11+ is needed to generate the parser):

```bash
# TypeScript: regenerates the parser, then runs every test, the three runners included:
#   ts/src/conformance.test.ts          syntax cases (conformance/*.json)
#   ts/src/written-conformance.test.ts  conformance/written/
#   ts/src/load-conformance.test.ts     conformance/load/
nvm use
corepack pnpm -C ts install
corepack pnpm -C ts test

# Python: tests/conftest.py regenerates the parser first; the runners are
#   tests/test_conformance.py, test_written_conformance.py, test_load_conformance.py
cd py && uv run pytest
```

Lint, format and typecheck commands are in `ts/README.md` and `py/README.md`.

## Traps found in review

- **Expected outputs are hand-derived.** Never regenerate a file in `conformance/*/expected/` from
  an implementation to make a runner pass. A mismatch is a bug in the runner or in the rules.
- **Skipping.** A runner may skip a case by its `needs` while you build; a finished binding skips
  nothing, and the runner should assert its feature set covers every case.
- **Positions are UTF-16 today** in both bindings. In Python, an offset is not a `str` index once a
  character outside the Basic Multilingual Plane comes before it. Convert before slicing.
- **Known differences with no shared case:** `plain("-0")` (TypeScript `-0`, Python `0`), a lone
  `"\r"`, integers beyond 2^53-1, and handed-in text such as `"1;"` (accepted by `load`, refused by
  `set handed`). Test these yourself when you touch them.
- **`written` on a rendered value is the end of the chain,** not the value on the same line.
  `arg.written.replaceWithText(...)` on `max_count`'s `$pixels` rewrites the `set` line, so every
  use changes. To change one use, edit the reference on the directive's own line.
- **`graph.diagnostics` is a method** but `rendered.diagnostics` is a property. In TypeScript
  `graph.diagnostics.length > 0` compiles and is never true.
- **Edits take villanelle text.** `set_values(2400)` fails inside the Python library; `"my host"`
  becomes two values. Use `quote()` for program strings.
- **Python's low level has no `__match_args__`,** so `match` with positional patterns raises
  TypeError there, while the rendered tree supports it.
- **Python separates kinds four ways** (literal strings, `StrEnum`s, classes with no `kind`, a
  `kind` on one class). Do not add a fifth: follow the design guide's rule 4.
- **`from villanelle import *`** replaces `typing.List` with the low-level `List` in Python.
- **The processor ownership check** (D27): `read`, `render` and `diff` refuse a graph or render
  made by another processor, at run time only.
- **Generated parser code is never committed.** `tools/gen.sh` writes it to git-ignored folders.
- **Python's `EditError` is a `ValueError`,** so a broad `except ValueError` also catches
  `DetachedError`.
- **The `rasl` key rule** in the load runner must match `conformance/load/format.md` exactly.

## Tracking

Work is tracked in beads (`bd`, prefix `vil-`), per `AGENTS.md`. File a bead for each finding,
divergence or open question you find; record a decided rule in the bead's design field and in the
spec, not in a new notes file.
