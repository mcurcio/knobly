## 2026-10-28, milestone 1 spec (kno-fy4), architect

- `spec/schema/api.json` (first draft) listed `format diagnostic` in the shared layer, but it takes a
  `document graph`, a low-level type, so shared would import the low level. Moved to the written
  layer in the schema; frozen-m1.md section 4 says where each binding puts it.
- The first draft of this milestone's spec (uncommitted) recorded the owner's answer 1 as "B
  graph.render()" with the low level depending on the rendered layer, and withdrew the round 13
  low-level value type for `extension use`. Superseded by his clarification (2026-10-29: "The low
  level shouldn't "depend on" the middle layer"): spec 5, 6.2, 7.0 now say `render(graph)` in the
  rendered layer, and `extension use` holds the new shared `expanded value` (spec 2.9).
- `AGENTS.md` ("Landing work") says to push directly to `main` and not open pull requests (owner,
  2026-10-22), while this work lands on `docs/binding-spec` through PR 5 and the global rules say
  never push to `main`. Not changed here; the owner should say which holds now.

## 2026-10-28, milestone 1 generator and public-name check (kno-fy4 part 2), build tooling

- `spec/schema/api.json` lists `kind` as a member of `place`, `override` and `change`, but
  frozen-m1.md (section 1, "Shared records") and the schema's own `disagreements` defer Python's
  `kind` on `Place`, `Override` and the change classes to root cause 3. The schema has no way to
  say "absent in one binding until a later milestone", so `py/tests/test_api_names.py` fails on
  those three for the whole milestone, while frozen-m1.md section 9.3 says the check passes when a
  lane is done. Either Python adds `kind` now, or the schema gets a per-binding deferral marker
  (for example `"later": {"py": "root cause 3"}` on the member) that both checks honour. The checks
  were not weakened to guess one.
- A member's `spell` mixes four things: a name (`as_word`, `length`), a call shape
  (`load(path, { overrides })`), a type (`ReadonlyMap<string, string>`,
  `Mapping[str, str] (...)`) and prose (`the block itself is a Sequence`,
  `with diagnostics.collecting():`, `len(diagnostics)`). Both name checks read it by pattern and
  fail on a spell they cannot read, but a tool should not have to parse prose: split it into
  `name` (the attribute) and `signature` (for people).
- frozen-m1.md section 6 says to keep ruff checking the generated `py/src/knobly/_api/`. Ruff
  skips git-ignored files by default (`ruff check src/knobly/_api` prints "No Python files
  found"), so once the folder is ignored, `ruff check` and `ruff format --check` never see it
  (mypy does). The generator's output passes both with `--no-respect-gitignore`; keeping it
  checked in CI needs a pyproject change (Python lane).

## 2026-10-28, milestone 1 Python lane (kno-094)

- The check of an override (frozen-m1.md section 3, spec 6.3) runs the text "as the values of `x <text>`", but
  the values check both bindings share (`values_text_problems` / `valuesTextProblems`) does not treat a line break
  as the end of the values: `"1\n2"` passed it, and the old `set_handed` then read only `1`, dropping `2`
  silently. Python's one check now refuses it (BadTextError E2001 at the `2`, test
  `test_load_and_set_override_refuse_an_override_text_alike`); the TypeScript lane should do the same so the
  bindings agree. The same gap remains in the edits: `stmt.set("1\n2")` on `port 80;` writes `port 1\n2;`, which
  parses as two statements. Not changed here (an edit-check behaviour change for both bindings); it needs its own
  bead and, if wanted, a written conformance case.
- `py/tests/test_api_names.py` still fails `place.kind`, `override.kind` and `change.kind` (the erratum above from
  the build-tooling lane): frozen-m1.md section 1 and the schema's own `disagreements` defer those to root cause 3,
  so the Python lane did not add them. Section 9.3 ("the public-name check passes") cannot hold for Python until
  the schema can mark a member as deferred per binding, or the owner moves those three into milestone 1.

## 2026-10-28, milestone 1 fix pass (PR 5 review findings), fix agent

- Python's missing `kind` on `Place`, `Override` and the change classes (the two entries above): the schema now
  marks those three members `"later": {"py": "root cause 3"}`, and both public-name checks skip a member only in
  the binding its marker names (spec/codegen.md says so). This is a design choice made to turn the gate green
  without guessing the owner's answer; if he wants `kind` in Python now, add it and delete the three markers.
- The check of an override now treats a line break as the end of the values in both bindings (`"1\n2"`: E2001 at
  the `2`, 1:0); spec 6.9's table says so and the written case `set-override-line-break` holds both bindings to it.
  The same gap in the statement edits (`stmt.set("1\n2")` on `port 80;` writes `port 1\n2;`, two statements) is
  still open and needs its own bead; this lane may not create beads.
- Review finding "render does not build on the low level's public objects" (TS `render` checks
  `instanceof DocumentGraph`, calls `graph.binding()` and casts handles; Python's render imports `_graph`, `_bind`,
  `_document`; `Bound`, `UnreadableReason` decisions and the E4xxx/E5xxx render checks live in the low level, and
  `graph.diagnostics` filters render-owned codes). frozen-m1.md section 4 explicitly allows "a package-internal
  accessor" to the graph's binding results, so the binding lanes followed the frozen page. Whether the owner's
  "they should have different domain objects. The middle layer of objects can build on the lower layer domains"
  also requires the rendered layer to build only on the low level's public API (its own expansion step from
  `copies()`, `resolutions()`, values and edges, with `Bound`, the unreadable reasons and the render checks moved
  into `src/rendered/`) is an owner question. Not done here: it is a redesign of both bindings' binder, and the
  include extension still needs expanded values from the low level during `load`.
- The schema's layer table ("shared may import nothing", "io may import shared") is enforced only for the rendered
  layer (test_layers.py, the ESLint block). Python's `value.py` imported `knobly.syntax._recovery` (fixed: it
  reads the generated `MESSAGES`), but the shared helper `_anatomy.py` (frozen-m1.md section 4 lists it as shared)
  imports `knobly.syntax`, and `include.py` imports `knobly.syntax._recovery`. Either the table is relaxed
  (shared helpers that read syntax trees sit in the syntax or written layer) or both checks enforce the whole
  table; a later milestone should pick.

## 2026-10-29, milestone 2 spec (kno-0vz, kno-9fy, kno-5ya, kno-gxu), architect

- The round 13 review (root cause 4) lists `address` among the located things that print as `path:line:col`. An
  address names a directive by its path of names, not by a file position; its to-text stays the people form of
  spec 7.4 (`graph > node "leds" > max_count`). `spec/contract.md` 2 says so.
- Root cause 3 asks for "every closed set ... with lowercase values". `token kind`'s values are the grammar's token
  names (`WORD`, `BAD_CHAR`), and the grammar is their one home: the spec keeps them as the one exception (spec
  2.10), and the generator now emits `TokenKind` from `grammar/Knobly.g4` instead of each binding typing it.
- The milestone brief says Python's `List` and `String` "clash with typing names". `List` does (`typing.List` on
  `from knobly import *`); `typing` has no `String`. The fix moves all six written value classes to
  `knobly.written` only, one rule rather than two names (spec 6.6).
- `spec/spec.md` 2.1 said a lone `"\r"` never ends a line, but TypeScript's `formatDiagnostic`
  (`ts/src/written/format.ts`) cuts the source line at `/\r\n|\n|\r/u`: a binding bug against the spec, now made
  explicit (contract 1) with the case `format-lone-cr`. Python's `split("\n")` was right.
- Spec 2.2 placed a `use` step at "the `use` line's name", which reads as the snippet name; the load expected
  outputs (`load-snippet-basic`: `use twinkle main.conf:4:9`) place it at the `use` keyword. Spec 2.2 now says
  the `use` keyword, and the contract case `format-via` follows it (`via use s at main.conf:4:1`).
- Not ruled: a values text holding a comment outside a list (`set("1 # note")`) puts the statement's `;` inside the
  comment. Noted on frozen-m2.md section 15 for its own bead.
- Committing the generator change ahead of the lanes leaves `ts/` and `py/` red on this branch (they still import
  `ValueKind.List`, the `Literal` aliases and the hand-written `TokenKind`) until both lanes land.

## 2026-10-29, milestone 2 Python lane (kno-0vz, kno-9fy, kno-5ya, kno-gxu)

- Frozen page 1.3 says `graph.variables(name?)` returns `list[Variable]` in Python. It returned a tuple before and
  every other reader returns a tuple; the lane keeps the tuple (element type now the `Variable` union, order
  unchanged), reading "list" as the element type only.
- Behaviour changes the frozen page's section 14 does not list for Python:
  - `render(object())` raised `TypeError("render takes a document graph ...")` in Python too, not only in
    TypeScript (item 21). Python drops the check as well: `render` reads only `graph.expand()` and
    `graph.root`, so a stand-in with those members renders (test `test_render_builds_on_the_graphs_public_members_only`).
  - `Unreadable.__match_args__` was the dataclass default `("reason", "origin", "written")`; the schema and page 1.6
    say `("reason",)`, so a three-positional pattern no longer matches.
  - `DiagnosticError` moved from `knobly.diagnostics` to the new `knobly.errors` (the one home of every error
    class, page 5), and `knobly.written.errors` is deleted: `from knobly.diagnostics import DiagnosticError`
    and `from knobly.written import BadTextError` (or `EditError`, `DetachedError`, `ReadError`, `SaveError`)
    no longer import. The root `knobly` exports every error class.
  - `ReadError`'s message changed (`cannot read the root file <path>: <reason>`); messages are not contract.
- Typing cost of behaviour change 14: under `mypy --strict`, `stmt.kind == "set"` is a `comparison-overlap` error
  (`Literal[StatementKind.SET]` against `Literal['set']`), though it is true at run time. Typed programs compare with
  the member (`stmt.kind is StatementKind.SET`) or match on the class. Worth a line in the docs pass.
- The memory writer's lost-update refusal raises `RuntimeError` (page 8 says "an `Error`"); `save` wraps it in
  `SaveError` with it as `__cause__`, as it does the file writer's `OSError`.

## 2026-10-29, milestone 2 TypeScript lane (kno-0vz, kno-9fy, kno-5ya, kno-gxu)

- Exported names the frozen page's section 11 does not list: the helper base types `IVariableBase` (what every
  variable variant has, beside `IStatementBase`/`IValueBase`), `IExpandedValueBase` (the readers every expanded
  variant has) and `IArgumentLinks` (page 1.5 left exporting it to the lane). They carry no behaviour; drop them in
  the docs pass if the owner prefers fewer names.
- `ts/src/syntax/tokens.test.ts` ("TokenKind names exactly the grammar's tokens") is deleted, not ported: with
  `TokenKind` a string-literal type generated from the grammar there is no run-time list to compare, and the
  generator is the guarantee. `src/types.test.ts` checks `IToken["kind"]` is `TokenKind` at compile time.
