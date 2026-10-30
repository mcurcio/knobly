---
name: knobly-binding
description: Use when adding a new language binding to knobly (Go, Rust, Java, any language beyond ts/, py/ and cpp/), or when changing the public API shape of any knobly binding - renaming or moving a type, member, function, error, kind or module in ts/, py/ or cpp/, adding an operation, or changing what a layer (syntax, low level / written, rendered tree) exposes. Also use when writing or fixing a binding's conformance adapter, the shared conformance driver or a corpus, or when the TypeScript and Python bindings disagree.
---

# knobly language bindings

The rules live in `spec/` (canonical). This skill does not repeat them: it says what to read, in
what order, how to work, and what has gone wrong before.

## Read first, in this order

1. `spec/README.md`: the layers and how the pieces fit.
2. `spec/glossary.md`: one word per concept, and each concept's type name per layer and binding.
3. `spec/spec.md`: what every binding must do. This wins over either binding's code
   (owner, 2026-10-27: "Within villanelle I want the spec to win over a reference language").
   `spec/schema/api.json`, `diagnostics.json` and `protocol.json` are the one home of every public
   signature, fixed list and adapter message, and win over the spec's tables.
4. `spec/contract.md`: the edges (positions per language, people forms, numbers, error
   classes, adapters).
5. `spec/binding-guide.md`: the owner's goals, naming rules, allowed differences, the
   concept map, and the new-binding checklist.
6. `spec/conformance.md`: the conformance levels, the adapter protocol and the shared driver.
7. `spec/codegen.md` whenever the task touches a public name, signature, kind, code, error class or the
   adapter protocol: every one of them is generated from the schema (milestone 6).
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
- Change the schema first (`spec/schema/api.json`; `python3 tools/gen-api.py --check` refuses an unresolved type,
  a layer-direction breach or a name collision), then the spec, both bindings, the reference docs
  (the user guide, `docs/site/pages/`, with a sample per language for a new capability) and any affected conformance format in the same change. A
  change to one binding alone is a divergence; a signature written by hand instead of generated is a defect.

## Workflow: a new binding

Follow the checklist in `spec/binding-guide.md` section 5. In short: pick one model and get the
first-hour program approved, then:

1. **Generate the parser** (`tools/gen.sh`): ANTLR 4.13.2 with its runtime (TypeScript, Python), or knobly's
   own generator `tools/parser/gen.py` with no runtime (C++: the binding hand-writes the tree hooks, error codes and
   recovery in `cpp/include/knobly/detail/syntax/parse.hpp`). `spec/binding-guide.md` step 3 has both routes.
