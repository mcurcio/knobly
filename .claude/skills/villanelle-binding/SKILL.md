---
name: villanelle-binding
description: Use when adding a new language binding to villanelle (Go, Rust, Java, any language beyond ts/ and py/), or when changing the public API shape of any villanelle binding - renaming or moving a type, member, function, error, kind or module in ts/ or py/, adding an operation, or changing what a layer (syntax, low level / written, rendered tree) exposes. Also use when writing or fixing a binding's conformance adapter, the shared conformance driver or a corpus, or when the TypeScript and Python bindings disagree.
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
4. `spec/contract.md`: the edges (positions per language, people forms, numbers, error
   classes, adapters).
5. `spec/binding-guide.md`: the owner's goals, naming rules, allowed differences, the
   concept map, and the new-binding checklist.
6. `spec/conformance.md`: the conformance levels, the adapter protocol and the shared driver.
7. `spec/codegen.md` only if the task touches the fixed lists (codes, kinds, limits).
8. For the reasons behind a rule: `.claude/design/consumer-api/requirements.md` (the owner's dated
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

Follow the checklist in `spec/binding-guide.md` section 5. In short: pick one model and get the
first-hour program approved, then:

1. **Generate**: the parser (`tools/gen.sh`) and the fixed lists (`tools/gen-api.py`).
2. **Write the adapter**: one small program answering the driver's requests through your public API
   (`spec/conformance.md` section 6). Start a new one from the TypeScript or Python adapter
   (`ts/conformance/adapter.ts`, `py/conformance/adapter.py`); each is under 300 lines.
3. **Run the driver**: `python3 conformance/driver/run.py -- <your adapter's command>`.
4. **Climb the levels**: claim L0 in `hello`, make the syntax cases pass, then build the low level (L1),
   the rendered tree (L2) and include (L3), raising the claim as each level's cases pass. Then write
   the first-hour program as a test, and add the driver with your adapter to CI.

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

One driver runs every corpus (`conformance/corpora.json`) against a binding's adapter and compares every output with
its expected one; no binding has a conformance runner of its own. From the repo root (Node from `.nvmrc`; on the
owner's Mac set `ANTLR_JAR_DIR=/Volumes/Dock/Home/.cache/antlr`; Java 11+ is needed to generate the parser):

```bash
# TypeScript: build first (the adapter imports ts/dist/), then run the driver with the adapter.
nvm use
corepack pnpm -C ts install && corepack pnpm -C ts build
(cd ts && python3 ../conformance/driver/run.py -- node conformance/adapter.ts)

# Python: generate the parser first (pytest's conftest.py also does), then the driver.
bash tools/gen.sh py
(cd py && python3 ../conformance/driver/run.py -- uv run --locked python conformance/adapter.py)

# One corpus or case, or the cases up to a level while you climb:
python3 conformance/driver/run.py --corpus written --case set-comment -- <adapter...>
python3 conformance/driver/run.py --level 1 -- <adapter...>
```

The output is TAP: `not ok` lines carry the first difference. Each package's own unit tests stay in
its test suite (`corepack pnpm -C ts test`, `cd py && uv run pytest`); lint, format and typecheck commands are in
`ts/README.md` and `py/README.md`. `bash tools/check.sh` runs the driver's own test.

## Traps found in review

- **Expected outputs are hand-derived.** Never regenerate a file in `conformance/*/expected/` from
  an implementation to make the driver pass. A mismatch is a bug in the binding, its adapter or the rules.
- **Climb by level, not by skipping.** The driver runs every case at or below the level the adapter
  claims; there is no per-case skip. A failing case at your claimed level is a red build. That holds for the three
  `surrogate-*` syntax cases too: a byte-unit binding passes them by holding a lone surrogate as WTF-8 (Go can; Rust's
  `String` cannot). spec 2.1's proposal for UTF-8 bindings (a skip plus invalid-byte cases) is pending the owner
  and not in the driver.
- **The adapter finds and compares nothing.** It dumps objects with ids and applies one member by id;
  the driver finds targets (a statement by its name token, a value by its start), converts positions
  and prints the expected bytes. Logic that creeps into an adapter is logic the next binding copies.
- **Negative zero cannot cross JSON as a number** (`JSON.stringify(-0)` is `0`): an adapter sends
  `"-0"` for it, so the driver fails the case (`spec/conformance.md` 4.4).
- **`null` in a case's edit arguments means absent**: TypeScript's adapter passes `undefined`
  (`setOverride(name, undefined)` removes the override), Python's `None`.
- **The adapter's standard output is the protocol.** Log to standard error only; one stray `print`
  is a fault for the case in flight.
- **Positions count each language's own string unit** (contract 1, milestone 2): UTF-16 in
  TypeScript, code points in Python, bytes in a UTF-8 language. The conformance files stay UTF-16:
  the driver converts with the text the position counts in, from the unit the adapter's `hello` names.
  Before milestone 2 Python reported UTF-16, so `text[s.start.offset:s.end.offset]` was wrong after an
  emoji; before milestone 3 Python's written runner also matched targets by code-point column against
  the corpus's UTF-16 column (no case had an astral character before a target, so it never showed).
- **Numbers at the edges** (contract 3): no reader returns `-0` (TypeScript used to); `1e400` is
  E4004, not infinity; beyond 2^53-1 a word is a rounded number but not an integer. The contract
  cases (`conformance/contract/`) cover them; ECMAScript's `Number::toString` is the print rule, which
  the driver applies, so an adapter sends the number, never its text.
- **A lone `"\r"` never ends a line**, also in `format diagnostic`'s source line. Python's
  `str.splitlines()` and a JavaScript `/\r\n|\n|\r/` both break there.
- **A values text with a line break outside a list splits the statement** (`set("1\n2")` on `port
  80;` wrote two statements, vil-5ya). The check of a values text refuses it (spec 2.8). So does a
  comment the text ends in (`set("1 # note")` wrote `port 1 # note;`, whose `;` the comment swallowed,
  vil-033), at the comment, list items included.
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
- **Every variant is its own type, with `kind`** (spec 2.10, milestone 2). An operation that cannot
  succeed for a variant is absent from it, not a run-time error: no `NoSetLineError`, no `rename`
  on an extension line. Python's `__match_args__` keep one field order per concept in every layer,
  so `match` works on the low level too. Before milestone 2 Python's low level had none.
- **Every kind list is generated** (TypeScript string-literal types, Python `StrEnum`s, token kinds
  from the grammar). Do not hand-write one, and do not add constant objects or `Literal` aliases.
- **`from villanelle import *`** replaced `typing.List` with the low-level `List` in Python; since
  milestone 2 the six written value classes live in `villanelle.written` only.
- **The rendered layer reads only the public low level** (`graph.expand()`, spec 6.10). A
  private accessor, a `_name` attribute or an `instanceof` of a low-level class there fails the
  layer check (binding guide rule 8).
- **The processor ownership check** (D27) is retired by milestone 1: no operation takes a graph or
  render back to a processor. On PR 4 it still refuses another processor's graph at run time.
- **Generated parser code is never committed.** `tools/gen.sh` writes it to git-ignored folders.
- **Errors** (contract 4): `VillanelleError` is the one base; `DetachedError` is not an edit error
  (Python: a `ReferenceError`), so `except ValueError` no longer swallows it; `ReadError` has no
  diagnostic and no E3004 (a missing root file is not an include failure); `ReadError` and
  `SaveError` both carry `paths`.
- **The `rasl` key rule is data** (`conformance/keys.json`, sent in `render` and `diff`). The adapter
  builds its key rule from the data (`spec/conformance.md` 4.3); it never names `rasl`.
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
