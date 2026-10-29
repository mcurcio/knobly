## 2026-10-28, milestone 1 spec (vil-fy4), architect

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

## 2026-10-28, milestone 1 generator and public-name check (vil-fy4 part 2), build tooling

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
- frozen-m1.md section 6 says to keep ruff checking the generated `py/src/villanelle/_api/`. Ruff
  skips git-ignored files by default (`ruff check src/villanelle/_api` prints "No Python files
  found"), so once the folder is ignored, `ruff check` and `ruff format --check` never see it
  (mypy does). The generator's output passes both with `--no-respect-gitignore`; keeping it
  checked in CI needs a pyproject change (Python lane).

## 2026-10-28, milestone 1 Python lane (vil-094)

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
  layer (test_layers.py, the ESLint block). Python's `value.py` imported `villanelle.syntax._recovery` (fixed: it
  reads the generated `MESSAGES`), but the shared helper `_anatomy.py` (frozen-m1.md section 4 lists it as shared)
  imports `villanelle.syntax`, and `include.py` imports `villanelle.syntax._recovery`. Either the table is relaxed
  (shared helpers that read syntax trees sit in the syntax or written layer) or both checks enforce the whole
  table; a later milestone should pick.

## 2026-10-29, milestone 2 spec (vil-0vz, vil-9fy, vil-5ya, vil-gxu), architect

- The round 13 review (root cause 4) lists `address` among the located things that print as `path:line:col`. An
  address names a directive by its path of names, not by a file position; its to-text stays the people form of
  spec 7.4 (`graph > node "leds" > max_count`). `spec/contract.md` 2 says so.
- Root cause 3 asks for "every closed set ... with lowercase values". `token kind`'s values are the grammar's token
  names (`WORD`, `BAD_CHAR`), and the grammar is their one home: the spec keeps them as the one exception (spec
  2.10), and the generator now emits `TokenKind` from `grammar/Villanelle.g4` instead of each binding typing it.
- The milestone brief says Python's `List` and `String` "clash with typing names". `List` does (`typing.List` on
  `from villanelle import *`); `typing` has no `String`. The fix moves all six written value classes to
  `villanelle.written` only, one rule rather than two names (spec 6.6).
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

## 2026-10-29, milestone 2 Python lane (vil-0vz, vil-9fy, vil-5ya, vil-gxu)

- Frozen page 1.3 says `graph.variables(name?)` returns `list[Variable]` in Python. It returned a tuple before and
  every other reader returns a tuple; the lane keeps the tuple (element type now the `Variable` union, order
  unchanged), reading "list" as the element type only.
- Behaviour changes the frozen page's section 14 does not list for Python:
  - `render(object())` raised `TypeError("render takes a document graph ...")` in Python too, not only in
    TypeScript (item 21). Python drops the check as well: `render` reads only `graph.expand()` and
    `graph.root`, so a stand-in with those members renders (test `test_render_builds_on_the_graphs_public_members_only`).
  - `Unreadable.__match_args__` was the dataclass default `("reason", "origin", "written")`; the schema and page 1.6
    say `("reason",)`, so a three-positional pattern no longer matches.
  - `DiagnosticError` moved from `villanelle.diagnostics` to the new `villanelle.errors` (the one home of every error
    class, page 5), and `villanelle.written.errors` is deleted: `from villanelle.diagnostics import DiagnosticError`
    and `from villanelle.written import BadTextError` (or `EditError`, `DetachedError`, `ReadError`, `SaveError`)
    no longer import. The root `villanelle` exports every error class.
  - `ReadError`'s message changed (`cannot read the root file <path>: <reason>`); messages are not contract.
- Typing cost of behaviour change 14: under `mypy --strict`, `stmt.kind == "set"` is a `comparison-overlap` error
  (`Literal[StatementKind.SET]` against `Literal['set']`), though it is true at run time. Typed programs compare with
  the member (`stmt.kind is StatementKind.SET`) or match on the class. Worth a line in the docs pass.
- The memory writer's lost-update refusal raises `RuntimeError` (page 8 says "an `Error`"); `save` wraps it in
  `SaveError` with it as `__cause__`, as it does the file writer's `OSError`.