2. **Write an emitter**: `tools/api/emit_<lang>.py`, rendering the loader's model (`tools/api/loader.py`) in your
   language's idiom: kind lists, codes, rules, the error tree, one declaration per concept with each trait of
   `spec/codegen.md` section 3 in your form, the names table, the adapter's message shapes and spelling table. Start
   from `emit_ts.py` or `emit_py.py`; give it a `LANGUAGE` (the loader's `Language` descriptor), register it in
   `tools/gen-api.py` and point `tools/gen.sh` at its output. The schema names no language: every fact about yours
   goes in `LANGUAGE`, never in `spec/schema/` (each root error group's class, your adapter modules' import paths,
   each factory's form, the argument type error's sentence, and what your idiom leaves out); `spec/codegen.md`
   section 10 lists each, and `tools/api/stub.py` is a third binding in miniature that `tools/gen-api.py --check`
   loads to prove it. Your classes implement what it generates; you write no signature, list or name by hand. Traps: a schema regex uses no `\s` `\w` `\d` `\b`
   (they differ between engines, and the loader refuses them); in Python the emitter writes what the pinned ruff
   writes, so a new construct needs `ruff format --check` on fresh output.
3. **Write the adapter**: one small program answering the driver's requests through your public API
   (`spec/conformance.md` section 6), typed by your generated shapes, spelling members with the generated
   `SPELLING` and naming error groups with `ERROR_GROUP_OF_CLASS`. Start a new one from the TypeScript or Python
   adapter (`ts/conformance/adapter.ts`, `py/conformance/adapter.py`); each is under 300 lines.
4. **Run the driver**: `python3 conformance/driver/run.py -- <your adapter's command>`.
5. **Climb the levels**: claim L0 in `hello`, make the syntax cases pass, then build the low level (L1),
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
4. Update the glossary and the concept map in the binding guide if a name changed (the schema already changed
   first). If a diagnostic code or the adapter protocol changed, run `python3 tools/gen-api.py docs` and commit the
   regenerated tables; `bash tools/check.sh` fails while one is stale.

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

# C++: configure generates the headers (tools/gen.sh cpp); ctest runs the unit tests, the contract and the driver.
# Build trees on the owner's Mac go under /Volumes/Dock (Catch2 is fetched at configure time).
cmake -S cpp -B /Volumes/Dock/tmp/kno-cpp-build -DKNOBLY_SANITIZE=ON && cmake --build /Volumes/Dock/tmp/kno-cpp-build
ctest --test-dir /Volumes/Dock/tmp/kno-cpp-build --output-on-failure   # add -DKNOBLY_COMPILED=ON for compiled mode
python3 conformance/driver/run.py -- /Volumes/Dock/tmp/kno-cpp-build/knobly_adapter

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
- **The driver is slow in `byte` units on long texts**: its position check (`conformance/driver/syntax.py`,
  `native_position`) rescans the text per position, so `list-5000` alone takes about 40 s and the C++ L0 run about a
  minute, almost all in the driver; the adapter answers all 168 cases in about a second under ASan.
- **C++ templates in `support/` cannot name an error class**: `errors.hpp` includes `sequence.hpp`, so
  `sequence::at` raises through `detail::raise_index_out_of_range`, declared in `detail/raise.hpp` and defined with
  the shared layer. GCC turns "inline function used but never defined" into an error under `-Werror` with no flag to
  silence it, so CMake links only the generated contract of an implemented layer (`api_contract_syntax.cpp` in
  milestone 1).
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
- **`@` statements, raw single quotes, `~` slices** (milestone 5, spec 3.1, 6.5): the first token
  decides a statement's kind (`WORD` a directive, `AT_WORD` `@set`/`@snippet`/`@use`/`@<extension>`, any
  other `@name` E3008); no directive name is reserved, so never classify by a word's text alone. A
  single-quoted string is raw (decode only double-quoted escapes). A slice is `name[1~3]`; `:` is a word
  character; a slice's name is a written value (a word or a `$name`, E4007 when the variable is not one
  word). There is no `plain` reader.
- **`;` ends every statement; a line break is whitespace** (milestone 4, owner Q1). A directive name
  cannot start with a digit or `-` (tokens `WORD`, `INTEGER`, `DIGIT_WORD`; all three are the value
  kind `word`). Error recovery resumes after the bad statement's `;` or block, never at a line break,
  and a broken statement is one `error` node (spec 3.2). E2008 is retired.
- **Check a given text's shape with the grammar's entry rules, never a probe or a scanner** (spec 2.8):
  `statementsText`, `valuesText`, `valueText`, `itemsText`, `boundText`, `sliceNameText`, `nameText`, parsed with
  the generated parser; the text-alone rules (E5002, E5005, E5009 to E5011, an empty no-value text, an override's
  no-`$name` rule) run on its tree. A text that
  ends in a comment is refused at its end; a line break in a values text is fine (`set("1\n2")`
  writes one statement with two values). Splicing the text into `x <text>;` and re-parsing was the
  old way: it leaked a `;` the user never typed into the diagnostics (round 15).
- **`written` on a rendered value** meant the end of the chain before milestone 1; the spec now
  calls that `definition`, and `written` is the value on the same line. Code on PR 4 still has the
  old meaning until the milestone 1 binding work lands: `arg.written.replaceWithText(...)` on
  `max_count`'s `$pixels` there rewrites the `set` line, so every use changes.
- **`graph.diagnostics` was a method** but `rendered.diagnostics` a property; the spec makes both
  properties. On PR 4, TypeScript's `graph.diagnostics.length > 0` compiles and is never true.
