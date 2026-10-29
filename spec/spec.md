# villanelle language-binding specification

Status: this page is canonical (owner, 2026-10-27: "Within villanelle I want the spec to win over a
reference language"). It describes the API after milestone 1 (bead vil-fy4): the words of
[glossary.md](glossary.md), and the operation homes and layer direction the owner settled on the
round 13 gate page (2026-10-29, 6.2). The bindings on `feat/low-level-layer` (PR 4) carry the older names until the
milestone 1 binding work lands; the exact old-to-new table is the milestone's frozen page,
`.claude/design/consumer-api/round14/frozen-m1.md`. Nothing here is locked: the owner approves API
shapes ("Nothing is locked until I see user APIs that I like", 2026-10-27). A note marked
**Proposed (pending owner)** is not agreed; it links to [review.md](../.claude/design/consumer-api/round13/review.md)
or names its open question.

This page is the one home of the rules a binding must follow. Each concept's one word, and its type
name in each layer and binding, is in [glossary.md](glossary.md). Every fixed list (kind lists,
error groups, limits, reserved names, diagnostic codes) has its one home in [schema/](schema/): the
tables on this page are copies for reading, and the schema wins where they differ. How to turn the
rules into a binding in a given language (names, idiom, what may differ) is in
[binding-guide.md](binding-guide.md). The language itself (what a config file may say) is in
[docs/language.md](../docs/language.md).

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
  `set` lines or an override; `render` reports E5001 or E5003 only where nothing does.
- "In order" lists are ordered as stated. When a list's order is stated, a binding MUST keep it:
  the conformance outputs depend on it.
- "Text" means the language's string type. Values going into edits are villanelle text, and only
  text (6.9).
- Error groups are named here (for example "misuse error"); which native class each group maps to
  is the binding's choice within the rules of 2.8 and the binding guide.

- **Where an operation lives** (6.2): the processor only loads; every later operation is a method on
  the object the program holds, within that object's layer; going up a layer is a free function of
  the upper layer, `render (graph)` (7.0), because the low level never depends on the rendered layer
  (owner, 2026-10-29, round 13 question 1: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"). The other free
  functions are pure helpers: `parse`, `span of` and `text of` (3.3), `quote` (6.9), `format
  diagnostic` (2.7), and the adapter and extension factories.

The glossary ([glossary.md](glossary.md)) and the schema ([schema/](schema/)) are split out of this
page. Splitting the rest into one page per layer and a separate edge contract (review, root causes
4 and 5) waits for the milestones that write those rules.

## 2. Shared pieces

These are used by more than one layer.

### 2.1 Positions and spans

- A `source position` has `offset`, `line` and `column`, all counting from 0.
- `offset` and `column` count **UTF-16 code units** in every binding today. This is also the unit of
  every conformance output.
- A line ends after each `"\n"`. `"\r\n"` ends one line. A lone `"\r"` does **not** end a line.
- A `source span` is a half-open range `[start, end)` of two positions, with
  `start.offset <= end.offset`.

A new binding follows the MUST above until the owner answers the proposal below, whatever its
string type. A binding whose strings are UTF-8 (Go, Rust) therefore converts byte offsets to UTF-16
units where it reports a position, and back where it takes one; it SHOULD offer that conversion as
a public helper so its users can slice their own strings.

> **Proposed (pending owner):** each binding reports positions in its own string unit (code points
> in Python, bytes in Go), so slicing a string at a reported position gives the right text;
> conformance runners convert to UTF-16. Today a Python offset is not a `str` index once a character
> outside the Basic Multilingual Plane comes before it. See [review.md, root cause 4](../.claude/design/consumer-api/round13/review.md#root-cause-4-the-contract-at-the-edges-is-not-written-down-neutrally).
>
> **Proposed (pending owner), for bindings whose strings are not UTF-16:** `parse` is total over the
> language's own strings (3.3). A Go or Rust string can hold bytes that are not valid UTF-8 but
> cannot hold a lone surrogate; a UTF-16 string is the other way round. The proposal: each
> invalid byte becomes one `BAD_CHAR` token with E1003 at that byte (inside a string or comment it
> breaks the token, as a raw control character does); the syntax cases `surrogate-bare`,
> `surrogate-str` and `surrogate-comment` (in `extra.json`) need UTF-16 strings, so a UTF-8 binding
> skips them and passes matching invalid-byte cases instead, which do not exist yet. Today no rule
> covers invalid UTF-8, and a runner that decodes those three cases with a standard JSON decoder
> gets U+FFFD, not the input.

> **Known gap:** the two bindings were reported to disagree on a lone `"\r"` and on `-0` (review
> finding P3). No conformance case covers either yet.

### 2.2 Place, step, origin

- A `place` is a range of one file's text: `kind` `"file"`, `resolved path` (the file's identity as
  the document source gave it) and `span`.
- An `override` is a value the program passes in at load (6.2), written in no file. As an
  origin's place it is `kind` `"override"` and `variable` (the name without `$`). The `place kind`
  list is `file`, `override`.
- A `step` is one expansion a directive or value went through: `kind` (one of the `step kind`
  list: `variable`, `use`, `extension`), `name` (the variable without `$`, the snippet, or the
  extension directive) and `place` (the place of the `$name` token, the `use` line's name, or the
  extension line's name).
- An `origin` is `place` (a place, or an override) plus `via` (steps, innermost first; empty when
  the text is read where it was written). For a value from a variable, `place` is the value in its
  `set` line (or the override) and `via[0]` is the `$name` that used it.
- A `directive origin` is an origin whose `place` is always a file place.

All of these are plain, read-only data.

### 2.3 Diagnostics

- A `diagnostic` (syntax layer) has `code`, `message` and `span`.
- A `located diagnostic` (every other layer) has `code`, `message`, `place` (a file place) and
  `via` (steps, innermost first). A problem caused by an override is placed at the `$name` that used
  it, and the message names the overridden variable.
- Only `code` and the position are part of the contract. `message` is for people and MAY differ
  between bindings.
- A `program code` is a program's own code, `<namespace>/<name>` (for example `rasl/unknown-node`).
  It never collides with villanelle's codes, which start with `E`. Every operation that takes a
  program code MUST refuse one without `/` with a misuse error.
- Every code is an error. There are no warning codes.

### 2.4 The diagnostic code registry

Codes are stable across bindings and releases and are never reused for another meaning. Retired,
never to be reused: E2006, E3002, E3003. Ranges: 1xxx lexical, 2xxx syntax, 3xxx files and
extensions, 4xxx values, 5xxx expansion, 6xxx reserved for the high level.

A binding MUST expose every code below, by its value and by a name. The "found by" column says
which operation reports it. This table is a copy of [schema/diagnostics.json](schema/diagnostics.json),
which also holds each code's message and owning layer; the schema wins.

| Code | Spec name | Found by | Unreadable reason | Meaning |
|---|---|---|---|---|
| E1001 | `unterminated string` | parse | syntax | A string reaches the end of its line or of the text without its closing quote. |
| E1003 | `unexpected character` | parse | syntax | A character no token may start with, or a byte-order mark after the first character. |
| E1004 | `lone dollar` | parse | syntax | A `$` not followed by a variable name. |
| E2001 | `unexpected token` | parse | syntax | A token the grammar does not allow here, when no more specific code applies. |
| E2003 | `expected closing brace` | parse | syntax | The text ends inside a block. |
| E2004 | `expected closing bracket` | parse | syntax | A stray `]`, or a `[` list with no matching `]`. |
| E2007 | `bad slice` | parse | syntax | A malformed slice after a word: `a[:]`, `a[1:b c]`, an unclosed slice. |
| E2008 | `brace on own line` | parse | syntax | A `{` that starts its line. |
| E2009 | `values touch` | parse | syntax | Two values with nothing between them, such as `a"b"`. |
| E2010 | `nesting too deep` | parse | syntax | Blocks and lists nested deeper than 100 levels. |
| E3001 | `include not found` | load, read | extension | An extension's spec matched no file. |
| E3004 | `include resolver failed` | load, read | extension | The document source rejected while resolving or reading a file. For the root file, `load` fails instead (6.2). |
| E3005 | `include bad path` | include extension | extension | An `include` whose values are not exactly one quoted path. |
| E3006 | `extension failed` | load, read | extension | An extension threw something other than a diagnostic error. |
| E4001 | `non-integer bound` | render, `load` and `set override` (an override's text) | value | A slice or index bound that is not an integer. |
| E4002 | `wrong value kind` | readers | none | A reader asked for a kind the value is not. |
| E4003 | `bad escape` | render, `load` and `set override` (an override's text) | value | A backslash escape other than the six the language allows. |
| E4004 | `not a number` | readers | none | A word read as a number that is not a JSON number. |
| E4005 | `not an integer` | readers | none | A word read as an integer that is not one. |
| E4006 | `not a boolean` | readers | none | A word other than `true` or `false`, read as a boolean. |
| E5001 | `unknown variable` | render | expansion | A `$name` with no `set` visible and no override. |
| E5002 | `variable set twice` | low level | expansion | Two `set` lines for one name in one block. |
| E5003 | `unknown snippet` | render | expansion | A `use` naming no visible snippet. |
| E5004 | `snippet arity` | render | expansion | A `use` with a different number of values than its snippet's parameters. |
| E5005 | `snippet defined twice` | low level | expansion | Two `snippet` lines for one name in one block. |
| E5006 | `expansion cycle` | low level | expansion | A `use` or extension line that reaches itself again. |
| E5007 | `expansion too deep` | low level | expansion | `use` and extension lines nested deeper than 16. |
| E5008 | `too many directives` | render | expansion | More than 100,000 directives after expansion. |
| E5009 | `bad set` | low level | expansion | A `set` that is not `set $name value...;`. |
| E5010 | `bad snippet` | low level | expansion | A malformed `snippet`, or one naming a parameter twice. |
| E5011 | `bad use` | low level | expansion | A `use` that is not `use name value...;`. |
| E5012 | `extension block not set` | low level | extension | An extension line whose block holds a line other than `set`. |

"Low level" codes appear in `document graph` `diagnostics`; "render" codes appear only in the
`rendered` tree's `diagnostics` (6.3, 7.1). "Load, read" codes are found when the load or `read`
runs, but are reported in both lists, at the extension line, as low-level codes are.

**Unreadable reason** is the `unreadable reason` (7.2) of the statement a code makes unreadable; it is
part of the load conformance output. "syntax" means the statement is an `error` node, or an
extension line whose block holds one (the code is then the parser's, reported once). A diagnostic
error an extension's `specs` throws keeps its own code (a program code included) and gives reason
`extension`. "none" means the code never makes a statement unreadable: readers raise it.

Each binding's code registry and message table are generated from
[schema/diagnostics.json](schema/diagnostics.json) ([codegen.md](codegen.md)); the schema marks which
layer owns each code.

> **Proposed (pending owner):** stop naming E3001 and E3004 after `include`, since the core load
> reports them for every extension (review, "Deferred"; P9).

### 2.5 Limits and reserved names

A copy of `limits` and `reserved names` in [schema/api.json](schema/api.json).

- Nesting of blocks and lists: at most 100 levels (E2010).
- Nesting of `use` and extension lines: at most 16 (E5007).
- Directives after expansion: at most 100,000 (E5008).
- Reserved at a line's start: `set`, `snippet`, `use`, and the directive name of every registered
  extension.

### 2.6 Diagnostic error

A `diagnostic error` is the error thrown by an operation whose input breaks its contract in a way
that has a place: a reader given the wrong kind of value, a program's `error(...)`, or a root file
that cannot be read. It carries one `located diagnostic` as `diagnostic`.

### 2.7 Formatting a diagnostic

`format diagnostic (diagnostic, graph?)` returns text for people:

```text
path:line:col: CODE: message          <- line and column count from 1
the source line                       <- only when the graph holds the file (its current text)
    ^^^^                              <- under the span; tabs kept so the caret lines up
  via <kind> <name> at path:line:col  <- one per step, innermost first
```

It MUST read text only from the graph it is given and MUST NOT do I/O.

### 2.8 Error groups

Every binding maps these groups onto its own error classes (a copy of `error groups` in
[schema/api.json](schema/api.json)):

| Group | Raised when | TypeScript today | Python today |
|---|---|---|---|
| problems in the config text | never raised: reported as diagnostics | | |
| `diagnostic error` | 2.6 | `DiagnosticError` | `DiagnosticError` |
| `read error` | `load` cannot resolve or read the root (a diagnostic error, E3004 at the root path) | `ReadError` | `ReadError` |
| `argument type error` | an argument of the wrong type: an edit, `quote`, `set override` or a `load` override given anything but text (6.9) | `TypeError` | `TypeError` |
| `edit error` (base) | an edit refused; nothing changed | `EditError` | `EditError` (a `ValueError`) |
| `bad text error` | the text given to an edit, or an override's text (6.3), is not what it takes | `BadTextError` | `BadTextError` |
| `detached error` | a member of a detached handle was used | `DetachedError` | `DetachedError` |
| `no set line error` | `set` or `rename` on a variable with no `set` line (a parameter or an override) | `NoSetLineError` | `NoSetLineError` |
| `save error` | the writer rejected | `SaveError` | `SaveError` |
| misuse error | a bad argument value a program could have checked (a bad variable name, a program code without `/`) | `TypeError` | `ValueError` |
| index out of range | an insert index outside a block; a token range outside a parse (3.3) | `RangeError` | `IndexError` |

A binding MUST raise the same group in the same situation. An edit that raises an `edit error`
MUST leave every document unchanged. A `detached error` is raised by every member of a detached
handle, edits included, before any other check.

The groups fall into two sorts, which matters to a language that reports errors as values:

- **A program bug** (the program could have checked first): misuse error, `argument type error`,
  index out of range, `detached error`, `no set line error`.
- **An expected outcome** (only the input or the outside world decides): `diagnostic error` (from
  a reader, `error (...)`, or the root read), `read error`, `bad text error`, `save error`, and
  whatever a key rule or a port fails with.

**`bad text error`** has `diagnostics`: a list of syntax-layer `diagnostic`s (2.3) whose spans
count from the start of the text the edit was given (0-based lines and UTF-16 columns), never from
the document. Which codes each edit checks, and where it places them:

| Edit | Codes | Placed at |
|---|---|---|
| `replace with text`, `insert statements`, `add statements` (statements) | the text's syntax diagnostics; then the text-alone rules (E5002, E5005, E5009, E5010, E5011) for every statement the new text touches, checked in the document as it would be after the edit | the syntax diagnostic's span; a rule's fault at its place in the given text, or 0:0 when the fault lies in a statement already there (a `set` inserted before an existing `set` of the same name) |
| `replace with text` (a value), `set` | the text's syntax diagnostics, then E2001 at the first token that is more than values (a `;`, a block), then the same text-alone rules | as above |
| a slice bound's `replace with text` | E2001 unless the text is exactly one word or `$name` | 0:0 |
| `set` on a `set line` with empty text; `remove` of a `set` line's last value | E5009 | 0:0 (of an empty text) |
| `rename` (a directive) | E2001 when the name is not one word, is `set`, `snippet`, `use` or a registered extension's name, or the line is an extension line | 0:0 |
| `rename` (a variable) | E2001 when the name is not letters, digits and `_`; E5002 when it would make a second `set` of a name in its block | 0:0 |
| `set override`, and each override `load` takes (the check of an override, 6.3) | the text's syntax diagnostics; E2001 at the first token that is more than values (so `"1;"` is refused at its `;`, and `"1\n2"` at its `2`: a line break ends the values, as it ends a statement), at a `$name`, or at 0:0 for no value; then E4003 or E4001 at the value the override reader refuses | as stated |

A `diagnostic error`, `read error` and `save error` have the fields of 2.6 and 6.8.

> **Proposed (pending owner), for languages that report errors as values (Go, Rust):** a member that
> reads a fact (a property in the TypeScript sense: `text`, `name`, `values`) returns the bare
> value and panics with the program-bug group when it cannot (a detached handle); every operation
> that can end in an expected outcome returns it as an error value. So edits, `load`, `read`,
> `save`, `addresses`, `diff` and the readers return errors (`error (...)` already returns one) (a detached handle's edit returns a
> `detached error`, since the edit already returns an error), and only misuse, index out of range
> and detached getters panic. The binding guide (section 3) carries the per-language form.

> **Proposed (pending owner):** one package base error per binding; `detached error` stops being an
> edit error (Python: under `ReferenceError`); `save error` and `read error` get the same fields;
> `no set line error` is deleted because each variable kind gets its own type. See [review.md, root causes 3 and 4](../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).
> (The fourth item of the round 13 list, one check of an override's text for `load` and `set
> override`, is settled: 6.3.)

### 2.9 Expanded value and its readers

An `expanded value` is one value after expansion: a `$name` has already become its value or values.
It is what an `extension use` holds (5) and what a rendered `argument` builds on (7.3), so the
readers have one home below both layers (owner, 2026-10-29: "they should have different domain
objects. The middle layer of objects can build on the lower layer domains"). It has `kind` (a
value kind without `reference`: `word`, `string`, `list`, `slice`, `index`), `text` (canonical,
below), `origin` (2.2), the readers below and `error (message, code)`. It is plain data: it holds no
low-level handle.

**Canonical text** (the same bytes in every binding): a word as written; a string as `"`, its
decoded text with `\`, `"`, newline, tab and carriage return escaped, then `"`; a slice
`name[start:end]` (either side may be empty) and an index `name[i]` with decimal integers; a list
`[`, its items' texts joined by `, `, then `]`. Comments and line breaks are never part of it. Two
values are the same exactly when their texts are equal.

Readers (each raises a `diagnostic error` with the code shown):

| Spec name | Returns | Codes |
|---|---|---|
| `word` | a bare word's text | E4002 |
| `string` | a word or string, decoded | E4002 for a list, slice or index |
| `number` | a word spelling a number (below) | E4002, E4004 |
| `integer` | a word spelling an integer (below) | E4002, E4005 |
| `boolean` | the word `true` or `false` | E4002, E4006 |
| `items` | a list's items, each an expanded value with its own origin (on an `argument`, each an `argument`, 7.3) | E4002 |
| `slice` | a `slice value` (`name`, optional `start`, optional `end`) or an `index value` (`name`, `index`) | E4002 |
| `plain` | any value by one rule: a string is its text; a word is a number if it spells one, a boolean if `true`/`false`, else its text; a list is its items read the same way; a slice or index is its value | never |
| `error (message, code)` | a `diagnostic error` placed on this value; for an override, on the `$name` that used it | misuse error for a code without `/` |

Quoting means text: `"8080"` and `"true"` are strings. Only a bare word is read as a number or a
boolean.

**Number and integer words.** Their spelling is `NumberText` and `IntegerText` in
`grammar/villanelle.ebnf` (copied here for reading); the range and the result types are ruled here.

- A number word is a JSON number (RFC 8259 section 6), the whole word: `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`.
  `8080`, `0.5`, `-1`, `1e3` and `1.0` are numbers; `+1`, `007`, `.5`, `1.` and `20hz` are not.
  `number` returns an IEEE 754 double (TypeScript `number`; Python `int` when the word has no
  fraction or exponent and lies within ±(2^53-1), else `float`, so both read the same value).
- An integer word is `-?(0|[1-9][0-9]*)` whose value lies within ±(2^53-1) (the range a double holds
  exactly). `1.0`, `1e3`, `+1` and `007` are not integers; `9007199254740992` is not either (E4005).
  `integer` returns a whole number; a binding MAY use a 64-bit integer type, since every value fits.
- Slice and index bounds are integer words, or E4001.

**`plain`'s results** are a closed set: text (from a string, or a word that is neither a number nor
a boolean), a number (as `number` returns it), a boolean, a list of `plain` results, a `slice
value`, an `index value`. A language without union types models it as a closed sum type (in Go, a
sealed interface with one type per member).

> **Known gap:** the word `-0` is an integer word, and `integer` and `plain` give `-0` in
> TypeScript but `0` in Python. A number word beyond the double range (`1e400`) reads as infinity
> in both, and a number word with more than 2^53 is rounded. No conformance case covers these.
>
> **Proposed (pending owner):** `kind` narrows the type so `items` is offered only on a list. See
> [review.md, root cause 3](../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).


## 3. Syntax layer

Read-only, one text at a time, no I/O. Covered by the syntax conformance cases (section 9).

### 3.1 Tokens

- A `token` has `kind` (from the `token kind` list), `text` and `span`.
- `token kind` values are the token names of `grammar/Villanelle.g4`: `BOM`, `SPACE`, `NEWLINE`,
  `COMMENT`, `VARIABLE`, `WORD`, `STRING`, `LBRACE`, `RBRACE`, `LBRACK`, `RBRACK`, `SEMI`, `COMMA`,
  `COLON`, and the error tokens `UNTERMINATED_STRING`, `LONE_DOLLAR`, `BAD_CHAR`. The grammar is the
  one source of these names.
- The tokens of one parse MUST be contiguous and in source order, and their texts joined MUST equal
  the input exactly, for valid and broken input alike. There is no end-of-file token. No token's
  text is empty, and each token's text length equals its span's length.

### 3.2 Nodes

- A `node` has `kind` (from the `node kind` list: `document`, `directive`, `block`, `list`,
  `slice`, `error`), a token range `start`/`end` (half-open indices into the tokens) and `children`.
- Children are in source order, do not overlap, and lie inside the parent's range. Tokens not
  covered by a child belong to the node itself.
- A `directive` node starts at its name token. A `slice` node spans `name[bounds]` exactly. An
  `error` node has no children.

### 3.3 Operations

| Spec name | Inputs | Output | Errors |
|---|---|---|---|
| `parse` | text | `syntax`: `tokens`, `root` (a `document` node over every token), `diagnostics` (in source order of their spans' starts, the order the parser reaches them) | none: total for any string, never reads files |
| `span of` | syntax, token range | the range's span; an empty range at `i` is zero-width at token `i`'s start, or at the text's end when `i` is the token count | index out of range when the range is outside `[0, count]` or `start > end` |
| `text of` | syntax, token range | the exact source text; `text of(syntax, root)` is the whole input | as `span of` |

`diagnostics` MUST be empty exactly when the input is in the grammar's language.

## 4. Ports: where files come from and go to

The core MUST NOT do I/O. Files come in through a `document source` and go out through a `document
writer` that the program supplies.

### 4.1 Document source

- `resolve (spec, load context)` returns the resolved paths a spec names (a path, or a glob with `*`
  and `?` in its last segment), in any order: the core sorts them (below). Empty means "not found"
  (E3001). A failure becomes E3004. Both codes are placed at the extension line's name (for
  include, the word `include`).
- `read (resolved path)` returns the text of one resolved file. A failure becomes E3004, or for the
  root file makes `load` fail with a `read error`.
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

### 4.3 Adapters

| Spec name | Port | Required | Notes |
|---|---|---|---|
| `memory source` | source | MUST | Texts keyed by path. `resolve` joins the spec to the directory of `parent path` by POSIX rules (`/` separators, `.` and `..` removed, a leading `/` taken as is) and returns the path when it is a key; a glob returns every key in that directory it matches (below). `read` of a missing key fails. Pure. |

The glob rule, shared by every source that takes globs: a spec is a glob when it holds `*` or `?`.
Only the last path segment is matched: `*` matches any run of characters (empty included), `?`
exactly one, every other character itself; nothing can be escaped. Neither can match `/`, since the
directory part is compared as written, so a `*` or `?` in an earlier segment matches only a
directory literally named so. A leading `.` gets no special treatment (`*.conf` matches
`.hidden.conf`). The root path may be a glob, but `load` fails with a `read error` unless it
resolves to exactly one file.
| `file source` | source | SHOULD | The local filesystem. |
| `file writer` | writer | SHOULD | The local filesystem. |
| `fetch source`, `fetch writer` | both | MAY | HTTP. TypeScript only today. |

> **Proposed (pending owner):** every binding ships memory and file adapters for both directions,
> each named after its medium and port (a `memory writer` is new). See [review.md, root cause 4](../.claude/design/consumer-api/round13/review.md#root-cause-4-the-contract-at-the-edges-is-not-written-down-neutrally).

## 5. Extensions

An `extension` owns one directive name and turns each use of it into specs of files to splice in its
place. It is not part of the core; a program turns it on when it makes the processor.

- An extension has `directive` (the name it owns) and `specs (extension use)`, which returns the
  specs for one use, in splice order. It MUST be pure: the load resolves and reads the specs, parses
  each file once, applies the use's block of `set` lines to the spliced files, and enforces depth,
  cycles and limits.
- An `extension use` has `values` (the line's values, expanded, as `expanded value`s, 2.9) and
  `origin` (a directive origin). It names no rendered type.
- `specs` throws a `diagnostic error` for a located failure. Any other failure becomes E3006 at the
  directive's name. (In a language with error values, a returned error that is not a diagnostic
  error; whether a panic is also caught is the binding's stated choice, binding guide section 3.)
- **Order of checks** on one extension line, each stopping the line (it becomes `unreadable`,
  kind per 2.4) before the next: its values are expanded (E5001, E4001, E4003, ...); its block is
  checked (a line other than `set` is E5012; a syntax error inside makes it kind `syntax`); `specs`
  is called; the specs are resolved and read (4.1); cycle (E5006) and depth (E5007) are checked.
  A line that stops before `specs` is never handed to the extension and names no file, so nothing is
  resolved or read for it and its `document edge` has empty `specs` and `targets`.
- Making a processor MUST refuse, with a misuse error, an extension whose name is reserved (2.5) or
  already taken by another extension.

**Layer direction** (owner, 2026-10-29: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"). Nothing below the rendered layer imports, names or
returns a rendered type: an `extension use` holds shared `expanded value`s (2.9), the graph has no
render member (6.3), and the processor returns only low-level objects. The rendered layer builds on
the layers below: `render (graph)` (7.0) takes a graph, an `argument` builds on an expanded value
(7.3), and rendered things name low-level handles (`written`, `graph`). Each binding checks the
direction mechanically (binding guide, rule 8). So a language whose packages cannot import each
other in a cycle (Go, Rust) can keep each layer in its own package or crate.

### 5.1 The include extension

`include "path";` or `include "path" { set $name value; }`. The one value MUST be a quoted path or
glob. Otherwise E3005, placed on the first value when it is not quoted, else on the second value,
else (no value at all) on the word `include`. Matching files are spliced in the order of 4.1. An
included file's top-level `set` and `snippet` lines are visible after the include line in the
including block. ([language.md, "Including files"](../docs/language.md) says the same for people
writing configs; this section is the rule.)

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
detaches, except the one a `rename` keeps. Values, statements and parameters inside a detached
statement detach with it. Per edit:

| Edit | Range replaced | Survives although its tokens are touched | Detaches | Returns |
|---|---|---|---|---|
| statement `replace with text` | the statement with its owned comments | | it and everything in it | the new statements at its level, in order |
| statement `remove` | the same, plus its line when nothing else is on it | | it and everything in it | nothing |
| `insert statements`, `add statements` | an empty range at the insert point | | nothing | the new statements, in order |
| `set` (any statement) | its first value to its last (an empty range after the name when it has none) | the statement | every old value of it | nothing |
| value `replace with text` | the value | its statement and list | it and its items or bounds | the new values, in order |
| value `remove` | the value and one separator | its statement and list | it and its items or bounds | nothing |
| directive `rename` | the name token | the directive | nothing | nothing |
| variable `rename` | the `$name` token in its `set` line or snippet | the variable and its line | nothing; references elsewhere keep their handles and are re-bound by name | nothing |
| document `replace with text` | the whole text | the document | every other handle into it | nothing |
| `set override` | no text | | nothing | nothing |

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
| `make processor` | `source` (a document source), `extensions` (optional, in order) | a `processor` | misuse error for a reserved or repeated extension name |
| `load` | root `path`; option `overrides` (name without `$` to villanelle text, in order) | a `document graph` | `read error` when the source cannot resolve the root to exactly one file or cannot read it; misuse error for a bad override name (not letters, digits and `_`); `argument type error` for an override that is not text; `bad text error` for an override's text the check of an override refuses (6.3). Never fails for anything in the files' text. |

- `load` resolves the root path through the source as an included file's spec is, so the root has
  one path in the graph. It reads every file that extension lines name, once each, repeating until
  nothing new is named.
- **Overrides** (owner, 2026-10-29, round 13 question 2: "A overrides"). An override wins over
  every `set` of its name, which acts as the default. `load`'s `overrides` option, the graph's
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
| `overrides` | property | the overrides by name (without `$`), each as villanelle text, in order (6.2); never saved. Python spells it as an editable mapping (binding guide, section 3) |
| `set override (name, text or absent)` | method | add, change, or (with absent) remove one override without a reload. Checks `text` with the check of an override (below): `bad text error` located in `text`; `argument type error` when `text` is neither text nor absent; misuse error for a bad name |
| `read ()` | method, I/O | resolve and read what `unread ()` names, through the graph's document source, repeating until nothing new is named; keeps every text and every failure it already had. Returns the resolved paths this call read (newly, not those read before), in read order |
| `save (writer)` | method, I/O | 6.8 |
| `edges ()` | method | every copy of every extension line, in walk order, as `document edge`s |
| `unread ()` | method | the edges naming a spec not resolved or a file not read yet; non-empty means copies and a render (7.0) lack them |
| `variables (name?)` | method | every variable (of that name when given): `set` and parameters in document order (documents in `documents` order), then override variables in `overrides` order |
| `diagnostics` | property | each document's syntax diagnostics (documents in order), then what the low level found, in walk order. It MUST NOT include the codes `render` reports: every E4xxx code (E4001 and E4003 included, round 12 decision D11) and E5001, E5003, E5004, E5008. `rendered.diagnostics` is this same list with those codes kept in their walk-order places (7.1). A property, as on the render (glossary, "Properties and methods") |

**No render member.** The graph has no `render` member and names no rendered type. A program
renders it with the rendered layer's `render (graph)` (7.0), which is the one home of the render
algorithm. A binding MUST NOT add a render member to the graph or copy the algorithm into the low
level.

**The check of an override** (one check, one home: `load` and `set override` both use it, and both
raise the same errors; round 13 root cause 2). Given a name and a value:

1. The name MUST be letters, digits and `_`; otherwise a misuse error.
2. The value MUST be text; otherwise an `argument type error` (6.9).
3. The text is read as the values of a line `x <text>`. It is refused with a `bad text error`
   whose diagnostics are located in the given text (2.8): its syntax diagnostics; else E2001 at the
   first token that is more than values (a `;`, a block), at a `$name`, or at 0:0 when it holds no
   value; else E4003 or E4001 at the first value the override reader refuses.

`"1;"` is refused (E2001 at 0:1), from `load` as from `set override`. (Before milestone 1, `load`
accepted it with a different check: round 13 review, root cause 2.)

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

A `statement` is one of the `statement kind` list: `directive`, `extension`, `set`, `snippet`,
`use`, `unreadable`. Every statement has:

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

Per kind:

| Kind | Type (spec name) | Extra members |
|---|---|---|
| `directive`, `extension` | `written directive` | `name`; `values` (in order; an include line's path); `block` (absent when written without one; an include line's `set` lines); `rename (name)`: `bad text error` when not one word, or a name that would change its kind; `set (text)`: replace its values, comments between them included, `bad text error` |
| `set` | `set line` | `variable`; `values` (after the `$name`); `set (text)`: `bad text error`, also for empty text (E5009) |
| `snippet` | `snippet line` | `name`; `parameters` (variables); `block` (always present) |
| `use` | `use line` | `snippet name`; `snippet` (by where written: a `snippet` line above it in its file; absent when free); `snippets ()` (per copy, a `resolution` of which snippet it splices); `values` (bound to parameters by position); `set (text)` |
| `unreadable` | `unreadable line` | none. A statement that does not parse, a malformed `set`/`snippet`/`use`, or a second `set` of a name in one block |

**`set (text)`** replaces a statement's (or a variable's, 6.7) values with `text` (owner,
2026-10-29: "Can "set_values" become simply "set"?"). It is not the language's `set` keyword: on a
`set line` it replaces the values after the `$name` and the line stays a `set` line, and it never
makes a `set` line. A program that wants a variable to take a value without editing a file uses
`set override` (6.3), which keeps its own name.

Cost of the name (a design consequence of the owner's pick, not his words): one object graph now
uses the word three ways: the statement kind `set` (a `set line`), the variable kind `set` (a
variable a `set` line declares) and the edit `set (text)`. On a `set line`, `set (text)` edits the
values of a `set` statement; on an override variable, `set (text)` refuses (`no set line error`,
its message points to `set override`), since an override has no line to edit. Docs keep saying
"not the language's `set` line" where the edit is taught. Renaming the variable kind (for example
to `declared`) would separate the kind from the edit; it is not done here, since it changes a
kind value programs and the conformance cases print.

A `written block` (a document's top level, or a statement's block):

| Member | Contract |
|---|---|
| `statements` | in order |
| `directives (name?)` | its statements of kind `directive`, of that name when given |
| `insert statements (index, text)` | insert before `statements[index]` (`index` equal to the count appends), placed and indented as below; returns the new statements. `bad text error`; index out of range |
| `add statements (text)` | `insert statements(count, text)` |

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
- Place: before `statements[index]` and its owned comments, on lines of their own; when that
  statement shares its line with an earlier one, between the two, ending with a line break and the
  target's indentation. Appending goes after the last statement's owned range. Into `{}` (or only
  whitespace between the braces): the lines between `{` and `}`, then the parent's indentation
  before `}`. Into a block holding only comments: before the `}` line, or before `}` when it shares
  a line with a comment.
- Line breaks: every line break a statement edit adds is the document's first line break
  (`"\r\n"` or `"\n"`), or `"\n"` when it has none, and the line breaks inside the given
  statements text are replaced by it. A values text (`set`, a value's `replace with text`)
  goes in as given.

> **Proposed (pending owner):** blocks are iterable and indexable in every layer with one `walk`;
> `insert before`/`insert after` on a statement; include lines get their own type; `statements of
> (kind, name?)` returns typed results so no cast is needed. See
> [review.md, root causes 3 and 4](../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).
> (`block` for every layer's statements in braces is settled: glossary.)

### 6.6 Values

A `written value` is one of the `value kind` list: `word`, `string`, `list`, `slice`, `index`,
`reference`. Every written value has:

| Member | Contract |
|---|---|
| `kind` | from the list |
| `text` | its exact source text |
| `place` | where it is written |
| `statement` | the statement holding it |
| `list` | the list it is an item of; absent otherwise |
| `replace with text (text)` | replace it with values written as villanelle text: separated by spaces on a line, by commas in a list; returns the new values; this handle detaches. `bad text error` (a slice bound takes exactly one word or `$name`) |
| `remove ()` | remove it and its separator; then it is detached. `bad text error` when that breaks a rule (a `set` left with no value) |

Per kind: `list` has `items`; `slice` has `name` (text, the word before `[`), `start` and `end`
(each a word or reference value, or absent); `index` has `name` (text) and `index` (a word or
reference value); `reference` (one `$name`) has `name`
(without `$`), `declaration` (by where written: the nearest `set` above it in its file, or its
snippet's parameter; absent when free) and `resolutions ()` (one `reference resolution` per copy of
its statement, in walk order).

### 6.7 Variables and resolutions

A `variable` is one of the `variable kind` list: `set` (a `set` line's `$name`), `parameter` (a
snippet's), `override` (an override, 6.2).

| Member | Contract |
|---|---|
| `kind`, `name` | |
| `place` | its `$name`; absent for an override |
| `line` | its `set line` or `snippet line`; absent for an override |
| `references ()` | the references whose `declaration` it is, reached or not, in document order |
| `wins ()` | the resolutions in which it wins, in walk order |
| `shadowed at ()` | the resolutions in which another variable wins, in walk order |
| `rename (name)` | rename its `$name` only. `bad text error` (also E5002); `no set line error` for an override |
| `set (text)` | its `set` line's values. `no set line error` for a parameter or an override; `bad text error` |

A `resolution` (snapshot, at one copy): `copy`; `winner` (absent when nothing of that name is
visible there, which a render reports as E5001 or E5003); `shadowed` (every other visible
definition, next first: the one that would win if the winner were gone).

A `reference resolution` adds `reference` and `values`: the winning `set` line's values, or for a
parameter the `use` line's values bound to it; empty for an override or when unbound. A reference
renders to all of `values` (`set $ports 8080 443;` gives two).

> **Proposed (pending owner):** each variable kind becomes its own type so `set` exists only
> where it can succeed. See [review.md, root cause 3](../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).
> (`wins ()`, `shadowed at ()` and `shadowed` are settled: glossary.)

### 6.8 Saving

The graph's `save (writer)`:

1. Collect every document whose `text` differs from its `saved text`, in `documents` order.
2. With none, MUST NOT call the writer, and returns an empty list.
3. Otherwise hand them to the writer in one batch.
4. When the writer succeeds, each written document's `saved text` becomes the text handed over (an
   edit made while the writer ran stays unsaved). Return the resolved paths handed over.
5. When the writer fails, no `saved text` changes, and `save` raises a `save error` with `files`
   (what was handed over) and the writer's failure as its cause.

### 6.9 Values going in: text only, and `quote`

Every edit takes villanelle text, not program values (owner, 2026-10-28: "values: A, new values
written as villanelle text, with quote()"; kept on 2026-10-29, round 13 question 3: "A Keep text
only, make misuse impossible").

- Every member that takes new villanelle text names that parameter `text`: `set (text)`,
  `replace with text (text)` (statement, value, document), `insert statements (index, text)`,
  `add statements (text)`, `set override (name, text)`, and each value of `load`'s `overrides`.
  `rename (name)` takes a `name`, and `quote (text)` takes a plain string; both are checked the
  same way.
- Given anything that is not text (a number, a boolean, a list, a null), each MUST raise an
  `argument type error` before it changes anything, whose message names the member and the
  parameter and points to `quote ()`. The exact wording per binding is in
  [schema/api.json](schema/api.json) (`argument type error message`): in Python,
  `statement.set(2400)` raises `TypeError: set() argument 'text' must be str, not int; ...` and
  never fails inside the library (before milestone 1, `set_values(2400)` did). Absent is allowed only where the member says so
  (`set override`'s text, which removes the override).
- A binding's docs show `quote ()` beside the first edit they teach.

`quote (text)` returns a plain string written as a villanelle string, escapes included:
`quote("10.0.60.31")` is `"10.0.60.31"`. It MUST give the same canonical string text a rendered
value has (7.3). A program writes a number or a boolean as its text (`"2400"`, `"true"`); text with a
space in it written without `quote` is two values (`"my host"` sets `my` and `host`).

`quote` escapes only what canonical text escapes (backslash, `"`, newline, tab, carriage return).
A string cannot hold, raw, any other character from U+0000 to U+001F, DEL (U+007F) or a lone
surrogate (`STRING` in `grammar/Villanelle.g4`): the parser ends the string before it (E1001) and
reads it as `BAD_CHAR` (syntax cases `edge-ctrl-str`, `edge-del-str`, `nul`). Today `quote`
passes such a character through, so the edit given its result raises a `bad text error`, and no
rendered value can hold one.

> **Proposed (pending owner):** `quote` raises a misuse error for a character a string cannot
> hold, so the failure names the cause. No case covers `quote` with such input yet.

## 7. Rendered tree (the middle layer)

The rendered tree is directives after expansion: variables replaced, snippets and extension files
spliced in. It is read-only. `set`, `snippet`, `use` and extension lines never appear in it; their
results do, in their place. A render reads no file: an unread include copy renders as nothing.
A render shows the texts as they were when it was made; after an edit, render again.

### 7.0 Render

`render (graph)` is the rendered layer's entry point: a free function of that layer that takes a
`document graph` and returns its `rendered` tree, built from the graph's current texts and
overrides. Going up a layer is the upper layer's function, so the low level depends on nothing
here (6.2; owner, 2026-10-29). It is pure: it reads no file, and an unread extension copy renders as
nothing (its edge is in the graph's `unread ()`). It MUST be synchronous, in every binding.

It is the one home of the render algorithm. It reads the graph through the low level's members; a
binding MAY also give it package-internal access to what the graph already worked out (the
binding of variables and copies), so the work is not done twice, but never the reverse: no
low-level module calls into the rendered layer. A binding exports `render` from its rendered module
and MAY re-export it at its top level.

### 7.1 Rendered

| Member | Contract |
|---|---|
| `block` | the top-level readable directives |
| `unreadable` | top-level statements that could not be read; their siblings stay |
| `origin` | a `directive origin`: the root file at 0:0, zero width, `via` empty: where a problem with no line of its own is placed |
| `diagnostics` | every file's syntax diagnostics (documents in order), then every problem the expansion found (low-level and render codes alike) in one walk order: the graph's `diagnostics` (6.3) with the render's codes kept in their places |
| `graph` | the graph it was rendered from |
| `walk (visit)` | every directive, depth-first in written order (7.5) |
| `error (message, code)` | returns (does not raise) a `diagnostic error` for a problem of the whole file. `code` is required, a program code; misuse error for a code without `/` |
| `addresses (key?)` | every directive's `address` under the key rule, in walk order. The key rule is called once per directive, parents before children. A key rule may fail; `addresses` and `diff` then fail with that failure unchanged, not wrapped. This is the one home of the address rule; `diff` uses it |
| `diff (after, key?)` | what differs from this render (the before) to `after`, another render (7.6). Any two renders may be compared, whichever graph or processor made them |

### 7.2 Directive

| Member | Contract |
|---|---|
| `name` | |
| `values` | its values, expanded, as `argument`s |
| `block` | its block's readable directives; absent when written without a block |
| `unreadable` | its block's statements that could not be read; empty when none |
| `parent` | the enclosing directive; absent at the top level |
| `origin` | a directive origin: where its name was written, and the uses and includes that brought it |
| `written` | the `written directive` this is a copy of: the same object for every copy of one line |
| `walk (visit)` | every directive inside this one, not itself (7.5) |
| `closest (predicate)` | this directive or its nearest enclosing one that matches |
| `error (message, code)` | returns a `diagnostic error` placed on its name (`code` as on `rendered`) |

An `unreadable` (rendered) has `reason` (from the `unreadable reason` list: `syntax`, `expansion`,
`value`, `extension`), `origin` and `written` (the statement that could not be read). It has no
name or address. (`kind` names a thing's type everywhere, so the reason has its own word:
glossary.)

### 7.3 Argument

An `argument` is a rendered value. It builds on the `expanded value` (2.9): it has everything an
expanded value has (`kind`, `text`, `origin`, the readers, `error`), its `items` are arguments, and
it adds three links to the low level, `written`, `definition` and `chain`:

- `written` is the written value on **the same line**: the line of the statement this value is read
  in. For a value that came through a variable it is the `$name` there (`chain[0].reference`: for
  `max_count $pixels;`, the `$pixels` on `max_count`'s line); a list item that came through a
  variable shares its list's `$name`; otherwise it is the value itself, which is also its
  `definition`. Never absent. Editing it edits that one written line and no other (`replace with
  text` on that `$pixels` unbinds it from the variable), but every copy of the line shares it: a
  file included twice has one line read in both copies (`statement`'s `copies ()`, 6.5), so the
  edit shows in both renders of it. To change one copy only, edit what that copy is given (its
  include block's `set` line, at the include step of `chain`).
- `definition` is the written value at the **end of the chain** (for `$pixels`, the `2284` in its
  `set` line); absent for an override. Editing it changes every use.
- `chain` has one `reference resolution` per variable step of `origin.via`, from the value's own
  line toward where it is written: `[0]` is the `$name` on the directive's line. Empty when the
  value is read where it is written. (`resolutions ()` names only the per-copy list on a written
  reference, 6.6.)

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
  (7.1).

> **Known gap:** a key holding a lone surrogate is written `\udxxx` (lowercase) by TypeScript and
> raw by Python's `json.dumps`. No corpus covers `address text` or `people form` yet (section 9);
> the load cases cover the people form of plain keys.

### 7.5 Walking

`walk` visits every directive below its start, depth-first in written order (pre-order: a
directive, then everything in its block, then its next sibling). The start itself is never
visited: walking a `rendered` visits every directive, walking a directive visits those inside it. A
binding MUST let the caller skip a directive's block and stop early. Whether to descend is decided
after the directive is visited and before its block: a callback's answer, or in a generator form,
the `descend` question asked when the caller asks for the next directive. `walk` is a method of
the rendered tree and of a directive in every binding (6.2's rule). TypeScript takes a callback that
may return `"skip"` or `"stop"`; Python's `walk(descend=...)` is a generator with a `descend`
predicate, stopped with `break`.

> **Proposed (pending owner):** `walk({ descend })` is a generator in both bindings, offered on
> both layers, with `closest`, `directives (name?)` and `statements of (kind, name?)`. See
> [review.md, naming rule 5](../.claude/design/consumer-api/round13/review.md#naming-and-structure-rules-across-languages).

### 7.6 Diff

A render's `diff (after, key?)` lists what differs from it (the before) to `after`, matched by
address under the key rule. It lives on the render because it compares two renders (6.2's rule).

- A `change` is one of the `change kind` list: `added` (`address`, `after`), `removed` (`address`,
  `before`), `changed` (`address`, `before`, `after`: same address, but its own values by text, or
  whether it has a block, differ), `unknown` (`address`, `before`).
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
| `report (at, message, code)` | append the diagnostic `at.error(message, code)` would carry; `at` is anything with `error (...)` (a rendered tree, a directive, an argument, an expanded value). `code` is required, as there |
| iterate | the diagnostics in the order added |
| `count` | how many |
| `collect (read)` | run `read`; when it raises a `diagnostic error`, append its diagnostic and return absent instead; any other error passes through; otherwise return `read`'s result |

Today TypeScript has `new Diagnostics(initial)`, `add`, `report`, `length`, iteration and
`collect(read)`; Python has `Diagnostics(initial)`, `add`, `report(at, message, code=...)`,
`len()`, iteration, and `collect` as the context manager `with problems.collecting():`, the Python
idiom for "run this block, catching one kind of error".

## 8. High level (future)

Idiomatic sugar per language (bead vil-xlo) is not built. It stays per language. When it is built,
it MUST use the spec names of the concepts it exposes and the error groups of 2.8, and MUST be
buildable purely on top of the layers above.

## 9. Conformance

The shared cases in `conformance/` are how a binding proves it meets this page. A binding meets a
section when its runner produces every expected file of that section's cases **byte for byte**. The
expected outputs were derived by hand from the rules, not generated by an implementation: a runner
that disagrees has found a bug in itself or in the rules, never a reason to rewrite an expected
file. A rule found wrong is reported as a finding against this page.

| Case files | Format | Covers |
|---|---|---|
| `conformance/cases.json`, `extra.json`, `depth.json`, `edge.json`, `tracer.json`, `variables.json`, with `conformance/expected/` | [conformance/format.md](../conformance/format.md) | 2.1 (positions in UTF-16), 2.4 (1xxx and 2xxx codes), 2.5 (nesting), 3 |
| `conformance/load/cases.json`, `conformance/load/expected/` | [conformance/load/format.md](../conformance/load/format.md) | 2.2, 2.4 (3xxx to 5xxx), 4.3 (`memory source`), 5, 6.2 (`load` with `overrides`), 7.0 (`render (graph)`), 7.1, 7.2, 7.3 (canonical text and origins), 7.4 (people form, with the `rasl` key rule), 7.6 |
| `conformance/written/cases.json`, `conformance/written/expected/` | [conformance/written/format.md](../conformance/written/format.md) | 6.3 to 6.9, by its `needs` tokens: `values`, `directive-values`, `statements`, `blocks`, `rename`, `document`, `override`, `save`, `quote`, `include`, `snippet`; and 7.3's `definition` and `chain` |

Rules for every runner:

- A runner MAY skip a case whose `needs` it does not implement yet. A finished binding skips nothing,
  and its runner SHOULD assert that its feature set covers every case's needs.
- Every output follows the byte rules of `conformance/format.md`: no extra whitespace, every
  character above U+007F as a lowercase `\uXXXX` UTF-16 escape, one trailing newline.

Not covered by any shared case today (each binding tests these on its own): the readers `word`
through `plain` (2.9); `address text` and keys needing escapes in the `people form`; `format diagnostic`;
the diagnostics sink; `error (...)`; the file and fetch adapters; `-0`, numbers beyond 2^53-1 and a
lone `"\r"`; an override's text refused at `load` (`"1;"`: the `set override` case covers the
check, no case covers `load` refusing it);
`quote` of a character a string cannot hold (6.9); paths whose sort differs between code points
and UTF-16 units (4.1); comment ownership across a blank line or over several comment lines (6.5);
the override order after `set override` (6.2); `argument type error` for a value that is not text
(6.9); the same-line `written` of a rendered value (7.3); a commented extension line in a written-case copy
text (`conformance/written/format.md`).

> **Proposed (pending owner):** conformance levels a binding claims (L0 syntax, L1 low level, L2
> rendered tree, L3 extensions, L4 adapters); new corpora for readers, addresses and formatting;
> one shared driver with a small adapter per binding. See [review.md, root cause 5](../.claude/design/consumer-api/round13/review.md#root-cause-5-no-neutral-spec-and-nothing-generated-from-one-source)
> and [codegen.md](codegen.md).
