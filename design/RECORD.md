# Config grammar: design record (system layer)

The answer page holds the full discussion:
https://claude.ai/artifact/H64AiZ7yuHTkzod9WauPLf (rounds 1 and 2). This file is the short
durable record. Every choice below is current and can be revised.

## Requirements

| # | Requirement | Source |
|---|---|---|
| R1 | "I want a formal language spec, but I don't care if it's EBNF. I'm ok with some other/better spec variant" (refines 2026-10-21: "I think we need a formal EBNF that describes the language so that we can prove its sound") | owner, 2026-10-22 |
| R1b | "I'm still hopeful we can build on some existing parser generator or code generator so that we can simplify the cross-language support." | owner, 2026-10-22 |
| R2 | Sound = "Both": (a) the grammar is unambiguous, checked by a tool; (b) the parser accepts exactly the grammar's language | owner, 2026-10-21 |
| R3 | "An EBNF gives a language independent syntax. And then parsers can be written against it, and then finally language-specific idiomatic sugar APIs can be layered on top" | owner, 2026-10-21 |
| R4 | "the TS *config* is canonical. The python version of the full runtime is still more comprehensive" | owner, 2026-10-21 |
| R5 | Slices `[n:m]`, `[n:]` and `[:m]`; `[:]` is rejected with a located error | `kno-9ze.1` |
| R6 | "A is ideal if we don't sacrifice the CST. Otherwise, C." (the condition on choosing ANTLR4) | owner, 2026-10-22 |

## Owner answers