- The public-name probe could not reach a `removed` change at the branch base (016f867): the probe's top level holds
  an unreadable statement, so removing a top-level directive is `unknown` (spec 7.6). The probe now also removes a
  directive inside a block with no unreadable statement. A probe fix, not a spec change.
- Behaviour change the page's section 14 does not list for TypeScript: `ReadError`'s message is now `cannot read the
  root file <path>: <reason>` (messages are not contract). The records (`IPlace`, `IOverride`, `IStep`,
  `IDiagnostic`, `ILocatedDiagnostic`) are small class instances now, so `toEqual` against a literal still holds but
  `toStrictEqual` does not.

## 2026-10-29, milestone 2 review fixes (one fix agent)

- `spec/schema/api.json` "program code" said `^[^/]+/.+$` (whitespace allowed) while both bindings refused
  whitespace (`[^/\s]+/\S+`). The schema now holds the shipped pattern, `^[^/\s]+/\S+$` (a revisable choice), as the
  generated `PROGRAM_CODE` of both bindings' limits modules; spec 2.3 points at it.
- spec 7.4 did not say what a key rule returning something other than text or absent does (both bindings kept it in
  the address). It is now the `argument type error` (`TypeError` in both), listed on `addresses` and `diff`.
- spec 6.7 `references ()` did not say it is lexical: a use in an included file has no declaration, so a variable
  used only there has no references. The row says so now. The review asked for one glossary word for "uses" across
  the lexical and per-copy views, or a rename (`declaredReferences`): an owner call, not made.
- `spec/binding-guide.md` section 3 had no row for the written block's shape (TypeScript `.statements`, Python a
  `Sequence`); by its own rule that is a defect. A row now records it as allowed until rule 5 (proposed) is decided.
- The frozen page gives `StringArgument` the match field `("text",)`, the canonical quoted text, so
  `case StringArgument("10.0.60.30")` never matches. The review proposes a `value` field (the decoded text) as the
  first match field. Kept as frozen (the docstring and py/README now say it); changing it is an owner call.

## 2026-10-29, milestone 3 spec lane (kno-j80, kno-033)

- The round 13 review's root cause 5 gave the adapter "find a target". `spec/conformance.md` moves target finding
  into the shared driver (the adapter dumps objects with ids; the driver finds the target in the dump), so the target
  rules and the position conversion they need have one home. A design choice of milestone 3, revisable.
- `conformance/load/format.md` said the `after` load is "by the same processor". The driver loads it as a second
  `load` (a second processor); spec 7.1 lets `diff` compare any two renders, and every load case passes either way
  with both bindings. The format page now says so.
- Latent bug in the Python written runner (deleted by the milestone 3 Python lane): `name_at` and `starts_at`
  compared code-point columns with the corpus's UTF-16 columns. No case had a character above U+FFFF before a target.
  The driver converts before it compares.
- spec 2.8's check of a values text did not cover a comment the text ends in (kno-033; frozen-m2.md section 15 had
  noted it as unruled). Both bindings accepted `set("1 # note")` and wrote `port 1 # note;`; a list item's
  `replace with text` with `"3 # note"` was refused, but with E2004 at the text's end, an artifact of the check's
  probe `x [<text>];`. The spec now refuses every such text with E2001 at the comment.
- `spec/codegen.md` said "the three case formats under `conformance/`"; there were four (syntax, load, written,
  contract), and milestone 3 adds a fifth (rendered).
- "Adapter" already named the source and writer adapters (spec 4.3, contract 5) and, in binding-guide step 3, the
  wrapper around the generated parser. The review's word for the per-binding conformance program is kept as
  `conformance adapter` in the glossary; the unqualified word keeps its port meaning. An owner call if he wants
  another word.
- (2026-10-29, milestone 3 verifier) frozen-m3.md section 7 says the comment "must be found before the probe's
  syntax diagnostics are reported"; spec 2.8's table orders the check as "the text's syntax diagnostics, then E2001
  at the first token that is more than values". The two bindings took different readings, and no shared case pins
  it: for `"1\n2 # c"` (set) TypeScript gives E2001 at 1:2 (the comment), Python at 1:0 (the `2`, the first token
  after the line break); for `"1 \\ # c"` TypeScript gives E2001 at 0:4, Python the syntax diagnostic E1003 at 0:2;
  for `"[1, # c"` TypeScript E2001 at 0:4, Python E2001 at 0:7. Python follows the spec's order; TypeScript reports
  the comment ahead of earlier problems. Needs a ruling and shared cases for a comment after a line break or a
  syntax error.
- (2026-10-29, milestone 3 fix) Resolved the entry above by the spec: spec 2.8's table is the source of truth, so the
  comment comes last (TypeScript now re-parses the probe with a line break before its closer, as Python does).
  frozen-m3.md section 7's "found before the probe's syntax diagnostics are reported" was about the probe's closer
  being swallowed, not the order of report; the frozen page is left as written. New cases pin it:
  `set-comment-after-line-break`, `set-comment-after-semicolon`, `set-comment-after-syntax-error`. The override
  check in TypeScript also skipped the values-text check for a text that trims to empty (`"  \n"` got 0:0, not the
  line break at 0:2); case `set-override-blank-line-break`.
- spec 2.1 said "A Go or Rust string ... cannot hold a lone surrogate": wrong for Go (a `string` is any bytes and holds
  the WTF-8 form). It also said a UTF-8 binding "skips" the `surrogate-*` cases, while the driver and the binding
  skill have no per-case skip. 2.1 now states today's rule (no skip; a lone surrogate is 3 bytes in byte units, as
  `conformance/driver/units.py` counts it) apart from the still-pending proposal. Whether to add the skip with
  invalid-byte cases, or to make WTF-8 the requirement (which a Rust `String` binding cannot meet), is an owner call.
- spec/conformance.md 4.2 called every dump shape exact, but the driver read only some members (a syntax
  diagnostic's id, message and end, and every token line and column, were never checked). The driver now checks the
  syntax dump exactly; 4.2 says the other shapes are checked only as far as the driver reads them. 4.2 also said every
  kind is lowercase; token kinds are the grammar's capitalised names.
- ANTLR 4.13.2 has no official Rust target, so binding-guide step 3 has no stated path for Rust: an owner question.

## 2026-10-29, milestone 4 spec lane (kno-umh.1 to kno-umh.8, kno-umh.12)

- **Expected outputs were not all derived by hand** (spec 9 says they are). The changed and new syntax cases
  (`conformance/expected/`, 152 files, mostly `WORD` becoming `INTEGER` or `DIGIT_WORD` and a `SEMI` token added),
  and nine new load cases plus four written outputs, were produced by a scratch copy of the Python binding (outside
  the repo) given the new grammar and the frozen page's recovery rules (one error node per broken statement, resume
  only at `;` or a block, a stray top-level `}` ends the statement), then checked by hand case by case at the level
  of diagnostics and tree shape. The written cases of the new rules (entry rules, misuse, lost update, unread copy,
  bounds, list items) were written by hand. The six expansion-semantics load cases were also run against the
  TypeScript binding as built before this milestone (`ts/dist`): both bindings agree on every one, so writing the
  model down exposed no difference between them. Owner call: accept tool-assisted derivation for a grammar change
  this wide, or ask for an independent hand check.
- **`grammar/knobly.ebnf` duplicates the grammar** and is kept in step by hand (updated for milestone 4). The
  round 15 review called it "an unchecked second grammar file". Open question for the owner: derive it from
  `Knobly.g4`, or retire it; it is no longer the source of the value rules (`IntegerText` and `EscapeText` are
  now token rules in the .g4).
- **Spec 3.2 never said a broken statement is one `error` node**, though every syntax expected file encoded it.
  With the new grammar ANTLR leaves a partial `directive` context behind an error, so the rule had to be written
  down (spec 3.2) and each binding's tree walk must fold an unfinished directive (one with a recognition error and
  no block) into the error node.
- **A missing `;` is E2001**, not a code of its own: no code was added (right-size). It is now the most common
  syntax error; the owner may want a specific code and message ("expected ';'").
- **Two costs of the owner's Q1 pick, stated in spec 3.2 and docs/language.md:** a forgotten `;` in the middle of
  a block silently joins the next line's statement onto this one's values (`b 2` then `c 3;` is `b 2 c 3`; case
  `load-missing-semicolon`), and an unterminated string's statement runs on to the next `;`, hiding the next line
  (syntax case `unterminated`). This is nginx's behaviour; only a schema (the next milestone) can catch the first.
- **E4003 is retired, not moved**: a bad escape is now found by parse, and 4xxx is the values range, so it became
  E1005 (lexical). A literal bound that is not an integer is E2007 (bad slice); E4001 remains for a bound through a
  variable and for a literal integer beyond 2^53-1, which a grammar cannot check.
- **The fetch writer cannot send `If-Match` on the ETag of the read**: the fetch source and writer are separate
  ports with no shared state. The spec has the writer `GET` each URL first, check, then `PUT` with `If-Match` on
  that `GET`'s ETag; without an ETag a window stays open (stated in spec 4.3). Pairing the two ports (one factory
  sharing ETags) would close it; that is the review's LOW finding on hand-wired port pairs, not done here.
- **An entry rule reports one diagnostic** (its first error), where the old probe could report several syntax
  diagnostics for one bad text. Every shared case had one diagnostic, so no expected file depended on it.
- **"Every bad name" was read as every name a program passes**: a directive `rename` to a reserved word or an
  extension's name is now a misuse error too, not a `bad text error` E2001 (`rename-kind-refused` changed). A
  variable `rename` that collides with an existing `set` (E5002) stays a `bad text error`, since the document
  decides it.
- **Python `BadTextError` is no longer a `ValueError`**: `ValueError` is Python's misuse class, a program bug, and
  the error tree now keeps the two sorts apart (spec 2.8). Code that caught a refused edit with `except
  ValueError` must catch `BadTextError` or `KnoblyError`.
- **The conformance protocol reported only `knobly error`s as `thrown`** (spec/conformance.md 3); a misuse
  error was a `fault`, so no shared case could pin kno-umh.7. `thrown` now covers every spec 2.8 group, with
  `paths` for the I/O groups; the written format gains `saveTo` (a memory writer over given texts) and `diff`.
- **Before this milestone the real bindings in this checkout break on import with the new grammar** (Python:
  `grammar has no rule "lastDirective"`), so the shared driver bails out for them until each lane lands: every case
  is red, not only the new ones.

## 2026-10-29, milestone 4 Python lane