- **Edits take config text, its own type** (milestone 5, spec 6.9): a TypeScript branded string, a
  Python `NewType`, made only by `quote()` and `text()`. A plain string is a type error for the checker
  but passes at run time; anything that is not a string must still raise `TypeError` naming the
  parameter and pointing to `quote()` and `text()` (the message is in `spec/schema/api.json`). The
  adapter wraps every text the driver sends with `text()`, never a cast. `text("my host")` is two
  values; use `quote()` for program strings.
- **`set` is a method name, not the `@set` statement.** `statement.set(text)` replaces values (it was
  `set_values`); since milestone 5 a written value has `set(text)` too, which writes one value and keeps
  the handle, changing its kind (and in Python its class) when the new value is of another kind. Before
  milestone 5 an edit loop over a render met a shared `written` handle twice and the second
  `replaceWithText` raised `DetachedError`; `value.written.set(...)` is the loop now. In a Python class that defines `set`, a later annotation `set[str]` in the class
  body resolves to the method: write `builtins.set[str]` there.
- **Every variant is its own type, with `kind`** (spec 2.10, milestone 2). An operation that cannot
  succeed for a variant is absent from it, not a run-time error: no `NoSetLineError`, no `rename`
  on an extension line. Python's `__match_args__` keep one field order per concept in every layer,
  so `match` works on the low level too. Before milestone 2 Python's low level had none.
