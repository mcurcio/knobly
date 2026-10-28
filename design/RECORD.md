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
| R5 | Slices `[n:m]`, `[n:]` and `[:m]`; `[:]` is rejected with a located error | `vil-9ze.1` |
| R6 | "A is ideal if we don't sacrifice the CST. Otherwise, C." (the condition on choosing ANTLR4) | owner, 2026-10-22 |

## Owner answers

| Question | Answer | Recorded in |
|---|---|---|
| Comments, and `:` in words | B: `#` only, where a token starts. A word that starts with a digit or `-` cannot contain `:` | `vil-m8w.1` |
| Values touching | A: values are separated by a space or comment; a slice touches its word; punctuation may touch | `vil-9ze` |
| Which tool | A: ANTLR4, provided the CST is kept. The check below says it is | `vil-k2e` |
| What a slice bound may be (2026-10-23) | "Integers only (Recommended)": `valueOf` gives integer start and end; any other bound is a located error with its own code (E4001) | `vil-9ze.3` |
| Is `foo[1]` a slice form (2026-10-23) | "Yes, add it now", and "Its own kind: index (Recommended)": `valueOf` gives `{kind: 'index', name, index}` | `vil-9ze.2` |
| Depth limit and bad lines (2026-10-23) | "Yes to both (Recommended)": nesting deeper than 100 is its own error (E2010); a bad line becomes one error node and later siblings are kept | `vil-bzv.3` |
| Licence (2026-10-23) | "MIT (Recommended)" | `vil-m8w.4` |
| Real rasl configs in the corpus (2026-10-23) | "Neutral here, real ones to rasl (Recommended)" | `vil-m8w.5` |
| Generated parser code (2026-10-23) | "Don't commit the generated code, just the source": every build and test regenerates it | `vil-g7n.2` |
| Releases (2026-10-23) | "Key from semantic-release and conventional commit on every PR merge"; "GitHub Release assets only"; "Dry-run until I enable it" (the repository variable `RELEASE_ENABLED`) | `vil-g7n.3` |

## Owner answers the low-level API rests on (since 2026-10-24)

The consumer API design (gate bead `vil-9vn`) ran from 2026-10-24 to 2026-10-28. The full working record is
`.claude/design/consumer-api/requirements.md` on the build branch; the answers are verbatim in `vil-9vn`. These are
the ones the low-level API, built on branch `feat/consumer-api-low-level`, rests on. A pick among offered options is
a current choice and can be revised; the others are requirements.

| Date | Answer (his words) | What it decided | Kind |
|---|---|---|---|
| 2026-10-24 | "All five" | the five epics (`vil-9ze`, `vil-stq`, `vil-xlo`, `vil-bgz`, `vil-bzv`) are one surface | requirement |
| 2026-10-24 | "Both, idiomatic in each language" | TypeScript and Python each get the API in their own idiom | requirement |
| 2026-10-25 | "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be optional extensions rather than core." | no third-party libraries in the core (amended 2026-10-28: "third party libraries are ok for things like reflect-metadata") | requirement |
| 2026-10-25 | "I think it's a first-party plugin/extension. And any configuration knobs that "includes" may require could be set when the plugin is instantiated and passed into the config tool." | include is an extension a program turns on (`include()`), not part of the core | requirement |
| 2026-10-25 | picked "Allowed, per place"; note: "Obviously the file only needs to be read once, and any core syntax errors can be communicated once." | a file included at two places is read once, its syntax errors reported once, each place read on its own | pick, with a requirement in the note |
| 2026-10-25 | "if we allow variables to passed into the included file, then each instance of the file would have its own bindings." | an include line's block of `set` lines gives that place its own values | requirement |
| 2026-10-26 | picked C: "Focus on the core, low level API and high level sugar APIs. The extensions can come later as additional sugar." | no pydantic, zod or JSON Schema integrations in this work | pick |
| 2026-10-27 | picked A, "The EBNF's rules win (recommended)" | values follow the EBNF: no leading zeros, only six string escapes (`\q` is now E4003) | pick |
| 2026-10-27 | "Within villanelle I want the spec to win over a reference language" | the spec is canonical in villanelle; R4's "TS config is canonical" was about rasl ("talking about the rasl codebase, not villanelle") | requirement |
| 2026-10-27 | "Value type directives can have multiple values. Not just “port 8080” but also “port 8080 443 dev tls”" | a directive takes any number of values of mixed kinds | requirement |
| 2026-10-27 | "B is the target." | variables, snippets with arguments, and a directive reading its own block are in scope | requirement |
| 2026-10-27 | "Nothing is locked until I see user APIs that I like." | the grammar may change; designs lead with user code | requirement |
| 2026-10-27 | "I like the direction of this, especially the addition of the variables and snippets. Those were on my wishlist" | variables and snippets kept | steer |
| 2026-10-28 | picked "whole" (recommended) | a variable is only ever a whole value, never joined to other text | pick |
| 2026-10-28 | "I approve of the language features and design. Should we move forward with the low-level API for now and defer the high-level sugar API for later?", then "Yes" to the plan | build the low-level API now (syntax tree and directive layer); the high-level API (`vil-xlo`) is deferred; done means rasl's `family_room.conf` and `hyperhdr.conf` load through it in both languages | requirement; the plan's details were the main session's, which he accepted |

## Current choices

