# Milestone 3, frozen for the binding lanes (beads vil-j80, vil-033)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 3. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical): `spec/conformance.md` (the levels, the adapter protocol, the driver), `spec/spec.md` 2.8 (the
check of a values text, with the comment rule of vil-033) and 9 (the corpora). Where this page and `spec/` differ,
`spec/` wins and the difference is an erratum.

Scope: the rest of round 13 root cause 5 (`.claude/design/consumer-api/round13/review.md`): "Every binding passes
the same corpora through one shared driver"; "a binding writes one small adapter (load files, find a target, apply
a neutral op, dump); one shared driver runs every case; the "rasl" key rule becomes data". Plus bug vil-033 (a
comment in a values text swallows the statement's `;`). Not in scope: the high level, L4 shared cases (adapters that
write files), the type skeletons of `spec/codegen.md`, and every "Proposed (pending owner)" note.

## What this rests on

- The owner, 2026-10-27: "Within villanelle I want the spec to win over a reference language" (so the spec and its
  corpora are the authority, and a binding's runner is not).
- The round 13 review's root cause 5 and its levels L0 to L4. These are the review's design proposals, adopted as
  this milestone's beads, not the owner's words.
- Everything else here is a design choice of this milestone, revisable: newline-delimited JSON, the three response
  shapes, the driver finding targets (the review gave that to the adapter), the dump shapes, the key rule's data
  form, the corpus manifest, TAP output, and the comment rule's placement.

## 1. What landed in `spec/`, `conformance/` and `tools/` (this lane, done)

| Path | What |
|---|---|
| `spec/conformance.md` (new) | prior art, the levels, the transport, every message, every dump shape, key rules as data, reader results, the driver, the corpus layout, what a binding writes |
| `spec/spec.md` 2.8, 7.4, 9 | the comment rule; the known gap's note; section 9 rewritten for the driver, the levels and the new corpora |
| `spec/README.md` | the levels table, "a new binding's path" (generate, write the adapter, run the driver, climb the levels), milestone 3 status |
| `spec/contract.md`, `binding-guide.md`, `codegen.md`, `glossary.md` | the driver converts positions and prints numbers; checklist steps 5 to 9 rewritten; codegen's driver row done by hand; the new terms (`conformance adapter`, `driver`, `conformance level`, `key rule data`, `dump`) |
| `conformance/driver/` (new) | the driver: `run.py` (CLI, levels, TAP), `adapter.py` (the process client), `units.py` (position conversion, one place), `encode.py` (the byte rule, one place), one module per format (`syntax.py`, `written.py`, `rendered.py` for load and rendered, `contract.py`), `test_driver.py` with `stub_adapter.py` (its own test) |
| `conformance/corpora.json`, `conformance/keys.json` (new) | the manifest of corpora; the key rules as data (`rasl`, `pins`) |
| `conformance/rendered/` (new corpus) | 9 cases: address text and people forms with escapes, occurrences, empty and absent keys, a parent rule; diff order, unknown, alone, keyed and positional moves, block presence, a duplicate key |
| `conformance/contract/cases.json` | 41 new cases: every reader of spec 2.9 beyond the number readers (`word-*`, `string-*`, `boolean-*`, `list-*`, `slice-*`, more `number-*`, `integer-*`, `plain-*`), and `format-tab-before`, `format-astral-before` (by unit), `format-crlf`, `format-no-graph` |
| `conformance/written/cases.json` | 7 new cases for vil-033 (section 7) |
| format pages | `conformance/format.md`, `load/format.md`, `written/format.md`, `contract/format.md` say the driver does what each runner did; `rendered/format.md` is new |
| `tools/check.sh` | step 5: the driver's own test |
| `.github/workflows/ci.yml` | the driver for each binding (section 6) |
| `.claude/design/consumer-api/round14/m3-adapter.py`, `m3-adapter.mts` | the two proof adapters (section 4): each lane moves its own into its package |
| `docs/low-level-api.md`, `README.md`, `.claude/skills/villanelle-binding/SKILL.md` | the comment rule; the driver; the skill's new-binding path and running the shared cases |

`spec/schema/` did not change, so `tools/gen-api.py` did not either (it still generates what each lane needs).

Proof, on this branch before any lane: the driver with `m3-adapter.py` (Python binding) and with `m3-adapter.mts`
(TypeScript binding, after `pnpm build`) runs 308 tests (5 corpus checks, 303 cases); each binding passes every case
but the five red vil-033 cases (section 7), at every level up to L3, in about a second.

## 2. The adapter protocol, message by message

Transport (`spec/conformance.md` 3): the driver starts the adapter once per run; one JSON request per line on its
standard input, one JSON response per line on its standard output, in order; the adapter exits when its input closes.
Responses: `{"id", "ok": value}`, `{"id", "thrown": {"group", "code"?, "diagnostics"?}}` for the binding's own errors
(`villanelle error` and below), `{"id", "fault": text}` for anything else. A position is `[line, column, offset]` in
the binding's own unit; the adapter never converts. Every dumped binding object has an `id` (text; an index into
the adapter's list of dumped objects is enough). Dump shapes: `spec/conformance.md` 4.2.

| # | Request | Response `ok` | Example |
|---|---|---|---|
| 1 | `{"id":1,"op":"hello","protocol":1}` | `{"protocol":1,"binding":"python","unit":"code point","level":3}` | TypeScript: `"unit":"utf-16"` |
| 2 | `{"op":"parse","text":...}` | syntax dump `{"tokens":[[kind,text,start,end],...],"root":[kind,start,end,[...]],"diagnostics":[...]}` | `parse("x;")` |
| 3 | `{"op":"load","files":{...},"root":"main.conf","extensions":[],"overrides"?:{...}}` | `{"graph":id}` | a processor over a `memory source` of `files`, the include extension when `extensions` holds `"include"` |
| 4 | `{"op":"graph","graph":id}` | graph dump: documents (with text, saved text, syntax, block tree, included-by copies), edges, variables (with wins and shadowed-at), diagnostics | asked again after every edit |
| 5 | `{"op":"render","graph":id,"key"?:[rules]}` | render dump: directive tree with each address (`text`, `people`), origins, arguments (`definition`, `chain`), unreadables, diagnostics | the addresses under the key rule built from `key` |
| 6 | `{"op":"diff","before":id,"after":id,"key"?:[rules]}` | `[{"kind","address":{"text","people"}},...]` | |
| 7 | `{"op":"edit","target":id,"member":"replace with text","args":["2400"]}` | `{"handles":[{"id","text"},...]}` when the member returns handles, else `{}` | `null` in `args` is absent (TypeScript `undefined`, Python `None`) |
| 8 | `{"op":"save","graph":id}` | `{"batches":[[[path,text],...],...]}` | a recording writer, one batch per `write` call |
| 9 | `{"op":"quote","text":...}` | text | |
| 10 | `{"op":"read","value":id,"reader":"plain"}` | `{"text"}`, `{"boolean"}`, `{"number"}` (`"-0"` for negative zero), `{"slice":[name,start,end]}`, `{"index":[name,i]}`, `{"value":text}`, `{"list":[...]}` | thrown `{"group":"diagnostic error","code":"E4002"}` |
| 11 | `{"op":"print","target":id}` | the object's people form (`String(x)`, `str(x)`) | |
| 12 | `{"op":"format","diagnostic":id,"graph"?:id}` | `format diagnostic (diagnostic, graph?)` | |
| 13 | `{"op":"cut","text":...,"start":n,"end":n}` | `text` cut with the language's own slicing | |

Members and readers arrive as spec names (`replace with text`, `insert statements`, `set override`); the adapter
spells them in its casing (`replaceWithText`, `replace_with_text`). Errors go back as spec group names, the class
name split into lowercase words (`BadTextError` to `bad text error`). Key rules arrive as data
(`spec/conformance.md` 4.3): the first rule whose `directive` is the directive's name and whose `parent` (if given)
is its parent's name; `["value", i]` is the `i`-th value's text or absent, `["join", sep]` the values' texts joined.

## 3. The driver CLI

```
python3 conformance/driver/run.py [--level N] [--corpus NAME]... [--case NAME]... [--cwd DIR] -- ADAPTER...
```

- Python 3.9+ standard library only. TAP 14 on standard output; exit 0 all passed, 1 a case failed, 2 the adapter
  did not start or its `hello` is wrong. A fault (the adapter exited or broke the protocol) fails that case and
  restarts the adapter.
- Default level: the one the adapter claims; cases above it are `# SKIP`. The last lines give the count per level
  and whether the claim holds.
- It alone: finds targets (a statement by its name token, a value by its start, a rendered directive by its people
  address), converts positions (`units.py`), maps the written corpus's tokens to spec names (`written.py` `OPS`,
  `ERRORS`), prints expected bytes (`encode.py`), applies the number rule (`contract.py`), and compares.

