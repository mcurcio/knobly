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
