---
name: villanelle-binding
description: Use when adding a new language binding to villanelle (Go, Rust, Java, any language beyond ts/ and py/), or when changing the public API shape of any villanelle binding - renaming or moving a type, member, function, error, kind or module in ts/ or py/, adding an operation, or changing what a layer (syntax, low level / written, rendered tree) exposes. Also use when writing or fixing a conformance runner, or when the TypeScript and Python bindings disagree.
---

# villanelle language bindings

The rules live in `spec/` (canonical). This skill does not repeat them: it says what to read, in
what order, how to work, and what has gone wrong before.

## Read first, in this order

1. `spec/README.md`: the layers and how the pieces fit.
2. `spec/glossary.md`: one word per concept, and each concept's type name per layer and binding.
3. `spec/spec.md`: what every binding must do. This wins over either binding's code
   (owner, 2026-10-27: "Within villanelle I want the spec to win over a reference language").
   `spec/schema/api.json` and `spec/schema/diagnostics.json` are the one home of every fixed list
   and win over the spec's tables.
4. `spec/binding-guide.md`: the owner's goals, naming rules, allowed differences, the
   concept map, and the new-binding checklist.
5. `spec/codegen.md` only if the task touches the fixed lists (codes, kinds, limits).
5. For the reasons behind a rule: `.claude/design/consumer-api/requirements.md` (the owner's dated
   words), `.claude/design/consumer-api/round12/decisions.md`, and
   `.claude/design/consumer-api/round13/review.md`.

## Before changing any API shape

API shape changes need the owner's approval. Nothing is locked, but nothing changes without him
(2026-10-27: "Nothing is locked until I see user APIs that I like"). For any rename, move, new
member or removed member:

- Show it as user code first: the first-hour program (binding guide rule 7) before and after, in
  every affected language.
- Check the spec name in `spec/glossary.md`. A concept keeps one word in every layer and binding; a
  new word goes in the glossary and the schema, and is approved.
- A "Proposed (pending owner)" note in the spec is not agreed. Do not build it until the owner
  answers the question it links to.
- No compatibility aliases or deprecated names (repo and global rule).
- Change the spec, both bindings, the reference docs (`docs/low-level-api.md`,
  `docs/rendered-tree.md`) and any affected conformance format in the same change. A change to
  one binding alone is a divergence.

## Workflow: a new binding

Follow the checklist in `spec/binding-guide.md` section 5. In short: pick one model, get the
first-hour program approved, generate the parser, pass the syntax cases, then the written cases,
then the load cases, then write the first-hour program as a test.

For a language with error values, no exceptions, UTF-8 strings or no cyclic imports (Go, Rust),
read the binding guide's "For languages unlike TypeScript and Python" table and the spec's
Proposed notes in 2.1, 2.8, 4.1 and 5 before planning: those rules are not agreed yet, so show the
owner the planned choice with the first-hour program.

## Workflow: changing an existing binding

1. Find the spec section for the concept. If the code and spec disagree, that is a finding: report
   it, do not quietly match either.
2. Make the change in both `ts/` and `py/`.
3. Run both test suites (below), then lint and typecheck for each package you changed.
4. Update the glossary, `spec/schema/api.json` and the concept map in the binding guide if a name
   changed.

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
  `"\r"` and integers beyond 2^53-1. Test these yourself when you touch them. (Before milestone 1,
  `load` accepted an override text such as `"1;"` that `set handed` refused: the spec now has one
  check of an override, spec 6.3.)
- **`written` on a rendered value** meant the end of the chain before milestone 1; the spec now
  calls that `definition`, and `written` is the value on the same line. Code on PR 4 still has the
  old meaning until the milestone 1 binding work lands: `arg.written.replaceWithText(...)` on
  `max_count`'s `$pixels` there rewrites the `set` line, so every use changes.
- **`graph.diagnostics` was a method** but `rendered.diagnostics` a property; the spec makes both
  properties. On PR 4, TypeScript's `graph.diagnostics.length > 0` compiles and is never true.
- **Edits take villanelle text, only text.** Anything else must raise `TypeError` naming the
  parameter and pointing to `quote()` (spec 6.9; the message is in `spec/schema/api.json`). On PR 4,
  `set_values(2400)` fails inside the Python library; `"my host"` becomes two values. Use `quote()`
  for program strings.
- **`set` is a method name, not only a keyword.** `statement.set(text)` replaces values (it was
  `set_values`). In a Python class that defines `set`, a later annotation `set[str]` in the class
  body resolves to the method: write `builtins.set[str]` there.
- **Python's low level has no `__match_args__`,** so `match` with positional patterns raises
  TypeError there, while the rendered tree supports it.
- **Python separates kinds four ways** (literal strings, `StrEnum`s, classes with no `kind`, a
  `kind` on one class). Do not add a fifth: follow the binding guide's rule 4.
- **`from villanelle import *`** replaces `typing.List` with the low-level `List` in Python.
- **The processor ownership check** (D27) is retired by milestone 1: no operation takes a graph or
  render back to a processor. On PR 4 it still refuses another processor's graph at run time.
- **Generated parser code is never committed.** `tools/gen.sh` writes it to git-ignored folders.
- **Python's `EditError` is a `ValueError`,** so a broad `except ValueError` also catches
  `DetachedError`.
- **The `rasl` key rule** in the load runner must match `conformance/load/format.md` exactly.
- **`graph.diagnostics()` leaves out every E4xxx code,** E4001 and E4003 included (decision D11);
  only the render reports them. An earlier draft of the spec said otherwise.
- **The low level never imports the rendered layer,** not even a type (owner, 2026-10-29: "The low
  level shouldn't "depend on" the middle layer"). `render(graph)` is the rendered layer's function;
  an extension use holds shared `expanded value`s. Each binding has a check (binding guide rule 8):
  ESLint `no-restricted-imports` in TypeScript, `py/tests/test_layers.py` in Python. On PR 4 the low
  level still imports the rendered `Argument`: that is what the milestone 1 work removes.
- **JSON libraries are not the byte rule.** Go's `encoding/json` escapes `<`, `>`, `&` and replaces
  invalid UTF-8; the conformance bytes and `address text` are defined in neutral terms
  (`conformance/format.md`, spec 7.4). Write the encoder to the rule.
- **Inserted statements copy the first statement's indentation,** not the one before the index
  (spec 6.5); line breaks are the document's first.

## Tracking

Work is tracked in beads (`bd`, prefix `vil-`), per `AGENTS.md`. File a bead for each finding,
divergence or open question you find; record a decided rule in the bead's design field and in the
spec, not in a new notes file.