## 4. What each binding adapter implements

Each lane moves its proof adapter into its package, adds its package's types and lint, and changes nothing about
what it sends: with them, every case passes today but the five red vil-033 cases.

| | TypeScript | Python |
|---|---|---|
| File | `ts/conformance/adapter.ts`, from `round14/m3-adapter.mts` | `py/conformance/adapter.py`, from `round14/m3-adapter.py` |
| Run (from the package directory) | `node conformance/adapter.ts`, after `corepack pnpm build` | `uv run --locked python conformance/adapter.py`, after `tools/gen.sh py` |
| Imports | `../dist/index.js`, `../dist/include.js` at run time (Node 24 strips types; so erasable syntax only: no `enum`, no parameter properties); types from `../src/index.js` with `import type` only | `villanelle`, `villanelle.written`, `villanelle.include` |
| Checks | it typechecks and lints with the package (it is not in `dist/` or the published files; `tsc` for it runs where `dist/` exists, or against `import type`s only) | `ruff check`, `ruff format --check` and `mypy` cover it (add `conformance` to mypy's `files`) |
| Size | under 200 lines | under 300 lines (about 220 of code) |
| `hello` | `{"protocol":1,"binding":"typescript","unit":"utf-16","level":3}` | `{"protocol":1,"binding":"python","unit":"code point","level":3}` |

Both claim L3. Every op of section 2 is implemented in both. The adapter uses the public API only (`import` from
the package entry points, never `src/written/...` internals).

## 5. The runner files deleted

Each lane deletes its four runners and whatever only they use; its unit tests stay.

- TypeScript: `ts/src/conformance.test.ts`, `ts/src/contract-conformance.test.ts`, `ts/src/load-conformance.test.ts`,
  `ts/src/written-conformance.test.ts` (1264 lines in all eight files with Python's). `ts/src/rendered/testing.ts`
  stays: eight unit tests import it (`browser`, `layers`, `node`, `rendered/rules`, `rendered/rasl`,
  `rendered/readers`, `rendered/diff`, `rendered/report`).
- Python: `py/tests/test_conformance.py`, `py/tests/test_contract_conformance.py`,
  `py/tests/test_load_conformance.py`, `py/tests/test_written_conformance.py`; and `utf16_length`, `utf16_column`
  in `py/tests/conftest.py` if nothing else uses them (only the runners do today). The number-rule unit test in
  `test_contract_conformance.py` moves to `conformance/driver/test_driver.py` (done).
- No other test may read `conformance/**` to compare outputs: the driver is the only comparer. A unit test may still
  load a fixture from `fixtures/`.

## 6. The CI change (done in `.github/workflows/ci.yml`)

- The `ts` job, after `corepack pnpm build`: `python3 ../conformance/driver/run.py -- node conformance/adapter.ts`.
- The `py` job (both Pythons of the matrix), after `mypy`: `python3 ../conformance/driver/run.py -- uv run --locked
  python conformance/adapter.py` (pytest has generated the parser by then).
- The `grammar` job runs `tools/check.sh`, which now runs the driver's own test.
- Each leg adds about one second. Until both lanes land, these two steps fail: the adapters do not exist yet in
  `ts/` and `py/`, and the vil-033 cases are red.

## 7. Bug vil-033: a comment in a values text

`stmt.set("1 # note")` on `port 80;` writes `port 1 # note;`: the comment runs to the end of the line, so the `;` is
inside it. Both bindings accept it today. Rule (spec 2.8): **a values text that ends in a comment is refused with
`bad text error` E2001 at the comment** (the first token that is more than values, after any `;` or block before
it), in every values text: `set` on a directive and on a set line, a value's `replace with text` (a list item's
included: its `,` or `]` would be swallowed), and an override's text (`set override`, and `load`'s overrides: one
check). A comment that a line break follows is the line-break rule's (refused at the line break outside a list,
allowed inside one).

