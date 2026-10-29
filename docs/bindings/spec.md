# villanelle language-binding specification

Status: describes the API as it stands on `feat/low-level-layer` (PR 4). Nothing here is locked: the
owner approves API shapes ("Nothing is locked until I see user APIs that I like", 2026-10-27). Where
the round 13 review proposes a change, a note marked **Proposed (pending owner)** links to
[review.md](../../.claude/design/consumer-api/round13/review.md). Those notes are not agreed.

This page is the one home of the rules a binding must follow. How to turn them into a binding in a
given language (names, idiom, what may differ) is in [design-guide.md](design-guide.md). The
language itself (what a config file may say) is in [docs/language.md](../language.md).

## 1. How to read this page

- **MUST**, **MUST NOT**, **SHOULD** and **MAY** mean what RFC 2119 says they mean.
- Each concept and operation has one **spec name**, written in lowercase words in backticks:
  `document graph`, `set values`. A binding spells that name in its language's casing; the casing
  rules are in the design guide. A binding MUST NOT give a spec concept a different word.
- "Absent" means the language's no-value (`undefined` in TypeScript, `None` in Python).
- "In order" lists are ordered as stated. When a list's order is stated, a binding MUST keep it:
  the conformance outputs depend on it.
- "Text" means the language's string type. Values going into edits are villanelle text (see 6.9).
- Error groups are named here (for example "misuse error"); which native class each group maps to
  is the binding's choice within the rules of 2.8 and the design guide.

