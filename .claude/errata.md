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