- **`conformance/written/expected/add-include-unread.json` predates kno-umh.4** and contradicts spec 6.3 and 6.10:
  after `addStatements 'include "part.conf";'` (not read yet), its `list` step expects the graph's `diagnostics`
  to be `[]` and its `render` step expects `"unreadable": []` and `"diagnostics": []`. The spec says each copy in
  `unread ()` is an `unreadable expansion` with reason `unread` and E3007 in the one diagnostics list, as the new
  case `render-unread-include` pins. The Python binding follows the spec, so this case is its one red case: it
  gives `"diagnostics": [["E3007", "main.conf:1:0"]]` in `list`, and `"unreadable": [["", "unread",
  "main.conf:1:0"]]` with the same diagnostic in `render`. The expected file needs re-deriving in the spec lane
  (outside the Python lane's owned paths).
- **An override's literal bound beyond ±(2^53-1)** (`overrides={"n": "c[99999999999999999999]"}`): the frozen
  page deletes the override check's old step 4, so the text is accepted, but spec 6.3 does not say where its E4001
  goes. The Python binding reports E4001 at each `$name` that reads the override (reason `value`), as for a bad
  bound through a variable (spec 2.4, E4001 "a bound reached through a variable"). No shared case covers it; the
  TypeScript lane should agree, or the spec should say.

## 2026-10-29, milestone 4 TypeScript lane

- **`add-include-unread` is the TypeScript binding's one red case too**, for the reason the Python lane gives: its
  expected file predates kno-umh.4. TypeScript gives the same output as Python (`"diagnostics": [["E3007",
  "main.conf:1:0"]]` in `list`; `"unreadable": [["", "unread", "main.conf:1:0"]]` and that diagnostic in `render`).
  The expected file needs re-deriving in the spec lane.
- **An override's literal bound beyond ±(2^53-1)**: TypeScript agrees with Python (E4001, reason `value`, at each
  `$name` that reads the override); the spec should say so in 6.3.
- **`slice value`, `index value` and `plain value` are `layer: shared` in `spec/schema/api.json`**, but the frozen
  page moves them into `knobly.written` for Python and moves `ts/src/value.ts` (which holds them) under
  `ts/src/written/` for TypeScript. TypeScript followed the frozen page (they are reader results of the expanded
  value, which the low level owns); the schema's layer should become `written`, or the page should keep them shared.
- **The adapter now reports a native `TypeError` and `RangeError` as `thrown`** (argument type error, index out of
  range), as spec/conformance.md 3 asks. A cost: an adapter's own JavaScript bug that throws a `TypeError` now shows
  as an argument type error, not a fault. The TypeScript adapter's own refusals (unknown op, no member) throw a
  plain `Error` so they stay faults.

## 2026-10-29, milestone 4 fix pass

- **`add-include-unread` re-derived** from spec 6.10 (kno-umh.4): `list` now expects `[["E3007","main.conf:1:0"]]`
  and `render` expects `"unreadable": [["","unread","main.conf:1:0"]]` with that diagnostic. Both bindings already
  gave it; every shared case now passes in both.
- **Contract 4.3 against spec 6.3** (order of checks): contract 4.3 said every text type check comes before
  everything else, while spec 6.3's check of an override puts the name's misuse check first. Both bindings follow
  6.3 (`setOverride("a-b", 5)` is a misuse error). Contract 4.3 now names the override check as the one exception;
  the owner may prefer the other order (swap 6.3's steps 1 and 2, and both bindings).
- **Spec 2.8 against spec 6.3** (not changed, owner call): 2.8 says every check of a text that depends only on the
  text is the grammar's, but the override check still filters `valuesText`'s tokens by hand (E2001 at a `$name`, or
  at 0:0 for a text with no value). An `overrideText` entry rule would need a second, variable-free copy of the value
  rules (value, slice, bounds, list, items) in the .g4 and the .ebnf, and would move the empty-text diagnostic from
  0:0 to the end of the text (a whitespace- or comment-only override). Options: add the rule and accept both costs,
  or reword 2.8 to admit the override's `$name` and no-value checks. Related: `set ("# c\n")` (the `valuesText` rule
  accepts a comment-only text) writes `a # c\n;`, a directive with no values; whether `set` should refuse a text with
  no value is not stated.
- **`render` given something that is not a graph**: spec 7.0 accepts any object with the graph's public members and
  names no error group otherwise; TypeScript fails with a native `TypeError`, Python with `AttributeError` (a fault
  in conformance terms). docs/rendered-tree.md claimed TypeError in both and now points at spec 7.0 instead. Owner
  call: make it an `argument type error` (both bindings check for a callable `expand`) or leave it unspecified.
- **Statements texts had no entry rule**: `replaceWithText`, `insertStatements` and `addStatements` parsed their text
  as a document, which accepts a leading byte-order mark, so `addStatements("﻿b 2;")` wrote a document with
  E1003. `statementsText : statements EOF` is added to the .g4 and the .ebnf and used for those edits; the BOM is
  refused with E2001 at 0:0 (case `add-statements-bom-refused`). A cost: such a text now reports only its first
  syntax error, as every entry rule does.
- **`check lost updates` with a `current` list not as long as the batch** is now a misuse error in both bindings
  (spec 4.2); TypeScript read missing entries as empty text.
- **New load cases' expected outputs** (`load-override-bound-too-big`, `load-var-failed-set-shows-outer`,
  `load-var-failed-set-top`, `load-var-set-reads-outer`, `load-var-set-reads-itself-top`) were taken from the
  bindings, which agree byte for byte, and checked by hand against the behaviour spec/expansion.md 4, 8 and 9 and
  spec 6.3 now state; they pin today's behaviour, not an independent derivation.

## 2026-10-29, milestone 5 spec lane (kno-umh.6, kno-umh.12 rest, kno-umh.14)

- **`..` cannot be the slice separator**, as the owner's answer allowed for: `..` is already a `WORD` (`../conf`),
  and longest match reads `1..3` as one `DIGIT_WORD`. A `DOTDOT : '..'` token makes `tools/g4overlap.py` report
  `OVERLAP WORD / DOTDOT, e.g. '..'`. The separator is `~` (`name[1~3]`), the closest clean spelling: outside the word
  alphabet and read as a range. Costs: `~` can never be a word character (`~/conf` must be quoted); a `~` outside a
  slice is now E2001 (it was `BAD_CHAR`, E1003). Owner call if he prefers another character.
- **`:` may not start a word** (`listen :80;` is E1003 at the `:`). The owner's "':' is legal in every word" was
  read as "inside every word", the old `NameChar` rule extended to digit words; widening the start set is his call.
- **Expected outputs were again tool-assisted**, as in milestone 4: every converted case (`@` statements, `~` slices)
  and the new syntax, load and written cases of A to D were produced by a scratch copy of the Python binding outside
  the repo, patched for raw single quotes, `AT_WORD` classification, E3008, the `~` separator, the slice name as a
  value and E4007, then checked by hand (positions shift by one column after each inserted `@`; canonical slices print
  `~`). The cases of E (value `set`), G2 (`set` with no value) and G3 (`render` of a non-graph) were written by hand;
  `split-value-set-twice`'s texts and render were taken from the same scratch binding running `replaceWithText`
  once, which writes the same text. Owner call, as before.
- **Most new syntax cases are red only against a binding built from the milestone 4 grammar.** Raw strings, `:` in
  words, `~`, `AT_WORD` and subscripts on variables are the grammar's alone, so both bindings pass them as soon as
  `tools/gen.sh` regenerates the parser (the Python binding at 20acec3 with a regenerated parser passes 165 of 168
  syntax cases). The three recovery cases (`var-slice-unclosed`, `at-word-touch`, `at-word-slice-unclosed`) stay red
  until each lane's classifier treats `AT_WORD` as a value and a `[` after a `VARIABLE` or `AT_WORD` as a slice
  bracket. Every new load, written and contract case is red against both bindings as they stand.