| Case (`conformance/written/`) | Edit | Expected | Today, both bindings |
|---|---|---|---|
| `set-comment` | `set "1 # note"` on `port 80;` | `["error","BadTextError",[["E2001",0,2]]]`, no text changed | `["ok"]`, `port 1 # note;` (red) |
| `set-line-comment` | `set "2 # note"` on `set $a 1;` | the same | accepted (red) |
| `value-replace-comment` | `80`'s `replaceWithText "1 # note"` | the same | accepted (red) |
| `list-item-replace-comment` | `2`'s `replaceWithText "3 # note"` in `x [1, 2];` | the same | E2004 at 0:8, from the check's own probe `x [3 # note];` (red) |
| `set-override-comment` | `setOverride a "1 # note"` | the same | accepted (red) |
| `set-comment-line-break` | `set "1 # note\n"` | E2001 at 0:8 (the line break) | passes (guard) |
| `set-comment-in-list` | `set "[1, # note\n2]"` | ok, `port [1, # note\n2];` | passes (guard) |

Red first: the five red cases were seen failing through the driver with both proof adapters on this branch. Each
lane makes them pass in its check of a values text (`valuesTextProblems` in `ts/src/written/document.ts`, its twin
in `py/src/villanelle/written/_document.py`; the override check calls it). Note the list item case: the check parses
the item inside a probe (`x [<text>];`), whose `]` the comment swallows, so the comment must be found before the
probe's syntax diagnostics are reported (for example, parse the probe with a line break before its closing `;` or
`]`, which the line-break scan never sees because it reads only the given text's tokens). The expected outputs above
are the contract; how the check finds the comment is the lane's.