| Question | Answer | Recorded in |
|---|---|---|
| Comments, and `:` in words | B: `#` only, where a token starts. A word that starts with a digit or `-` cannot contain `:` | `kno-m8w.1` |
| Values touching | A: values are separated by a space or comment; a slice touches its word; punctuation may touch | `kno-9ze` |
| Which tool | A: ANTLR4, provided the CST is kept. The check below says it is | `kno-k2e` |
| What a slice bound may be (2026-10-23) | "Integers only (Recommended)": `valueOf` gives integer start and end; any other bound is a located error with its own code (E4001) | `kno-9ze.3` |
| Is `foo[1]` a slice form (2026-10-23) | "Yes, add it now", and "Its own kind: index (Recommended)": `valueOf` gives `{kind: 'index', name, index}` | `kno-9ze.2` |
| Depth limit and bad lines (2026-10-23) | "Yes to both (Recommended)": nesting deeper than 100 is its own error (E2010); a bad line becomes one error node and later siblings are kept | `kno-bzv.3` |
| Licence (2026-10-23) | "MIT (Recommended)" | `kno-m8w.4` |
| Real rasl configs in the corpus (2026-10-23) | "Neutral here, real ones to rasl (Recommended)" | `kno-m8w.5` |
| Generated parser code (2026-10-23) | "Don't commit the generated code, just the source": every build and test regenerates it | `kno-g7n.2` |
| Releases (2026-10-23) | "Key from semantic-release and conventional commit on every PR merge"; "GitHub Release assets only"; "Dry-run until I enable it" (the repository variable `RELEASE_ENABLED`) | `kno-g7n.3` |
| Skipped brackets and the 100-level limit (2026-10-30) | Answer, to the proposal that brackets error recovery skips not count: "that sounds right" | spec 2.5; errata N1, N6; kno-qa3, kno-bzv.6 |
| A limit after expansion (2026-10-30) | Answer: "100 seems too low. can we increase it?"; asked which limit: "after expansion"; real configs "likely a few dozen, but i want the headroom". 256 (`MAX_EXPANDED_NESTING`, E5013) is a revisable choice, not his number | `kno-bzv.6` |
| What one nesting level is (2026-10-30) | Proposal, not objected to (the current rule, revisable): each block and each list a value sits inside is one level; a slice's brackets are none | spec 2.5; errata N3 |
| An edit past `MAX_NESTING` (2026-10-30) | Answer, to the recommendation that such an edit be refused as a bad text error with the document unchanged: "Yes". E2010, its place and the already-past rule are revisable choices (errata D2, D3) | spec 2.8; `kno-bzv.8` |
| An `@include` glob that matches no file (2026-10-30) | Asked to choose among (1) error E3001, as today, (2) a new warning code, (3) no diagnostic (nginx): "2". His pick is about globs, so a plain path that matches no file stays E3001. Replaces "Every code is an error. There are no warning codes." | spec 2.3, 4.1; `kno-bzv.2` |
| The warning's code (2026-10-30) | Asked about code W3005 "include matched nothing": "Yes". Revisable choice, not his: C++'s `diagnostic_code` value for a warning is its number plus 10000 (W3005 is 13005; errata W2) | spec 2.4; `kno-bzv.2` |
| Warnings in the diagnostics list (2026-10-30) | Asked whether warnings sit in the same diagnostics list as errors, each diagnostic with a severity field (error \| warning): "Yes". Revisable choices, not his: `severity` is derived from the code's letter, so no constructor takes it; a program's own code is always an error (errata W1 d, e) | spec 2.3; `kno-bzv.2` |
| What a warning does (2026-10-30) | Asked what a warning does: "Nothing. Just a diagnostic, not thrown/raised like errors are. They have to be intentionally fetched". The reading stated to him: every API that throws or raises because of diagnostics ignores warnings; a program sees a warning only by reading the list. Revisable choices, not his: an empty glob does not stop its line (resolution goes on to the next spec and the line's later checks); a later error on the same line keeps W3005 before it; the core applies the glob rule to the spec's text, whatever the source (errata W1 a to c) | spec 2.3, 4.1; `kno-bzv.2` |
| A warning an extension throws (2026-10-31) | Asked what happens when an extension throws a diagnostic whose code is a warning, offered a. E3006 "extension failed" (the line unreadable) or b. record the warning and keep the line readable: "A". Revisable choice, not his: the code's letter decides, not the severity a thrown object claims | spec 2.4, 5; `kno-bzv.2` |

## Owner answers the low-level API rests on (since 2026-10-24)

The consumer API design (gate bead `kno-9vn`) ran from 2026-10-24 to 2026-10-28. The full working record is
`.claude/design/consumer-api/requirements.md` on the build branch; the answers are verbatim in `kno-9vn`. These are
the ones the low-level API, built on branch `feat/consumer-api-low-level`, rests on. A pick among offered options is
a current choice and can be revised; the others are requirements.

| Date | Answer (his words) | What it decided | Kind |
|---|---|---|---|
| 2026-10-24 | "All five" | the five epics (`kno-9ze`, `kno-stq`, `kno-xlo`, `kno-bgz`, `kno-bzv`) are one surface | requirement |
| 2026-10-24 | "Both, idiomatic in each language" | TypeScript and Python each get the API in their own idiom | requirement |
| 2026-10-25 | "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be optional extensions rather than core." | no third-party libraries in the core (amended 2026-10-28: "third party libraries are ok for things like reflect-metadata") | requirement |
| 2026-10-25 | "I think it's a first-party plugin/extension. And any configuration knobs that "includes" may require could be set when the plugin is instantiated and passed into the config tool." | include is an extension a program turns on (`include()`), not part of the core | requirement |
| 2026-10-25 | picked "Allowed, per place"; note: "Obviously the file only needs to be read once, and any core syntax errors can be communicated once." | a file included at two places is read once, its syntax errors reported once, each place read on its own | pick, with a requirement in the note |
| 2026-10-25 | "if we allow variables to passed into the included file, then each instance of the file would have its own bindings." | an include line's block of `set` lines gives that place its own values | requirement |
| 2026-10-26 | picked C: "Focus on the core, low level API and high level sugar APIs. The extensions can come later as additional sugar." | no pydantic, zod or JSON Schema integrations in this work | pick |
| 2026-10-27 | picked A, "The EBNF's rules win (recommended)" | values follow the EBNF: no leading zeros, only six string escapes (`\q` is now E4003) | pick |
| 2026-10-27 | "Within villanelle I want the spec to win over a reference language" | the spec is canonical in knobly; R4's "TS config is canonical" was about rasl ("talking about the rasl codebase, not villanelle") | requirement |
| 2026-10-27 | "Value type directives can have multiple values. Not just “port 8080” but also “port 8080 443 dev tls”" | a directive takes any number of values of mixed kinds | requirement |
| 2026-10-27 | "B is the target." | variables, snippets with arguments, and a directive reading its own block are in scope | requirement |
| 2026-10-27 | "Nothing is locked until I see user APIs that I like." | the grammar may change; designs lead with user code | requirement |
| 2026-10-27 | "I like the direction of this, especially the addition of the variables and snippets. Those were on my wishlist" | variables and snippets kept | steer |
| 2026-10-28 | picked "whole" (recommended) | a variable is only ever a whole value, never joined to other text | pick |
| 2026-10-28 | "I approve of the language features and design. Should we move forward with the low-level API for now and defer the high-level sugar API for later?", then "Yes" to the plan | build the low-level API now (syntax tree and directive layer); the high-level API (`kno-xlo`) is deferred; done means rasl's `family_room.conf` and `hyperhdr.conf` load through it in both languages | requirement; the plan's details were the main session's, which he accepted |

## Round 12: the low level as written (2026-10-28)

After PR 3 merged, the owner said its directive layer was the middle layer, not the low level. Round 12 designed
and built the real low level (gate page v12; working record `.claude/design/consumer-api/round12/` and
`.claude/design/consumer-api/requirements.md` on branch `feat/low-level-layer`; epic `kno-e4x`).

| Date | Answer (his words) | What it decided | Kind |
|---|---|---|---|
| 2026-10-28 | "a rendered config tree is not something that we currently have. that seems like a medium layer between the low-level API (AST level?) and the high-level (idiomatic integrations)." | PR 3's tree is the middle layer, named the rendered tree | requirement |
| 2026-10-28 | "consumers need to be able to see which files were included in a config load, what variables exist, and where they were overloaded. consumers should be able to manipulate/alter that data so that it can be written back to the source files" | the low level is the files as written: documents, variables, resolutions, edits and save | requirement |
| 2026-10-28 | "It depends if the integration program changes the `$pixels` variable itself, or if it instead changes `max_count` to no longer use the variable. both kinds of changes should be possible" | both edits, from a rendered value's `resolutions` | requirement |
| 2026-10-24 | "How will includes be round-tripped through modifications to an included subtree?" | an edit lands in the included file's own document; `save` writes that file | his question, answered by the design |
| 2026-10-28 | one `set` per name per block: "this seems alright" | E5002 stays | requirement |
| 2026-10-28 | names: picked A; note: "i like this layered approach, because it allows consumers to build on top of any of the APIs" | `load` returns the files as written; `render(graph)` builds the rendered tree (`ILoaded` became `IRendered`) | pick |
| 2026-10-28 | copies: picked A; note: "the API _could_ provide helpers to do other operations like \"disconnect\" the variable or to \"inline\" the include, for example" | an edit lands on the written line and every place that reads it changes; the helpers are a proposal (`kno-chn`), not built | pick |
| 2026-10-28 | values: picked A | new values are written as knobly text, with `quote()` | pick |
| 2026-10-28 | "if the low-level API doesnt know about directives, then why is it trying to key them?" (relayed by the run brief) | the key rule left the processor: `rendered.addresses({ key })` and `diff(before, after, { key })` | requirement |
| 2026-10-28 | "If any questions come up, make a decision and move on." | the build's own choices are recorded one line each in `decisions.md` | instruction |

The current choices of round 12, by id in `.claude/design/consumer-api/round12/decisions.md` (each revisable):

- **Layers and names:** `load` returns the document graph, `render` the rendered tree (O1); the key rule and
  addresses moved to `addresses()` and `diff` (D1, D4, D5, D6); directory names stay, the low level is
  `written/` (D21); the new reference took `docs/low-level-api.md` and PR 3's page moved to
  `docs/rendered-tree.md` (D22).
- **What is stored:** only the texts, the handed-in values and which files were read; everything else is worked
  out when asked (D12); `read(graph)` keeps a failure and does not retry it (D12, D26).
- **Edits:** a refused edit changes nothing and throws `BadTextError` located in the given text (D16, D17, D30);
  new text takes the file's own indentation and line breaks (D14); a statement owns the comments above it and on
  its line (D15, D31, D-S1-4).
- **Handles:** one object per written thing; a handle whose tokens are gone throws `DetachedError` (D20); one
  variable per handed-in name for the graph's life (D28); `rename` keeps its handle (D-S2-6, D-S3-2).
- **Save:** one batch to the program's writer, nothing when nothing changed (D18, D19); the filesystem writer
  refuses a lost update and stages before renaming (D18, D-S2-5, D-S3-8).
- **Resolutions:** `resolutions[0]` is the `$name` on the value's own line (D7); orders follow rendering (D29).
- **Both languages:** Python ports the same model and passes the same shared cases (`conformance/written/`, D9,
  D10); Python splices by `str` index but places count UTF-16 units (D-S3-1).

## Current choices

- **The spec.**
  - [grammar/Knobly.g4](../grammar/Knobly.g4) is the one grammar file.
  - Whitespace, comments and newlines are ordinary grammar tokens: nothing goes on a hidden
    channel and nothing is skipped.
  - Lists and value runs are written as loops, not recursion.
  - `*` and `?` are word characters, so include globs work (`kno-trv`).
  - [grammar/knobly.ebnf](../grammar/knobly.ebnf) stays as the readable EBNF view and the
    reference used in testing.
- **Soundness (a)**, checked by `tools/check.sh`, which CI runs on every push:
  - `g4bison.py` translates the parser rules mechanically, and Bison must report 0 conflicts
    with `%expect 0`.
  - `g4overlap.py` proves that no two token kinds can match the same text.
  - Both checks fail on the planted grammars.
  - The translator refuses predicates, actions, lexer modes and other features that could hide
    a conflict.
- **Soundness (b):** ANTLR4 generates both the TS and the Python parser from that file. On
  14,900 inputs:
  - the TS and Python trees and diagnostics are byte-identical;
  - they match the `knobly.ebnf` reference parser;
  - there were 0 round-trip failures.
- **The CST**, the condition in R6:
  - It is lossless: every character is in exactly one token, for valid and broken input alike.
  - Node kinds: document, directive, block, list, slice, error.
  - The parts of a slice stay separate tokens.
- **Recovery:**
  - A custom ANTLR error strategy, about 95 lines per language, meets `kno-bzv.1`.
  - The first error is reported at the real position.
  - A bad statement becomes one error node, and later siblings are kept.
- **The layers** (round 11 built the middle one; round 12 the low level under it): the language page is
  [the guide's language page](../docs/site/pages/language.md); the low level is
  [Editing and saving](../docs/site/pages/editing.md); the rendered tree is
  [Walking, addresses and reloads](../docs/site/pages/walking.md).
  - A processor is made once with a document source and extensions. `load` reads a root file and every file it
    includes, each once, and returns the document graph: the files as written, their variables, and what each
    `$name` reads at each place where it is read. Named edits change the text and keep comments and layout; `save`
    hands the changed files to the program's writer in one batch.
  - `render(graph)` expands `set`, `$name`, `snippet`, `use` and include lines into directives. Every directive and
    value carries its origin and leads back to what is written (`written`, `resolutions`); `addresses({ key })`
    names directives under the program's key rule; `diff` lists added, removed, changed and unknown directives by
    address.
  - Problems are located diagnostics, never exceptions; a line that cannot be read stays in place as unreadable.
  - Both languages must give the same trees, codes, places, addresses, change lists, resolutions and edit results;
    `conformance/load/` and `conformance/written/` are the shared tests of that.
- **Runtime:** the official `antlr4` 4.13.2 for TS (sync, pure JS, about 36 KB gzip in the
  browser) and `antlr4-python3-runtime` 4.13.2 for Python, both pinned to the generator
  version. The fallback is antlr4ng, if CI should not need Java.

## Design rules (design choices)

1. **One file defines the language.** Every parser and every check comes from
   `grammar/Knobly.g4`.
2. **Every character is in exactly one token, and no two token kinds overlap.** So ANTLR's
   tie-break by rule order never decides anything.
3. **ANTLR stays behind the adapter.** Layers above see only our tokens, CST, stable codes and
   the load layer's own types.

## Recommended as shown (can be reopened)

- **Error codes tidied** (landed with recovery, `kno-g7n.1.2` and `kno-g7n.2.2`):
  - E2007 for a bad slice;
  - E2008 for `{` on its own line;
  - E2009 for touching values;
  - E2002 and E2005 removed.

The depth limit, the one-node bad line and `foo[1]` were recommendations here; the owner has
since answered them (see Owner answers).

## Diagnostic codes

The full table, with what each code means and where it is placed, is in
[the guide's error codes](../docs/site/pages/diagnostics.md#error-codes). The bands:

| Band | What | Codes in use |
|---|---|---|
| 1xxx | lexical | E1001, E1003, E1004 (a lone `$`, new in round 11) |
| 2xxx | syntax | E2001, E2003, E2004, E2007, E2008, E2009, E2010 |
| 3xxx | files and extensions | E3001, E3004, E3005 (include path; was E2006), W3005 (a glob that matched nothing: a warning, 2026-10-30), E3006 (an extension failed; new) |
| 4xxx | values | E4001 (bound), E4002-E4006 (readers; E4003 checked at load) |
| 5xxx | expansion (new in round 11) | E5001-E5013 (E5013: nesting after expansion, 2026-10-30) |
| 6xxx | reserved for the high-level API | none defined |
| `namespace/name` | a program's own codes, such as `rasl/unknown-node` | checked when made |

**Retired, never reused:** E2002 and E2005 (removed with recovery), E2006 (replaced by E3005), E3002 and E3003
(replaced by E5006 and E5007).

## Bead outline (under `kno-g7n`; ported beads keep their old rasl numbers with the `kno-` prefix)

Status as of 2026-10-28.

1. **Spec and CI checks:** done (`kno-g7n.3`, `kno-k2e`).
   - `grammar/Knobly.g4`, with the parsers generated by `tools/gen.sh` on every build and
     test, never committed;
   - `g4bison.py`, `g4overlap.py` and the planted grammars;
   - the conformance corpus with alphabet-edge inputs.
2. **TS parser on ANTLR (the tracer):** done (`kno-g7n.1`).
   - the generated parser replaced the hand-written `lexer.ts` and `parser.ts` (copies stay in
     `reference/`);
   - rasl's part, under `rasl-8st` in mcurcio/rasl, is open: rasl adopts knobly and deletes
     its `parseSliceTokens`.
3. **Recovery and stable codes:** done in TS and Python (`kno-g7n.1.2`, `kno-g7n.2.2`); the rest
   of `kno-bzv.1` is open.
4. **Python parser on ANTLR:** done (`kno-g7n.2`), replacing crossplane.
5. **The low-level consumer API** (gate `kno-9vn`, open until the owner reviews the build):
   - variables and snippets in the grammar, and the TS load tracer: done (`kno-9ze.4`);
   - the TS low-level API: done (`kno-stq.3`);
   - the Python low-level API: done (`kno-stq.4`);
   - the docs: `kno-9vn.1`.
6. **Later:** the high-level API, declared directives (`kno-xlo`, deferred by the owner on
   2026-10-28); editing files through the tree (`kno-uji`); the epics `kno-9ze`, `kno-stq`,
   `kno-bgz` and `kno-bzv` stay open for their remaining beads.

## NOT RUN

- A `tsc` type-check of the adapters.
- A real browser.
- Bison 3.x.
- Linux CI.
- Python versions other than 3.13.
- Performance on large files.