- **Every kind list is generated** (TypeScript `as const` objects with the derived string-literal type, Python
  `StrEnum`s, token kinds from the grammar; milestone 6 reversed milestone 2's "no constant objects"). Do not
  hand-write one or add `Literal` aliases. Inside a binding compare `kind`, `reason` and `code` with a member
  (`StatementKind.Set`, `StatementKind.SET`), never a string literal: the kind lint (`tools/lint/`) fails the
  build. Statement keywords are dispatched through the generated `STATEMENT_OF_KEYWORD`, never by comparing text.
- **Every public signature is generated** (milestone 6): TypeScript classes `implements` the generated interfaces
  and the layer entries re-export them; Python handle classes subclass the generated Protocols, and records are the
  generated dataclasses. A name test compares each import path's exports with the generated `PUBLIC_NAMES`, both
  ways; there is no hand-kept list of removed names.
- **Python's public types and generated types are one** (milestone 7): every generated annotation naming a concept
  the binding implements names the binding's public class (`knobly.rendered.Directive`), so a program
  annotating with public classes type-checks against every record, callback and Protocol. A union over hand classes
  (`written.Statement`) is the binding's own, checked against the generated `UNIONS`. Nothing outside the package
  imports `knobly._api` (but the contract's type checker's block): the tests' half of the contract is the
  generated `py/tests/api_contract.py` (`PUBLIC_NAMES`, `MATCH_ARGS`, `UNIONS`, each `<Module>Functions` and
  `<Class>Constructor`, and the mypy assignments that check every module, constructor and hand class against the
  schema), and the adapter's `ERROR_GROUP_OF_CLASS` is in its `shapes.py`. TypeScript mirrors it: `PUBLIC_NAMES` in
  the generated `ts/test/api-contract.ts`, `ERROR_GROUP_OF_CLASS` in `ts/conformance/shapes.ts`; neither ships.
- **Schema docs are for users** (milestone 7): a schema entry's `doc` is emitted as JSDoc and docstrings; its
  `rationale` (history, owner quotes, bead ids, one language's notes) is never emitted. `tools/gen-api.py --check`
  refuses a bead id, `milestone N`, an `owner, <date>` quote or a language's name in any emitted doc, protocol
  docs and parameter docs included; each binding's name test refuses the same (and private paths) in the
  hand-written public docs. Maintainer notes go in comments.
- **Schema patterns are I-Regexps** (RFC 9485) between `^` and `$`; a type with a union after a function's result
  or a generic inside an argument list is written in parentheses.
- **One import path per name** (milestone 6, binding guide rule 9): `knobly` (shared and io),
  `knobly/syntax`, `knobly/written`, `knobly/rendered` (Python: subpackages). No re-export under a second
  path, no `I` prefix, no alias for an old name.
- **One block shape** (spec 2.11): a block is iterated and indexed, has `directives (name?)` and `walk`; there is no
  `block.statements`, and `walk` is on the block (`rendered.block.walk(...)`), not on the render or a directive.
- **`from knobly import *`** replaced `typing.List` with the low-level `List` in Python; since
  milestone 2 the six written value classes live in `knobly.written` only.
- **The rendered layer reads only the public low level** (`graph.expand()`, spec 6.10). A
  private accessor, a `_name` attribute or an `instanceof` of a low-level class there fails the
  layer check (binding guide rule 8).
- **The processor ownership check** (D27) is retired by milestone 1: no operation takes a graph or
  render back to a processor. On PR 4 it still refuses another processor's graph at run time.
- **Generated code is never committed** (the parser, `ts/src/gen/api/`, `py/src/knobly/_api/`, the adapters'
  `shapes` files, `py/tests/api_contract.py`): `tools/gen.sh` writes it to git-ignored paths. The generated docs tables (spec 2.4,
  docs/site/pages/diagnostics.md, the members tables of docs/tables.json, spec/conformance.md 4.1 and 4.2) are the one committed output; edit `diagnostics.json` or
  `protocol.json`, never the table.
- **Errors** (contract 4, milestone 4): `KnoblyError` is the base of the expected outcomes only
  (`DiagnosticError`, `ReadError`, `BadTextError`, `SaveError` and its `LostUpdateError`). Program bugs
  sit outside it: `DetachedError` (a `ReferenceError`), `TypeError`, misuse (`MisuseError` in
  TypeScript, `ValueError` in Python), `RangeError` / `IndexError`. There is no `EditError`. Every bad
  name is a misuse error, from `load`, `setOverride` and `rename` alike. `ReadError` has no diagnostic
  and no E3004; `ReadError`, `SaveError` and `LostUpdateError` carry `paths`.
- **A lost update has its own error and one check.** Every writer calls `check lost updates`
  (spec 4.2) before writing; `LostUpdateError.paths` are only the conflicting files. The fetch writer
  sends `If-Match` on the ETag of a `GET` it makes first.
- **The `rasl` key rule is data** (`conformance/keys.json`, sent in `render` and `diff`). The adapter
  builds its key rule from the data (`spec/conformance.md` 4.3); it never names `rasl`.
- **One diagnostics list** (milestone 4): `graph.diagnostics` holds every code the expansion finds,
  E5001 and E4001 included; the expansion and the render show the same list. Decision D11 (render-only
  codes) is retired: do not keep a list of codes to filter.
- **An unread include copy is an unreadable with reason `unread`** (E3007), never nothing, so `diff`
  reports what it held as `unknown`.
- **Scoping and precedence live in `spec/expansion.md`** (one table). `docs/site/pages/language.md` only teaches.
- **The low level never imports the rendered layer,** not even a type (owner, 2026-10-29: "The low
  level shouldn't "depend on" the middle layer"). `render(graph)` is the rendered layer's function;
  the low level owns expansion, the extension port and the expanded values (milestone 4), and a
  rendered directive holds its directive expansion's own objects (no `Argument` family, no rendered
  `Unreadable`). Each binding has a check (binding guide rule 8): ESLint `no-restricted-imports` in
  TypeScript, `py/tests/test_layers.py` in Python.
- **JSON libraries are not the byte rule.** Go's `encoding/json` escapes `<`, `>`, `&` and replaces
  invalid UTF-8; the conformance bytes and `address text` are defined in neutral terms
  (`conformance/format.md`, spec 7.4). Write the encoder to the rule.
- **Inserted statements copy the first statement's indentation,** not the one before the index
  (spec 6.5); line breaks are the document's first.
- **Python: a `str` is a `Sequence[str]`.** Type port results `tuple[str, ...]` and refuse a bare
  `str` at run time (a `resolve` or `specs` returning `"dark.conf"` used to resolve `d`, `a`, `r` ...).
  Expanded values compare by text (`==`, `hash`).

## Tracking

Work is tracked in beads (`bd`, prefix `kno-`), per `AGENTS.md`. File a bead for each finding,
divergence or open question you find; record a decided rule in the bead's design field and in the
spec, not in a new notes file.