- **The spec.**
  - [grammar/Villanelle.g4](../grammar/Villanelle.g4) is the one grammar file.
  - Whitespace, comments and newlines are ordinary grammar tokens: nothing goes on a hidden
    channel and nothing is skipped.
  - Lists and value runs are written as loops, not recursion.
  - `*` and `?` are word characters, so include globs work (`vil-trv`).
  - [grammar/villanelle.ebnf](../grammar/villanelle.ebnf) stays as the readable EBNF view and the
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
  - they match the `villanelle.ebnf` reference parser;
  - there were 0 round-trip failures.
- **The CST**, the condition in R6:
  - It is lossless: every character is in exactly one token, for valid and broken input alike.
  - Node kinds: document, directive, block, list, slice, error.
  - The parts of a slice stay separate tokens.
- **Recovery:**
  - A custom ANTLR error strategy, about 95 lines per language, meets `vil-bzv.1`.
  - The first error is reported at the real position.
  - A bad statement becomes one error node, and later siblings are kept.
- **The low-level API** (round 11 build): the language page is [docs/language.md](../docs/language.md) and the API
  reference for both languages is [docs/low-level-api.md](../docs/low-level-api.md).
  - A processor is made once with a document source, extensions and a key rule; `load` reads a root file and every
    file it includes, each once, and expands `set`, `$name`, `snippet`, `use` and include lines.
  - Every directive and value carries its origin (where it was written and the variables, uses and include lines that
    brought it); every directive has an address that the key rule keeps stable across edits; `diff` lists added,
    removed, changed and unknown directives by address.
  - Problems are located diagnostics, never exceptions; a line that cannot be read stays in place as unreadable.
  - Both languages must give the same trees, codes, places, addresses and change lists; `conformance/load/` is the
    shared test of that.
- **Runtime:** the official `antlr4` 4.13.2 for TS (sync, pure JS, about 36 KB gzip in the
  browser) and `antlr4-python3-runtime` 4.13.2 for Python, both pinned to the generator
  version. The fallback is antlr4ng, if CI should not need Java.

## Design rules (design choices)

1. **One file defines the language.** Every parser and every check comes from
   `grammar/Villanelle.g4`.
2. **Every character is in exactly one token, and no two token kinds overlap.** So ANTLR's
   tie-break by rule order never decides anything.
3. **ANTLR stays behind the adapter.** Layers above see only our tokens, CST, stable codes and
   the load layer's own types.

## Recommended as shown (can be reopened)

- **Error codes tidied** (landed with recovery, `vil-g7n.1.2` and `vil-g7n.2.2`):
  - E2007 for a bad slice;
  - E2008 for `{` on its own line;
  - E2009 for touching values;
  - E2002 and E2005 removed.

The depth limit, the one-node bad line and `foo[1]` were recommendations here; the owner has
since answered them (see Owner answers).

## Diagnostic codes

The full table, with what each code means and where it is placed, is in
[docs/low-level-api.md](../docs/low-level-api.md#error-codes). The bands:

| Band | What | Codes in use |
|---|---|---|
| 1xxx | lexical | E1001, E1003, E1004 (a lone `$`, new in round 11) |
| 2xxx | syntax | E2001, E2003, E2004, E2007, E2008, E2009, E2010 |
| 3xxx | files and extensions | E3001, E3004, E3005 (include path; was E2006), E3006 (an extension failed; new) |
| 4xxx | values | E4001 (bound), E4002-E4006 (readers; E4003 checked at load) |
| 5xxx | expansion (new in round 11) | E5001-E5012 |
| 6xxx | reserved for the high-level API | none defined |
| `namespace/name` | a program's own codes, such as `rasl/unknown-node` | checked when made |

**Retired, never reused:** E2002 and E2005 (removed with recovery), E2006 (replaced by E3005), E3002 and E3003
(replaced by E5006 and E5007).

## Bead outline (under `vil-g7n`; ported beads keep their old rasl numbers with the `vil-` prefix)

Status as of 2026-10-28.

1. **Spec and CI checks:** done (`vil-g7n.3`, `vil-k2e`).
   - `grammar/Villanelle.g4`, with the parsers generated by `tools/gen.sh` on every build and
     test, never committed;
   - `g4bison.py`, `g4overlap.py` and the planted grammars;
   - the conformance corpus with alphabet-edge inputs.
2. **TS parser on ANTLR (the tracer):** done (`vil-g7n.1`).
   - the generated parser replaced the hand-written `lexer.ts` and `parser.ts` (copies stay in
     `reference/`);
   - rasl's part, under `rasl-8st` in mcurcio/rasl, is open: rasl adopts villanelle and deletes
     its `parseSliceTokens`.
3. **Recovery and stable codes:** done in TS and Python (`vil-g7n.1.2`, `vil-g7n.2.2`); the rest
   of `vil-bzv.1` is open.
4. **Python parser on ANTLR:** done (`vil-g7n.2`), replacing crossplane.
5. **The low-level consumer API** (gate `vil-9vn`, open until the owner reviews the build):
   - variables and snippets in the grammar, and the TS load tracer: done (`vil-9ze.4`);
   - the TS low-level API: done (`vil-stq.3`);
   - the Python low-level API: done (`vil-stq.4`);
   - the docs: `vil-9vn.1`.
6. **Later:** the high-level API, declared directives (`vil-xlo`, deferred by the owner on
   2026-10-28); editing files through the tree (`vil-uji`); the epics `vil-9ze`, `vil-stq`,
   `vil-bgz` and `vil-bzv` stay open for their remaining beads.

## NOT RUN

- A `tsc` type-check of the adapters.
- A real browser.
- Bison 3.x.
- Linux CI.
- Python versions other than 3.13.
- Performance on large files.
