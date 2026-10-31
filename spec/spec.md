# knobly language-binding specification

Status: this page is canonical (owner, 2026-10-27: "Within villanelle I want the spec to win over a
reference language"). It describes the API after milestone 6 (beads kno-umh.9, kno-umh.10, kno-umh.11 and
kno-umh.13: the schema is the source of every public signature, kind lists are generated enumerations (2.10), one
namespace per layer without an `I` prefix (binding guide rules 1 and 2), one block shape in every layer (2.11);
`.claude/design/consumer-api/round15/frozen-m6.md`), milestone 5 (beads kno-umh.6, kno-umh.12 and kno-umh.14: raw single
quotes, no `plain` reader, the `~` slice separator and subscripts on variables, `@` statements, a value's `set` that
keeps its handle, config text as its own type) and milestone 4 (beads kno-umh.1 to kno-umh.8 and kno-umh.12, the
round 15 review's next steps: `.claude/design/consumer-api/round15/`), built on milestone 2 (beads kno-0vz, kno-9fy,
kno-5ya, kno-gxu): the words of
[glossary.md](glossary.md), the operation homes and layer direction the owner settled on the
round 13 gate page (2026-10-29, 6.2), types that carry their kinds (2.10, round 13 root cause 3), the rendered
layer built only on the low level's public members (6.10, 7.0), and the edge contract of
[contract.md](contract.md) (round 13 root cause 4). The exact old-to-new tables are the milestones' frozen pages,
`.claude/design/consumer-api/round14/frozen-m1.md` and `frozen-m2.md`; the bindings carry the older names until each
milestone's binding work lands; milestone 4's and milestone 5's old-to-new tables are
`.claude/design/consumer-api/round15/frozen-m4.md` and `frozen-m5.md`.
Nothing here is locked: the owner approves API
shapes ("Nothing is locked until I see user APIs that I like", 2026-10-27). A note marked
**Proposed (pending owner)** is not agreed; it links to [review.md](../.claude/design/consumer-api/round13/review.md)
or names its open question.

This page is the one home of the rules a binding must follow. Each concept's one word, and its type
name in each layer and binding, is in [glossary.md](glossary.md). Every fixed list (kind lists,
error groups, limits, reserved names, diagnostic codes) and every public signature has its one home in
[schema/](schema/): each binding's declarations are generated from it ([codegen.md](codegen.md)), the code table of
2.4 is generated, the other tables on this page are copies for reading, and the schema wins where they differ. How to turn the
rules into a binding in a given language (names, idiom, what may differ) is in
[binding-guide.md](binding-guide.md). The syntax is [grammar/Knobly.g4](../grammar/Knobly.g4); which
definition a `$name` or a `use` reaches, and which one wins, is [expansion.md](expansion.md) (normative); the
language for people writing configs is the user guide's [language page](../docs/site/pages/language.md), which teaches both and is not a
source of rules.

## 1. How to read this page

- **MUST**, **MUST NOT**, **SHOULD** and **MAY** mean what RFC 2119 says they mean.
- Each concept and operation has one **spec name**, written in lowercase words in backticks:
  `document graph`, `replace with text`. A binding spells that name in its language's casing; the casing
  rules are in the binding guide. A binding MUST NOT give a spec concept a different word.
- "Absent" means the language's no-value (`undefined` in TypeScript, `None` in Python). Absent and
  empty are different values wherever both can occur, and a binding MUST keep them apart: empty
  text is a present value (a key rule that returns empty text gives the key `""`, which the address
  text writes as `""`, never `null`), and an empty list is not an absent one (a directive written
  `name {}` has an empty `block`; one written without a block has none). A language that cannot
  tell absent from empty for a type (a Go `nil` slice against an empty one) adds a boolean beside
  it instead (binding guide, section 3).
- **Raise**, **throw** and **fail** all mean the operation ends with an error of the named group,
  however the language reports one (an exception, a returned error value, a rejected promise). How
  a language without exceptions maps the groups is in 2.8.
- **Free**: a reference or a `use` line is free when no declaration is found for it by where it is
  written (6.5, 6.6). A free reference can still resolve at a copy, through an extension line's
  `set` lines or an override ([expansion.md](expansion.md) 5); the low level reports E5001 or E5003 only where
  nothing does.
- "In order" lists are ordered as stated. When a list's order is stated, a binding MUST keep it:
  the conformance outputs depend on it.
- "Text" means the language's string type. Values going into edits are `config text` (6.9): knobly text in a
  type of its own, made only by `quote` or `text`.
- Error groups are named here (for example "misuse error"); which native class each group maps to
  is the binding's choice within the rules of 2.8 and the binding guide.

