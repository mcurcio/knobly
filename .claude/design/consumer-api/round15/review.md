## Knobly PR 5: critical review

### 1. Bottom line

Five reviewers looked at the language, the domain model, TypeScript, Python, and DRY plus code generation. All five failed it. The most important finding: **the language can silently misread what an author wrote.** A statement wrapped across two lines becomes two statements, an included file's variables collide with the file that includes it, and one `--set` override rewrites every variable of that name at any depth. None of these gives an error. The second problem: the libraries in each language (the *bindings*) give types only to what the spec lists as data. So three states the spec only describes in prose reach programs as a bare string, a plain error, or nothing at all: config text versus an ordinary string, a save that would overwrite someone else's edit, and an include not yet read. The third problem: the API schema (`api.json`) is a list of names, not a typed description. Code generation produces 449 lines while each binding hand-writes about 6,000. Fix the language model and the layer split first, then make the schema typed and generate from it. Generating now would freeze 22 value types that should not all exist.

The core is sound: the grammar is proven free of ambiguity, the syntax tree keeps every character of the text, and a broken line never hides its neighbours. I re-ran every finding I lead with against the checkout, and each one reproduced.

### 2. Summary

| Area | Problem | How bad | Direction |
|---|---|---|---|
| Language concepts | A line break or `;` both end a statement, and a directive's name can be a number, so a wrapped line silently becomes two directives | serious | One statement ending (Q1) |
| Language concepts | Included files leak their `set` lines to the includer; an override beats every `set` of its name at any depth | serious | One scoping model in the spec; overrides only for declared names (Q2) |
| TypeScript, Python | Config text and a program string are the same type, so a forgotten `quote()` changes meaning | serious | A separate type for config text |
| Domain model | A render with an include not yet read drops its directives; `diff` calls them removed | serious | Show them as unreadable, reason `unread` |
| Domain model | A lost update (the file changed since it was read) has no error type; the browser writer never checks for one | serious | A `lost update error` group |
| Python | A port typed `Sequence[str]` accepts one string and splits it into letters | noticeable | `tuple[str, ...]` plus a runtime refusal |
| Python | Editing through a render fails on a file included twice | noticeable | A value edit that keeps its handle |
| Domain model | The rendered layer copies the low level's expansion; one value has 22 types across three families | noticeable (binding authors) | One owner of expansion |
| Domain model | The error classes contradict their own rule; one bad name raises two different error groups | noticeable | Rebuild them on the spec's two sorts of error |
| Language concepts | Rules that depend only on the text are hand-written in each binding and have already drifted | latent | Move them into the grammar |
| DRY and codegen | The schema has free-text types; three copies of the API are tied together only by a runtime test | internal | A typed schema; generate the declarations (Q3) |
| DRY and codegen | Three copies of the diagnostic table disagree; Python enums let misspelled strings through | latent | Generate the tables; compare enum members, enforced by a lint |

### 3. Root causes

**A. The language's meaning has no single home beyond the grammar.** The grammar covers syntax. The scoping and precedence rules (which `set` a name refers to, who wins) live only in a user guide, `docs/language.md`, as lists of examples. Rules that depend only on the text (checking an edit's values text, string escapes, keywords) live in each binding's code. *Why the structure admits this:* each feature (snippets, include blocks, overrides, one `set` per block) brought its own rule and conformance cases, but there was no model to check new rules against. The result is five precedence orders nobody chose as a whole, and two scoping rules for two ways of reusing text. A snippet looks names up where it is written (*lexical scope*); an included file looks them up where it is included. *The fix:* a normative "Expansion semantics" section in `spec/`, on the pattern of CUE's "Declarations and scopes". It defines one lexical model in which an included file is its own scope, plus one precedence table. Every rule that depends only on the text moves into the grammar as entry rules, so each generated parser enforces it. *Why this makes the class impossible:* a rule then has exactly two possible homes. The generated parser carries the text rules and the spec carries the meaning rules, so no binding can hold a private copy that drifts.