> **Proposed (pending owner):** the review proposes splitting this page into `spec/glossary.md`,
> `spec/layers/*.md`, `spec/contract.md` and a schema, and renaming several concepts (root cause
> 1). See [review.md, root causes 1 and 5](../../.claude/design/consumer-api/round13/review.md#root-cause-1-no-shared-glossary-so-each-layer-named-things-on-its-own).

## 2. Shared pieces

These are used by more than one layer.

### 2.1 Positions and spans

- A `source position` has `offset`, `line` and `column`, all counting from 0.
- `offset` and `column` count **UTF-16 code units** in every binding today. This is also the unit of
  every conformance output.
- A line ends after each `"\n"`. `"\r\n"` ends one line. A lone `"\r"` does **not** end a line.
- A `source span` is a half-open range `[start, end)` of two positions, with
  `start.offset <= end.offset`.

> **Proposed (pending owner):** each binding reports positions in its own string unit (code points
> in Python), so slicing a string at a reported position gives the right text; conformance runners
> convert to UTF-16. Today a Python offset is not a `str` index once a character outside the Basic
> Multilingual Plane comes before it. See [review.md, root cause 4](../../.claude/design/consumer-api/round13/review.md#root-cause-4-the-contract-at-the-edges-is-not-written-down-neutrally).

> **Known gap:** the two bindings were reported to disagree on a lone `"\r"` and on `-0` (review
> finding P3). No conformance case covers either yet.

### 2.2 Place, step, origin

- A `place` is a range of one file's text: `kind` `"file"`, `resolved path` (the file's identity as
  the document source gave it) and `span`.
- A `handed` origin is a value the program handed in at load, written in no file: `kind`
  `"handed"` and `variable` (the name without `$`).
- A `step` is one expansion a directive or value went through: `kind` (one of the `step kind`
  list: `variable`, `use`, `extension`), `name` (the variable without `$`, the snippet, or the
  extension directive) and `at` (the place of the `$name` token, the `use` line's name, or the
  extension line's name).
- An `origin` is `written` (a place, or a handed origin) plus `via` (steps, innermost first; empty
  when the text is read where it was written). For a value from a variable, `written` is the value
  in its `set` line (or the handed origin) and `via[0]` is the `$name` that used it.
- A `directive origin` is an origin whose `written` is always a place.

All of these are plain, read-only data.

### 2.3 Diagnostics

- A `diagnostic` (syntax layer) has `code`, `message` and `span`.
- A `located diagnostic` (every other layer) has `code`, `message`, `at` (a place) and `via`
  (steps, innermost first). A problem caused by a handed-in value is placed at the `$name` that used
  it, and the message names the handed-in variable.
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
which operation reports it.

| Code | Spec name | Found by | Meaning |
|---|---|---|---|
| E1001 | `unterminated string` | parse | A string reaches the end of its line or of the text without its closing quote. |
| E1003 | `unexpected character` | parse | A character no token may start with, or a byte-order mark after the first character. |
| E1004 | `lone dollar` | parse | A `$` not followed by a variable name. |
| E2001 | `unexpected token` | parse | A token the grammar does not allow here, when no more specific code applies. |
| E2003 | `expected closing brace` | parse | The text ends inside a block. |
| E2004 | `expected closing bracket` | parse | A stray `]`, or a `[` list with no matching `]`. |
| E2007 | `bad slice` | parse | A malformed slice after a word: `a[:]`, `a[1:b c]`, an unclosed slice. |
| E2008 | `brace on own line` | parse | A `{` that starts its line. |
| E2009 | `values touch` | parse | Two values with nothing between them, such as `a"b"`. |
| E2010 | `nesting too deep` | parse | Blocks and lists nested deeper than 100 levels. |
| E3001 | `include not found` | load, read | An extension's spec matched no file. |
| E3004 | `include resolver failed` | load, read | The document source rejected while resolving or reading a file. For the root file, `load` fails instead (6.2). |
| E3005 | `include bad path` | include extension | An `include` whose values are not exactly one quoted path. |
| E3006 | `extension failed` | load, read | An extension threw something other than a diagnostic error. |
| E4001 | `non-integer bound` | low level | A slice or index bound that is not an integer. |
| E4002 | `wrong value kind` | readers | A reader asked for a kind the value is not. |
| E4003 | `bad escape` | low level | A backslash escape other than the six the language allows. |
| E4004 | `not a number` | readers | A word read as a number that is not a JSON number. |
| E4005 | `not an integer` | readers | A word read as an integer that is not one. |
| E4006 | `not a boolean` | readers | A word other than `true` or `false`, read as a boolean. |
| E5001 | `unknown variable` | render | A `$name` with no `set` visible and no handed-in value. |
| E5002 | `variable set twice` | low level | Two `set` lines for one name in one block. |
| E5003 | `unknown snippet` | render | A `use` naming no visible snippet. |
| E5004 | `snippet arity` | render | A `use` with a different number of values than its snippet's parameters. |
| E5005 | `snippet defined twice` | low level | Two `snippet` lines for one name in one block. |
| E5006 | `expansion cycle` | low level | A `use` or extension line that reaches itself again. |
| E5007 | `expansion too deep` | low level | `use` and extension lines nested deeper than 16. |
| E5008 | `too many directives` | render | More than 100,000 directives after expansion. |
| E5009 | `bad set` | low level | A `set` that is not `set $name value...;`. |
| E5010 | `bad snippet` | low level | A malformed `snippet`, or one naming a parameter twice. |
| E5011 | `bad use` | low level | A `use` that is not `use name value...;`. |
| E5012 | `extension block not set` | low level | An extension line whose block holds a line other than `set`. |

"Low level" codes appear in `document graph` `diagnostics`; "render" codes appear only in the
`rendered` tree's `diagnostics` (6.3, 7.1).

> **Proposed (pending owner):** generate this table and each binding's registry from one schema
> ([codegen.md](codegen.md)); mark which layer owns each code, and stop naming E3001, E3004 and E3005
> after `include` in the core list (review, "Deferred").

### 2.5 Limits and reserved names

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

Every binding maps these groups onto its own error classes. Today:

| Group | Raised when | TypeScript today | Python today |
|---|---|---|---|
| problems in the config text | never raised: reported as diagnostics | | |
| `diagnostic error` | 2.6 | `DiagnosticError` | `DiagnosticError` |
| `read error` | `load` cannot resolve or read the root (a diagnostic error, E3004 at the root path) | `ReadError` | `ReadError` |
| `edit error` (base) | an edit refused; nothing changed | `EditError` | `EditError` (a `ValueError`) |
| `bad text error` | the text given to an edit is not what it takes | `BadTextError` | `BadTextError` |
| `detached error` | a member of a detached handle was used | `DetachedError` | `DetachedError` |
| `no set line error` | `set values` or `rename` on a variable with no `set` line | `NoSetLineError` | `NoSetLineError` |
| `save error` | the writer rejected | `SaveError` | `SaveError` |
| misuse error | a bad argument a program could have checked | `TypeError` | `ValueError` |
| index out of range | an insert index outside a block | `RangeError` | `IndexError` |

A binding MUST raise the same group in the same situation. An edit that raises an `edit error`
MUST leave every document unchanged.

> **Proposed (pending owner):** one package base error per binding; `detached error` stops being an
> edit error (Python: under `ReferenceError`); `save error` and `read error` get the same fields;
> `no set line error` is deleted because each variable kind gets its own type; one check for
> handed-in text used by both `load` and `set handed`. See [review.md, root causes 2 to 4](../../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).

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
| `parse` | text | `syntax`: `tokens`, `root` (a `document` node over every token), `diagnostics` (in source order) | none: total for any string, never reads files |
| `span of` | syntax, token range | the range's span; an empty range at `i` is zero-width at token `i`'s start, or at the text's end when `i` is the token count | index out of range when the range is outside `[0, count]` or `start > end` |
| `text of` | syntax, token range | the exact source text; `text of(syntax, root)` is the whole input | as `span of` |

`diagnostics` MUST be empty exactly when the input is in the grammar's language.

## 4. Ports: where files come from and go to

The core MUST NOT do I/O. Files come in through a `document source` and go out through a `document
writer` that the program supplies.

### 4.1 Document source

- `resolve (spec, load context)` returns the resolved paths a spec names (a path, or a glob with `*`
  and `?` in its last segment), in any order. Empty means "not found" (E3001). A failure becomes
  E3004 at the extension line.
- `read (resolved path)` returns the text of one resolved file. A failure becomes E3004, or for the
  root file makes `load` fail with a `read error`.
- A `load context` has `parent path`: the resolved path of the file holding the extension line, or
  empty when the root path itself is resolved.
- A load MUST call `read` at most once per resolved path, however many places splice the file in.
- In a binding whose I/O is asynchronous, both operations MAY be asynchronous.

### 4.2 Document writer

- `write (files)` takes one batch of `file write` records and commits them together. A failure
  while staging means nothing was committed. A writer that can fail part way through committing
  leaves the files it committed changed while their `saved text` stays the old one, so the next save
  treats them as lost updates until the program reloads (a stated cost).
- A `file write` has `resolved path`, `text` (what to write) and `source` (the document's last-read
  or last-saved text, to compare with the disk and find a lost update).

### 4.3 Adapters

| Spec name | Port | Required | Notes |
|---|---|---|---|
| `memory source` | source | MUST | Texts keyed by path. `resolve` joins the spec to the directory of `parent path` by POSIX rules (`/` separators, `.` and `..` removed, a leading `/` taken as is) and returns the path when it is a key; a glob returns every key in that directory it matches. `read` of a missing key fails. Pure. |
| `file source` | source | SHOULD | The local filesystem. |
| `file writer` | writer | SHOULD | The local filesystem. |
| `fetch source`, `fetch writer` | both | MAY | HTTP. TypeScript only today. |

> **Proposed (pending owner):** every binding ships memory and file adapters for both directions,
> each named after its medium and port (a `memory writer` is new). See [review.md, root cause 4](../../.claude/design/consumer-api/round13/review.md#root-cause-4-the-contract-at-the-edges-is-not-written-down-neutrally).

## 5. Extensions

An `extension` owns one directive name and turns each use of it into specs of files to splice in its
place. It is not part of the core; a program turns it on when it makes the processor.

- An extension has `directive` (the name it owns) and `specs (extension use)`, which returns the
  specs for one use, in splice order. It MUST be pure: the load resolves and reads the specs, parses
  each file once, applies the use's block of `set` lines to the spliced files, and enforces depth,
  cycles and limits.
- An `extension use` has `args` (the line's values, expanded, as rendered `argument`s, 7.3) and
  `origin` (a directive origin).
- `specs` throws a `diagnostic error` for a located failure. Any other failure becomes E3006 at the
  directive.
- Making a processor MUST refuse, with a misuse error, an extension whose name is reserved (2.5) or
  already taken by another extension.

### 5.1 The include extension

`include "path";` or `include "path" { set $name value; }`. The one value MUST be a quoted path or
glob (E3005 otherwise, placed on the value). Matching files are spliced in code-point order of
resolved path. An included file's top-level `set` and `snippet` lines are visible after the include
line in the including block.

## 6. Low level: the config as written

The low level is the files as written: editable, saved back. Today the `processor` that makes
graphs also renders and compares them (6.2); the proposal there would remove that link.

**Design rule:** the texts and the handed-in values are the only source of truth. Copies, edges,
variables and resolutions are worked out from them when asked; the objects returned (`copy`,
`document edge`, `resolution`) are snapshots of one working-out, not handles. The only other state
is which files were read.

### 6.1 Handles and identity

- Each written thing (document, statement, value, variable) MUST be one object for the life of its
  graph: asking twice gives the same object (identity comparison holds).
- A handle follows its tokens across other edits.
- A handle whose tokens an edit removed, or whose document's whole text was replaced, is
  **detached**. Every member of a detached handle except `kind` MUST raise a `detached error`.
- Snapshots (`copy`, `document edge`, `resolution`, `reference resolution`) are plain data; the
  handles inside them are live.

### 6.2 Processor

| Spec name | Inputs | Output | Errors |
|---|---|---|---|
| `make processor` | `source` (a document source), `extensions` (optional, in order) | a `processor` | misuse error for a reserved or repeated extension name |
| `load` | root `path`; option `variables` (handed-in values: name without `$` to villanelle text) | a `document graph` | `read error` when the source cannot resolve or read the root; misuse error for a bad handed-in name (not letters, digits and `_`) or text that is not one or more values. Never fails for anything in the text. |
| `read` | a graph | the resolved paths read, in read order | misuse error for a graph another processor loaded |
| `render` | a graph | a `rendered` tree (7.1) | misuse error for a graph another processor loaded |
| `diff` | two `rendered` trees; option `key` (a key rule) | a list of `change`s (7.6) | misuse error when either render came from another processor; whatever the key rule throws |

- `load` resolves the root path through the source as an included file's spec is, so the root has
  one path in the graph. It reads every file that extension lines name, once each, repeating until
  nothing new is named.
- `read` resolves and reads what `unread` names (6.3), repeating until nothing new is named. It
  keeps every text and every failure it already had.
- A handed-in value wins over every `set` of its name, which acts as the default.
- In a binding whose I/O is asynchronous, `load` and `read` MAY be asynchronous. `render` and
  `diff` MUST be synchronous and pure.

> **Proposed (pending owner):** the processor only loads; `read` and `save` become graph methods;
> going up a layer is a function of the upper layer (`render(graph)`); `diff` lives on a render;
> the "another processor's graph" check is removed. The review recommends this as question 1
> option A and rejects `graph.render()`. See [review.md, root cause 2 and question 1](../../.claude/design/consumer-api/round13/review.md#1-where-does-render-live).
>
> **Proposed (pending owner):** one word for handed-in values, used going in and coming out
> (recommended `overrides`). See [review.md, question 2](../../.claude/design/consumer-api/round13/review.md#2-one-word-for-the-values-a-program-passes-in).

### 6.3 Document graph

| Member | Kind | Contract |
|---|---|---|
| `root` | property | the root `document` |
| `documents` | property | every document read, by resolved path, root first, then in first-read order; never shrinks |
| `handed` | property | handed-in values by name (without `$`), each as villanelle text; never saved |
| `set handed (name, text or absent)` | method | add, change, or (with absent) remove one handed-in value without a reload. `bad text error` (located in `text`) when `text` is not one or more values without a `$name`; misuse error for a bad name |
| `edges ()` | method | every copy of every extension line, in walk order, as `document edge`s |
| `unread ()` | method | the edges naming a spec not resolved or a file not read yet; non-empty means copies and `render` lack them |
| `variables (name?)` | method | every variable (of that name when given): `set` and parameters in document order, then handed-in ones |
| `diagnostics ()` | method | each document's syntax diagnostics (documents in order), then what the low level found, in walk order. It MUST NOT include the codes `render` owns: E5001, E5003, E5004, E5008. (The reader codes E4002 and E4004 to E4006 never arise here; E4001 and E4003 do.) |

### 6.4 Document, edge, copy

`document`:

| Member | Contract |
|---|---|
| `resolved path` | its identity |
| `source` | the text as read, or as last handed to a writer that succeeded |
| `text` | the text now; differs from `source` exactly when there are unsaved changes |
| `syntax` | the syntax layer's result for `text` |
| `body` | a `written block` of its top-level statements |
| `included by ()` | the include copies that splice it in; empty for the root and for a file no include reaches now |
| `replace with text (text)` | replace the whole text; takes any text, broken or not. Every handle into the document detaches except the document's own; `source` is untouched |

`document edge` (snapshot): `copy` (whose `statement` is the extension line, editable), `specs` (as
the extension gave them; empty when its values failed), `targets` (every file matched, in splice
order; empty when it failed or is unread).

`copy` (snapshot): `statement`, and `via` (the include and `use` steps that bring it there,
innermost first; empty at the root).

> **Proposed (pending owner):** `source` here and in `file write` is renamed `saved text`, because
> `source` also names the reader port. See [review.md, root cause 1](../../.claude/design/consumer-api/round13/review.md#root-cause-1-no-shared-glossary-so-each-layer-named-things-on-its-own).

### 6.5 Statements

A `statement` is one of the `statement kind` list: `directive`, `extension`, `set`, `snippet`,
`use`, `unreadable`. Every statement has:

| Member | Contract |
|---|---|
| `kind` | from the list |
| `document` | the document holding it |
| `parent` | the statement whose block holds it; absent at a document's top level |
| `place` | from its first owned token to its last, comments it owns included |
| `text` | exact, with the comments it owns; without the indentation before it and the line break after it |
| `copies ()` | every place it is read now, in walk order; empty when no copy reaches it |
| `replace with text (text)` | replace it and its owned comments with zero or more statements; returns the new statements; this handle detaches. `bad text error` |
| `remove ()` | remove it with its owned comments, and its line when nothing else is on it; then it is detached |

Per kind:

| Kind | Type (spec name) | Extra members |
|---|---|---|
| `directive`, `extension` | `written directive` | `name`; `values` (in order; an include line's path); `block` (absent when written without one; an include line's `set` lines); `rename (name)`: `bad text error` when not one word, or a name that would change its kind; `set values (text)`: replace its values, comments between them included, `bad text error` |
| `set` | `set line` | `variable`; `values` (after the `$name`); `set values (text)`: `bad text error`, also for empty text (E5009) |
| `snippet` | `snippet line` | `name`; `parameters` (variables); `block` (always present) |
| `use` | `use line` | `snippet name`; `snippet` (by where written: a `snippet` line above it in its file; absent when free); `snippets ()` (per copy, a `resolution` of which snippet it splices); `values` (bound to parameters by position); `set values (text)` |
| `unreadable` | `unreadable line` | none. A statement that does not parse, a malformed `set`/`snippet`/`use`, or a second `set` of a name in one block |

A `written block` (a document's top level, or a statement's block):

| Member | Contract |
|---|---|
| `statements` | in order |
| `directives (name?)` | its statements of kind `directive`, of that name when given |
| `insert statements (index, text)` | insert before `statements[index]` (`index` equal to the count appends), indented as siblings, inner lines keeping their own relative indentation; returns the new statements. `bad text error`; index out of range |
| `add statements (text)` | `insert statements(count, text)` |

> **Proposed (pending owner):** `body` becomes `block` everywhere; blocks are iterable and indexable
> in every layer with one `walk`; `insert before`/`insert after` on a statement; include lines get
> their own type; `statements of (kind, name?)` returns typed results so no cast is needed. See
> [review.md, root causes 1 and 3](../../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).

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

Per kind: `list` has `items`; `slice` has `name`, `start` and `end` (each a word or reference, or
absent); `index` has `name` and `index` (a word or reference); `reference` (one `$name`) has `name`
(without `$`), `declaration` (by where written: the nearest `set` above it in its file, or its
snippet's parameter; absent when free) and `resolutions ()` (one `reference resolution` per copy of
its statement, in walk order).

### 6.7 Variables and resolutions

A `variable` is one of the `variable kind` list: `set` (a `set` line's `$name`), `parameter` (a
snippet's), `handed` (a handed-in value).

| Member | Contract |
|---|---|
| `kind`, `name` | |
| `place` | its `$name`; absent when handed in |
| `line` | its `set line` or `snippet line`; absent when handed in |
| `references ()` | the references whose `declaration` it is, reached or not, in document order |
| `reaches ()` | the resolutions in which it wins, in walk order |
| `overridden ()` | the resolutions in which another variable wins, in walk order |
| `rename (name)` | rename its `$name` only. `bad text error` (also E5002); `no set line error` when handed in |
| `set values (text)` | its `set` line's values. `no set line error` for a parameter or a handed-in value; `bad text error` |

A `resolution` (snapshot, at one copy): `copy`; `winner` (absent when nothing of that name is
visible there, which `render` reports as E5001 or E5003); `overridden` (every other visible
definition, next first: the one that would win if the winner were gone).

A `reference resolution` adds `reference` and `values`: the winning `set` line's values, or for a
parameter the `use` line's values bound to it; empty when handed in or unbound. A reference renders
to all of `values` (`set $ports 8080 443;` gives two).

> **Proposed (pending owner):** `wins ()` and `shadowed at ()` replace `reaches ()` and
> `overridden ()`; a resolution's `overridden` becomes `shadowed`; each variable kind becomes its
> own type so `set values` exists only where it can succeed. See [review.md, root causes 1 and 3](../../.claude/design/consumer-api/round13/review.md#root-cause-3-the-types-do-not-carry-the-kinds).

### 6.8 Saving

`save (graph, writer)`:

1. Collect every document whose `text` differs from its `source`, in `documents` order.
2. With none, MUST NOT call the writer, and returns an empty list.
3. Otherwise hand them to the writer in one batch.
4. When the writer succeeds, each written document's `source` becomes the text handed over (an edit
   made while the writer ran stays unsaved). Return the resolved paths handed over.
5. When the writer fails, no `source` changes, and `save` raises a `save error` with `files` (what
   was handed over) and the writer's failure as its cause.

### 6.9 Values going in: `quote`

Every edit takes villanelle text, not program values (owner, 2026-10-28: "values: A, new values
written as villanelle text, with quote()"). `quote (text)` returns a plain string written as a
villanelle string, escapes included: `quote("10.0.60.31")` is `"10.0.60.31"`. It MUST give the same
canonical string text a rendered value has (7.3).

> **Proposed (pending owner):** every edit refuses a non-text argument with a clear misuse error
> (today Python's `set_values(2400)` fails inside the library); or, as an alternative, also accept
> program values. See [review.md, question 3](../../.claude/design/consumer-api/round13/review.md#3-values-going-in-text-only-or-program-values-too).

## 7. Rendered tree (the middle layer)

The rendered tree is directives after expansion: variables replaced, snippets and extension files
spliced in. It is read-only. `set`, `snippet`, `use` and extension lines never appear in it; their
results do, in their place. A render reads no file: an unread include copy renders as nothing.
A render shows the texts as they were when it was made; after an edit, render again.

### 7.1 Rendered

| Member | Contract |
|---|---|
| `body` | the top-level readable directives |
| `unreadable` | top-level statements that could not be read; their siblings stay |
| `origin` | the root file at 0:0, zero width: where a problem with no line of its own is placed |
| `diagnostics` | every file's syntax diagnostics (documents in order), then the render's problems in walk order |
| `graph` | the graph it was rendered from |
| `walk (visit)` | every directive, depth-first in written order (7.5) |
| `error (message, code)` | a `diagnostic error` for a problem of the whole file; misuse error for a code without `/` |
| `addresses (key?)` | every directive's `address` under the key rule, in walk order. The key rule is called once per directive, parents before children; what it throws propagates. This is the one home of the address rule; `diff` uses it |

### 7.2 Directive

| Member | Contract |
|---|---|
| `name` | |
| `args` | its values, expanded, as `argument`s |
| `body` | its block's readable directives; absent when written without a block |
| `unreadable` | its block's statements that could not be read; empty when none |
| `parent` | the enclosing directive; absent at the top level |
| `origin` | a directive origin: where its name was written, and the uses and includes that brought it |
| `written` | the `written directive` this is a copy of: the same object for every copy of one line |
| `walk (visit)` | every directive inside this one, not itself (7.5) |
| `closest (predicate)` | this directive or its nearest enclosing one that matches |
| `error (message, code)` | a `diagnostic error` placed on its name |

An `unreadable` (rendered) has `kind` (from the `unreadable kind` list: `syntax`, `expansion`,
`value`, `extension`), `origin` and `written` (the statement that could not be read). It has no
name or address.

### 7.3 Argument and its readers

An `argument` has `kind` (a value kind without `reference`: `word`, `string`, `list`, `slice`,
`index`), `text` (canonical, below), `origin`, `written` and `resolutions`:

- `written` is the written value at the **end of its chain** (for `$pixels`, the `2284` in its
  `set` line); absent when handed in.
- `resolutions` has one `reference resolution` per variable step of `origin.via`, from the value's
  own line toward where it is written: `[0]` is the `$name` on the directive's line. Empty when the
  value is read where it is written.

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
| `number` | a word spelling a JSON number (`8080`, `0.5`; not `20hz`) | E4002, E4004 |
| `integer` | a word spelling an integer | E4002, E4005 |
| `boolean` | the word `true` or `false` | E4002, E4006 |
| `items` | a list's items, each an argument with its own origin | E4002 |
| `slice` | a `slice value` (`name`, optional `start`, optional `end`) or an `index value` (`name`, `index`) | E4002 |
| `plain` | any value by one rule: a string is its text; a word is a number if it spells one, a boolean if `true`/`false`, else its text; a list is its items read the same way; a slice or index is its value | never |
| `error (message, code)` | a `diagnostic error` placed on this value; for a handed-in value, on the `$name` that used it | misuse error for a code without `/` |

Quoting means text: `"8080"` and `"true"` are strings. Only a bare word is read as a number or a
boolean. Slice and index bounds are integers within the safe integer range.

> **Known gap:** `plain("-0")`, integers beyond 2^53-1, and `1e400` have no stated rule and no
> conformance case. TypeScript gives `-0` and Python `0` today.
>
> **Proposed (pending owner):** a value's `written` means the handle on **the same line** (the
> `$pixels` on `max_count`'s line), and a new `definition` names the value at the end of the chain;
> `args` becomes `values`; the rendered `resolutions` becomes `chain`; `kind` narrows the type so
> `items` is offered only on a list. See [review.md, root causes 1 and 3](../../.claude/design/consumer-api/round13/review.md#root-cause-1-no-shared-glossary-so-each-layer-named-things-on-its-own).

### 7.4 Address and key rule

- An `address step` has `name`, `key` (what the key rule returned; absent when nothing or no rule)
  and `occurrence` (0-based among earlier siblings with the same name and key).
- An `address` has `steps` (top level down), `text`, `parent` (absent at the top level) and a
  people form.
- `text` MUST be the same bytes in every binding: the JSON array of `[name, key or null,
  occurrence]` per step, with no spaces, as JavaScript's `JSON.stringify` writes it.
- The people form: each step as its name, then a space and the JSON-quoted key when there is one,
  then ` #n` when the occurrence is not 0, joined by ` > `: `graph > node "leds" > max_count`.
- Addresses are unique within one render. A file included at two places, or a snippet used twice,
  lands at two addresses.
- A `key rule` takes a rendered directive and returns text or absent. It is the program's rule for
  naming a directive among its siblings, so it keeps its address when lines move.

### 7.5 Walking

`walk` visits every directive below its start, depth-first in written order. A binding MUST let the
caller skip a directive's block and stop early. Today TypeScript takes a callback that may return
`"skip"` or `"stop"`; Python is a generator with a `descend` predicate, stopped with `break`.

> **Proposed (pending owner):** `walk({ descend })` is a generator in both bindings, offered on
> both layers, with `closest`, `directives (name?)` and `statements of (kind, name?)`. See
> [review.md, naming rule 5](../../.claude/design/consumer-api/round13/review.md#naming-and-structure-rules-across-languages).

### 7.6 Diff

`diff (before, after, key?)` lists what differs between two renders, matched by address under the
key rule.

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

A `diagnostics` collection is the one place problems collect. It starts with a list (usually a
render's `diagnostics`), and offers: add one, `report (at, message, code)` (at anything with
`error`), iterate in order, count, and a way to run one read so that a `diagnostic error` is
recorded instead of raised (any other error passes through). Today TypeScript has `collect(read)`
and Python a `collecting()` context manager.

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
| `conformance/cases.json`, `extra.json`, `depth.json`, `edge.json`, `tracer.json`, `variables.json`, with `conformance/expected/` | [conformance/format.md](../../conformance/format.md) | 2.1 (positions in UTF-16), 2.4 (1xxx and 2xxx codes), 2.5 (nesting), 3 |
| `conformance/load/cases.json`, `conformance/load/expected/` | [conformance/load/format.md](../../conformance/load/format.md) | 2.2, 2.4 (3xxx to 5xxx), 4.3 (`memory source`), 5, 6.2 (`load` with `variables`, `render`, `diff`), 7.1, 7.2, 7.3 (canonical text and origins), 7.4 (people form, with the `rasl` key rule), 7.6 |
| `conformance/written/cases.json`, `conformance/written/expected/` | [conformance/written/format.md](../../conformance/written/format.md) | 6.3 to 6.9, by its `needs` tokens: `values`, `directive-values`, `statements`, `blocks`, `rename`, `document`, `handed`, `save`, `quote`, `include`, `snippet`; and 7.3's `written` and `resolutions` |

Rules for every runner:

- A runner MAY skip a case whose `needs` it does not implement yet. A finished binding skips nothing,
  and its runner SHOULD assert that its feature set covers every case's needs.
- Every output follows the byte rules of `conformance/format.md`: no extra whitespace, every
  character above U+007F as a lowercase `\uXXXX` UTF-16 escape, one trailing newline.

Not covered by any shared case today (each binding tests these on its own): the readers `word`
through `plain`; `address text`; `format diagnostic`; the diagnostics sink; `error (...)`; the file
and fetch adapters; `-0`, numbers beyond 2^53-1 and a lone `"\r"`; handed-in text such as `"1;"`
(accepted by `load`, refused by `set handed` today).

> **Proposed (pending owner):** conformance levels a binding claims (L0 syntax, L1 low level, L2
> rendered tree, L3 extensions, L4 adapters); new corpora for readers, addresses and formatting;
> one shared driver with a small adapter per binding. See [review.md, root cause 5](../../.claude/design/consumer-api/round13/review.md#root-cause-5-no-neutral-spec-and-nothing-generated-from-one-source)
> and [codegen.md](codegen.md).