- **Where an operation lives** (6.2): the processor only loads; every later operation is a method on
  the object the program holds, within that object's layer; going up a layer is a free function of
  the upper layer, `render (graph)` (7.0), because the low level never depends on the rendered layer
  (owner, 2026-10-29, round 13 question 1: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"). The other free
  functions are pure helpers: `parse`, `span of` and `text of` (3.3), `quote` and `text` (6.9), `format
  diagnostic` (2.7), and the adapter and extension factories.

The glossary ([glossary.md](glossary.md)), the schema ([schema/](schema/)) and the edge contract
([contract.md](contract.md): positions, people forms, numbers, error classes, adapters) are split out of this page.
Splitting the rest into one page per layer (review, root cause 5) waits for the milestone that writes those rules.

## 2. Shared pieces

These are used by more than one layer.

### 2.1 Positions and spans

- A `source position` has `offset`, `line` and `column`, all counting from 0.
- `offset` and `column` count **the binding's own string unit**: UTF-16 code units in TypeScript, code points in
  Python, so cutting the program's string at a reported position gives the right text
  ([contract.md 1](contract.md#1-positions)). Every conformance output stays in UTF-16 units; the shared driver converts ([conformance.md](conformance.md)).
- A line ends after each `"\n"`. `"\r\n"` ends one line. A lone `"\r"` does **not** end a line, in positions and
  in `format diagnostic` alike.
- A `source span` is a half-open range `[start, end)` of two positions, with
  `start.offset <= end.offset`.

> **Proposed (pending owner), for bindings whose strings are not UTF-16:** `parse` is total over the
> language's own strings (3.3). A UTF-16 string can hold a lone surrogate but not an invalid byte; a Rust `String`
> is always valid UTF-8, so it can hold neither a lone surrogate nor an invalid byte. A Go `string` is any byte
> sequence, so it can hold both: a lone surrogate as its 3-byte WTF-8 form (`\ud800` is the bytes `ED A0 80`). The
> proposal: each invalid byte becomes one `BAD_CHAR` token with E1003 at that byte (inside a string or comment it
> breaks the token, as a raw control character does), and a binding whose strings cannot hold a lone surrogate
> skips the syntax cases `surrogate-bare`, `surrogate-str` and `surrogate-comment` (in `extra.json`) and passes
> matching invalid-byte cases instead, which do not exist yet. Today no rule covers invalid UTF-8, and there is no
> such skip.

**Today's rule for a lone surrogate** (what the driver checks): the three `surrogate-*` cases are L0 cases like any
other, with no per-case skip ([conformance.md 2](conformance.md#2-conformance-levels)). In `byte` units a lone
surrogate counts 3 bytes, its WTF-8 form (`conformance/driver/units.py`). So a Go binding passes them when its
adapter decodes a request's `\ud800` escape into those 3 bytes and writes them back as `\ud800` (a standard JSON
codec does neither: [conformance.md 3](conformance.md#3-transport)); a binding on Rust's `String` cannot pass them,
and so cannot hold L0, until the owner rules on the proposal above.

The two bindings disagreed on a lone `"\r"` (TypeScript's `format diagnostic` cut the source line there) and on
`-0` (review finding P3); [contract.md](contract.md) rules both, with conformance cases.

### 2.2 Place, step, origin

- A `place` is a range of one file's text: `kind` `"file"`, `resolved path` (the file's identity as
  the document source gave it) and `span`.
- An `override` is a value the program passes in at load (6.2), written in no file. As an
  origin's place it is `kind` `"override"` and `variable` (the name without `$`). The `place kind`
  list is `file`, `override`; `place` and `override` are its two variants (2.10), each with `kind`, in every
  binding.
- A `step` is one expansion a directive or value went through: `kind` (one of the `step kind`
  list: `variable`, `use`, `extension`), `name` (the variable without `$`, the snippet, or the
  extension's name without `@`, such as `include`) and `place` (the place of the `$name` token, the `@use` of the
  `use` line, or the extension line's `@name`), as the load cases print it (`use twinkle main.conf:4:9`).
- An `origin` is `place` (a place, or an override) plus `via` (steps, innermost first; empty when
  the text is read where it was written). For a value from a variable, `place` is the value in its
  `set` line (or the override) and `via[0]` is the `$name` that used it.
- A `directive origin` is an origin whose `place` is always a file place.

All of these are plain, read-only data. A `place`, an `override` and a `step` each have a `people form`, the text
a person reads (`path:line:col` counting from 1, `override <variable>`, `<kind> <name> at <place>`), exposed as the
language's to-text conversion ([contract.md 2](contract.md#2-people-forms-the-text-a-located-thing-prints-as)).

### 2.3 Diagnostics

- A `diagnostic` (syntax layer) has `code`, `message` and `span`.
- A `located diagnostic` (every other layer) has `code`, `message`, `place` (a file place) and
  `via` (steps, innermost first). A problem caused by an override is placed at the `$name` that used
  it, and the message names the overridden variable.
- Only `code` and the position are part of the contract. `message` is for people and MAY differ
  between bindings.
- A `program code` is a program's own code, `<namespace>/<name>` (for example `rasl/unknown-node`): both parts
  non-empty and without whitespace, the `program code` pattern of `spec/schema/api.json`.
  It never collides with knobly's codes, which start with `E`. Every operation that takes a
  program code MUST refuse one without `/` with a misuse error.
- Every code is an error. There are no warning codes.
- A `diagnostic` and a `located diagnostic` each have a `people form`: `line:col: CODE: message` and
  `path:line:col: CODE: message`, counting from 1 ([contract.md 2](contract.md#2-people-forms-the-text-a-located-thing-prints-as)).

### 2.4 The diagnostic code registry

Codes are stable across bindings and releases and are never reused for another meaning. Retired,
never to be reused: E2006, E3002, E3003, E2008 and E4003 (milestone 4: a line break is whitespace, so a `{` may
start its line; a bad escape is found by parse, E1005). Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and
extensions, 4xxx values, 5xxx expansion, 6xxx reserved for the high level.

A binding MUST expose every code below, by its value and by a name. The "found by" column says
which operation reports it: `parse`, `edit` (in a `bad text error`'s diagnostics, 2.8), `load and read`, `low
level` (worked out from the current texts), `readers` (2.9) or `include extension`. The table is generated from
[schema/diagnostics.json](schema/diagnostics.json) (`python3 tools/gen-api.py docs`; `tools/check.sh` fails when it
is stale), which also holds each code's message and owning layer.

<!-- generated: diagnostic codes (tools/gen-api.py docs) -->
| Code | Spec name | Found by | Unreadable reason | Meaning |
|---|---|---|---|---|
| E1001 | `unterminated string` | parse | syntax | A string reaches the end of its line or of the text without its closing quote. |
| E1003 | `unexpected character` | parse | syntax | A character no token may start with, or a byte-order mark after the first character. |
| E1004 | `lone dollar` | parse | syntax | A `$` not followed by a variable name. |
| E1005 | `bad escape` | parse | syntax | A closed double-quoted string holding a backslash escape other than the six (the `BAD_ESCAPE` error token), placed on the string. A single-quoted string is raw: it has no escapes. |
| E2001 | `unexpected token` | parse | syntax | A token the grammar does not allow here, when no more specific code applies: among them the end of the text at the top level, or a `}`, where a directive's `;` or block is due (3.2). Also an edit's bad text error, from its entry rule (2.8): at the first token the entry rule does not allow, or at the end of the text. |
| E2003 | `expected closing brace` | parse | syntax | The text ends inside a block: reported once, at the end of the text, however many blocks are open; not after a statement whose error runs to the end of the text, and not inside an open `[` (E2004) (3.2). |
| E2004 | `expected closing bracket` | parse | syntax | A stray `]`, or a `[` list with no matching `]`. |
| E2007 | `bad slice` | parse | syntax | A malformed slice after a slice name (a word or a `$name`): `a[~]`, `a[1~b c]`, an unclosed slice, or a literal bound that is not an integer (`a[i]`, `a[1.5]`, `a[1:3]`, whose `1:3` is one word). |
| E2009 | `values touch` | parse | syntax | Two values with nothing between them, such as `a"b"`. |
| E2010 | `nesting too deep` | parse | syntax | Blocks and lists nested deeper than 100 levels. |
| E3001 | `include not found` | load and read | extension | An extension's spec matched no file. |
| E3004 | `include resolver failed` | load and read | extension | The document source rejected while resolving or reading a file. For the root file, `load` fails instead (6.2). |
| E3005 | `include bad path` | include extension | extension | An `include` whose values are not exactly one quoted path. |
| E3006 | `extension failed` | load and read | extension | An extension threw something other than a diagnostic error, or returned something other than a list of texts. |
| E3007 | `unread copy` | low level | unread | An extension line's copy whose specs are not resolved or whose files are not read yet (it is in `unread ()`); `read ()` reads them. Placed on the extension line's name. |
| E3008 | `unknown extension` | low level | extension | A statement written `@name` where `name` is no language statement (`set`, `snippet`, `use`) and no registered extension's name. Placed on the `@name`; the statement is an `unreadable line`. |
| E4001 | `non-integer bound` | low level | value | A slice or index bound reached through a variable that is not one integer word, or a literal integer beyond the integer range. A literal bound that is not an integer is E2007, found by parse. |
| E4002 | `wrong value kind` | readers | none | A reader asked for a kind the value is not. |
| E4004 | `not a number` | readers | none | A word read as a number that is not a JSON number, or one beyond the double range (`1e400`; contract 2). |
| E4005 | `not an integer` | readers | none | A word read as an integer that is not one, or one beyond plus or minus 2^53-1. |
| E4006 | `not a boolean` | readers | none | A word other than `true` or `false`, read as a boolean. |
| E4007 | `bad slice name` | low level | value | A slice or index whose name is a `$name` that does not hold exactly one `WORD` or `AT_WORD`, the words the grammar's `sliceName` takes (`$src[0~3]` with `$src` a string, a list, two values, or a number-like word such as `5`, `1.5`, `-` or `07:30`); placed as E4001 is. |
| E5001 | `unknown variable` | low level | expansion | A `$name` with no `set` visible and no override. |
| E5002 | `variable set twice` | low level, edit | expansion | Two `set` lines for one name in one block. |
| E5003 | `unknown snippet` | low level | expansion | A `use` naming no visible snippet. |
| E5004 | `snippet arity` | low level | expansion | A `use` with a different number of values than its snippet's parameters. |
| E5005 | `snippet defined twice` | low level, edit | expansion | Two `snippet` lines for one name in one block. |
| E5006 | `expansion cycle` | low level | expansion | A `use` or extension line that reaches itself again. |
| E5007 | `expansion too deep` | low level | expansion | `use` and extension lines nested deeper than 16. |
| E5008 | `too many directives` | low level | expansion | More than 100,000 directives after expansion. |
| E5009 | `bad set` | low level, edit | expansion | A `set` line that is not `@set $name value...;`. |
| E5010 | `bad snippet` | low level, edit | expansion | A malformed `snippet` line (`@snippet name $p... { ... }`), or one naming a parameter twice. |
| E5011 | `bad use` | low level, edit | expansion | A `use` line that is not `@use name value...;`. |
| E5012 | `extension block not set` | low level | extension | An extension line whose block holds a line other than `@set`. |
| E5013 | `expanded nesting too deep` | low level | expansion | Blocks and lists nested deeper than 256 levels after expansion (2.5): a directive whose block or values, or a `set`, `use` or extension line whose values, would sit deeper. The statement is unreadable there and its block is not walked. |
<!-- end generated -->

Every code but the readers' is in the one diagnostics list: the `document graph`'s `diagnostics` (6.3), which the
`expansion` and the `rendered` tree show unchanged (6.10, 7.1). "Low level" codes are found when the list is worked
out from the current texts; "load, read" codes when the load or `read` runs, reported at the extension line.
(Before milestone 4 the graph left out E4xxx, E5001, E5003, E5004 and E5008, which only a render showed: round 15,
root cause C.)

**Unreadable reason** is the `unreadable reason` (6.10) of the statement a code makes unreadable; it is
part of the load conformance output. "syntax" means the statement is an `error` node, or an
extension line whose block holds one (the code is then the parser's, reported once). A diagnostic
error an extension's `specs` throws keeps its own code (a program code included) and gives reason
`extension`. "unread" (E3007) marks an extension copy not read yet. "none" means the code never makes a statement
unreadable: readers raise it.

Each binding's code registry and message table are generated from
[schema/diagnostics.json](schema/diagnostics.json) ([codegen.md](codegen.md)); the schema marks which
layer owns each code.

> **Proposed (pending owner):** stop naming E3001 and E3004 after `include`, since the core load
> reports them for every extension (review, "Deferred"; P9).

### 2.5 Limits and reserved names

`limits`, `keywords`, `reserved names` and `patterns` in [schema/api.json](schema/api.json) are their one home.
Each binding exports them from the layer that owns them, generated as the **rules module** (milestone 6, bead
kno-umh.10; codegen.md); the list below is generated from the schema too. The keywords are one generated list
(`Keyword`) with one dispatch table from keyword to statement kind (`STATEMENT_OF_KEYWORD`), which every binding's
statement classification reads; no binding compares a keyword's text by hand.

<!-- generated: limits (tools/gen-api.py docs) -->
- `MAX_NESTING` (nesting depth; the syntax layer): 100, blocks and lists nested at most this deep (E2010).
- `MAX_EXPANDED_NESTING` (expanded nesting depth; the written layer): 256, blocks and lists nested at most this deep after expansion (E5013).
- `MAX_DEPTH` (expansion depth; the written layer): 16, use and extension lines nested at most this deep (E5007).
- `MAX_DIRECTIVES` (directives; the written layer): 100,000, directives after expansion, at most (E5008).
- `MAX_SAFE_INTEGER` (integer range; the written layer): 9,007,199,254,740,991, integer words and slice or index bounds lie within plus or minus this (2^53-1) (E4005).
- `RESERVED` (reserved names; the written layer): `set`, `snippet`, `use`: the language statements' names, written @set, @snippet and @use: no extension may take one. No directive name is reserved: a directive's name is a WORD, which never starts with @.
- `VARIABLE_NAME` (variable name pattern; the written layer): `^[A-Za-z0-9_]+$`, a $name without its $, an override name, a variable rename.
- `PROGRAM_CODE` (program code pattern; the shared layer): `^[^/\t\n\u000b\u000c\r \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/[^\t\n\u000b\u000c\r \u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$`, <namespace>/<name>, a program's own diagnostic code: both parts non-empty, no whitespace (the Unicode White_Space set, written out); knobly's codes start with E.
<!-- end generated -->

- **Nesting levels** (`MAX_NESTING`, `MAX_EXPANDED_NESTING`; proposed to the owner 2026-10-30 and not objected to: the
  current rule). Each block `{...}` and each list `[...]` a value sits inside is one level, blocks and lists counted
  together: `[[1,2],[3,4]]` is 2 levels, and in `a { b [1]; }` the `1` sits 2 deep. A slice's brackets (`foo[0~3]`) are
  no level: a slice holds only bounds.
- **In one text (E2010).** Only the blocks and lists the parser opens count, the ones error recovery opens included;
  brackets that recovery skips open nothing and do not count (owner, 2026-10-30, of the proposal that they not count:
  "that sounds right"). So `"]"` 500 times then `"["` 101 times is E2004, and `a {` then `x [` 100 times is E2001 at 0:8,
  each the statement's first error (3.2). The block or list that would be level 101 ends the parse: `parse` returns a
  `document` node over every token whose one child is an `error` node over every token, and one diagnostic, E2010,
  on the `{` or `[` that opens that level. An entry rule (2.8) returns a `document` node with no children and that one
  E2010. Cases `nest-*`, `nestlist-*`, `nest-recovered-*` (`depth.json`). An edit that would make a document nest
  past the limit is refused, the document unchanged (2.8, "An edit that would nest the document past").
- **After expansion (E5013).** The same count over the expanded tree: a directive's block is one level deeper than
  the directive; a snippet's body at a `use` and an included file's top level stand where their line stands (their
  own braces are gone); a `$name` brings its values' lists with it. A statement whose block, or a list among its
  values, would sit deeper than `MAX_EXPANDED_NESTING` is unreadable (reason `expansion`), with E5013 at its name (a
  directive's name, the `@set`, the `@use`, an extension's `@name`), and its block is not walked; a `set` that fails
  so defines nothing ([expansion.md](expansion.md) 8). It is checked once the statement's values are expanded: after
  the checks that need no expanded value (the line's shape, E5009 to E5011; a `set` of a name already set, E5002; a
  `use` of no visible snippet, E5003) and the codes its values give while they expand (E5001 among them), and before
  the statement's other checks (E5004, E5006, E5007, E5008's count, an extension's `specs`, and for an extension line
  the `@set` lines of its block, each checked as a `set` line standing where the extension line stands). So no value
  or block deeper than the limit is ever kept and no walk over the expanded tree goes deeper. The owner, 2026-10-30
  (bead kno-bzv.6), of a limit of 100 after expansion: "100 seems too low. can we increase it?"; asked which limit:
  "after expansion"; real configs are "likely a few dozen, but i want the headroom". 256 is a revisable choice, not
  his number; `MAX_NESTING` stays 100. Cases `diag-expanded-nesting-*` (written corpus: 257 and 1568 levels of
  blocks, and the place and order cases), `load-expanded-nesting-256`, `load-expanded-nesting-lists`.
- **No directive name is reserved** (milestone 5; owner, 2026-10-29, bead kno-umh.14: "yes" to language
  statements behind one sigil). A statement written `@name` is a language statement (`@set`, `@snippet`, `@use`) or
  an extension statement (`@include`); a directive's name is a `WORD` token, which never starts with `@` (3.1). So
  `events { use epoll; }` is a plain directive `use`.
- An extension's name is any word the `nameText` entry rule takes that is not in `RESERVED` (5).

### 2.6 Diagnostic error

A `diagnostic error` is the error thrown by an operation whose input breaks its contract in a way
that has a place in the config: a reader given the wrong kind of value, or a program's `error(...)`. It carries one
`located diagnostic` as `diagnostic`. (A root file that cannot be read is a `read error`, which has no place in any
file: [contract.md 4](contract.md#4-errors).)

### 2.7 Formatting a diagnostic

`format diagnostic (diagnostic, graph?)` returns text for people:

```text
path:line:col: CODE: message          <- the located diagnostic's people form: line and column count from 1
the source line                       <- only when the graph holds the file (its current text); ends only at
                                         "\n" or "\r\n", never at a lone "\r"
    ^^^^                              <- under the span; tabs kept so the caret lines up
  via <kind> <name> at path:line:col  <- "  via " and each step's people form, innermost first
```

Columns and carets count the binding's string unit ([contract.md 1 and 2](contract.md#2-people-forms-the-text-a-located-thing-prints-as)).
It MUST read text only from the graph it is given and MUST NOT do I/O.

### 2.8 Error groups

Every binding maps these groups onto its own error classes (a copy of `error groups` in
[schema/api.json](schema/api.json); the class tree and the fields are [contract.md 4](contract.md#4-errors)):

The groups fall into **two sorts**, decided here once (round 15, kno-umh.7):

- **An expected outcome**: only the input or the outside world decides it, so a correct program still meets it and
  handles it. Every expected-outcome class is under the package's one base class, `knobly error`, and nothing
  else is: one `catch` or `except` clause for `KnoblyError` catches every outcome and no bug.
- **A program bug**: the program could have checked first. These raise the language's own classes, or a package
  class outside the base; never a `knobly error`.

Problems in the config text are no group: they are never raised, only reported as diagnostics. The table is
generated from the schema:

<!-- generated: error groups (tools/gen-api.py docs) -->
| Group | Sort | Raised when | TypeScript | Python | C++ |
|---|---|---|---|---|---|
| `knobly error` | base | never by itself: the base class of every expected-outcome class, so one except or catch clause catches every outcome the input or the outside world decides, and no program bug | `KnoblyError`, extends `Error` | `KnoblyError`, subclass of `Exception` | `knobly_error`, derives from `std::runtime_error` |
| `diagnostic error` | expected outcome, under `knobly error` | a reader is given a value of the wrong kind or spelling, or a program's error(...); carries one located diagnostic as 'diagnostic' | `DiagnosticError` | `DiagnosticError` | `diagnostic_error` |
| `read error` | expected outcome, under `knobly error` | load cannot resolve the root path to exactly one file, or cannot read it. No diagnostic and no code | `ReadError` | `ReadError` | `read_error` |
| `bad text error` | expected outcome, under `knobly error` | the text given to an edit, or an override's text, is not what that place takes; 'diagnostics' are located in that text, in the binding's string unit, and its message is built from them | `BadTextError` | `BadTextError` | `bad_text_error` |
| `save error` | expected outcome, under `knobly error` | the writer failed | `SaveError` | `SaveError` | `save_error` |
| `lost update error` | expected outcome, under `save error` | a file the save would write changed since it was read or last saved: its current text differs from its saved text. Check lost updates raises it inside every writer, and save passes it on unchanged | `LostUpdateError` | `LostUpdateError` | `lost_update_error` |
| `detached error` | program bug | any member but kind of a detached handle is used | `DetachedError`, extends `ReferenceError` | `DetachedError`, subclass of `ReferenceError` | `detached_error`, derives from `std::logic_error` |
| `argument type error` | program bug | an argument of the wrong type: anything but text where config text or a name is taken (an extension's name when the processor is made included), and to quote and text; a writer that is not a document writer; a render given something that is not a document graph (no callable expand); a key rule that returns anything but text or absent | `TypeError` | `TypeError` | `argument_type_error`, derives from `std::logic_error` |
| `misuse error` | program bug | a bad argument value a program could have checked: every bad name (a variable or override name not matching the variable name pattern; a directive's new name, or an extension's name when the processor is made, that is not one word), a program code without '/', a reserved (set, snippet, use) or repeated extension name, a current list in check lost updates not as long as its files, and removing a slice's or index's name or its only bound | `MisuseError`, extends `Error` | `ValueError` | `misuse_error`, derives from `std::invalid_argument` |
| `index out of range` | program bug | an insert index outside a block; a token range outside a parse | `RangeError` | `IndexError` | `index_out_of_range`, derives from `std::out_of_range` |
<!-- end generated -->

There is no `edit error` (milestone 4: it was never raised; `bad text error` is the only refusal of an edit) and no
`no set line error` (`set` and `rename` exist only on the variable kinds where they succeed, 6.7). Each group has
its own class, so the conformance adapter tells every group apart by class (TypeScript's misuse error was
`TypeError`, the class of an argument type error, before milestone 4).

A binding MUST raise the same group in the same situation. An edit that raises a `bad text error`
MUST leave every document unchanged. A `detached error` is raised by every member of a detached
handle, edits included, before any other check.

**Every bad name is a misuse error**, through one check per kind of name, the same from every member that takes
one (kno-umh.7): a variable or override name that does not match the `variable name` pattern (`load`'s `overrides`,
`set override`, a variable's `rename`); a name the grammar's `nameText` entry rule refuses (a name that is not one
`WORD`: not one word, or a word that starts with a digit, `-` or `@`), for a directive's `rename` and for an
extension's name at `make processor` (5); and an extension name that is reserved (2.5) or already taken. Since
milestone 5 no directive name is reserved (2.5): a directive may be renamed `use` or `include`, and `rename ("@set")`
is refused by `nameText` alone. A name that is well formed but collides with a line already there (a variable
`rename` that would make a second `set` of a name in its block, E5002) is a `bad text error`: the document decides
it.

**`bad text error`** has `diagnostics`: a list of syntax-layer `diagnostic`s (2.3) whose spans
count from the start of the text the edit was given (0-based lines, columns in the binding's string unit), never
from the document. Its message is built from them: a summary, then each diagnostic's people form (2.3), joined by
`; ` (Python `str (error)`, TypeScript `error.message`): `bad text: 1:2: E2001: unexpected token: ";"`. It never
shows text the program did not give.

**Entry rules** (kno-umh.3). Every check of a given text's **shape** (which tokens it may hold and in what order) is
the grammar's: a binding parses the text with the entry rule of [grammar/Knobly.g4](../grammar/Knobly.g4) the
table names, with the generated parser, never by splicing it into a probe document and never with a scanner of its
own. What a text **means** is checked after that, on the entry rule's tree, by the **text-alone rules** of this page,
each with one home here: the statement rules E5002, E5005 and E5009 to E5011 (6.5), the rule that a values text with
no value is empty (below), and the override's two rules (6.3: no `$name`, at least one value). (Milestone 5, the
milestone 4 leftover: these were called checks of the grammar, though the override's rules and the statement rules
are not shapes. An `overrideText` entry rule would need a second, variable-free copy of the value rules in the
grammar, a second home for them, so the rule here is reworded instead.) The entry rule's
diagnostics are its parse's first error, coded as in a document (2.4: E1xxx for an error token, E2004, E2007,
E2009, E2010 for nesting past `MAX_NESTING` (2.5), else E2001) and placed at the offending token, or at the end of the
text when the text ends too soon. Which
codes each edit checks, and where it places them:

| Edit | Codes | Placed at |
|---|---|---|
| `replace with text`, `insert statements`, `add statements` (statements) | the `statementsText` entry rule (so a byte-order mark is refused: it is allowed only at the start of a document); then the text-alone rules (E5002, E5005, E5009, E5010, E5011) for every statement the new text touches, checked in the document as it would be after the edit | the syntax diagnostic's span; a rule's fault at its place in the given text, or 0:0 when the fault lies in a statement already there (a `set` inserted before an existing `set` of the same name) |
| `replace with text` (a value that is not a list item), `set` (a statement, a `set variable`) | the `valuesText` entry rule (so a `;`, a block, or a comment the text ends in is refused); then, for `set`, a text with no value MUST be empty (E2001 at 0:0: `set ("")` clears the values, `set ("# c\n")` and `set ("\n")` are refused, milestone 5); then the same text-alone rules | the entry rule's diagnostic; as above |
| `replace with text` (a list item) | the `itemsText` entry rule (values separated by `,`, no trailing `,`), then the same text-alone rules | as above |
| `set` (a written value that is not a slice's bound or name, list items included, milestone 5) | the `valueText` entry rule: exactly one value (so `"1 2"` is refused at the `2`, and `""` at 0:0), then the same text-alone rules | the entry rule's diagnostic; as above |
| a slice or index bound's `set` or `replace with text` | the `boundText` entry rule: exactly one integer word or `$name` | the entry rule's diagnostic (E2001 at 0:0 for anything else) |
| a slice or index name's `set` or `replace with text` (milestone 5) | the `sliceNameText` entry rule: exactly one word that may name a slice (a `WORD` or `AT_WORD`) or a `$name` | the entry rule's diagnostic |
| `set` on a `set line` with empty text; `remove` of a `set` line's last value | E5009 | 0:0 (of an empty text) |
| `rename` (a directive) | none: a bad name is a misuse error (above); an extension line has no `rename` | |
| `rename` (a variable) | E5002 when it would make a second `set` of a name in its block (a bad name is a misuse error) | 0:0 |
| `set override`, and each override `load` takes (the check of an override, 6.3) | the `valuesText` entry rule (so `"1;"` is refused at its `;` and `"1 # c"` at the text's end; `"1\n2"` is two values), then E2001 at a `$name`, or at 0:0 for no value | as stated |

**An edit that would nest the document past `MAX_NESTING`** (bead kno-bzv.8; owner, 2026-10-30, to the
recommendation that such an edit be refused as a bad text error with the document left unchanged: "Yes"). The entry
rule counts levels in the given text alone; where the text goes adds the levels around it. So every edit but a
document's `replace with text` (`remove` and `rename` included) also parses the document as it would be after the
edit, and when that nests past `MAX_NESTING` (2.5) it is refused: a `bad text error` with one diagnostic, E2010, at
the `{` or `[` of the given text that would open the level past the limit, or at 0:0 when that bracket is not in the
given text (the document was already past the limit). This check comes after the entry rule and before the
text-alone rules, which need the tree the limit takes away. Every edit that writes a `{` or `[` can so deepen a document: a
statement's `replace with text`, `insert statements`, `add statements`, `insert before`, `insert after`, a
statement's, variable's or value's `set`, and a value's `replace with text`, list items included. A document's
`replace with text` is not refused: it takes any text (6.4), and a text past the limit then parses as 2.5 says. So
no edit but that one leaves a document whose tree the limit took away; one already past it accepts only an edit that
brings it back within the limit (a `remove`, a `replace with text`). Cases `nest-edit-*` (written corpus: one per
edit that can deepen, each limit's last level accepted, and a document already past the limit).

**A values text and line breaks** (milestone 4). A line break is whitespace (owner, 2026-10-29, round 15 question
1: "';' is required and a line break is plain whitespace (nginx); directive names cannot start with a digit or
'-'"), so a values text may hold line breaks anywhere: `set ("1\n2")` on `port 80;` writes `port 1\n2;`, one
statement with two values. The line-break half of the old check of a values text (kno-5ya) is deleted. Cases:
`set-line-break`, `set-line-break-trailing`, `set-line-break-leading`, `set-line-break-in-list`,
`value-replace-line-break`, `set-override-line-break`, `set-override-trailing-line-break`, `set-wrapped-values`;
`set-override-blank-line-break` (`"  \n"` holds no value: E2001 at 0:0).

**A comment the text ends in** (kno-033) is still refused: a comment runs to the end of its line, so the statement's
`;` (or a list's `,` or `]`) written after it would become part of the comment. The grammar says so: in a `gap` a
`COMMENT` is always followed by a `NEWLINE`, so the entry rules refuse a text whose last token is a comment, with
E2001 at the text's end (the token the rule wanted is missing there), or E2004 inside an open `[`. A comment a line
break follows is allowed (`"1 # c\n"` writes `port 1 # c\n;`). Earlier problems win, since the entry rule reports
its first error (`"1; # c"` at its `;`). Cases: `set-comment`, `set-line-comment`, `value-replace-comment`,
`list-item-replace-comment`, `set-override-comment`, `set-comment-line-break`, `set-comment-in-list`,
`set-comment-after-line-break`, `set-comment-after-semicolon`, `set-comment-after-syntax-error`.

**A values text with no value** (milestone 5, the milestone 4 leftover; a design call the owner may revise). A
statement's `set (text)` with a text that holds no value MUST be given empty text: `set ("")` clears the values
(`port 80;` becomes `port;`), and any other text with no value, a comment or a line break alone, is a `bad text
error` E2001 at 0:0 (`set ("# c\n")` wrote `a # c\n;`, a directive whose only content is a comment, before). On a
`set line` an empty text stays E5009. An override with no value was already refused (6.3). Case:
`set-comment-only-refused`.

A `diagnostic error`, `read error`, `save error` and `lost update error` have the fields of 2.6, 4.2 and 6.8.

> **Proposed (pending owner), for languages that report errors as values (Go, Rust):** a member that
> reads a fact (a property in the TypeScript sense: `text`, `name`, `values`) returns the bare
> value and panics with the program-bug group when it cannot (a detached handle); every operation
> that can end in an expected outcome returns it as an error value. So edits, `load`, `read`,
> `save`, `addresses`, `diff` and the readers return errors (`error (...)` already returns one) (a detached handle's edit returns a
> `detached error`, since the edit already returns an error), and only misuse, index out of range
> and detached getters panic. The binding guide (section 3) carries the per-language form.


### 2.9 Expanded value and its readers

An `expanded value` is one value after expansion: a `$name` has already become its value or values. The low level
owns it (kno-umh.8: the low level is the one owner of expansion): it is what an `extension use` holds (5), what a
`directive expansion`'s `values` are (6.10), and the very objects a rendered directive's `values` are (7.2), so the
readers have one home. (Before milestone 4 it sat in a shared layer beside two more families, `value expansion` and
the rendered `argument`, that copied it: round 15, root cause C.) It is a union of five variants (2.10), one per
value kind without `reference`:

| Variant | `kind` | Adds | Python `__match_args__` |
|---|---|---|---|
| `expanded word` | `word` | | `("text",)` |
| `expanded string` | `string` | | `("text",)` |
| `expanded list` | `list` | `items` (expanded values, in order) | `("items",)` |
| `expanded slice` | `slice` | `name` (text), `start`, `end` (integers, each absent when not written) | `("name", "start", "end")` |
| `expanded index` | `index` | `name` (text), `index` (integer) | `("name", "index")` |

Every variant has `kind`, `text` (canonical, below), `origin` (2.2), three links to the lines it came through, the
readers below and `error (message, code)`. It is a snapshot (worked out once per expansion) that holds live
handles:

- `written`: the written value on **the same line**, the line of the statement this value is read in. For a value
  that came through a variable it is the `$name` there (`chain[0].reference`: for `max_count $pixels;`, the
  `$pixels` on `max_count`'s line); a list item that came through a variable shares its list's `$name`; otherwise it
  is the value itself, which is also its `definition`. Never absent. Editing it edits that one written line and no
  other (`replace with text` on that `$pixels` unbinds it from the variable), but every copy of the line shares it:
  a file included twice has one line read in both copies (`statement`'s `copies ()`, 6.5), so the edit shows in
  both. A written value's `set (text)` keeps the handle (6.1, 6.6), so a loop over a render that edits each copy's
  `written` meets the shared handle twice and both edits succeed, the second writing the same text again (owner,
  2026-10-29: "the natural loop should work. i figured that they were references anyway, so both nodes essentially
  held the same pointer and editing either was fine"). To change one copy only, edit what that copy is given (its
  include block's `set` line, at the include step of `chain`).
- `definition`: the written value at the **end of the chain** (for `$pixels`, the `2284` in its `set` line); absent
  for an override. Editing it changes every use.
- `chain`: one `reference resolution` per variable step of `origin.via`, from the value's own line toward where it
  is written: `[0]` is the `$name` on the directive's line. Empty when the value is read where it is written.

An `expanded list`'s `items` are expanded values, each with its own links.

**Canonical text** (the same bytes in every binding): a word as written; a string as `"`, its
decoded text with `\`, `"`, newline, tab and carriage return escaped, then `"` (a single-quoted string's text is
its raw text, so `'C:\new'` is `"C:\\new"`); a slice `name[start~end]` (either side may be empty) and an index
`name[i]` with decimal integers, `name` the word the slice's name holds; a list
`[`, its items' texts joined by `, `, then `]`. Comments and line breaks are never part of it. Two
values are the same exactly when their texts are equal: a language with an equality operator that a type defines
MUST make it compare the texts (Python `==` and `hash ()` on `text`, kno-umh.12; before milestone 4 Python compared
identity). TypeScript has no such operator: a program compares `a.text === b.text`.

Readers are on **every** variant (each raises a `diagnostic error` with the code shown). They are the one place a
kind is checked at run time, because the config text decides it, not the program: a program asks for a list where
the user wrote a word, and the user gets a located E4002. Everything else about a kind is in the types (2.10).

| Spec name | Returns | Codes |
|---|---|---|
| `word` | a bare word's text | E4002 |
| `string` | a word or string, decoded | E4002 for a list, slice or index |
| `number` | a word spelling a number (below) | E4002, E4004 |
| `integer` | a word spelling an integer (below) | E4002, E4005 |
| `boolean` | the word `true` or `false` | E4002, E4006 |
| `list` | a list's items, each an expanded value with its own origin and links; the same as the list variant's `items` | E4002 |
| `slice` | a `slice value` (`name`, optional `start`, optional `end`) or an `index value` (`name`, `index`) | E4002 |
| `error (message, code)` | a `diagnostic error` placed on this value; for an override, on the `$name` that used it | misuse error for a code without `/` |

Quoting means text: `"8080"` and `"true"` are strings. Only a bare word is read as a number or a
boolean, and only when the program asks: a word is untyped until a reader decides what it is. There is no reader
that guesses (milestone 5 deletes `plain`; owner, 2026-10-29: "agreed. the raw strings are raw/plain/tokens until
some schema-aware layer decides "this one is a number" or "this is a string""). The typed readers stay, since they
are the program deciding.

The readers' names are the spec words in each binding's casing, and nothing else (kno-gxu): `word`, `string`,
`number`, `integer`, `boolean`, `list`, `slice`, in Python as in TypeScript. (Before milestone 2, Python
spelled them `as_word` ... `as_slice`, and the list reader was `items ()`; `items` is now the list variants'
property, the same shape as the written `list`'s `items`, 6.6.) In Python, inside a class body that defines `list`
or `slice`, annotate the builtins as `builtins.list` and `builtins.slice`, as for `set` (6.5).

**Number and integer words.** Their spelling is `NumberText` and `IntegerText` in
`grammar/knobly.ebnf` (copied here for reading); the range and the result types are ruled here, and the values
at the edges (zero, beyond 2^53-1, beyond the double range) in [contract.md 3](contract.md#3-numbers).

- A number word is a JSON number (RFC 8259 section 6), the whole word: `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`.
  `8080`, `0.5`, `-1`, `1e3` and `1.0` are numbers; `+1`, `007`, `.5`, `1.` and `20hz` are not.
  `number` returns an IEEE 754 double (TypeScript `number`; Python `int` when the word has no
  fraction or exponent and lies within ±(2^53-1), else `float`, so both read the same value).
- A number word whose value is beyond the double range (`1e400`) is not a number (E4004). No reader returns
  negative zero: `-0` reads as `0` ([contract.md 3](contract.md#3-numbers)).
- An integer word is `-?(0|[1-9][0-9]*)` whose value lies within ±(2^53-1) (the range a double holds
  exactly). `1.0`, `1e3`, `+1` and `007` are not integers; `9007199254740992` is not either (E4005).
  `integer` returns a whole number; a binding MAY use a 64-bit integer type, since every value fits.
- Slice and index bounds are integer words, or E4001. A slice's or index's name through a variable is one word,
  or E4007.

### 2.10 Closed lists and variants

Every closed set of the API is one named list in [schema/api.json](schema/api.json) (`kinds`), with lowercase
values (round 13 root cause 3). The one exception is `token kind`, whose values are the grammar's token names
(`WORD`, `BAD_CHAR`) because the grammar is their one home. Each list is generated into each binding as a real
enumeration (milestone 6, bead kno-umh.11; owner, 2026-10-29, asked for "proper enumerations instead of hardcoded
strings" and picked "Yes, generate both"):

- **TypeScript:** an `as const` object and the string-literal union derived from it, under one name:
  `export const StatementKind = { Directive: "directive", ..., Set: "set", ... } as const;` and
  `export type StatementKind = (typeof StatementKind)[keyof typeof StatementKind];`. A program may write either
  `s.kind === StatementKind.Set` or `s.kind === "set"`: both are checked by the compiler and both narrow. Not a
  TypeScript `enum` (a nominal type with its own run-time object, outside the language's erasable subset). Keys are
  the value in PascalCase (`StatementKind.Set`); `TokenKind`'s keys are the token names (`TokenKind.WORD`).
- **Python:** a `StrEnum` (`StatementKind.SET`, whose value is `"set"`), as before.
- **Inside each binding** a `kind`, `reason` or `code` is compared only with a member, never with a string literal,
  so a renamed or misspelled value fails to compile (TypeScript) or to import (Python) instead of comparing false
  (Python's `s.kind == "sett"` passes `mypy --strict` against a `StrEnum`). A lint refuses the literal form in both
  bindings (codegen.md section 7). Programs using a binding are free to write either form.

This reverses the milestone 2 rule ("no TypeScript constant objects"), which made the string-literal type the only
spelling. No binding spells a list any other way: no Python `Literal` aliases, no classes told apart without a
`kind`. `DiagnosticCode` has the same two forms (an `as const` object keyed by each code's name in PascalCase, and
the union of the `E` codes).

A list is one of two sorts (the schema's `sort`):

- **A variant set**, whose members have different members or operations: `statement kind`, `value kind`, `variable
  kind`, `place kind`, `change kind`. **Every variant is its own type** (a member of a TypeScript discriminated
  union; a Python class), and **every variant carries `kind`** typed by the list, holding its own value. The union
  has the members every variant has; a variant adds its own. **An operation exists only on the variants where it can
  succeed**: nothing is left to refuse at run time for a type the checker could have caught (so `no set line
  error` is gone, 6.7). The readers of 2.9 stay on every value variant: they report a problem in the config text,
  not a misused type.
- **A tag**, whose members share one shape: `token kind` (`token`), `node kind` (`node`), `step kind` (`step`),
  `unreadable reason` (`unreadable expansion`). One type, whose `kind` or `reason` is typed by the list.

The variant types, per layer:

| List | Low level (written) | Shared | Rendered |
|---|---|---|---|
| `statement kind` | `written directive`, `extension line`, `set line`, `snippet line`, `use line`, `unreadable line` (6.5) | | |
| `value kind` | `word`, `string`, `list`, `slice`, `index`, `reference` (6.6); `expanded word`, `expanded string`, `expanded list`, `expanded slice`, `expanded index` (2.9) | | (the expanded values, 7.2) |
| `variable kind` | `set variable`, `parameter`, `override variable` (6.7) | | |
| `place kind` | | `place`, `override` (2.2) | |
| `change kind` | | | `added`, `removed`, `changed`, `unknown` (7.6) |

**Python matching.** Every variant class has `__match_args__`, and a concept found in two layers keeps **the same
field order in every layer**, so `match` works on the low level as on the rendered tree: a written directive and a
rendered directive are both `("name", "values", "block")`; a written `list` and an `expanded list` are both
`("items",)`. Each section gives its order; the schema (`match args`) holds them all.

**TypeScript narrowing.** A union narrows on `kind`; a program never casts (`as SetLine`). A filter narrows too,
since TypeScript infers the predicate: `[...block].filter((s) => s.kind === StatementKind.Set)` is `SetLine[]`.

### 2.11 Blocks: one shape in every layer

A block is the statements or directives of one level, in written order (milestone 6, bead kno-umh.13; owner,
2026-10-29, "Yes, rename now", for "one block shape (iterate, index, directives(name), walk) in every layer"). Every
block has the same members, whatever it holds:

| Member | Contract |
|---|---|
| `iterate` | its items in written order (TypeScript `Symbol.iterator`, so `for...of` and `[...block]`; Python `__iter__`) |
| `count` | how many items (TypeScript `length`; Python `len(block)`) |
| `at (index)` | the item at a 0-based index (TypeScript `at(i)`, absent out of range, as an array's `at`; Python `block[i]`, `IndexError` out of range, as a `Sequence`) |
| `directives (name?)` | its directives, of that name when given, in written order |
| `walk` | every item at any depth below it, depth-first in written order (7.5's order; the block's owner is not visited): TypeScript `walk(visit)`, the callback returning `"skip"` (`WalkControl.Skip`) or `"stop"`; Python `walk(*, descend=None)`, a generator |

The three blocks:

| Block | Layer | Items | `directives (name?)` gives | Where |
|---|---|---|---|---|
| `written block` | written | statements (6.5) | `written directive`s | a document's `block`, a written directive's, extension line's or snippet line's `block` |
| `expansion block` | written | `directive expansion`s (6.10) | the same | an expansion's `block`, a directive expansion's `block` |
| `rendered block` | rendered | `directive`s (7.2) | the same | a render's `block`, a directive's `block` |

A written block is live (a handle: it follows edits, and its items are worked out from the current text when
asked); the expansion and rendered blocks are snapshots of one working-out. The syntax layer has no block: a
`block` node is a node like any other, with `children` (3.2).


## 3. Syntax layer

Read-only, one text at a time, no I/O. Covered by the syntax conformance cases (section 9).

### 3.1 Tokens

- A `token` has `kind` (from the `token kind` list), `text` and `span`.
- `token kind` values are the token names of `grammar/Knobly.g4`: `BOM`, `SPACE`, `NEWLINE`,
  `COMMENT`, `VARIABLE`, `WORD`, `AT_WORD`, `INTEGER`, `DIGIT_WORD`, `STRING`, `LBRACE`, `RBRACE`, `LBRACK`,
  `RBRACK`, `SEMI`, `COMMA`, `TILDE`, and the error tokens `UNTERMINATED_STRING`, `BAD_ESCAPE`, `LONE_DOLLAR`,
  `BAD_CHAR` (21 kinds). The grammar is the one source of these names. (Milestone 5: `AT_WORD` and `TILDE` are new,
  `COLON` is gone.)
- A bare word is one of four tokens: `WORD` starts with a letter or one of `_ . / * ?` (the only word a directive
  name can be); `AT_WORD` is `@` and the word characters after it (`@set`, `@include`, `@daily`: the keyword of a
  language or extension statement at a statement's start, 6.5, and a plain word anywhere else); `INTEGER` is
  `-?(0|[1-9][0-9]*)` (`IntegerText`, the only literal slice or index bound); `DIGIT_WORD` is every other word that
  starts with a digit or `-` (`1.5`, `20hz`, `007`, `-x`, `-`, `07:30`). All four are the value kind `word` (6.6,
  2.9). After its first character every word may hold letters, digits and `_ . / @ # + : * ? -`: so `:` is a word
  character in every word (`07:30`, `00:1a:2b:3c:4d:5e`, `127.0.0.1:3000`), and a word cannot start with `:`
  (`:80` is E1003 at the `:`); a value that starts with `:` is quoted (nginx `listen "[::]:80";`, `"::1:80"`;
  owner, 2026-10-30, bead kno-umh.15: "If the tradeoff is that those strings require quotes, let's go with that"). Milestone 5 (owner, 2026-10-29, bead kno-umh.14: "yes" to a slice separator outside
  the word alphabet); before it `:` was the slice separator and could not follow a digit word's digits.
- A slice or index is a **slice name** touching `[`, its bounds, then `]` (grammar `slicedWord : sliceName '['
  bounds ']'`). The slice name is a `WORD`, an `AT_WORD` or a `VARIABLE` (milestone 5: a variable may be
  subscripted wherever a name can stand, a snippet's parameter included, `$src[0~3]`). The separator between two
  bounds is `~`, the `TILDE` token: `name[1~3]`, `name[~3]`, `name[1~]`, and `name[1]` is an index. The owner's
  proposed spelling `..` cannot lex next to number-like words: `..` is already a `WORD` (`../conf`), and longest
  match reads `1..3` as one `DIGIT_WORD`, so a `..` token would overlap `WORD` (`tools/g4overlap.py` reports
  `WORD / DOTDOT`). `~` is the closest spelling outside the word alphabet that reads as a range; a `~` anywhere but
  between a slice's bounds is E2001 (it was `BAD_CHAR`, E1003). The cost: `~` can never be a word character
  (`~/conf` must be quoted).
- A double-quoted `STRING` holds only the six escapes `\\ \" \' \n \t \r`; a closed double-quoted string with any
  other is one `BAD_ESCAPE` token (E1005). A **single-quoted** string is raw (TOML's literal string; owner,
  2026-10-29, bead kno-umh.14: "yes"): its text is exactly what is typed between the quotes, a backslash is a plain
  character, and it cannot hold `'`, a line break or a control character (`'C:\new'` is the text `C:\new`; `'x\'`
  is the text `x\`). Its unterminated form runs to the end of the line (E1001).
- The tokens of one parse MUST be contiguous and in source order, and their texts joined MUST equal
  the input exactly, for valid and broken input alike. There is no end-of-file token. No token's
  text is empty, and each token's text length equals its span's length.

### 3.2 Nodes

- A `node` has `kind` (from the `node kind` list: `document`, `directive`, `block`, `list`,
  `slice`, `error`), a token range `start`/`end` (half-open indices into the tokens) and `children`.
- Children are in source order, do not overlap, and lie inside the parent's range. Tokens not
  covered by a child belong to the node itself.
- A `directive` node starts at its name token and ends with its `;` or its block's `}`. A `slice` node spans
  `name[bounds]` exactly. An `error` node has no children.
- **A statement ends with `;` or a block**; a line break is whitespace (grammar `directive : header (';' |
  block)`). A statement the parser cannot read is one `error` node, from its first token to where recovery resumes,
  and the diagnostic is its first error. Recovery skips to the end of the bad statement: its `;` outside brackets,
  or a whole block it opens, and it stops before the `}` that closes the enclosing block (or consumes a stray `}` at
  the top level, which ends the statement). A directive whose block was opened keeps its node, and its block's
  statements are read (an unclosed block at the end of the text is E2003, below). So a broken statement never hides a
  later statement after its `;` (`rec-*` syntax cases), but an unterminated string or a missing `;` runs on to the
  next `;` (`unterminated`, `load-missing-semicolon`).
- **The end of the text.** A statement still open when the text ends has its first error there: E2004 when a list's
  `[` is open, else E2003 when a block is open around it, else E2001 (a top-level statement's `;` or block is due).
  When the text ends between statements inside open blocks, E2003 is reported once, at the end of the text, however
  many blocks are open. A statement whose error node runs to the end of the text (recovery found no `;` or block that
  ends it) carries only its first error, so no E2003 follows for the blocks still open around it. So `a { b [1;` is
  E2001 at 0:8 alone, `a { b [1` is E2004 at 0:8, `a {\n b 1\n` is E2003 at 2:0, and `a { b { c 1;` is one E2003
  (cases `nest-skipped-list`, `nest-recovered-100`).

### 3.3 Operations

| Spec name | Inputs | Output | Errors |
|---|---|---|---|
| `parse` | text | `syntax`: `tokens`, `root` (a `document` node over every token), `diagnostics` (in source order of their spans' starts, the order the parser reaches them) | none: total for any string, never reads files |
| `span of` | syntax, token range | the range's span; an empty range at `i` is zero-width at token `i`'s start, or at the text's end when `i` is the token count | index out of range when the range is outside `[0, count]` or `start > end` |
| `text of` | syntax, token range | the exact source text; `text of(syntax, root)` is the whole input | as `span of` |

`diagnostics` MUST be empty exactly when the input is in the grammar's language.

The grammar's entry rules `statementsText`, `valuesText`, `valueText`, `itemsText`, `boundText`, `sliceNameText` and
`nameText` (2.8) are parsed with the same
generated parser and the same recovery and codes. They are not part of the syntax layer's public API: the edits
and the check of an override call them.

## 4. Ports: where files come from and go to

The core MUST NOT do I/O. Files come in through a `document source` and go out through a `document
writer` that the program supplies.

### 4.1 Document source

- `resolve (spec, load context)` returns the resolved paths a spec names (a path, or a glob with `*`
  and `?` in its last segment), in any order: the core sorts them (below). Empty means "not found"
  (E3001). A failure becomes E3004. Both codes are placed at the extension line's name (for
  include, the word `include`).
- `read (resolved path)` returns the text of one resolved file. A failure becomes E3004 at the extension line, or
  for the root file makes `load` fail with a `read error` (no code: [contract.md 4](contract.md#4-errors)).
- A `load context` has `parent path`: the resolved path of the file holding the extension line, or
  empty when the root path itself is resolved.
- A load MUST call `read` at most once per resolved path, however many places splice the file in.
  A failure is kept: a later `read` does not retry it.
- **Order:** for every extension, the core resolves the specs in the order `specs` returned them,
  stops at the first spec that fails or matches nothing, and sorts each spec's paths by Unicode code
  point (scalar value) order, comparing whole paths; the spliced files are the specs' sorted paths in
  turn. Code-point order is not UTF-16 code-unit order (a character above U+FFFF sorts after U+FFFF
  here, before U+E000 in a plain JavaScript sort). No conformance case has such a path yet.
- In a binding whose I/O is asynchronous, both operations MAY be asynchronous.
- **Results are checked at run time** (kno-umh.12): `resolve` MUST return a list of texts. Anything else, a bare
  text included (in Python a `str` is a sequence of one-letter strings), is the source's failure: E3004 at the
  extension line, or a `read error` for the root. `read` MUST return a text, the same way. Python types these
  results `tuple[str, ...]` and `str` and refuses a bare `str` where a tuple is due; a type checker alone does not
  catch it.
- **Concurrency:** no binding makes a graph or its handles safe for concurrent use. Even `render
  (graph)` writes the graph's cache of what it worked out, so a binding with threads MUST NOT promise that
  two renders of one graph, or a render beside an edit, may run at once, unless it adds the locking
  itself and says so.

> **Proposed (pending owner), for languages with cancellation (Go's `context.Context`, .NET's
> `CancellationToken`):** cancellation or a deadline ends `load`, `read` or `save` with the
> language's cancellation error and is never turned into a diagnostic (E3004) or kept as a failed
> read, since it says nothing about the file. Today the rule above would turn it into E3004.

### 4.2 Document writer

- `write (files)` takes one batch of `file write` records and commits them together. A failure
  while staging means nothing was committed. A writer that can fail part way through committing
  leaves the files it committed changed while their `saved text` stays the old one, so the next save
  treats them as lost updates until the program reloads (a stated cost).
- A `file write` has `resolved path`, `text` (what to write) and `saved text` (the document's
  last-read or last-saved text, to compare with the disk and find a lost update).
- **A lost update** is a file the batch would write whose text in the medium now differs from its `saved text`
  (someone changed it since it was read). Every writer MUST refuse a batch that holds one, before it writes
  anything, with a `lost update error` (2.8) whose `paths` are exactly the conflicting files, in batch order (not
  every file of the batch). There is **one check**, `check lost updates (files, current)`, a pure function of the
  io layer that every writer calls: given the batch and each file's text in the medium now (absent, read as empty
  text, when the file does not exist), it raises the `lost update error` or returns. A `current` list that is not as long
  as the batch is a misuse error (2.8), raised before any comparison. A program's own writer calls it
  too. `save` raises a `lost update error` from the writer as it is (it is already a `save error`), never wrapped.
  Prior art: HTTP's conditional requests (RFC 9110 13.1.1, `If-Match`) and optimistic concurrency.

### 4.3 Adapters

| Spec name | Port | Required | Notes |
|---|---|---|---|
| `memory source` | source | MUST | Texts keyed by path, read from the map it was given at every call (never a copy). `resolve` joins the spec to the directory of `parent path` by POSIX rules (`/` separators, `.` and `..` removed, a leading `/` taken as is) and returns the path when it is a key; a glob returns every key in that directory it matches (below). `read` of a missing key fails. Pure. |
| `memory writer` | writer | MUST | Writes each batch into the map it was given (the one a memory source reads), all or nothing: `check lost updates` with each file's text in the map first. |

The glob rule, shared by every source that takes globs: a spec is a glob when it holds `*` or `?`.
Only the last path segment is matched: `*` matches any run of characters (empty included), `?`
exactly one, every other character itself; nothing can be escaped. Neither can match `/`, since the
directory part is compared as written, so a `*` or `?` in an earlier segment matches only a
directory literally named so. A leading `.` gets no special treatment (`*.conf` matches
`.hidden.conf`). The root path may be a glob, but `load` fails with a `read error` unless it
resolves to exactly one file.
| `file source` | source | MUST | The local filesystem. |
| `file writer` | writer | MUST | The local filesystem: `check lost updates` with each file's text on disk first, then the staged write. |
| `fetch source`, `fetch writer` | both | MAY | HTTP. TypeScript only today. The fetch writer, per file: `GET` its URL, `check lost updates` with the body (a 404 is absent), then `PUT` (or the configured method) with the precondition `If-Match: <the GET's ETag>` when the GET gave one; a `412 Precondition Failed` is a lost update of that file. Without an ETag the window between the GET and the PUT stays open (a stated cost: the server cannot enforce it). |

Each adapter is named after its medium and its port, and every binding ships the memory and file adapters for both
ports; the names in each binding are [contract.md 5](contract.md#5-adapters).

## 5. Extensions

An `extension` owns one directive name and turns each use of it into specs of files to splice in its
place. It is not part of the core; a program turns it on when it makes the processor. The extension port, the
`extension use` and the include extension belong to the low level (the written layer, kno-umh.8): an extension is
pure, and the low level is the one owner of expansion. (Before milestone 4 they sat in the io layer, beside the
ports that do I/O.)

- An extension has `directive` (the name it owns, without `@`: `include`) and `specs (extension use)`, which
  returns the specs for one use, in splice order. A line uses the extension when it is written `@` and that name
  (`@include "f.conf";`), never by the bare name: since milestone 5 `include "f.conf";` is a plain directive named
  `include`, whatever extensions are registered, and an `@name` no extension owns is E3008. It MUST be pure: the load resolves and reads the specs, parses
  each file once, applies the use's block of `set` lines to the spliced files, and enforces depth,
  cycles and limits.
- An `extension use` has `values` (the line's values, expanded, as `expanded value`s, 2.9: each one of the five
  variants, with its links) and `origin` (a directive origin). It names no rendered type.
- `specs` MUST return a list of texts; anything else, a bare text included, is a failure: E3006 at the directive's
  name (kno-umh.12). Python types it `tuple[str, ...]` and refuses a bare `str` at run time.
- `specs` throws a `diagnostic error` for a located failure. Any other failure becomes E3006 at the
  directive's name. (In a language with error values, a returned error that is not a diagnostic
  error; whether a panic is also caught is the binding's stated choice, binding guide section 3.)
- **Order of checks** on one extension line, each stopping the line (it becomes `unreadable`,
  kind per 2.4) before the next: its values are expanded (E5001, E4001, ...); its block is
  checked (a line other than `set` is E5012; a syntax error inside makes it kind `syntax`); `specs`
  is called; the specs are resolved and read (4.1); cycle (E5006) and depth (E5007) are checked.
  A line that stops before `specs` is never handed to the extension and names no file, so nothing is
  resolved or read for it and its `document edge` has empty `specs` and `targets`.
- Making a processor MUST refuse, with a misuse error, an extension whose name is reserved (2.5: `set`, `snippet`,
  `use`), already taken by another extension, or not a name the `nameText` entry rule takes (so `@` and the name are
  one `AT_WORD`; milestone 5); a name that is not text is an `argument type error` (2.8). The checks run in that
  order: the type, then `nameText` (the one directive-name check of 2.8, shared with `rename`), then reserved or
  taken.

**Layer direction** (owner, 2026-10-29: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"). Nothing below the rendered layer imports, names or
returns a rendered type: an `extension use` holds the low level's `expanded value`s (2.9), the graph has no
render member (6.3), and the processor returns only low-level objects. The rendered layer builds on
the layers below: `render (graph)` (7.0) takes a graph, a rendered directive holds its `directive expansion`'s
own objects (7.2), and rendered things name low-level handles (`written`, `graph`). Each binding checks the
direction mechanically (binding guide, rule 8). So a language whose packages cannot import each
other in a cycle (Go, Rust) can keep each layer in its own package or crate.

### 5.1 The include extension

`@include "path";` or `@include "path" { @set $name value; }`. The one value MUST be a quoted path or
glob. Otherwise E3005, placed on the first value when it is not quoted, else on the second value,
else (no value at all) on the `@include`. Matching files are spliced in the order of 4.1. What an included
file sees, and where its own `set` and `snippet` lines are visible, is [expansion.md](expansion.md) 3, 4 and 7.

## 6. Low level: the config as written

The low level is the files as written: editable, saved back. The `processor` only makes graphs;
the graph reads and saves itself (6.2, 6.3). The low level knows nothing of the rendered tree; the
rendered layer renders a graph (7.0).

**Design rule:** the texts and the overrides are the only source of truth. Copies, edges,
variables and resolutions are worked out from them when asked; the objects returned (`copy`,
`document edge`, `resolution`) are snapshots of one working-out, not handles. The only other state
is which files were read.

### 6.1 Handles and identity

- Each written thing (document, statement, value, variable) MUST be one object for the life of its
  graph: asking twice gives the same object (identity comparison holds).
- A handle follows its tokens across other edits.
- A handle whose tokens an edit removed, or whose document's whole text was replaced, is
  **detached**. Every member of a detached handle except `kind` MUST raise a `detached error`.
  A detached handle never comes back.
- Snapshots (`copy`, `document edge`, `resolution`, `reference resolution`) are plain data; the
  handles inside them are live.

**Which handles an edit keeps.** Every text edit replaces one range of one document's text. A
handle survives when its tokens lie wholly outside that range, or strictly contain it (a block's
statement survives an insert into the block); a handle whose tokens start inside the range
detaches, except the one a `rename` or a value's `set` keeps. Values, statements and parameters inside a detached
statement detach with it. Per edit:

| Edit | Range replaced | Survives although its tokens are touched | Detaches | Returns |
|---|---|---|---|---|
| statement `replace with text` | the statement with its owned comments | | it and everything in it | the new statements at its level, in order |
| statement `remove` | the same, plus its line when nothing else is on it | | it and everything in it | nothing |
| `insert statements`, `add statements` | an empty range at the insert point | | nothing | the new statements, in order |
| `set` (any statement) | its first value to its last (an empty range after the name when it has none) | the statement | every old value of it | nothing |
| value `set` (milestone 5) | the value | the value itself, and its statement and list | its old items, bounds and name | nothing |
| value `replace with text` | the value | its statement and list | it and its items or bounds | the new values, in order |
| value `remove` | the value and one separator | its statement and list | it and its items or bounds | nothing |
| directive `rename` | the name token | the directive | nothing | nothing |
| variable `rename` | the `$name` token in its `set` line or snippet | the variable and its line | nothing; references elsewhere keep their handles and are re-bound by name | nothing |
| document `replace with text` | the whole text | the document | every other handle into it | nothing |
| `set override` | no text | | nothing | nothing |

**A value's `set` keeps its handle** (milestone 5, the rest of bead kno-umh.12; owner, 2026-10-29: "the natural loop
should work. i figured that they were references anyway, so both nodes essentially held the same pointer and editing
either was fine"). `set (text)` on a written value replaces it with exactly one value (the `valueText` entry rule,
2.8) and edits in place: the same object stays in its statement's `values` (or its list's `items`, or as its slice's
bound or name), now holding the new text. The text is written as given, spaces around the value included, and the
handle is kept by the one value the text holds wherever in it that value starts (`set (" 5 ")`; case
`value-set-padded`). When the new value is of another kind (`$pixels` set to `2400` is a
`reference` that becomes a `word`; `80` set to `[1, 2]` becomes a `list`), the handle takes the new kind: its `kind`
and its type are the new kind's (TypeScript: the same object reports the new `kind`; Python: the object's class
becomes the new kind's class, as the state pattern does with `__class__` assignment, Python Cookbook recipe 8.19).
Its old items, bounds or name detach; its new ones are new handles. Setting it again, through any copy that shares
it, writes again and raises nothing. Prior art: the DOM's `textContent` and lxml's `element.text`, edits that keep
the node; a spreadsheet cell, which keeps its identity whatever kind of value it holds. Costs: in TypeScript a
variable narrowed on `kind` before the edit is stale after it (a program narrows again); in Python the six value
classes share one layout so the class can change. `replace with text` keeps its meaning (it may write several
values and detaches the handle).

An override variable is never detached: after `set override` removes its name it is no longer listed
by `variables ()` and resolves nowhere, and it is the same object again if the name is overridden
again later.

### 6.2 Processor

**Where operations live** (round 13 root cause 2; the owner's answer to question 1, 2026-10-29: he
first picked "B graph.render()", then clarified: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"):

1. The processor is the factory. It holds the document source and the extensions, and `load` is its
   only operation. It belongs to the low level and returns only low-level objects.
2. Every later operation is a method on the object the program holds, within that object's layer:
   the graph reads and saves itself (6.3); a render compares itself with another (7.1).
3. Going up a layer is a free function of the upper layer that takes the lower object: `render
   (graph)` (7.0). The low level has no render member and never imports, names or returns a
   rendered type (5, "Layer direction").
4. The graph keeps the document source and extensions it was loaded with. The core still does no
   I/O: the source is the program's, injected at `make processor`.
5. Nothing checks at run time which processor made a graph or a render: no operation takes one
   back to a processor. (The round 12 ownership check, D27, is retired.)

| Spec name | Inputs | Output | Errors |
|---|---|---|---|
| `make processor` | `source` (a document source), `extensions` (optional, in order) | a `processor` | argument type error for an extension name that is not text; misuse error for a malformed, reserved or repeated one (5) |
| `load` | root `path`; option `overrides` (name without `$` to `config text`, in order, 6.9) | a `document graph` | `read error` (with `paths`, the root path given) when the source cannot resolve the root to exactly one file or cannot read it; misuse error for a bad override name (not letters, digits and `_`: the one name check, 2.8); `argument type error` for an override that is not text; `bad text error` for an override's text the check of an override refuses (6.3). Never fails for anything in the files' text. |

- `load` resolves the root path through the source as an included file's spec is, so the root has
  one path in the graph. It reads every file that extension lines name, once each, repeating until
  nothing new is named.
- **Overrides** (owner, 2026-10-29, round 13 question 2: "A overrides"). An override wins over
  every `set` of its name, which acts as the default; where it does not win, and what it reaches, is
  [expansion.md](expansion.md) 6 and 7. `load`'s `overrides` option, the graph's
  `overrides` and `set override` (6.3), the variable kind `override` (6.7) and the place kind
  `override` (2.2) all use this one word.
- **Override order.** `overrides` is ordered: the graph's `overrides` and the override part of
  `variables ()` keep the order the program gave. A binding whose map type has no order (Go) takes
  an ordered input, such as a list of name and text pairs. `set override` keeps a changed name in
  its place and puts a new name, or one removed earlier, at the end. (A TypeScript plain object puts
  names made only of digits first, whatever order they were written in: a known gap.)
- Each override `load` takes goes through the check of an override (6.3), the same check `set
  override` uses, in the order given; the first refusal ends the load with that error, before any
  file is read.
- In a binding whose I/O is asynchronous, `load` and the graph's `read` and `save` MAY be
  asynchronous. `render` and `diff` MUST be synchronous and pure.

### 6.3 Document graph

| Member | Kind | Contract |
|---|---|---|
| `root` | property | the root `document` |
| `documents` | property | every document read, root first, then in first-read order; never shrinks. An ordered map from resolved path to `document`: a binding MUST offer both the ordered list and the lookup by path |
| `overrides` | property | the overrides by name (without `$`), each as `config text` (6.9), in order (6.2); never saved. Python spells it as an editable mapping (binding guide, section 3) |
| `set override (name, text or absent)` | method | add, change, or (with absent) remove one override without a reload. Checks `text` with the check of an override (below): `bad text error` located in `text`; `argument type error` when `text` is neither text nor absent; misuse error for a bad name |
| `read ()` | method, I/O | resolve and read what `unread ()` names, through the graph's document source, repeating until nothing new is named; keeps every text and every failure it already had. Returns the resolved paths this call read (newly, not those read before), in read order |
| `save (writer)` | method, I/O | 6.8 |
| `edges ()` | method | every copy of every extension line, in walk order, as `document edge`s |
| `unread ()` | method | the edges naming a spec not resolved or a file not read yet; each such copy is an `unreadable expansion` with reason `unread` and E3007 in `diagnostics` (6.10) |
| `variables (name?)` | method | every variable (of that name when given): set variables and parameters in document order (documents in `documents` order), then override variables in `overrides` order. Each is one of the three variable types (6.7) |
| `expand ()` | method | the `expansion` of the graph's current texts and overrides (6.10): every copy as read, with each value expanded and linked to the lines it came through. Pure: reads no file. What `render (graph)` builds on |
| `diagnostics` | property | each document's syntax diagnostics (documents in order), then every problem the low level finds, in walk order: **the one list** (kno-umh.8). The `expansion`'s and the `rendered` tree's `diagnostics` are this same list (6.10, 7.1); `x $nope;` shows E5001 here. No binding keeps a list of codes to leave out (round 12 decision D11, which made E4xxx, E5001, E5003, E5004 and E5008 render-only, is retired). A property, as on the render (glossary, "Properties and methods") |

**No render member.** The graph has no `render` member and names no rendered type. A program
renders it with the rendered layer's `render (graph)` (7.0), which turns the graph's public `expand ()` into the
rendered tree. A binding MUST NOT add a render member to the graph.

**The check of an override** (one check, one home: `load` and `set override` both use it, and both
raise the same errors; round 13 root cause 2). Given a name and a value:

1. The name MUST be letters, digits and `_`; otherwise a misuse error.
2. The value MUST be text; otherwise an `argument type error` (6.9).
3. The text is parsed with the grammar's `valuesText` entry rule (2.8). It is refused with a `bad text error`
   whose diagnostics are located in the given text: the entry rule's diagnostic; else E2001 at a `$name`, or at
   0:0 when it holds no value. (A bad escape, E1005, and a literal bound that is not an integer, E2007, are now
   the entry rule's; the old step 4, E4003 or E4001 from an override reader, is deleted.)

A literal slice or index bound beyond ±(2^53-1) in an override's text passes this check (the grammar cannot see a
number's size). It is E4001 at each `$name` that reads the override, found by the low level, with that `$name`'s
statement an `unreadable expansion` of reason `value`, as for a bound reached through a variable (2.4;
`load-override-bound-too-big`).

`"1;"` is refused (E2001 at 0:1), from `load` as from `set override`; `"1\n2"` is two values. (Before milestone 1,
`load` accepted `"1;"` with a different check: round 13 review, root cause 2.)

### 6.4 Document, edge, copy

`document`:

| Member | Contract |
|---|---|
| `resolved path` | its identity |
| `saved text` | the text as read, or as last handed to a writer that succeeded |
| `text` | the text now; differs from `saved text` exactly when there are unsaved changes |
| `syntax` | the syntax layer's result for `text` |
| `block` | a `written block` of its top-level statements |
| `included by ()` | the include copies that splice it in; empty for the root and for a file no include reaches now |
| `replace with text (text)` | replace the whole text; takes any text, broken or not. Every handle into the document detaches except the document's own; `saved text` is untouched |

`document edge` (snapshot): `copy` (whose `statement` is the extension line, editable), `specs` (as
the extension gave them; empty when the line stopped before `specs` was called, 5), `targets` (the
resolved paths of every file matched, as text, in splice order; empty when it failed or is
unread). A program finds the documents through `documents`.

`copy` (snapshot): `statement`, and `via` (the include and `use` steps that bring it there,
innermost first; empty at the root).

### 6.5 Statements

A `statement` is a union (2.10) over the `statement kind` list: `directive`, `extension`, `set`, `snippet`,
`use`, `unreadable`, one type per kind. Every statement has:

| Member | Contract |
|---|---|
| `kind` | from the list |
| `document` | the document holding it |
| `parent` | the statement whose block holds it (typed as a `statement`: a `written directive`, an extension line or a `snippet line`); absent at a document's top level |
| `place` | from its first owned token to its last, comments it owns included (below) |
| `text` | exact, with the comments it owns; without the indentation before it and the line break after it |
| `copies ()` | every place it is read now, in walk order; empty when no copy reaches it |
| `replace with text (text)` | replace it and its owned comments with zero or more statements; returns the new statements; this handle detaches. `bad text error` |
| `remove ()` | remove it with its owned comments, and its line when nothing else is on it; then it is detached |
| `insert before (text)` | insert statements before this one in its block: exactly its block's `insert statements (index of this one, text)`, with the same placement, indentation, checks and errors; returns the new statements |
| `insert after (text)` | the same after this one: `insert statements (index of this one + 1, text)`, so after its owned comments (round 13 review: "insertBefore/insertAfter, as PostCSS has") |

Per kind, each its own type (2.10):

| Kind | Type (spec name) | Extra members | Python `__match_args__` |
|---|---|---|---|
| `directive` | `written directive` | `name`; `values` (in order); `block` (absent when written without one); `rename (name)`: misuse error when the `nameText` entry rule refuses it (not one `WORD`: not one word, or a word that starts with a digit, `-` or `@`), 2.8; any other name is allowed, `use` and `include` among them (milestone 5: no directive name is reserved); `set (text)`: replace its values, comments between them included, `bad text error` | `("name", "values", "block")` |
| `extension` | `extension line` | `name` (the name an extension owns, without `@`: `include` for `@include`); `values` (an include line's path); `block` (absent when written without one; its `set` lines); `set (text)`. No `rename`: any new name would change its kind | `("name", "values", "block")` |
| `set` | `set line` | `variable` (a `set variable`); `values` (after the `$name`); `set (text)`: `bad text error`, also for empty text (E5009) | `("variable", "values")` |
| `snippet` | `snippet line` | `name`; `parameters` (`parameter`s); `block` (always present) | `("name", "parameters", "block")` |
| `use` | `use line` | `snippet name`; `snippet` (by where written: a `snippet` line above it in its file; absent when free); `snippets ()` (per copy, a `resolution` of which snippet it splices); `values` (bound to parameters by position); `set (text)` | `("snippet_name", "values")` |
| `unreadable` | `unreadable line` | none. A statement that does not parse, a malformed `set`/`snippet`/`use` line, a second `set` of a name in one block, or an `@name` no extension owns (E3008) | `("text",)` |

A statement's `parent` is a `written directive`, an `extension line` or a `snippet line`. A block's `directives
(name?)` lists `written directive`s only (kind `directive`), never extension lines.

**Which kind a statement is** (milestone 5, bead kno-umh.14; owner, 2026-10-29: "yes" to language statements behind
one sigil). Its first token decides, and nothing else does: a `WORD` heads a `written directive`, whatever the word
(`use epoll;` is a directive named `use`); an `AT_WORD` heads a language or extension statement: `@set $name
value...;` a `set line`, `@snippet name $p... { ... }` a `snippet line`, `@use name value...;` a `use line`, `@`
and a registered extension's name an `extension line` (`@include "f.conf";`), and any other `@name` an `unreadable
line` with E3008 (reason `extension`) at the `@name`. A malformed `@set`, `@snippet` or `@use` is E5009, E5010 or
E5011 as before. Before milestone 5 the words `set`, `snippet` and `use`, and each registered extension's name, were
reserved at the start of every line in every block.

**`set (text)`** replaces a statement's (or a variable's, 6.7) values with `text` (owner,
2026-10-29: "Can "set_values" become simply "set"?"). It is not the language's `set` keyword: on a
`set line` it replaces the values after the `$name` and the line stays a `set` line, and it never
makes a `set` line. A program that wants a variable to take a value without editing a file uses
`set override` (6.3), which keeps its own name.

Cost of the name (a design consequence of the owner's pick, not his words): one object graph now
uses the word three ways: the statement kind `set` (a `set line`), the variable kind `set` (a
`set variable`, declared by a `set` line) and the edit `set (text)`. On a `set line`, `set (text)` edits the
values of a `set` statement; an `override variable` has no `set` at all (an override has no line to edit: a program
uses `set override`). Docs keep saying "not the language's `set` line" where the edit is taught. Renaming the
variable kind (for example to `declared`) would separate the kind from the edit; it is not done here, since it
changes a kind value programs and the conformance cases print.

A `written block` (a document's top level, or a statement's block) is a block (2.11) of statements: iterated and
indexed in order, `directives (name?)` (its statements of kind `directive`, of that name when given) and `walk` (its
statements at any depth: a written directive's, extension line's and snippet line's blocks included). It adds:

| Member | Contract |
|---|---|
| `insert statements (index, text)` | insert before the statement at `index` (`index` equal to the count appends), placed and indented as below; returns the new statements. `bad text error`; index out of range |
| `add statements (text)` | `insert statements(count, text)` |

(Milestone 6 removed the `statements` member: the block itself is iterated and indexed, as in every layer.)

**Comment ownership** (round 12 decision D15, after LibCST's leading lines and Roslyn's trivia). A
statement owns:

- the comment after its last token on its own line (spaces between allowed);
- when the statement starts its line, the comment lines directly above it: each a line holding only
  spaces and one comment, taken upward until a line that is not one. A blank line stops it, so a
  comment separated by a blank line belongs to no statement, and so does a comment on the line of
  an opening `{` or after another statement's last token on its line (that one is the other
  statement's trailing comment).

A comment no statement owns stays where it is through every edit. Ownership is worked out again
after each edit, so a comment can come to be owned: statements inserted into a block that holds
only `# c` go below it on lines of their own, and the first one then owns `# c` (case
`insert-empty-block-lines`).

**Where inserted text goes, and how it is indented** (round 12 decision D14):

- The text's leading and trailing blank lines are dropped and its common indentation removed; each
  line then gets the indentation below, inner lines keeping their indentation relative to the
  others, and blank inner lines get none.
- Indentation: the leading whitespace (spaces and tabs, copied as they are) of the line where the
  block's **first** statement, with its owned comments, starts, whichever index is given. In an
  empty block: the line indentation of the statement that owns the block, plus the document's
  unit. The unit is the leading whitespace of the document's first line that starts with spaces or
  tabs followed by something else; four spaces when no line does. At a document's top level with
  no statements: no indentation.
- Place: before the statement at `index` and its owned comments, on lines of their own; when that
  statement shares its line with an earlier one, between the two, ending with a line break and the
  target's indentation. Appending goes after the last statement's owned range. Into `{}` (or only
  whitespace between the braces): the lines between `{` and `}`, then the parent's indentation
  before `}`. Into a block holding only comments: before the `}` line, or before `}` when it shares
  a line with a comment.
- Line breaks: every line break a statement edit adds is the document's first line break
  (`"\r\n"` or `"\n"`), or `"\n"` when it has none, and the line breaks inside the given
  statements text are replaced by it. A values text (`set`, a value's `replace with text`)
  goes in as given.

(Settled in milestone 2: `insert before` and `insert after` above; include lines as `extension line`; no cast is
needed, since a filter on `kind` narrows, 2.10. Settled in milestone 6: one block shape in every layer, 2.11.)

### 6.6 Values

A `written value` is a union (2.10) over the `value kind` list: `word`, `string`, `list`, `slice`, `index`,
`reference`, one type per kind. Every written value has:

| Member | Contract |
|---|---|
| `kind` | from the list |
| `text` | its exact source text |
| `place` | where it is written |
| `statement` | the statement holding it |
| `list` | the list it is an item of; absent otherwise |
| `set (text)` | milestone 5: replace it with exactly one value written as `config text`, keeping this handle (6.1): it stays the same object and takes the new value's kind. `bad text error` (the `valueText` entry rule; a slice bound takes `boundText`, a slice's name `sliceNameText`) |
| `replace with text (text)` | replace it with values written as `config text`: separated by spaces on a line, by commas in a list; returns the new values; this handle detaches. `bad text error` (a slice bound takes exactly one word or `$name`) |
| `remove ()` | remove it and its separator; then it is detached. `bad text error` when that breaks a rule (a `set` left with no value). A slice's or index's `name`, and a bound that is its slice's or index's only one (`b[1]`, `x[0~]`), refuse: a `misuse error`, the text unchanged (milestone 5; a design call the owner may revise: the other choice was to remove the whole slice). Case: `slice-name-and-only-bound-remove` |

Per kind:

| Kind | Extra members | Python `__match_args__` |
|---|---|---|
| `word` | none | `("text",)` |
| `string` | none | `("text",)` |
| `list` | `items` (written values, in order: a property, a tuple in Python, the same shape as an expanded list's `items`) | `("items",)` |
| `slice` | `name` (the slice name before `[`: a word or reference value, milestone 5), `start` and `end` (each a word or reference value, or absent) | `("name", "start", "end")` |
| `index` | `name` (a word or reference value) and `index` (a word or reference value) | `("name", "index")` |
| `reference` | `name` (without `$`), `declaration` (by where written: the nearest `set` above it in its file, a `set variable`, or its snippet's `parameter`; absent when free) and `resolutions ()` (one `reference resolution` per copy of its statement, in walk order) | `("name",)` |

In Python the six value classes are exported from `knobly.written` only, not from the package root: `List`
replaced `typing.List` on `from knobly import *`, and a bare `String` or `Index` reads as a general type, not a
written value. The glossary keeps the words, so the module gives the context (`written.List`, `written.String`;
binding guide rule 2), the same rule for all six.

### 6.7 Variables and resolutions

A `variable` is a union (2.10) over the `variable kind` list, one type per kind. Every variable has:

| Member | Contract |
|---|---|
| `kind`, `name` | |
| `references ()` | the references whose `declaration` it is, reached or not, in document order (always empty for an override variable: an override is never a declaration). Lexical only: a `$name` in an included file has no declaration (it is resolved per copy), so a variable used only there has no references; every use, per copy, is in `wins ()` and `shadowed at ()` |
| `wins ()` | the resolutions in which it wins, in walk order |
| `shadowed at ()` | the resolutions in which another variable wins, in walk order |

Per kind:

| Kind | Type | Extra members | Python `__match_args__` |
|---|---|---|---|
| `set` | `set variable` (a `set` line's `$name`) | `place` (its `$name`); `line` (its `set line`); `rename (name)`: its `$name` only; misuse error for a bad name, `bad text error` E5002 for a second `set` of the name in its block; `set (text)`: its `set` line's values, `bad text error` | `("name",)` |
| `parameter` | `parameter` (a snippet's) | `place`; `line` (its `snippet line`); `rename (name)` as above. No `set`: a parameter's values are the `use` line's (edit that line) | `("name",)` |
| `override` | `override variable` (an override, 6.2) | none: no place, no line, no `rename`, no `set`. A program changes it with the graph's `set override` | `("name",)` |

So the edits exist only where they can succeed (round 13 root cause 3): `NoSetLineError` is deleted, and calling
`set` on a parameter does not compile in TypeScript and is an `AttributeError` in Python, as for any missing
member.

A `resolution` (snapshot, at one copy): `copy`; `winner` (absent when nothing of that name is
visible there, which the low level reports as E5001 or E5003); `shadowed` (every other visible
definition, next first: the one that would win if the winner were gone). Which definitions are visible and which
wins is [expansion.md](expansion.md) 5 and 6.

A `reference resolution` adds `reference` and `values`: the winning `set` line's values, or for a
parameter the `use` line's values bound to it; empty for an override or when unbound. A reference
renders to all of `values` (`@set $ports 8080 443;` gives two).

`wins ()`, `shadowed at ()`, a resolution's `winner` and `shadowed`, and a reference's `resolutions ()` are the low
level's public account of what each `set` reaches and what wins over it (owner, 2026-10-28: consumers "see ... what
variables exist, and where they were overloaded"); the rendered layer reads them, never anything private (7.0).
They follow [expansion.md](expansion.md), the one home of the scoping and precedence rules.

### 6.8 Saving

The graph's `save (writer)`:

1. Collect every document whose `text` differs from its `saved text`, in `documents` order.
2. With none, MUST NOT call the writer, and returns an empty list.
3. Otherwise hand them to the writer in one batch.
4. When the writer succeeds, each written document's `saved text` becomes the text handed over (an
   edit made while the writer ran stays unsaved). Return the resolved paths handed over.
5. When the writer fails, no `saved text` changes. A `lost update error` from the writer (4.2) is raised as it
   is, its `paths` the conflicting files. Any other failure makes `save` raise a `save error` with `paths` (the
   resolved paths handed over, in batch order) and the writer's failure as its cause.

Before step 1, `save` raises an `argument type error` when `writer` is not a document writer (no callable `write`),
so a writer that never ran is not reported as one that failed.

### 6.9 Values going in: config text, `quote` and `text`

Every edit takes knobly text, not program values (owner, 2026-10-28: "values: A, new values
written as villanelle text, with quote()"; kept on 2026-10-29, round 13 question 3: "A Keep text
only, make misuse impossible").

**`config text` is its own type** (milestone 5, bead kno-umh.6; owner, 2026-10-29: he picked "Yes, its own type"):
knobly text a program hands to an edit or an override, made only by `quote (text)` or by an explicit `text
(raw)`, so passing a program's plain string where config text is due is a type error the checker reports. In
TypeScript it is a branded string, `ConfigText` (`string & { readonly [configTextBrand]: true }`, a `unique symbol`
brand that no other module can write); in Python a `NewType`, `ConfigText = NewType("ConfigText", str)`. Both are
still the language's string at run time, so a `ConfigText` reads as text anywhere a string does. Prior art: the
branded types of TypeScript's own handbook and Zod's `.brand()`, Python's `typing.NewType` (PEP 484), and the
trusted-types idea of the browser's `TrustedHTML`: a string is safe in a sink only when a named factory made it.
The schema names it as the concept `config text` ([schema/api.json](schema/api.json)).

- Every member that takes new knobly text names that parameter `text` and types it `config text`: `set
  (text)` (statement, variable, value), `replace with text (text)` (statement, value, document), `insert statements
  (index, text)`, `add statements (text)`, `insert before (text)`, `insert after (text)`, `set override (name,
  text)`, and each value of `load`'s `overrides` (and of the graph's `overrides`, which hold what the program gave).
  A name is not config text: `rename (name)`, `set override`'s `name` and the override names take the language's
  text, checked by the one check per kind of name (2.8).
- `quote (text)` takes a program's plain text and returns `config text`, written as a knobly string (below).
  `text (raw)` takes plain text and returns it as `config text` unchanged, checking nothing: it is the program's
  statement that `raw` is already written as knobly text (`text("8080 udp")`, `text("[1, 2]")`). The edit it
  is given checks it, as for any config text. Nothing else makes config text: no reading member returns it (a
  statement's or value's `text` is plain text; pass it on with `text (...)`).
- At run time the check is unchanged: given anything that is not text (a number, a boolean, a list, a null), each
  member above, `quote` and `text` MUST raise an `argument type error` before it changes anything, whose message
  names the member and the parameter and points to `quote ()` and `text ()`. Its placeholders and rule are in
  [schema/api.json](schema/api.json) (`argument type error message`); each binding's exact sentence is its
  emitter's (`LANGUAGE.argument_type_message`), shown in the generated table below. The error is raised before the
  library does anything with the value, so it never fails inside the library. A plain string
  passes at run time (neither language can tell it from config text then); the type checker refuses it. Absent is
  allowed only where the member says so (`set override`'s text, which removes the override).
- A binding's docs show `quote ()` and `text ()` beside the first edit they teach.

Each binding's argument type error message, from its emitter (`{member}`, `{parameter}` and `{got}` are filled in at
the raise):

<!-- generated: argument type messages (tools/gen-api.py docs) -->
| Binding | Message |
|---|---|
| TypeScript | `{member}(): argument "{parameter}" must be a string, not {got}; knobly edits take config text: quote() a program string, text() one already written as knobly text, String() a number first` |
| Python | `{member}() argument '{parameter}' must be str, not {got}; knobly edits take config text: quote() a program string, text() one already written as knobly text, str() a number first` |
| C++ | `{member}(): argument '{parameter}' must be a live object, not {got}` |
<!-- end generated -->

Costs: every literal a program writes into an edit needs `text (...)` (`statement.set(text("8080"))`), and a value's
`text` read from one line must be wrapped to be written into another. A cast (`as ConfigText`, `cast(ConfigText,
s)`) gets past the checker, as any cast does.

`quote (text)` returns `config text` written as a knobly string, escapes included:
`quote("10.0.60.31")` is `"10.0.60.31"`. It MUST give the same canonical string text an expanded
value has (2.9). A program writes a number or a boolean as its text (`text("2400")`, `text("true")`); text with a
space in it written without `quote` is two values (`text("my host")` sets `my` and `host`).

`quote` escapes only what canonical text escapes (backslash, `"`, newline, tab, carriage return).
A string cannot hold, raw, any other character from U+0000 to U+001F, DEL (U+007F) or a lone
surrogate (`STRING` in `grammar/Knobly.g4`): the parser ends the string before it (E1001) and
reads it as `BAD_CHAR` (syntax cases `edge-ctrl-str`, `edge-del-str`, `nul`). Today `quote`
passes such a character through, so the edit given its result raises a `bad text error`, and no
rendered value can hold one.

> **Proposed (pending owner):** `quote` raises a misuse error for a character a string cannot
> hold, so the failure names the cause. No case covers `quote` with such input yet.

### 6.10 Expansion: the low level's public account of a render

The graph's `expand ()` returns an `expansion`: every copy of the graph's current texts and overrides as a program
reads it, with each value expanded and linked back to the lines it came through. It is the low level's own domain
object (a snapshot, worked out once, holding live handles), and it is all the rendered layer builds on (7.0), so a
render needs nothing private (owner, 2026-10-29, answering "Yes" to: the rendered layer builds only on the low
level's public objects, and the low level makes public what each set reaches and what wins over it). It is pure:
it reads no file. An extension copy not read yet (its edge is in `unread ()`) expands to an `unreadable expansion`
with reason `unread`, placed at the extension line, with E3007 in `diagnostics` (kno-umh.4), so a render shows it
and `diff` reports what it held as `unknown`, not `removed` (7.6). (Before milestone 4 it expanded to nothing.) It
follows [expansion.md](expansion.md).

`expansion`:

| Member | Contract |
|---|---|
| `block` | the top-level readable directive copies, in written order: an `expansion block` (2.11) of `directive expansion`s |
| `unreadable` | the top-level copies that could not be read, as `unreadable expansion`s |
| `diagnostics` | the graph's `diagnostics` (6.3), the one list |

`directive expansion` (one copy of a `written directive`, after `use` and extension lines spliced it in):

| Member | Contract |
|---|---|
| `written` | the `written directive` it is a copy of (was `statement`: one name for the link, kno-umh.8) |
| `origin` | a directive origin: its name's place and the copy's `via` |
| `values` | its values, expanded, as `expanded value`s with their links (2.9), in order (a reference gives every value it reaches) |
| `block` | its block's readable directive copies, an `expansion block` (2.11); absent when written without a block |
| `unreadable` | its block's copies that could not be read; empty when none |

`unreadable expansion`: `reason` (`unreadable reason`, 2.4: `syntax`, `expansion`, `value`, `extension`, or
`unread` for an extension copy not read yet), `written` (the statement that could not be read: an unreadable line,
or a directive, `use` or extension line this copy could not expand or has not read; was `statement`) and `origin`
(the place of the statement's own tokens, owned comments left out, with the copy's `via`). The rendered tree lists
these same objects (7.2).

Python `__match_args__`: `directive expansion` `("written", "values", "block")`, `unreadable expansion`
`("reason", "written")`.

Cost: the rendered directive still mirrors the directive expansion (it adds `parent`, `name`, `closest`,
an address and `error`), so two directive types of one shape exist, one per layer. The values and unreadables are
one family each, shared by both (kno-umh.8; before milestone 4 there were three value families, 22 types).

## 7. Rendered tree (the middle layer)

The rendered tree is directives after expansion: variables replaced, snippets and extension files
spliced in. It is read-only. `set`, `snippet`, `use` and extension lines never appear in it; their
results do, in their place. A render reads no file: an unread include copy renders as an `unreadable expansion`
with reason `unread` at the include line (6.10).
A render shows the texts as they were when it was made; after an edit, render again.

### 7.0 Render

`render (graph)` is the rendered layer's entry point: a free function of that layer that takes a
`document graph` and returns its `rendered` tree, built from the graph's current texts and
overrides. Going up a layer is the upper layer's function, so the low level depends on nothing
here (6.2; owner, 2026-10-29). It is pure: it reads no file, and an unread extension copy renders as an
unreadable with reason `unread` (its edge is in the graph's `unread ()`). It MUST be synchronous, in every binding.

It builds the tree from the graph's public `expand ()` (6.10) and nothing else of the low level that is not
public, and it builds on the expansion's own objects instead of copying them (kno-umh.8): each `directive
expansion` becomes a `directive` whose `written`, `origin` and `values` are the expansion's (the same objects), and
whose `unreadable` lists the expansion's `unreadable expansion`s; the `rendered` tree's `unreadable` are the
expansion's top-level ones, its `origin` is the root file at 0:0 (from `graph.root`'s `resolved path`) and its
`diagnostics` are the graph's. The rendered layer adds what is its own: `name`, parents, `walk`, `closest`,
addresses, `diff`, `error`.

A binding MUST NOT give the rendered layer package-internal access to the low level (a private module, member or
accessor, a class check such as `instanceof` on a low-level class): it reads only what any program could
(owner, 2026-10-29). Each binding checks this mechanically (binding guide rule 8). So `render` accepts any object
that has the document graph's public members. Given anything without a callable `expand` (a document, a statement,
a number), `render` MUST raise the `argument type error` (2.8) before any other work, whose message names `render`,
the parameter `graph` and what it takes (milestone 5, the milestone 4 leftover: TypeScript failed with a native
`TypeError` from inside the render and Python with an `AttributeError`; case `render-not-a-graph`). The work is still done once: `expand ()` is the low level's one
working-out of the binding, and no low-level module calls into the rendered layer. A binding exports `render` only from
its rendered layer's namespace (binding guide rule 9: a name is never exported under a second path).

### 7.1 Rendered

| Member | Contract |
|---|---|
| `block` | the top-level readable directives, a `rendered block` (2.11); `block.walk` visits every directive (7.5) |
| `unreadable` | top-level statements that could not be read, as `unreadable expansion`s (6.10); their siblings stay |
| `origin` | a `directive origin`: the root file at 0:0, zero width, `via` empty: where a problem with no line of its own is placed |
| `diagnostics` | the graph's `diagnostics` (6.3), the one list |
| `graph` | the graph it was rendered from |
| `error (message, code)` | returns (does not raise) a `diagnostic error` for a problem of the whole file. `code` is required, a program code; misuse error for a code without `/` |
| `addresses (key?)` | every directive's `address` under the key rule, in walk order. The key rule is called once per directive, parents before children. A key rule may fail; `addresses` and `diff` then fail with that failure unchanged, not wrapped. This is the one home of the address rule; `diff` uses it |
| `diff (after, key?)` | what differs from this render (the before) to `after`, another render (7.6). Any two renders may be compared, whichever graph or processor made them |

### 7.2 Directive

| Member | Contract |
|---|---|
| `name` | |
| `values` | its values: its directive expansion's `expanded value`s (2.9), the same objects |
| `block` | its block's readable directives, a `rendered block` (2.11); absent when written without a block |
| `unreadable` | its block's statements that could not be read, as `unreadable expansion`s; empty when none |
| `parent` | the enclosing directive; absent at the top level |
| `origin` | a directive origin: where its name was written, and the uses and includes that brought it |
| `written` | the `written directive` this is a copy of: the same object for every copy of one line (its directive expansion's `written`) |
| `closest (predicate)` | this directive or its nearest enclosing one that matches |
| `error (message, code)` | returns a `diagnostic error` placed on its name (`code` as on `rendered`) |

Python `__match_args__`: `("name", "values", "block")`, the same as a `written directive` (2.10).

A statement that could not be read is an `unreadable expansion` (6.10): `reason` (`syntax`, `expansion`,
`value`, `extension`, `unread`), `written` and `origin`. It has no name or address. (`kind` names a thing's type
everywhere, so the reason has its own word: glossary.) The rendered `unreadable` type is gone (milestone 4).

### 7.3 Values

A rendered directive's values are `expanded value`s (2.9), the very objects of its directive expansion: the five
variants, the readers, `error`, and the links `written`, `definition` and `chain`. The rendered layer adds no value
type (kno-umh.8; before milestone 4 it had an `argument` family of five types that copied them: the old names are
in `frozen-m4.md`).

### 7.4 Address and key rule

- An `address step` has `name` (text), `key` (what the key rule returned, which may be empty
  text; absent when it returned absent or there is no rule) and `occurrence` (a 0-based integer
  among earlier siblings with the same name and key).
- An `address` has `steps` (top level down), `text`, `parent` (absent at the top level) and
  `people form`. A binding exposes `people form` as its language's to-text conversion when it has
  one (`toString()`, `__str__`, Go's `String()`), since that is the text a person reads.
- `text` MUST be the same bytes in every binding: the JSON array of `[name, key, occurrence]` per
  step, with `null` for an absent key, no spaces, and the integer in decimal. A JSON string here is
  written as **address JSON**: `"`, then each character, then `"`, where `"` is `\"`, `\` is
  `\\`, U+0008 is `\b`, tab `\t`, newline `\n`, U+000C `\f`, carriage return `\r`, any other
  character from U+0000 to U+001F is `\u00` and two lowercase hex digits, and every other
  character is itself (`/`, `<`, `>`, `&`, DEL, U+2028, U+2029 and everything above U+007F
  unescaped). This is what JavaScript's `JSON.stringify` writes; a library that escapes HTML
  characters or U+2028 (Go's `encoding/json` by default) does not give these bytes.
- `people form`: each step as its name, then a space and its key in address JSON when there is
  one, then ` #n` when the occurrence is not 0, joined by ` > `: `graph > node "leds" > max_count`.
- Addresses are unique within one render. A file included at two places, or a snippet used twice,
  lands at two addresses.
- A `key rule` takes a rendered directive and returns text or absent. It is the program's rule for
  naming a directive among its siblings, so it keeps its address when lines move. It may fail
  (7.1). One that returns anything else (a number, say) makes `addresses` and `diff` raise the
  `argument type error`.

> **Known gap:** a key holding a lone surrogate is written `\udxxx` (lowercase) by TypeScript and
> raw by Python's `json.dumps`. The rendered corpus covers `address text` and the `people form` with escapes
> (`address-keys`), but no case holds a lone surrogate in a key (section 9).

### 7.5 Walking

`walk` is a member of every block (2.11). It visits every item below the block, depth-first in written order
(pre-order: an item, then everything in its block, then its next sibling); the block's owner is never visited:
`rendered.block.walk` visits every directive, `directive.block.walk` those inside the directive. A binding MUST let
the caller skip an item's block and stop early. Whether to descend is decided after the item is visited and before
its block: a callback's answer, or in a generator form, the `descend` question asked when the caller asks for the
next item. TypeScript takes a callback that may return `WalkControl.Skip` or `WalkControl.Stop` (`"skip"`,
`"stop"`); Python's `walk(descend=...)` is a generator with a `descend` predicate, stopped with `break`. (Before
milestone 6 `walk` was a method of the render and of a directive; it moved onto the block, its one home.)

### 7.6 Diff

A render's `diff (after, key?)` lists what differs from it (the before) to `after`, matched by
address under the key rule. It lives on the render because it compares two renders (6.2's rule).

- A `change` is a union (2.10) over the `change kind` list, every variant with `kind` and `address`: `added`
  (`after`), `removed` (`before`), `changed` (`before`, `after`: same address, but its own values by text, or
  whether it has a block, differ), `unknown` (`before`). Python `__match_args__`: `Added` `("address", "after")`,
  `Removed` and `Unknown` `("address", "before")`, `Changed` `("address", "before", "after")`.
- A directive missing from `after` is `unknown`, not `removed`, when its container in `after` (its
  block, or the top level) holds an unreadable statement.
- An added, removed or unknown directive is listed alone, never with the directives inside it. A
  changed directive's block is compared at its own addresses.
- Order: removed and unknown in `before`'s walk order, then added and changed in `after`'s walk
  order.

### 7.7 The diagnostics sink

A `diagnostics` collection is the one place problems collect. `make diagnostics (initial?)` starts
it with a list of `located diagnostic`s (usually a render's `diagnostics`). Its members:

| Spec name | Contract |
|---|---|
| `add (diagnostic)` | append one `located diagnostic` |
| `report (at, message, code)` | append the diagnostic `at.error(message, code)` would carry; `at` is anything with `error (...)` (a rendered tree, a directive, an expanded value). `code` is required, as there |
| iterate | the diagnostics in the order added |
| `count` | how many |
| `collect (read)` | run `read`; when it raises a `diagnostic error`, append its diagnostic and return absent instead; any other error passes through; otherwise return `read`'s result |

Today TypeScript has `new Diagnostics(initial)`, `add`, `report`, `length`, iteration and
`collect(read)`; Python has `Diagnostics(initial)`, `add`, `report(at, message, code=...)`,
`len()`, iteration, and `collect` as the context manager `with problems.collecting():`, the Python
idiom for "run this block, catching one kind of error".

## 8. High level (future)

Idiomatic sugar per language (bead kno-xlo) is not built. It stays per language. When it is built,
it MUST use the spec names of the concepts it exposes and the error groups of 2.8, and MUST be
buildable purely on top of the layers above.

## 9. Conformance

The shared cases in `conformance/` are how a binding proves it meets this page. The shared driver
(`conformance/driver/run.py`) runs every case against the binding's adapter and compares each output with its expected
one **byte for byte**; the protocol, the driver and the levels are [conformance.md](conformance.md). The expected
outputs were derived by hand from the rules, not generated by an implementation: an output that disagrees is a bug in
the binding, its adapter or the rules, never a reason to rewrite an expected file. A rule found wrong is reported as a
finding against this page.

| Corpus | Format | Level | Covers |
|---|---|---|---|
| `syntax`: `conformance/cases.json`, `extra.json`, `depth.json`, `edge.json`, `tracer.json`, `variables.json`, with `conformance/expected/` | [conformance/format.md](../conformance/format.md) | L0 | 2.1 (positions in UTF-16), 2.4 (1xxx and 2xxx codes), 2.5 (nesting), 3 |
| `written`: `conformance/written/{cases,diagnostics}.json`, `conformance/written/expected/` | [conformance/written/format.md](../conformance/written/format.md) | L1 (L2 for a case that renders, L3 with include) | 6.3 to 6.9, by its `needs` tokens: `values`, `directive-values`, `statements`, `blocks`, `rename`, `document`, `override`, `save`, `quote`, `include`, `snippet`; 2.8's entry rules (line breaks, comments, bounds, list items, a values text with no value) and bad names (misuse error); 4.2's lost update (`saveTo`); 6.10's unread copy (and its `diff`); 2.9's `definition` and `chain`; 6.1's value `set` that keeps its handle; 6.5's `@` statements; 7.0's `argument type error` (`["render", target]`); 2.5's E5013 (after expansion: its place and order) |
| `load`: `conformance/load/cases.json`, `conformance/load/expected/` | [conformance/load/format.md](../conformance/load/format.md) | L2 (L3 with include) | 2.2, 2.4 (3xxx to 5xxx), 2.5 (after expansion), 4.3 (`memory source`), 5, 6.2 (`load` with `overrides`), 7.0 (`render (graph)`), 7.1, 7.2, 7.3 (canonical text and origins), 7.4 (people form, with the `rasl` key rule), 7.6; [expansion.md](expansion.md) 6 (each row of the precedence table) |
| `rendered`: `conformance/rendered/cases.json`, `conformance/rendered/expected/` | [conformance/rendered/format.md](../conformance/rendered/format.md) | L2 | 7.4 (`address text` with escapes, keys from data, occurrences, an empty and an absent key, a rule on the parent), 7.6 (the order of a diff, unknown, a directive listed alone, a block's presence) |
| `contract`: `conformance/contract/cases.json` (expected results inline) | [conformance/contract/format.md](../conformance/contract/format.md) | L2 | 2.9 (every reader, its results and codes), [contract.md](contract.md) 1 (positions in the binding's unit), 2 (people forms, `format diagnostic` with tabs, a character outside the Basic Multilingual Plane, `"\r\n"` and no graph), 3 (numbers) |

Rules for every binding:

- The driver runs every case at or below the level the binding claims; a case above it is skipped. A binding
  builds a layer, raises its claim, and skips nothing at its claimed level. (The `needs` tokens of the written and
  load cases stay as a record of what each case uses; the driver reads `include` from them for the level.)
- Every output follows the byte rules of `conformance/format.md`, applied by the driver.

Not covered by any shared case today (each binding tests these on its own): the diagnostics sink; `error (...)`; the
file and fetch adapters (L4: the fetch writer's precondition); the error class tree beyond the groups the adapter
reports (contract 4); a port result that is a bare text (4.1, 5); expanded value equality (2.9); a bad text error's
message (2.8); that an operation is
absent where it cannot succeed (2.10: a type test per binding); that `plain` is gone (milestone 5: each binding's
public-name test against `removed in milestone 5`); the `config text` type (6.9: a type test per binding, since a
plain string passes at run time); a value handle's new class or `kind` after a `set` that changes its kind (6.1); `expand ()` itself, beyond the renders built from it;
an override's text refused at `load` (`"1;"`: the `set override` case covers the check, no case covers `load`
refusing it); `quote` of a character a string cannot hold (6.9); paths whose sort differs between code points and
UTF-16 units (4.1); comment ownership across a blank line or over several comment lines (6.5); the override order
after `set override` (6.2); `argument type error` for a value that is not text (6.9) or a key rule returning
something other than text (7.4); the same-line `written` of an expanded value (2.9); a key holding a lone surrogate
(7.4, known gap); a commented extension line in a written-case copy text (`conformance/written/format.md`); a
statements text that ends in a comment (`replace with text` on a statement whose text has no `;`).