**B. The schema is a list of names, not a typed interface description.** Types in `api.json` are free text ("place or override"), and about seven type names are never defined. The 31 per-language `spell` notes are prose that three tools parse with regular expressions. States the spec describes only in prose (config text, lost update, unread include) have no schema type at all. *Why the structure admits this:* nothing can be generated from free text, so each binding re-declares all 73 concepts by hand, and a 450-line runtime probe (plus 219 lines in Python) checks names in one direction only. *The fix:* a small closed type grammar, a meta-schema that rejects unresolved types, typed per-language traits instead of `spell`, spellings derived from the casing rule, and named types for the prose-only states. *Why this makes the class impossible:* each class implements a generated interface, so the compiler catches a drifted or missing member, and an undefined state cannot pass the schema check.

**C. The layers were drawn to satisfy import rules, not the domain.** The extension port sits in an "io" layer, although the spec requires it to be pure. That pushed a handle-free "expanded value" family into "shared", and then a third family on top. Meanwhile the low level's `expand()` already builds the whole tree, and `render` re-copies it in 46 lines (`ts/src/rendered/render.ts`). *What follows from it:* 22 value types, a hand-kept list of "render-only" codes that hides `E5001` from low-level programs, and the same link named `statement` in one family and `written` in another. *The fix:* the low level owns expansion and the extension port, and the rendered tree builds on the expansion's nodes, adding only parent, walk, address and diff. Prior art: LibCST and Roslyn attach derived facts to one tree; HOCON does the same work with two layers. *Why this makes the class impossible:* with one tree and one diagnostics list, no second place decides what a layer reports.

### 4. By area

#### 4.1 Language concepts
- `grammar/Knobly.g4:14` (`separator : ';' | NEWLINE`) with `:29` (words may start with a digit): `ranges 0.0627⏎ 0.922;` renders as `ranges 0.0627` plus a directive named `0.922`, with no diagnostic.
- `docs/language.md:197-203`: a file containing `set $port 80;` included twice in one block gives E5002. This breaks your requirement (2026-10-25) that "each instance of the file would have its own bindings".
- `spec/spec.md:625-628`: the override `{name: x}` turns both per-place `node leds` and `node porch` into `node x`, silently.
- `Knobly.g4:30-31`: the two quote styles behave identically, so `'C:\temp\new'` reads as a tab and a newline.

Good: the grammar is proven unambiguous (Bison `%expect 0`, plus a check that no two token kinds overlap), the tree keeps every character of the text, and quoting always means text.

#### 4.2 Domain model across layers
- `ts/src/written/graph.ts:25-30` and `py/.../_graph.py:23`: a hand-kept set of codes filters the graph's diagnostics, so `x $nope;` shows no problem at the low level.
- `spec/schema/api.json` error groups: `DetachedError` (a program bug) sits under `KnoblyError`, although contract 4.1 says program bugs must not.
- `spec.md:490-509`: the spec names the lost update but gives it no error. `ts/src/browser.ts:47` sends the save with no check that the file is unchanged.

Good: the direction between layers is enforced by a lint with a planted-violation test, and operations exist only on the variants where they can succeed.

#### 4.3 TypeScript
- `written/model.ts` edits take `text: string`: `server.set("my host")` writes two values, and `setOverride("dir", "/my dir")` gives two words.
- `rendered/render.ts:19`: before `read()`, the render's diff says `removed b`; after the read it shows nothing.
- `ts/src/include.ts:7-11`: the built-in include extension uses unexported internals, so a third-party extension cannot report a located error on its directive.
- `index.ts`: 114 names in one namespace, 76 of them with an `I` prefix, which contradicts binding-guide rule 1 (adopted).

Good: kinds are checked string unions, so a typo is TS2367, a missing switch case is caught, and user code needed zero casts under the strictest flags.

#### 4.4 Python
- `extension.py:33` (`-> Sequence[str]`): returning `"dark.conf"` resolves `d`, `a`, `r`… one letter at a time; `mypy --strict` stays silent and the error names `include`.
- `README.md:66-77`: the natural edit loop over a render raises `DetachedError` on the second copy of a file included twice.
- `errors.py:59-69`: `str(BadTextError)` prints only `bad text: E2001`, and its diagnostics show a `;` the user never typed.
- `value.py:46-75`: spec 2.9 says two values are the same when their texts match, but Python's `==` compares object identity.