- **A value's `set` that keeps its handle must change the handle's kind** to make the owner's loop work: the README
  loop sets `max_count`'s `$pixels` (a `reference`) to `2400` (a `word`), and the second copy holds the same handle.
  Spec 6.1 therefore lets one object change kind: in TypeScript the object's `kind` changes (a narrowed variable is
  stale), in Python its class is reassigned (`__class__`, which needs the six value classes to share one slot layout;
  Python Cookbook recipe 8.19's state pattern). The alternative, a `set` that refuses a kind change, would leave the
  owner's loop raising on its first call. Owner call if he dislikes either cost.
- **`rename` lost its reserved-word check, and `make processor` gained one name check.** With `@` statements no
  directive name is reserved, so `rename("use")` and `rename("include")` now succeed (`rename-to-keyword-word`), and
  `rename("@set")` is refused by `nameText` alone (an `AT_WORD` is not a `WORD`). An extension's name must now be a
  word `nameText` takes, so `@` and the name lex as one `AT_WORD`; an extension named `x y` was accepted before and
  could never be used. This is a design call of this milestone (misuse error, spec 5).
- **An `AT_WORD` is still a value and a slice name** (`cron @daily;`, `x @a[1];`), so no text that is not a
  statement's start parses differently because of the sigil; only the statement head and `rename` changed.
- **Spec 2.8 was reworded instead of adding an `overrideText` entry rule** (milestone 4 leftover): an entry rule would
  need a second, variable-free copy of the value rules in the grammar. The grammar owns a text's shape; the
  text-alone rules (E5002, E5005, E5009 to E5011, the no-value rule, the override's no-`$name` rule) are spec rules
  run on the entry rule's tree. The milestone 4 claim "every check that depends only on the text is the grammar's"
  was not true of those rules and is gone.
- **`set` with a text that has no value must be given empty text** (milestone 4 leftover): `set("")` still clears the
  values (case `directive-set`); `"# c\n"`, `"\n"` and `"  "` are E2001 at 0:0. A whitespace-only text is refused too
  (the rule is "empty", not "no comment"); the owner may prefer to allow whitespace.
- **`render` of a non-graph is an argument type error** in both (milestone 4 leftover), checked by a callable
  `expand`; the conformance driver gains `["render", target]` in the written format, token `TypeError`.
- **Config text: what makes it.** The owner said "made only by quote() or an explicit text(...)", so no reading member
  returns `ConfigText` (a value's or statement's `text` is plain text, and copying it into an edit takes
  `text(v.text)`), except the graph's `overrides`, which return the config text the program gave. `text()` checks
  nothing; the edit checks. Bead kno-umh.6's description also names a `vl` tagged template, which the owner's answer
  does not: not built. Python's `NewType` is erased at run time, so neither binding can refuse a plain string at run
  time; only the type checker does, and no shared case can pin it.
- **`plain` has no red shared case.** No case can call a member a binding should not have, and each binding's
  public-name test checks only that the schema's names exist. The schema now has `removed in milestone 5`; the frozen
  page asks each lane to fail its build on any name listed there (the reverse check for removed names).
- **A slice's `name` is now a written value** (a word or a reference), like its bounds, so a `$src` in `$src[0~3]` is
  a reference with a declaration and resolutions. Python `match` on a written slice changes:
  `written.Slice(written.Word("leds"), ...)`, not `Slice("leds", ...)`. The expanded slice's `name` stays text. In the
  written dump the slice and its name start at the same place; the driver's `["value", path, line, col]` finds the
  slice (it is yielded first), and no case targets a slice's name.
- **The `reserved names` schema key and the `RESERVED` constant keep their names** with a new meaning (the names no
  extension may take: `set`, `snippet`, `use`); "No directive name is reserved any more" is spec 2.5. Renaming the key
  would rename a generated constant in both bindings, which per-layer naming (kno-umh.13) may revisit.
- **The extension step's `name` is the name without `@`** (`extension include at main.conf:1:2`), as a variable step's
  is without `$`; the step's place is the whole `@include` token. Design call.
- **The rasl fixtures diverge further from rasl's own files**: `@set`, `@snippet`, `@use`, `@include` and `[144~152]`
  (rasl writes `[144:152]`), commented-out lines included (fixtures/rasl/README.md says so).
- **Docs quote tests that do not exist yet in that form**: `docs/low-level-api.md` and `docs/rendered-tree.md` now
  show `text(...)` around every edit argument and the `@` spellings; the lanes must make the cited tests match, or
  report the doc wrong here. `py/README.md`'s skip-list workaround is in the Python lane's paths: it must go there.

## 2026-10-29, milestone 5 Python lane

- **Doc excerpts that no longer match a test that type-checks** (outside `py/`, so not changed here):
  `docs/rendered-tree.md` (rasl fixture excerpt) passes `overrides = {"leds_host": '"10.0.0.9"'}`, a plain str where
  `load` now takes `ConfigText`; the test has `vl.quote("10.0.0.9")`. `docs/rendered-tree.md`
  (`test_a_variable_value_has_its_set_place_and_the_variable_step`) shows `SourcePosition(12, 0, 12)`; with `@set` the
  `2284` starts at offset and column 13, and the note below it still says `set $pixels 2284;`.
  `docs/low-level-api.md` (tracer excerpt) shows `doc.replace_with_text(kept)` with `kept = doc.text`, a plain str; the
  test has `doc.replace_with_text(vl.text(kept))` (frozen page F: every call site passes `text(...)` or `quote(...)`).
- **E4007's place when a `$name` holds several values.** Frozen page C says "at the value's place via the variable when
  it has one value in a file, else at the `$name`"; the corpus (`load-var-subscript-not-word`, `y $t[0~1]` with
  `@set $t a b;`) places it at the first value (`main.conf:1:8 < variable t`). The Python binding follows the corpus
  and the existing E4001 rule for a bound (the first value's place when it is written in a file; the `$name` when there
  is no value or it is an override), through one helper for both codes.
- **A value's `set` splices the given text as given** (as `replace with text` does), so a text with a leading or
  trailing gap that `valueText` allows (`" 5 "`, `"5 # c\n"`) keeps its spaces or comment in the file. The handle is
  kept for the first value built inside the replaced range. Design call; the spec says only "replaces the value's
  range".
- **The removed-names check reads api.json's prose entries.** `removed in milestone 5` lists names in sentences
  (`"plain (the expanded value reader), plain value"`); the Python test splits each entry at commas outside
  parentheses and checks the snake_case, PascalCase and as-written spellings (`plain`, `PlainValue`, `COLON`) are not
  on the package root, `knobly.written`, `TokenKind` or an expanded value class. The other entries yield phrases
  that are vacuously absent. A list of identifiers in the schema would make the check exact.

## 2026-10-29, milestone 5 TypeScript lane

- **Doc excerpts that no longer match their cited tests (docs/ is outside this lane's paths):**
  `docs/low-level-api.md` at "changes nothing when an edit's text is refused" shows `for (const text of [...])` with
  `set.set(text(given)), given`, which does not compile (the loop variable shadows `text` and `given` is unbound); the
  test reads `for (const given of [...]) { expect(() => set.set(text(given)), given)...`. `docs/rendered-tree.md` at
  "keeps a bad line in its place..." still writes `  : x;` with E2001, but under milestone 5 a `:` cannot start a word
  (E1003); the test now writes `  ~ x;` (E2001, behaviour change 4). `docs/rendered-tree.md` at "gives E3006 when an
  extension throws..." still writes `pull;\npull x;` with `test/bad-pull` at 1:5; a WORD head is a plain directive now,
  so the test writes `@pull;\n@pull x;` (1:6). `docs/rendered-tree.md`'s rasl excerpt shows `const OVERRIDES = {
  leds_host: '"10.0.70.1"' }` and `rendered(..., options?: { overrides?: Readonly<Record<string, string>> })`, a type
  error under config text; the test and helper now read `text('"10.0.70.1"')` and `Record<string, ConfigText>` (the
  `return render(await processor.load(path, options));` line matches). The tests were made to match every other cited
  line (`quote("10.0.70.1")` in the tracer, the `unread` line in "reads an include line an edit added once").
- **TypeScript's kind change under a value's `set` uses `Object.setPrototypeOf`**, the JavaScript form of Python's
  `__class__` assignment (the state pattern the frozen page names): the six value classes keep their inner slots on the
  shared base and `kind` is each class's getter, so the same object reports the new kind and only the new kind's
  members. MDN warns that changing a prototype deoptimises that object; a value handle is not on a hot path. Design
  call inside the frozen page's "the object's `kind` and members are the new kind's".
- **`remove()` of a slice's or index's name is unspecified.** The name is now a written value, so it has `remove()`,
  which deletes the name token and leaves `[0~3]` (a list holding a `~`: a syntax error in the document, and the edit
  is not refused). Removing an index's only bound (`a[]`) had the same gap before. Spec 6.6 could refuse it (misuse
  error or `bad text error`) or say what is left; not changed in this lane.
- **Red first was not observed for TypeScript through the driver**: the binding at 50977f8 does not build against the
  new grammar (`tsc`: three `"COLON"` comparisons), as the frozen page says, so the first driver run was after the
  change (371 of 371). The binding's own new tests (removed names, config text type tests, value `set`, the natural
  rasl loop, `@` statements, render of a non-graph) were written with the change, not before it.

## 2026-10-29, milestone 5 review fixes

- **`remove()` of a slice's or index's name, or of its only bound, is now a misuse error** (spec 6.6, case
  `slice-name-and-only-bound-remove`), the text unchanged. Design call the owner may revise: the other choice was to
  remove the whole slice. The written-conformance `value` target gained an optional fifth element, `"name"`, to reach
  a slice's name (it starts where the slice does).
- **An extension name that is not text is an argument type error** at make processor (spec 5, api.json), checked
  before `nameText`, then reserved or taken, in both bindings; TypeScript now calls the one directive-name check.
- **A blank text is spaces, tabs, CR and LF only** (spec 2.8, case `value-replace-bom-refused`): TypeScript's
  `trim()` counted U+FEFF as blank, so a value's `replace with text` given a lone byte-order mark removed it.
- **E4007 now refuses a word the grammar's `sliceName` does not take** (`5`, `1.5`, `-`, `07:30`; case
  `load-var-subscript-number`): both bindings check the word with the `sliceNameText` entry rule.
- **`:` as a word's first character is still an open question for the owner.** His "yes" was to `:` in every word;
  spec 3.1 reads it as after the first character. Evidence: nginx `listen [::]:80;` lexes as three BAD_CHARs and E1003,
  and `listen ::1:80;` is E1003, so an IPv6 address starting with `::` must be quoted. Not changed.
- The nine older plants in `tools/planted/` are still copies of older grammars (some headed `@rasl/config grammar`);
  they still bite. Two milestone-5 plants were added beside them, and `tools/planted-tokens/` holds the token-check
  plants.

## 2026-10-29, milestone 6 (spec, schema, generator lane)

- **spec 2.4 and `diagnostics.json` disagreed** (round 15 finding: 8 meanings, 14 found-by entries). Resolved by
  taking the spec's wording (the newer, milestone 5 text) as each code's `meaning`, adding the schema-only facts that
  are true (E2001 also in a bad text error; E4001's literal-bound note; E4004's and E4005's range clauses), and a
  closed `found by` list: E5002, E5005, E5009 to E5011 are `low level, edit` (the spec said `low level`, the schema
  `load, edits`), E5006, E5007 and E5012 `low level` (the schema said `load`). The table in spec 2.4 and the
  user guide's table in docs/rendered-tree.md are now generated from `diagnostics.json`.
- **`diagnostic` was in the syntax layer, but `bad text error` (shared) carries it**: a layer-direction breach the
  new loader refuses. Moved to the shared layer (where TypeScript's `IDiagnostic` already lives,
  `ts/src/diagnostics.ts`).
- **Seven undefined types in api.json** (`definition`, `result`, `function`, `key rule`, `locatable`, `program code`,
  `token range`, plus `map of text` and `text or absent[]`): each is now a concept, a type parameter or a type
  expression of the closed grammar. `resolution` is generic (`resolution of snippet line`, `resolution of variable`),
  as both bindings already were.
- **`statement.parent` said `statement`**; both bindings and spec 6.5 give the statement whose block holds it, so it
  is now `written directive or extension line or snippet line or absent`.
- **`slice value`'s `start` and `end`**: TypeScript's `ISliceValue` has optional members (`start?: number`), its
  `IExpandedSlice` `number | undefined`. The generated `SliceValue` uses `number | undefined` like every absent
  member; the TypeScript lane changes `ISliceValue` (no run-time change). Found by a scratch assignability check of
  every hand-written TypeScript type against its generated interface (the other mismatches are the approved block
  shape and its cascade).
- **The two public-name tests read sections the schema no longer has** (`ts/src/api-names.test.ts` reads
  `removed in milestone 5`, `ts`, `spell`; `py/tests/test_api_names.py` the same): both fail to collect at this
  commit. Every other test passes (TypeScript 222, Python 433) and the shared driver passes all 375 cases with both
  adapters. The lanes replace both tests with the generated `PUBLIC_NAMES` comparison (frozen-m6.md).
- **"One block shape in every layer" has no syntax-layer block**: a `block` node is a node with `children`. Design
  call: the shape is given to the written block, the expansion's block and the rendered block (spec 2.11); the
  owner may want a syntax-layer view too.
- **`walk` moves from the render and the directive onto the block** (spec 7.5, 2.11). Keeping both would be two
  homes for one operation; design call recorded in frozen-m6.md "Behaviour changes".
- **TypeScript `MAX_SAFE_INTEGER` is now generated** in `limits.ts` (equal to `Number.MAX_SAFE_INTEGER`): the
  schema's `integer range` limit had a TypeScript spelling naming the language constant, the one per-language
  spelling the casing rule could not derive.

## 2026-10-29, milestone 6 (TypeScript lane)

- **The generated `LoadOptions.overrides` is a `ReadonlyMap`; spec/codegen.md section 3 says a map passed in is a
  `Readonly<Record>`** (and TypeScript has always taken `load(path, { overrides: { port: text("8080") } })`).
  `tools/api/emit_ts.py` spells an options record's map as a result's map. The spec wins: `ts/src/written/processor.ts`
  keeps a hand-written `LoadOptions` (a `Readonly<Record<string, ConfigText>>`) and `Processor`, exported under the
  generated names, and `ts/src/types.test.ts` checks every free function against its generated `<Module>Functions`
  but `knobly`. Both go when the emitter spells an options record's map as a parameter's. frozen-m6.md section 1
  ("the only mismatches are the block shape and `ISliceValue`") missed this one.
- **`Diagnostics.toArray()` is a public TypeScript member the schema and spec do not have.** Kept (behaviour
  unchanged, one test uses it); the schema should either add it or the binding drop it (`[...diagnostics]` does the
  same).
- **The kind rule refuses every `.kind` compared with a literal, internal unions included.** Three internal
  discriminated unions of the binding (`ts/src/written/bind.ts`: bound items, scope entries, read needs) used `kind`
  with values outside any generated list (`forced`, `resolve`, `read`); their discriminant is now `tag`, as
  `ts/src/syntax/walk.ts` already named its own. No public member changed.
- **The adapter loads `ERROR_GROUP_OF_CLASS` from the build** (`dist/gen/api/names.js`, as it loads the entry points)
  and names a thrown error by `error.name`; before, it tested `instanceof` most specific first. The same group for
  every class knobly throws (each sets `name`); a program's own subclass of a group's class, which no case
  throws, would now be a fault. `ts/conformance/tsconfig.json` gains `allowImportingTsExtensions` so the adapter can
  import `./shapes.ts` at run time under Node's type stripping.

## 2026-10-29, milestone 6 (Python lane)

- **The generator writes the whole field list as `__match_args__` for two snapshots.** `DirectiveExpansion` gets
  `(written, values, block, origin, unreadable)` and `UnreadableExpansion` `(reason, written, origin)`, while the
  generated `MATCH_ARGS` (and spec 2.10's one field order) say `(written, values, block)` and `(reason, written)`:
  `tools/api/emit_py.py` `record_lines` sorts the match-args fields first but never writes `match_args=False` with
  an explicit `__match_args__`. The hand classes had the short lists. Python lane: uses the generated classes as
  frozen-m6.md says, and `py/tests/test_api_names.py` marks these two `xfail(strict=True)` so the test fails once
  the generator is fixed. A `case DirectiveExpansion(w, v, b, o)` now binds where it raised before.
- **Generated records and callbacks are typed with Protocols a program cannot import.** The records' fields
  (`Origin.place`, `Copy.statement`, `DirectiveExpansion.values`, `Added.after`, `DiagnosticError.diagnostic` ...)
  and `KeyRule` name the generated Protocols, which live only in the private `knobly._api`; the public names
  (`knobly.Place`, `written.SetLine`, `rendered.Directive` ...) are the hand classes, as they must be for
  `match` and `isinstance`. So under mypy a function annotated with a public class refuses a value read from a
  record until it is narrowed (`isinstance`, `match`), and `def key(d: rendered.Directive)` is not a
  `rendered.KeyRule`. Found by the tests: `test_load.py`'s key rules and its `at(d: LocatedDiagnostic)` helper,
  `test_tracer.py`'s `line_of(place: Place)`. In the lane: `Rendered.addresses` and `diff` take a function of
  either `Directive` (a wider parameter, so the Protocol still holds); the adapter and three test helpers annotate
  with `knobly._api` types. Needs a decision above the lanes: public Protocol names, or records typed by
  the binding's classes. Not decided here.
- **Records with a people form are generated as Protocols, not dataclasses** (`place`, `override`, `step`,
  `diagnostic`, `located diagnostic`, `address`: `is_record` excludes a member with a trait). frozen-m6.md 2.B lists
  neither deleting them nor subclassing. Python lane: the hand dataclasses stay and subclass their Protocols, each
  field written `= field()` (otherwise the Protocol's property becomes the field's default; checked under 3.11 and
  3.13). No behaviour change.
- **List to tuple, not in frozen-m6.md section 3.** The schema types `read()`, `save()` and `diff()` as tuples;
  Python returned lists. Now `DocumentGraph.read()`, `DocumentGraph.save(writer)` and `Rendered.diff(after)` return
  tuples, so `graph.save(w) == ["a"]` is now false. `Rendered.diff` also raises `TypeError` for an `after` that is
  not a `Rendered` (it took the hand class; the Protocol parameter is wider), where it raised `AttributeError`.
- **Positional field order of generated records, not in section 3.** `Node` is `(start, end, kind, children)` (was
  `(kind, start, end, children)`: the generated `Node` extends `TokenRange`), `DirectiveExpansion`
  `(written, values, block, origin, unreadable)` (was `written, origin, values, block, unreadable`). Construction
  sites now pass keywords.
- **The adapter names a group from the first class in the error's `__mro__` that `ERROR_GROUP_OF_CLASS` holds**, not
  `ERROR_GROUP_OF_CLASS[type(e).__name__]` (frozen-m6.md 2.B): a builtin subclass (a `UnicodeError` is a
  `ValueError`) keeps its group, as the old `isinstance` order did. Same result for every class knobly raises.
- **Not done, for a later call:** the package's internal modules keep names without `_` (`knobly.origin`,
  `knobly.report`, `knobly.source`, `knobly.diagnostics`, `knobly.syntax.cst`,
  `knobly.written.model` ...), so a public class is still importable from a second path. frozen-m6.md does not
  ask to rename them.

## Milestone 6 review fixes (one fix agent, 2026-10-29)

- **spec/codegen.md section 10 was wrong**: a new binding was "one emitter registered in gen-api.py plus gen.sh",
  but the language set was closed in the loader (`LANGUAGES`, `ERROR_BASES`, `public()`'s per-language rules) and
  in the meta-schema and `api.json` (per-language keys). Now the loader takes a `Language` descriptor from each
  emitter and knows no language; section 10 lists the schema keys a new binding still adds. Moving the
  per-language schema data (each root error's base, factory forms, adapter modules, the argument type sentence)
  into the emitters is not done: an owner's call.
- **Behaviour change: `PROGRAM_CODE`'s whitespace.** The schema regex was `^[^/\s]+/\S+$`, which JavaScript and
  Python read differently (JS `\s` holds U+FEFF, Python's holds U+001C-U+001F). It is now the Unicode White_Space
  set written out, the same in both: TypeScript now accepts U+FEFF and refuses U+0085 in a program code; Python
  now accepts U+001C-U+001F. The loader refuses `\s \S \w \W \d \D \b \B` and `"` in any schema regex.
- **Renamed in the schema, not public:** `fetch function` is now `platform fetch` (a type name may hold no word of
  the type grammar; it is native, so no binding exports it). `collecting` is no longer a concept: Python's
  `Collecting` is the collect trait's public class (`emit_py._trait_names`). `index out of range` keeps its name and
  is simply not a type name (it holds `of`).
- **Behaviour change (widening): Python `Processor(extensions=None)` and `Diagnostics(None)`** are accepted, as the
  generated constructor Protocols say (an optional parameter is `X | None = None` in every generated signature).
- **Not done, for the owner:** schema `note`s still carry history, quotes, bead ids and other-language advice, and
  now reach Python docstrings as well as TypeScript JSDoc (the Python emitter emits member notes). Splitting each
  into a user-facing `doc` and an unemitted `rationale` (or moving history to schema-history.json) is an editorial
  pass over about 35 notes. Also not done: a typed `checks text` flag per parameter in place of the argument type
  error's `member` / `parameter` prose; the per-binding "public class" mapping for Python records (above, "Needs a
  decision above the lanes").
- The Python implementation modules are now private (`knobly._origin`, `_report`, `_source`, `_diagnostics`,
  `syntax._cst`, `syntax._parse`, `written._model`, `_value`, `_processor`, `_format`), closing the item above;
  tests/test_api_names.py fails on any non-underscore module that is not a public path.

## 2026-10-29, milestone 7 (codegen leftovers: kno-umh.16, kno-umh.17, kno-umh.18), spec and generator lane

- **The brief's "generated output must compile alongside today's hand code" cannot hold for Python with item A.**
  Making the generated types name the public classes is a type change the hand code must follow: at this commit
  `mypy` reports 39 errors in 11 Python files, all in hand code (none in generated code), and the package fails to
  import because three hand modules import the four union aliases the generator no longer writes (`Statement`,
  `WrittenValue`, `Variable`, `ExpandedValue` from `knobly._api.written`). frozen-m7.md section A lists each
  change the Python lane makes. TypeScript's generated output changed only in doc comments: `pnpm test` (232),
  `typecheck`, `lint`, `build` and the shared driver (L3) pass unchanged.
- **spec/codegen.md section 10 said moving the per-language data into the emitters "is not done: it would put facts
  the owner reads (which base each group has) in code".** kno-umh.17 does it; the facts stay readable in the generated
  tables of spec 2.8 and contract 4.2, which now read them from the emitters. Section 10 is rewritten.
- **History removed from emitted text outside the notes.** The doc check covers every text an emitter writes, so
  three code meanings (E1005, E3008, E4007: "(milestone 5)"), two constants' `means` (`RESERVED`: "Milestone 5: no
  directive name is reserved any more"; `PROGRAM_CODE`: "so JavaScript and Python agree") and the argument type
  error's `raised when` ("milestone 5") lost their history clauses. No meaning changed; spec 2.4's and 2.5's
  generated text changed with them.
- **`fetch writer options`' note called it "the browser writer's options"**; the schema's name is `fetch writer`.
  Its doc now says "the fetch writer's options". The adapter module names in the schema are now what each module
  holds (`files`, `fetch`, `include`); TypeScript maps them to `node`, `browser`, `include` and Python to `files` and
  `include`, so no import path changed.
- **`Diagnostics.toArray()` (TypeScript only, in no schema or spec): dropped, not added.** The iterate trait already
  gives `[...diagnostics]` and `Array.from(diagnostics)`, and Python's idiom is `list(diagnostics)`; a schema member
  would give Python a `to_array()` no Python reader expects. The TypeScript lane deletes it (`ts/src/report.ts`) and
  its one use (`ts/src/rendered/report.test.ts`).
- **The generated files' header quoted the owner** ("Never committed (owner, 2026-10-23)"), in every generated module
  docstring. It now reads "do not edit, and never commit"; the quote stays in `tools/gen-api.py` and spec/codegen.md.

## 2026-10-29, milestone 7 (Python lane)

- **frozen-m7.md section A's list misses `py/tests/test_layers.py`.** With item A, the generated
  `knobly._api.rendered` imports `knobly.rendered` under `TYPE_CHECKING` (its annotations name
  `knobly.rendered.Directive`, `Rendered`, ...), and the layer check (spec 5, "Layer direction") governed every
  module outside `knobly.rendered`, `_api/` included, so it failed for that one module. The rendered layer's
  generated declarations are the rendered layer's own: the check now treats `knobly.rendered` and
  `knobly._api.rendered` as the layer, so a lower module importing either still fails (none does). The page's
  list came from `mypy`; `pytest` could not run at the spec lane's commit (the package failed to import).
- **"The shared driver must pass every case before" could not hold for Python**: at 0477392 the package fails to
  import (milestone 7 spec lane erratum above), so the driver ran only after this lane. After: 380 of 380, L3 holds.
- **`grep -rn "knobly._api" py/tests` is not empty, by design:** `tests/test_layers.py` names the modules
  `knobly._api.kinds` and `knobly._api.rendered` as strings (the layer check's coverage and the layer's
  extent), not imports. No test, adapter or doc imports `knobly._api`.
- **Milestone 6's `own()` helper (`written/_model.py`) went with the workarounds:** it narrowed a generated record's
  `Copy.statement` (typed with the `_api` Protocol union) to the binding's classes; the field is now typed
  `knobly.written.Statement`, so its three call sites read the field directly.

## 2026-10-30, milestone 7 (review fixes)

- **spec/codegen.md section 10 listed too few touch points for a new binding.** A binding also had to edit
  `emit_docs.py` (hard-coded TypeScript and Python columns), keep its own layer list, a native-type table outside
  its `Language`, and possibly the loader's JavaScript-and-Python regex rule. The code now makes the section true
  (columns from the languages, layers from `api.json`, `Language.native`, I-Regexp patterns) and the section names
  every touch point, the hand-written name test included.
- **spec/codegen.md section 3 promised parameter, kind list and error group docs that no emitter wrote** (the loader
  dropped parameter docs). Both emitters now write them (`@param` / `Args:`, the group's and list's doc), with each
  member's `errors` (`@throws` / `Raises:`) and `order`.
- **The glossary's generated io table said Python has `WalkControl` (`StrEnum`)**: the table ignored the Python
  emitter's `omit` for kind lists. It now reads "none".
- **frozen-m7.md differs from spec/ after the review** (spec wins): TypeScript's `names.ts` is gone
  (`PUBLIC_NAMES` in the generated `ts/test/api-contract.ts`, `ERROR_GROUP_OF_CLASS` in `ts/conformance/shapes.ts`);
  `protocol.json`'s `note` / `params note` are `doc` / `params doc` with a `rationale`; `api.json` has `registry
  layer` and `adapter layer`; the key rule's type is `function of directive to (text or absent)`; schema patterns
  are I-Regexps (the program code pattern holds its characters as JSON escapes); `tests/test_api_names.py` no longer
  lists the `<Module>Functions` / `<Class>Constructor` assignments (the generated contract holds them).

## 2026-10-30, schema docs (kno-umh.19)

- **spec/schema/api.json's `errors` lists missed two misuse errors the spec states.** `check lost updates` raises a
  misuse error when `current` is not as long as `files` (spec 4.2; both bindings do), and a written value's `remove`
  refuses a slice's or index's name or only bound with one (spec 6.6). Both lists now name `misuse error`; `errors`
  feeds only the generated `@throws` / `Raises:` docs, so no behaviour changes.
- **The brief called spec/codegen.md section 11 a "deferred list"**: it is "Costs". The deferred item (most schema
  entries undocumented, hand docstrings repeating schema docs) was one of its bullets; it is replaced by the costs of
  the new rule (section 3, "The schema's doc is the one home of each public doc").
- **frozen-m7.md differs from spec/ after this change** (spec wins): Python's `<Module>Functions` and
  `<Class>Constructor` Protocols moved from `py/tests/api_contract.py` into the layer modules of `knobly._api`
  (as TypeScript's are in `gen/api/`), and `_api/docs.py` is new; TypeScript's public functions and `Diagnostics`
  are constants typed by their generated signatures.
- **spec/spec.md 2.8's misuse error row (generated from the schema's `raised when`) left out two cases the spec
  states elsewhere**: a `current` list in check lost updates not as long as its files (4.2), and removing a slice's or
  index's name or only bound (6.6). The group's text now lists both. The two renames (`set variable`, `parameter`)
  promised a misuse error and `save` a lost update error their `errors` lists left out; the lists now name them, and
  the loader refuses a member doc naming an error group its `errors` neither list nor return.
- **Error groups' `raised when` texts and the schema's other user docs cited spec sections** ("(spec 2.8)"), which a
  binding's user cannot follow from a doc comment; the docs drop the citations, so the generated tables in spec/spec.md
  (2.5 reserved names, 2.8 error groups) lose them too.
- **spec/conformance.md 6 calls the driver "standard library only (as `tools/gen-api.py`)"** (kno-umh.20): the
  driver still is, and so is `tools/gen-api.py`'s own Python, but generating a binding now also runs its pinned
  formatter (Prettier from `ts/node_modules`, ruff through `uv`), the one exception spec/codegen.md sections 4 and 11
  record. The comparison in spec/conformance.md is left as written (not an owned path); it reads true of imports
  only.

## 2026-10-30, C++ binding milestone 1 skeleton (.claude/design/cpp/frozen-m1.md)

- **C++ 1. Two error groups had no `message`, so a binding that makes them its own classes could not load.**
  `argument type error` and `index out of range` carried no `message` in spec/schema/api.json because TypeScript and
  Python both map them to built-in classes (`TypeError`, `RangeError`, `IndexError`); the loader requires `message`
  for any group some binding makes a class of, and C++ makes both (`knobly::argument_type_error`,
  `knobly::index_out_of_range`, design.md 2.2). Both now say `"message": {"given": true}`. TypeScript, Python and
  docs output are byte-identical with and without it (rendered both schemas and compared).
- **C++ 2. spec/codegen.md section 10 says a new binding needs no loader edit, but the loader spells type names in
  PascalCase.** `Model.public` uses `pascal(c.name)` and tools/gen-api.py's `check_layers` looks for `"Widget"`, so a
  binding whose types are snake_case (C++, design.md 1.2) fails both. Lane A adds a `type_case` hook (frozen-m1.md
  4.1), beside design finding F2's `member_spelling`; section 10 should then name the hooks.
- **C++ 3. `Formatter.suffix` held one suffix**; C++ formats `.hpp` and `.cpp`. It now takes one suffix or a tuple
  (`str.endswith` takes either); TypeScript and Python unchanged.
- **C++ 4. spec/README.md and spec/binding-guide.md step 3 name ANTLR as the only way to get a parser** (design finding
  F18). Slice T rewrites both to name knobly's own generator as the second route.

## 2026-10-30, C++ binding milestone 1, Lane A (the C++ API emitter)

- **A1. Two loader hooks beyond frozen-m1.md 4.1's four.** `constant_case` (C++ spells a limit `max_nesting`;
  `Model.public` and the glossary spelled every constant UPPER_SNAKE) and `kinds_in_package` (frozen 3.2 puts
  `token_kind` and `node_kind` in `::knobly`, the one `kinds.hpp` the generated parser includes, while
  `Model.public` put each kind list in its layer's namespace). Both default to what TypeScript and Python spell; their
  generated code is byte-identical. `emit_docs.py` now spells types and constants through `type_case`,
  `constant_case` and `pattern_form` (the C++ column needs it). spec/codegen.md section 10 names all five hooks.
- **A2. Lane A's owned paths leave out `docs/rendered-tree.md`**, which `tools/gen-api.py docs` also rewrites (the
  error codes table, one column per binding); `--check` fails until it has the C++ column, so Lane A commits it with
  the other generated tables.
- **A3. Templates have no home for their definitions in compiled mode.** frozen 4.3 sends every hand definition to
  `detail/<layer>/definitions.hpp`, which a public header includes only in header-only mode. The template members
  (`diagnostics::collect`, `diagnostics::report`, each union's `as<V>()` and `visit(f)`) and the class template
  `written::resolution<Definition>` cannot be compiled once: slice 2 needs a header every mode includes (say
  `detail/<layer>/templates.hpp`) or explicit instantiation with `extern template` (design.md 2.5, point 2).
- **A4. The skeleton's compile check builds every `tests/generated/*.cpp` under `-Werror`**, but a contract for a
  layer with no definitions yet odr-uses inline functions that are declared and never defined. The generated
  contract turns off clang's `-Wundefined-inline` before its include (a missing definition is the linker's to report,
  which is the contract's point); GCC's equivalent warning ("used but never defined") has no flag, so on the gcc leg
  Slice T should compile and link only the contracts of implemented layers (M1: `api_contract_syntax.cpp`).
- **A5. The skeleton's compile check stays red until Slice T defines three M1 items** the generated code uses inline:
  `detail::decode_utf8` (every pattern matcher, so `program_code`'s compile-time check), `to_string(const
  diagnostic&)` (`bad_text_error`'s message) and `sequence<T>::iterator` (`diagnostics::begin()` in the shared
  contract). Lane A proved the build green with stand-ins for exactly those three, defined by a test overlay outside
  the repo.
- **A6. The contract takes each address, it does not call each free function** (frozen 4.2 says "calls each free
  function through a volatile function pointer"): a call needs an argument of every type, which the generator cannot
  make in general. Each hand-defined function, member, constructor, `operator==` and `to_string` is wrapped in a
  lambda stored in a volatile function pointer, which odr-uses it, so a missing definition still fails to link.
- **A7. A record union is a view class, not a record written whole** (frozen 4.3 says records are generated whole;
  design.md 1.3 lists `change` with the view-class unions). A `sequence<change>` returns `change` by value, which
  would slice an `added` held by a class hierarchy of plain records; so `change` and its variants hold one
  `detail::view` and their members are the hand code's.
- **A8. `memory_source` takes `std::shared_ptr<const ordered_map<std::string, std::string>>`** (design.md 3.1), not
  the map by value (design.md 1.3's table): its schema doc says it reads the map it is given at each call, and a
  copy-on-write map copied by value would never see a memory writer's change. The rule the emitter applies: a map a
  free function takes is shared.
- **A9. `errors.hpp` and `knobly.hpp` include each other.** The error classes hold shared records
  (`diagnostic_error` holds a `located_diagnostic`), so `knobly.hpp` forward-declares the error classes, declares
  its records, then includes `errors.hpp` at its end (frozen 4.2 lists it among the includes); `errors.hpp` entered
  first includes `knobly.hpp`, which includes it back. Every header compiles alone.
- **A10. A union's or extended class's view constructor is protected**, not private (frozen 4.3): each variant (and
  `reference_resolution`, which extends `resolution<variable>`) constructs its base from the view. The view itself
  stays private, read through `detail::access`.
- **A11. The layer check is per header, and `knobly.hpp` holds the shared and io layers together**, so a syntax
  header that used an io name would pass `layers_syntax.cpp`. A header is allowed when it holds any layer the
  header's layers may import; every adapter module's header is forbidden to every other header.
- **A12. The loader's doc check could not catch "C++"**: it searched `\bC\+\+\b`, and no word boundary follows `+`.
  It now matches a language's name not inside a word, which is the same test for TypeScript and Python.

## 2026-10-30, C++ binding milestone 1, Slice T (the tracer)

- **T1. The CI compilers are pinned to a major version from the runner image, not to an exact apt version**
  (frozen-m1.md 5.4 says "GCC 13 (apt, pinned version)", "Clang 18 (apt, pinned version)"). Ubuntu keeps only the
  newest build of a package in `-updates`; pinning the release-pocket build would downgrade the image's runtime
  libraries (`libgcc`, `libstdc++`) that `g++-13` and `clang-18` depend on. The legs run the image's `g++-13` and
  `clang++-18` and print the full version; AppleClang is pinned through `DEVELOPER_DIR` (Xcode 16.4).
- **T2. The shared driver's position check is quadratic in `byte` units** (`conformance/driver/syntax.py`,
  `native_position`, not an owned path): it rescans the text for every position, so the case `list-5000` alone
  takes about 40 s and the C++ L0 run about a minute per CI leg; the C++ adapter answers all 168 cases in about a
  second under ASan and UBSan. A fix (one pass building an offset table per case) belongs to the driver's owner.
- **T3. `sequence::at` cannot name `index_out_of_range`**: `errors.hpp` includes `support/sequence.hpp`, so the
  error class is incomplete where the template is defined. `detail/raise.hpp` declares
  `raise_index_out_of_range(index, size)` (`KNOBLY_API`), defined with the shared layer; `ordered_map::at` and
  `block::at` (slice 2) use the same helper.
- **T4. Only the contract of an implemented layer is built** (Lane A's A4): GCC reports "inline function used but
  never defined" as an error under `-Werror`, with no flag to silence it, so `api_contract_knobly.cpp` and the
  other layers' contracts are not compiled in milestone 1. `api_contract_syntax.cpp` is linked and run by `ctest`.
  The shared layer's contract joins when the io functions, `diagnostics` and the other people forms are defined.
- **T5. No MSVC leg** (frozen-m1.md 5.4 allows leaving it out): on `windows-2022` the checkout itself fails, "invalid
  path 'conformance/expected/nul.json'", because `NUL` is a reserved device name on Windows. Passing there would
  need the syntax case `nul` renamed (its expected file with it) or a sparse checkout in the leg, which is special
  casing; the case's name is the conformance corpus's to change, not Slice T's.

## 2026-10-30, C++ binding milestone 2 freeze (.claude/design/cpp/frozen-m2.md)

- **M2-1. The milestone 2 ask ("L1 and L2 as spec/conformance.md defines them") needs the rendered layer.** L2 is the
  load, rendered and contract corpora, which `render`, `diff` and `read`; design.md section 7 puts render in slice 3
  and says slice 2 proves "the `load` ... cases", which render. Milestone 2 takes in the rendered layer and, since the
  include extension is in its scope, claims level 3 (frozen-m2.md choice 1).
- **M2-2. `program_code(std::string_view)` was declared `KNOBLY_API` but missing from the generated contract** (the
  named type had no `Hand`): a missing definition would not have failed to link. The emitter now records it.
- **M2-3. The block shape had no way to reach its layer** (support/block.hpp declared members over a bare view):
  frozen-m2.md 3.1 adds `detail::block_traits<Item>`, specialized per item type in `detail/<layer>/templates.hpp`.
- **M2-4. design.md 2.4's `file_source` join (`lexically_normal()`) and spec 4.3's memory source join (POSIX rules) were
  two rules**; milestone 2 resolves both through `detail::io::join` (frozen-m2.md choice 7). A trailing `/` and
  Windows paths are where they would differ.

## 2026-10-30, C++ binding milestone 2, slice F

- **F1. spec/conformance.md section 3 (transport) does not say a stalled adapter is a fault.** The driver now waits at
  most 60 s per request (`KNOBLY_DRIVER_TIMEOUT` overrides it, bead kno-p5x, frozen-m2.md 5 and choice 9), then
  kills the adapter, fails the case with "timed out after N s waiting for <op>" and restarts it for the next case, as
  for any fault. Section 3's fault list ("If it exits early, or writes a line that is not a response") should name the
  timeout too; spec/ is not slice F's to change, so this is a follow-up.

## 2026-10-30, C++ binding milestone 2, Slice W (the written layer)

- **W1. frozen-m2.md 3.3 rules 6 and 7 disagree**: rule 6 has `load` and `save` catch the ports' `std::exception`s,
  rule 7 allows a `try` only in `detail/raise.hpp` and `collect`. The catching lives in `detail/raise.hpp`:
  `catch_exception(f)`, `when_caught<E>(error, read)`, `message_of`, `rethrow` and `raise_nested` (the
  `std::throw_with_nested` behind `read_error` and `save_error`), each with its `-fno-exceptions` branch.
  `tests/compile/no_exceptions.cpp` now compiles the written layer too.
- **W2. The syntax layer has no entry mode** (spec 2.8: an entry rule's statement is the whole text,
  `ts/src/syntax/recovery.ts` `statementStart`): its `report` hook classifies an error from the token where it
  happens when no directive is open, so `set("[1 # note")` gave E2001 where spec 2.4's rules give E2004 (the L1 case
  `set-comment-after-syntax-error`). `detail/written/entry.hpp` (`parse_entry`, built on the generated parser and its
  public hooks, since `detail/syntax/` is not slice W's) re-classifies the first error of a non-statements entry rule
  from token 0. Follow-up for the syntax layer's owner: `parse_entry` with an entry mode there.
- **W3. `block<Item, Directive>` needs a constructor from a view** (frozen-m2.md 3.1 lists none): `expansion_block` is
  the class template itself, so `access::make<expansion_block>(view)` needs `block(detail::view)`; it is protected,
  beside a protected default constructor that `written_block`'s generated constructor uses.
- **W4. `detail::view`'s members are defined inline in `support/view.hpp`** (frozen-m2.md 3.1 allows it), and
  `detail/shared/view.hpp` is gone: once `block` and `walk_view` hold views, `tests/compile/support.cpp` (support
  headers only) odr-uses the destructor through `std::optional<view>`, and `-Wundefined-inline` fails it.
- **W5. Floating-point `std::from_chars` is deleted for macOS 13.3** (the AppleClang leg's deployment target):
  `number_of` reads with `std::strtod`, handing the text's `.` over as the current C locale's decimal point.

## 2026-10-30, C++ binding milestone 2, Slice R (the rendered layer, level 3)

- **R1. The contract corpus had no `"byte"` expectations** for its two astral cases, `position-astral-print` and
  `format-astral-before`, though `conformance/contract/format.md` names the `"byte"` key and spec/contract.md 1 lets a
  binding count bytes. A byte binding failed both with "no expectation for the unit byte", so frozen-m2.md's "all 380
  cases pass" could not hold. Following the spec's intent (contract 2: one column, one space and one caret per unit),
  slice R added the byte expectations to `conformance/contract/cases.json`, a path outside its list: `main.conf:1:10`,
  and `main.conf:1:10: E5001: {message}` with nine spaces before the carets (`x "` is 3 bytes, the emoji 4, `" ` 2).
  TypeScript and Python read their own unit's key, so their results do not change (their contract corpora ran green).
- **R2. `render` of something that is not a graph cannot be written in C++** (design.md finding F1): `render` takes a
  `const written::document_graph&`, so the compiler refuses the call. The adapter answers the `render` request for a
  non-graph id with the `argument type error` itself, standing in for that refusal; `render` raises
  `argument_type_error` for the one graph a C++ program can pass that has no callable `expand`, a moved-from handle.
  The spec's "given anything without a callable expand" needs the `needs` token F1 proposes for statically typed
  bindings.
- **R3. A key rule's "returns anything but text or absent" (spec 7.4) is a compile-time refusal in C++**: `key_rule` is
  `std::function<std::optional<std::string>(const directive&)>`, so `addresses` and `diff` never raise that
  `argument_type_error`. Same follow-up as R2.

## 2026-10-30, C++ binding milestone 3, Slice P (format tests, programs 4.1 and 4.3, compile-fail tests)

- **P1. `9bad=1` is not a bad override name** (frozen-m3.md 4 and the slice brief: "`9bad=1` (the usage line, exit
  2)"). spec.md's `VARIABLE_NAME` is `^[A-Za-z0-9_]+$` (grammar `VARIABLE : '$' [A-Za-z0-9_]+`), so a leading digit
  is allowed: `is_variable_name("9bad")` is true, program 4.1 loads with an override nobody reads and prints the two
  sinks (exit 1), not the usage line. Following the spec, the `programs_sinks` usage run passes `bad-name=1` (a `-` is
  outside the pattern), which prints `usage: sinks name=value...` and exits 2. No code changed.
- **P2. design.md 4.3's prose builds `vl::located_diagnostic(code, message, field.place())` with three arguments**;
  the generated record constructor takes four (`via` too, no default), so the call as written does not compile. The
  `report_written_statement` compile-fail control passes `{}` for `via`. Whether records get defaulted trailing
  fields is a generator question for every binding's record constructors (follow-up), not changed here.

## 2026-10-30, C++ binding milestone 3, Slice D (generated per-language documentation tables)

- **D1. frozen-m3.md 3.3's row shape could not spell every hand table, so it grew** (additions only; spec/codegen.md
  section 6 documents the result): a row may carry `receiver` (`graph.read()`), `names` (README's entry points list
  their exports after the path) and a list `ref` (`kind`, `name` in one row); a bare `ref` naming two things
  (`include` is a module and a free function; `rendered`, `syntax` are layers and concepts) fails, and `layer: X` /
  `module: X` pick one. `Language` gained `property_form` (C++ reads a property through an accessor, `root()`) and
  `call_params` (each binding's optional and options parameters) beside 3.3's `trait_forms`.
- **D2. section 3's trait table had rows 3.3 has no ref for** (factory, native, module, what a binding leaves out, a
  trait's own names, the root error classes, the argument type sentence): `trait: factory|native|module|omit|names|
  error roots|argument type message` are computed from the facts each `Language` already holds, instead of hand cells;
  `trait_forms` also covers the typed fields the table lists (`io`, `passed: keyword|option`, `brand`, `template`,
  `list`, `map`), which the loader requires beside every trait the schema uses.
- **D3. C++'s `trait_names` puts a description where `Model.public` expects `type`, `value` or `both`**
  (`emit_cpp.LANGUAGE.trait_names`: "the list type form"; Python gives `value`). Not changed (it would change C++'s
  generated contract, which P builds against); follow-up for the emitter's owner.

## 2026-10-30, C++ binding review fixes (PR 8, overnight)

- **F1. design.md 1.3 promises `std::hash` for every view class and text equality for `expanded_value` (spec 2.9:
  "a language with an equality operator ... MUST make it compare the texts"); the C++ code had neither** (identity
  `==` on `expanded_value`, no hash anywhere). Fixed: api.json's `expanded value` gained `"equal by": "text"` (a new
  concept key in api.schema.json, read only by emit_cpp today; Python's `__eq__`/`__hash__` stay hand-written), and
  emit_cpp emits `==` and `std::hash` for every view class from it.
- **F2. design.md 2.3 names three handle states (live, detached, gone with its graph) but a moved-from view was a
  fourth, null one** that crashed on any member, `kind()` included. Choice made overnight (the finding's first
  option): a view's move copies (one atomic increment), so no handle is ever null. Render's "an empty document
  graph" argument type error for a moved-from graph is gone with it (frozen-m3.md R2's moved-from case).
- **F3. design.md 2.3 does not state that a graph keeps every node it ever made** (detached ones until the graph
  dies; about 20 KB per whole-document replace of a 50-line file). Stated in cpp/README.md ("Memory"); design 2.3
  should say it too. Freeing detached nodes when their last view goes is a follow-up.
- **F4. cpp/README.md said "An edit that throws changes nothing"; that held only for refusals.** An edit cut short by
  `std::bad_alloc` part way through re-building the handle tree leaves a half-built tree (a probe that failed each
  allocation in turn then saw `expand()` raise `unordered_map::at`). Choice made overnight (the finding's second
  option): the graph's version is bumped before the change, and the README now says a refused edit changes nothing
  and a graph an allocation failure cut short should be dropped. A real strong guarantee (build the new handle tree
  aside, then commit) is a follow-up.
- **F5. spec 4.2 does not say how a file writer replaces a file**, and the bindings differ: Python stages with
  `mkstemp` (mode 0600) and renames, TypeScript writes in place (0666 less the umask). C++ now replaces a symbolic
  link's target (the link stays) and gives the staged file the old file's permissions. The rule belongs in spec 4.2
  for all three bindings (follow-up).

## 2026-10-30, user guide samples, slice py-samples (PR 8, overnight)

- **G1. Python's E3007 message leaves out the extension's name, so `include_read` cannot print
  `examples/expected/include_read.txt` in Python.** TypeScript (`ts/src/written/bind.ts`, `unread`) and C++
  (`detail/written/bind.hpp`, `fail(unread_copy, directive)`) pass the extension directive as the message detail:
  `main.conf:2:1: E3007: extension copy not read yet: include`. Python (`py/src/knobly/written/_bind.py`,
  `_unread`) calls `_problem(DiagnosticCode.UNREAD_COPY, text, name.span, via)` without it and prints
  `main.conf:2:1: E3007: extension copy not read yet`. The message is for people (spec: it may differ), so the
  sample table is not wrong; the fix that matches the other two is passing the extension's directive as `detail`
  in Python's `_unread` (not in py-samples' owned paths). `py/examples/include_read.py` is written and kept on
  branch `wip/py-samples` until then; the other sixteen Python samples print their expected files.

## 2026-10-30, packaging, slice packaging (PR 8, overnight)

- **P1. frozen-docs.md section 6, packaging step 5: the grep `find_package\|cmake --install\|KNOBLY_INSTALL`
  cannot find nothing.** `cpp/CMakeLists.txt` keeps `find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)`
  inside `if(KNOBLY_BUILD_TESTS)`: the conformance test runs the shared driver under Python. It is a test-only
  tool, off in every consumer route, not knobly's own package. Followed the intent: no `find_package(knobly`,
  no `cmake --install`, no `KNOBLY_INSTALL` remain outside `.claude/design/` and `.beads/`; the one hit left is
  that Python line.

## 2026-10-30, user guide pages, slice pages (PR 8, overnight)

- **W1. frozen-docs.md section 6, pages step 4 cannot pass while G1 stands: the hook requires the Python tab of
  `include_read`, and `py/examples/include_read.py` is not on the branch** (kept on `wip/py-samples`, errata G1). By
  design the build fails (`SnippetMissingError` for the page's include, and the hook names the file). Checked: with
  G1's fix (Python's `_unread` in `py/src/knobly/written/_bind.py` passing `name.text[1:]` as the `detail`, as
  TypeScript and C++ do) and the wip file, all 18 Python samples pass and `mkdocs build --strict` passes. Neither is
  in the pages slice's owned paths, so the pages work is on `wip/pages` until they land.
- **W2. frozen-docs.md section 6, pages step 5: the grep `low-level-api.md\|rendered-tree.md\|docs/language.md`
  cannot find nothing outside `.claude/design/` and `.beads/`.** `design/RECORD.md` (the grammar's design record, not
  in the slice's owned paths) still links the three deleted pages at lines 128-129 and 168 (live links, now broken
  on GitHub) and names them as history at 82-83; `.claude/errata.md`'s own history entries name them too. Followed
  the intent: every other file now points at the guide. Pointing RECORD.md's three links at the guide is a
  follow-up.

## 2026-10-30, guide landing (PR 8, overnight)

- **G1 and W1 resolved.** Python's `_unread` now passes the extension's name as E3007's detail (test
  `test_an_unread_copys_message_names_its_extension`); `py/examples/include_read.py` and the pages commit are on
  `feat/cpp-binding`, all 18 Python samples print their expected files and `mkdocs build --strict` passes. The shared
  corpus cannot pin the message: `conformance/format.md` says the message is not part of the contract, so the three
  bindings agree on it by their own tests and the guide's sample, not by a conformance case. W2 (RECORD.md's links)
  stays a follow-up.

## 2026-10-30, corpus cases for codes no shared case gave (kno-bzv.4)

- **C1. E3004 and E3006 cannot be reached through the shared corpus; the bead's acceptance asks for both.** The
  protocol's `load` (spec/schema/protocol.json, spec/conformance.md 4.1) offers only a `memory source` over `files`
  and `extensions` of `[]` or `["include"]`. A memory source never fails a `resolve` (it returns the keys it holds,
  spec 4.3) and `read` is only called on a path `resolve` returned, so E3004 has no input; the include extension
  throws only a `diagnostic error` (E3005), so E3006 has none either. Both need new protocol surface: for example a
  `load` option naming paths whose `resolve` or `read` the adapter's source fails (or returns a non-list), and a test
  extension (`["include", "throwing"]`) whose `specs` throws a plain error or returns a bare text. That changes the
  protocol schema, the generated message types and all three adapters, so it is a design choice, not made here.
  The other codes (E5003 E5005 E5007 E5008 E5010 E5011) and the empty glob's E3001 are in
  `conformance/written/diagnostics.json`, and all three bindings pass them.

## 2026-10-30, nesting limits (kno-bzv.6), applied

- **N1. Applied: skipped brackets do not count toward the 100-level limit.** Owner, 2026-10-30, asked whether
  brackets that error recovery skips should count: "that sounds right". Recorded in spec 2.5 ("In one text (E2010)").
  The bindings already counted this way since 3d759bc (the guard on the parser's own block and list rules).
- **N2. Applied: a limit after expansion, MAX_EXPANDED_NESTING = 256, code E5013.** Owner, 2026-10-30, of a limit of
  100 after expansion: "100 seems too low. can we increase it?"; asked which limit: "after expansion"; real configs
  "likely a few dozen, but i want the headroom". 256 is a revisable choice, not his number; MAX_NESTING stays 100.
  Spec 2.4 (E5013), 2.5 ("After expansion (E5013)"), spec/schema/api.json and diagnostics.json. Placed at the name
  of the statement whose block or values would sit deeper, the statement unreadable with reason expansion, checked
  once its values are expanded and before its other checks.
- **N3. Applied: the nesting level definition** (proposed to the owner 2026-10-30, not objected to; the current rule,
  revisable): each block and each list a value sits inside is one level, blocks and lists counted together,
  `[[1,2],[3,4]]` is 2 levels, a slice's brackets are no level. Spec 2.5 ("Nesting levels").
- **N4. Spec 2.5 did not say what parse returns at E2010**, though `py/src/knobly/syntax/_parse.py` and
  `cpp/include/knobly/detail/syntax/definitions.hpp` cited "spec 2.5" for it. Spec 2.5 now says it (a document over
  every token holding one error node over every token, one E2010 on the bracket that opens level 101; an entry rule:
  a document with no children and that E2010), and 2.8's list of an entry rule's codes now names E2010.
- **N5. `.claude/design/cpp/design.md` said the nesting guard "runs before parsing"**; since 3d759bc it counts in the
  parser's `open_node` hook. Corrected there.

## 2026-10-30, nesting review round (kno-bzv.6), applied

- **N6. N1's wording read the wrong way round.** He answered the proposal that skipped brackets not count ("that
  sounds right"), not a question whether they should count. Spec 2.5 now says so. That answer is recorded in the notes of
  kno-qa3 and kno-bzv.6 (kno-bzv.6 also holds the after-expansion quotes, cited in 2.5).
- **N7. Spec 2.5 named only the checks after E5013.** It now also names those before it: the line's shape (E5009 to
  E5011), E5002, E5003 and the codes its values give while they expand; an extension block's `@set` lines come after
  the extension line's own E5013. The bindings already agreed; `diag-expanded-nesting-*` pin the order against the checks before and after,
  but no case yet pins an extension line's E5013 before its block's `@set` E5013 (a swapped-order mutant survived).
- **N8. Spec 3.2 did not say which code the end of the text gives inside a block, or how many E2003.** It now
  states what all three bindings and the corpus (`nest-skipped-list`, `nest-recovered-100`) already do: an open `[`
  gives E2004, else an open block E2003, else E2001; E2003 once, however many blocks are open; none after a
  statement whose error node runs to the end. E2001's and E2003's meanings in diagnostics.json say the same.
- **W2 applied.** `design/RECORD.md`'s three links to the deleted pages (and its error-codes link) now point at the
  guide: `docs/site/pages/language.md`, `editing.md`, `walking.md` and `diagnostics.md#error-codes`. Its history
  lines (82-83) still name the old pages as history.
- **C1 is tracked in `kno-bzv.5`** (protocol surface to reach E3004 and E3006): the design choice stays open there.
- **F5 (spec 4.2, how a file writer replaces a file) is tracked in `kno-epi`:** which binding's behaviour
  becomes the rule is a choice for the owner, not made here.
- **N9. Stale lists.** `spec/codegen.md`'s `limits.ts` row now names `MAX_EXPANDED_NESTING`; RECORD's 5xxx band is
  E5001-E5013 and its owner-answers table holds the three 2026-10-30 nesting rows (two answers, one proposal); spec
  9's load and written rows name 2.5 after expansion.
## 2026-10-30, an edit past MAX_NESTING (kno-bzv.8), applied
- **D1. Applied: an edit that would nest a document past MAX_NESTING is refused.** Owner, 2026-10-30, to the
  recommendation that it be refused as a bad text error with the document left unchanged: "Yes". Before, TS, Python
  and C++ (probed: the same) all accepted such an insert, replace or set inside a deep block and wiped the whole
  tree with no error. Spec 2.8 ("An edit that would nest the document past `MAX_NESTING`") and a pointer in 2.5; the
  check is one function beside the text-alone rules in each binding's splice (`nestingProblem`, `_nesting_problem`,
  `nesting_problem`). Cases `nest-edit-*` in the written corpus.
- **D2. Revisable choice: the code and place.** 2.8 did not say which code; E2010 (the code an entry rule already
  gives for nesting in the given text alone) is used, one diagnostic, at the `{` or `[` of the given text that would
  open level 101 of the document, or at 0:0 when that bracket is not in the given text (as 2.8 places a text-alone
  rule's fault that lies outside the given text). Checked after the entry rule and before the text-alone rules.
- **D3. Revisable choice: a document already past the limit.** The rule is "refused when the document after the edit
  nests past the limit", not "when the edit raises its nesting": so on a document loaded past the limit (one
  unreadable line) an insert is refused (E2010 at 0:0) and only an edit that brings it back within the limit (the
  line's `remove`, or the document's `replace with text`, which is never refused) succeeds. Case
  `nest-edit-already-deep`. The other reading would accept edits whose result is still a wiped tree.