## 2026-10-29, milestone 2 TypeScript lane (vil-0vz, vil-9fy, vil-5ya, vil-gxu)

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

## 2026-10-29, milestone 3 spec lane (vil-j80, vil-033)

- The round 13 review's root cause 5 gave the adapter "find a target". `spec/conformance.md` moves target finding
  into the shared driver (the adapter dumps objects with ids; the driver finds the target in the dump), so the target
  rules and the position conversion they need have one home. A design choice of milestone 3, revisable.
- `conformance/load/format.md` said the `after` load is "by the same processor". The driver loads it as a second
  `load` (a second processor); spec 7.1 lets `diff` compare any two renders, and every load case passes either way
  with both bindings. The format page now says so.
- Latent bug in the Python written runner (deleted by the milestone 3 Python lane): `name_at` and `starts_at`
  compared code-point columns with the corpus's UTF-16 columns. No case had a character above U+FFFF before a target.
  The driver converts before it compares.
- spec 2.8's check of a values text did not cover a comment the text ends in (vil-033; frozen-m2.md section 15 had
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

## 2026-10-29, milestone 4 spec lane (vil-umh.1 to vil-umh.8, vil-umh.12)

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
- **`grammar/villanelle.ebnf` duplicates the grammar** and is kept in step by hand (updated for milestone 4). The
  round 15 review called it "an unchecked second grammar file". Open question for the owner: derive it from
  `Villanelle.g4`, or retire it; it is no longer the source of the value rules (`IntegerText` and `EscapeText` are
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
  ValueError` must catch `BadTextError` or `VillanelleError`.
- **The conformance protocol reported only `villanelle error`s as `thrown`** (spec/conformance.md 3); a misuse
  error was a `fault`, so no shared case could pin vil-umh.7. `thrown` now covers every spec 2.8 group, with
  `paths` for the I/O groups; the written format gains `saveTo` (a memory writer over given texts) and `diff`.
- **Before this milestone the real bindings in this checkout break on import with the new grammar** (Python:
  `grammar has no rule "lastDirective"`), so the shared driver bails out for them until each lane lands: every case
  is red, not only the new ones.

## 2026-10-29, milestone 4 Python lane

- **`conformance/written/expected/add-include-unread.json` predates vil-umh.4** and contradicts spec 6.3 and 6.10:
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
  expected file predates vil-umh.4. TypeScript gives the same output as Python (`"diagnostics": [["E3007",
  "main.conf:1:0"]]` in `list`; `"unreadable": [["", "unread", "main.conf:1:0"]]` and that diagnostic in `render`).
  The expected file needs re-deriving in the spec lane.
- **An override's literal bound beyond ±(2^53-1)**: TypeScript agrees with Python (E4001, reason `value`, at each
  `$name` that reads the override); the spec should say so in 6.3.
- **`slice value`, `index value` and `plain value` are `layer: shared` in `spec/schema/api.json`**, but the frozen
  page moves them into `villanelle.written` for Python and moves `ts/src/value.ts` (which holds them) under
  `ts/src/written/` for TypeScript. TypeScript followed the frozen page (they are reader results of the expanded
  value, which the low level owns); the schema's layer should become `written`, or the page should keep them shared.
- **The adapter now reports a native `TypeError` and `RangeError` as `thrown`** (argument type error, index out of
  range), as spec/conformance.md 3 asks. A cost: an adapter's own JavaScript bug that throws a `TypeError` now shows
  as an argument type error, not a fault. The TypeScript adapter's own refusals (unknown op, no member) throw a
  plain `Error` so they stay faults.

## 2026-10-29, milestone 4 fix pass

- **`add-include-unread` re-derived** from spec 6.10 (vil-umh.4): `list` now expects `[["E3007","main.conf:1:0"]]`
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

## 2026-10-29, milestone 5 spec lane (vil-umh.6, vil-umh.12 rest, vil-umh.14)

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
  nothing; the edit checks. Bead vil-umh.6's description also names a `vl` tagged template, which the owner's answer
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
  would rename a generated constant in both bindings, which per-layer naming (vil-umh.13) may revisit.
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
  on the package root, `villanelle.written`, `TokenKind` or an expanded value class. The other entries yield phrases
  that are vacuously absent. A list of identifiers in the schema would make the check exact.