Good: `mypy --strict` passes, kinds narrow in `match`, and rasl's task ran correctly on the first try.

#### 4.5 DRY, enumerations, codegen
- Generated output is 449 lines; hand-written code is about 6,000 lines per binding. `spec/codegen.md:115` limits generation to lists and data records.
- `spec.md` 2.4 and `diagnostics.json` disagree on 8 of 32 meanings and 14 of 32 "found by" entries; `docs/rendered-tree.md` is a third copy.
- `py/.../_shape.py:92` and `_bind.py:548-555`: keywords are dispatched by raw string in two places. `k == "sett"` against a StrEnum (Python's string enumeration) passes `mypy --strict`.
- The casing rule is written seven times in five files, and the copies already differ.

On enumerations: you asked (2026-10-29) for "proper enumerations instead of hardcoded strings". TypeScript's string unions are already checked by the compiler. Python's enums are the weak spot, because a misspelled bare string still type-checks. Spec 2.10 currently forbids TypeScript constant objects. I recommend generating an `as const` object (a typed constant object, not a TS `enum`) with its type derived from it, so both `StatementKind.Set` and `"set"` are checked. This reverses 2.10, so it is listed as a step for your OK. Cost: two legal spellings in TypeScript unless a lint picks one.

Good: generated files are never committed, `--check` proves itself against planted broken copies, and there is one shared conformance driver.

### 5. Proposed codegen target

**The schema holds** (JSON, in the shape of the Language Server Protocol's `metaModel.json`): concepts with their nature, layer, typed members and errors; a closed type grammar; kind lists; error groups with their sort and each language's base class; diagnostics with message templates, reason and owning layer; limits, patterns and value-text tables; typed per-language traits (display, length, iterate, options style, generator).

**Generated per language:** enums, a names module, interfaces (TypeScript) and Protocols (Python's structural interfaces), complete data records, the error class tree, typed diagnostic constructors (so a call can never pass the wrong reason), kind-to-class tables, an exported rules module (name pattern, reserved words, limits), the docs tables, and the conformance data shapes.

**Hand-written:** the algorithms (binding, expansion, render, diff), the parser glue, the I/O adapters and their sync or async style, the module layout, and docs prose with examples. That keeps your 2026-10-26 point that generated shapes are "not conducive to building natural APIs that are idiomatic in each target language" unless idiom is expressed per language.

**Prior art:** the LSP metaModel feeds both `vscode-languageserver-types` and `lsprotocol`; TypeScript's `diagnosticMessages.json`; Babel's `@babel/types`; Smithy traits; test262's tagging of each test with its spec section, for the algorithms.

**Cost:** each of the 231 members is retyped once, plus about 300-500 lines of emitter per language. It must wait for causes A and C, or it freezes types that should be deleted. In exchange, 93 hand-written TypeScript interfaces and most of the 669 lines of name tests go away.

### 6. Questions

### Q1 How should a statement end? (section 4.1)
### Q2 Which variables may an override reach, and what does an included file see? (section 4.1)
### Q3 Should the schema become the source of every public signature? (section 5)

### 7. Next steps (in order)

1. Decide the statement ending (Q1) and apply it to the grammar.
2. Write the expansion-semantics section of the spec (Q2).
3. Move the rules that depend only on the text into the grammar.
4. Show an unread include as unreadable `unread`.
5. Add the lost update error, with one shared check in every writer.
6. Give config text its own type in both bindings.
7. Rebuild the error classes on the two sorts.
8. Make the low level the one owner of expansion and the extension port.
9. Make the schema typed.
10. Generate the declarations, errors, diagnostics and tables.
11. Generated enumerations and a no-raw-string lint.
12. Python correctness fixes.
13. Per-layer namespaces.
14. Smaller language fixes (raw single quotes, `plain`, the slice `:`, reserved words).