## 8. Behaviour changes

For programs using the library:

1. **A values text that ends in a comment is refused** (vil-033): `set`, a value's `replace with text`, `set
   override` and `load`'s overrides raise `bad text error` with E2001 at the comment. Before, the first three wrote a
   statement whose `;` (or a list's `,` / `]`) was inside the comment, and an override took the text; a list item's
   `replace with text` was refused with E2004 at the text's end instead.

For the bindings' own test suites and CI (no library behaviour changes):

2. `corepack pnpm test` and `uv run pytest` no longer run the shared cases; the driver does, as its own CI step.
3. A case is no longer skipped by its `needs`: the driver runs every case at or below the claimed level.
4. The load corpus's `after` load is a second `load` (a second processor), not a reload by the same one; spec 7.1
   lets `diff` compare any two renders, and every case passes either way.
5. The `rasl` key rule is data (`conformance/keys.json`); no binding code names it.
6. Targets are found with UTF-16 columns: the Python runner matched code-point columns against the corpus's
   UTF-16 ones (latent: no case had a character above U+FFFF before a target).
7. 50 new shared cases (41 contract, 9 rendered) that both bindings already pass, and 7 written cases (section 7).

## 9. Errata and follow-ups

Recorded in `.claude/errata.md` (2026-10-29, milestone 3 spec lane): the adapter no longer finds targets (the
review said it would); `load/format.md`'s "the same processor"; the Python runner's code-point target columns;
the list item check's E2004 artifact; codegen's "three case formats" (there were four); the word "adapter" now
also names the conformance adapter. Not covered by any shared case (spec 9 lists them): L4; a statements text that
ends in a comment (a statement's `replace with text` with no `;`, whose next statement shares its line); a key
holding a lone surrogate. Follow-up beads are the orchestrator's to file (this lane files none).

## 10. How each lane proves it is done

1. Its package's checks pass (TypeScript: `corepack pnpm test`, `typecheck`, `lint`, `build`; Python:
   `uv run --locked pytest`, `ruff check`, `ruff format --check`, `mypy`).
2. `python3 ../conformance/driver/run.py -- <its adapter>` from the package directory exits 0 with
   `# claimed L3 extensions: holds`.
3. The four runner files are gone; `grep -rln "conformance/" ts/src py/tests` finds no test that reads an expected
   file.
4. The five red vil-033 cases were seen failing before the fix (say so in the commit or the lane's report).
5. Its adapter is under the size in section 4 and imports only the package's public entry points.
