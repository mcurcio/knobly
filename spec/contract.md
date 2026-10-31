# The contract at the edges

Status: canonical, like the rest of `spec/` (owner, 2026-10-27: "Within villanelle I want the spec to win over a
reference language"). Written in milestone 2 (bead kno-0vz) from the round 13 review's root cause 4
([review.md](../.claude/design/consumer-api/round13/review.md#root-cause-4-the-contract-at-the-edges-is-not-written-down-neutrally)).
The rules below are design choices adopted with the milestone, not the owner's words; each is revisable. The exact
per-binding classes, names and old-to-new list are on the milestone's frozen page,
`.claude/design/consumer-api/round14/frozen-m2.md`.

This page holds the places where a value or an error crosses from the library into a program: positions, the text a
located thing prints as, numbers, error classes and the adapters. Each rule is stated in neutral terms here, and each
binding maps it once. [spec.md](spec.md) holds everything else and points here.

## 1. Positions

- A `source position` has `offset`, `line` and `column`, all counting from 0 (spec 2.1).
- **Each binding counts `offset` and `column` in its own language's string unit**, so cutting the program's own
  string at a reported position gives the right text:

  | Binding | Unit | `text[start.offset:end.offset]` / `text.slice(start.offset, end.offset)` |
  |---|---|---|
  | TypeScript | UTF-16 code units | the token's text |
  | Python | code points (`str` indices) | the token's text |
  | Go, Rust (when written) | bytes of UTF-8 | the token's text |

- This holds for every position a binding reports or takes: a syntax `diagnostic`'s span, a `place`'s span, the
  `diagnostics` of a `bad text error` (located in the text the edit was given, spec 2.8), `span of`, and the column
  and carets of `format diagnostic`.
- **Lines** do not depend on the unit. A line ends after each `"\n"`; `"\r\n"` ends one line; a lone `"\r"` never
  ends a line, in positions and in `format diagnostic`'s source line alike (a binding MUST NOT use a library split
  that breaks at `"\r"`, U+2028 or other characters: Python's `str.splitlines` does, JavaScript's `/\r\n|\n|\r/`
  does).
- **The conformance corpus stays in UTF-16 units** (round 11 decision D-S3-1). A binding's adapter reports every
  position in the binding's own unit and names the unit in its `hello`; the shared driver converts each one to UTF-16
  before it prints it, in one place (`conformance/driver/units.py`, [conformance.md](conformance.md) section 4), using
  the text the position counts in (the document's text, or the text given to an edit). A character above U+FFFF
  counts two units there.
- Cost: TypeScript and Python report different offsets and columns for the same place when a character outside the
  Basic Multilingual Plane comes before it on its line. A Python program talking to an editor over LSP (whose
  default unit is UTF-16) converts, as pygls already does.

Conformance: `conformance/contract/cases.json` cases `position-astral-value` and `position-astral-print`;
`conformance/written/cases.json` case `set-bad-astral` (a bad text error's column after an astral character). The
lone `"\r"` rule is covered by the syntax cases `lone-cr`, `rec-lone-cr` and `edge-cr-in-comment` and by
`format-lone-cr` here.

## 2. People forms: the text a located thing prints as

Every located thing has a `people form`: the text a person reads, which each binding exposes as its language's
to-text conversion (`toString()` in TypeScript, so `String(x)` and template literals use it; `__str__` in Python,
so `str(x)` and f-strings use it). Lines and columns in it count from 1, columns in the binding's unit (section 1).
It is the same text `format diagnostic` prints, which builds on these forms (one home).

| Thing | People form | Example |
|---|---|---|
| `place` | `path:line:col` (the span's start) | `sink.conf:4:5` |
| `override` (as an origin's place) | `override <variable>` (no `$`) | `override pixels` |
| `step` | `<kind> <name> at <place>` | `variable pixels at main.conf:7:15` |
| `located diagnostic` | `<place>: <code>: <message>` | `main.conf:7:15: E5001: unknown variable: $pixels` |
| `diagnostic` (syntax layer, no file) | `line:col: <code>: <message>` | `1:3: E2004: expected closing bracket` |
| `address` | its people form (spec 7.4), unchanged | `graph > node "leds" > max_count` |

`format diagnostic (diagnostic, graph?)` (spec 2.7) is then: the located diagnostic's people form; when the graph
holds the file, the source line (section 1's line rule) and the caret line under the span (tabs kept, every other
character before the span a space, one caret per unit of the span on its first line, at least one); then
`  via ` and the step's people form, per step, innermost first.

Messages stay for people (spec 2.3); a conformance case writes `{message}` where the message goes.

The review listed `address` among the things that print as `path:line:col`; an address names a directive by its
path of names, not a file position, so its people form stays the one spec 7.4 gives (an erratum on the review).

Conformance: `conformance/contract/cases.json` cases `print-place`, `print-override`, `print-step`,
`print-located-diagnostic`, `print-syntax-diagnostic`, `format-lone-cr`, `format-lone-cr-at-end`, `format-via`,
`format-tab-before`, `format-astral-before` (its carets' column by unit), `format-crlf` and `format-no-graph`.

## 3. Numbers

The spelling of number and integer words is spec 2.9 (`NumberText`, `IntegerText` in `grammar/knobly.ebnf`).
The values are ruled here, the same in every binding:

| Rule | `number` | `integer` |
|---|---|---|
| **Zero** has one sign. Any word whose value is zero (`0`, `-0`, `0.0`, `-0.0`, `-0e5`, `1e-400` after rounding) reads as zero, never negative zero | `0` | `0` (for `-0`) |
| **Integers** lie within plus or minus 2^53-1 (the `integer range` limit) | the value | the value |
| **Beyond 2^53-1**, an integer word is not an integer, but is still a number, rounded to the nearest double (ties to even) | `9007199254740993` gives `9007199254740992` | E4005 |
| **Beyond the double range** (a value whose rounding overflows: `1e400`, `-1e400`), a word is not a number | E4004 | E4005 |
| A tiny value rounds to zero, which the zero rule then reads | `1e-400` gives `0` | E4005 |

(Milestone 5 deleted the `plain` reader and its column: a word is untyped until a typed reader decides, spec 2.9.)

- `number` returns an IEEE 754 double. Python returns an `int` when the word has no fraction or exponent and lies
  within plus or minus 2^53-1, else a `float`, so both bindings read the same value; a Python `float` result is
  never `-0.0`.
- `integer` returns a whole number; a binding MAY use a 64-bit integer type, since every value fits.
- Slice and index bounds are integer words, or E4001 (spec 2.9).
- A conformance case prints a number by one rule so that both bindings give the same bytes: an integer in decimal;
  a double as ECMAScript's `Number::toString` (shortest round trip; `1e+21` from 10^21 up, `1e-7` below 10^-6).
  The shared driver writes that form (`conformance/driver/contract.py`); Python's `repr` of a `float` differs
  (`1e+16` against `10000000000000000`, `100.0` against `100`), so an adapter sends the number itself, never its
  text.

Before milestone 2, TypeScript read `-0` as negative zero and Python as `0` (review finding P3), and both read
`1e400` as infinity. Both are behaviour changes, listed on the frozen page.

Conformance: `conformance/contract/cases.json`, every case of kind `reader` (`zero-*`, `int-*`, `number-*`,
`integer-*`; the `plain-*` cases went with `plain` in milestone 5; milestone 3 added every other reader of spec 2.9: `word-*`, `string-*`, `boolean-*`,
`list-*`, `slice-*`).

## 4. Errors

### 4.1 The groups

Each binding maps these groups onto its own classes (the list is `error groups` in
[schema/api.json](schema/api.json); spec 2.8 says which operation raises which):

- **Problems in the config text** are diagnostics and are never thrown.
- **Text the caller passes in that breaks the language** raises `bad text error`, with located diagnostics, from
  every entry point (edits, `set override`, each override `load` takes); so does an edit after which the document
  would nest past `MAX_NESTING` (spec 2.8).
- **A problem a reader finds in the config's values** (a list where a word was asked for, `20hz` read as a number)
  raises `diagnostic error`: the config text decides it, not the program, so it stays a run-time error.
- **Program bugs** raise classes outside the package base (spec 2.8, the two sorts): `argument type error` (a
  value of the wrong type), `misuse error` (a bad value the program could have checked, every bad name among
  them), `index out of range`, and `detached error` (a removed handle; reading a property of one raises it too).
- **I/O** raises `read error` (the root file, from `load`), `save error` (the writer, from `save`) and its
  subgroup `lost update error` (a file changed since it was read, spec 4.2). All three have `paths` (text[]); a read
  error and a save error chain the port's failure as the cause; a lost update error has no cause. A missing root
  file is a `read error` with no diagnostic and no code: it is not an extension line's failure, so it is never
  E3004 ("include resolver failed"), which stays an extension line's code.
- **One package base class per binding**, `knobly error`, is the parent of every expected-outcome class and of
  nothing else, so one clause catches every outcome and no bug (kno-umh.7; before milestone 4 `DetachedError` sat
  under it, against this rule).

`read error` `paths`: the root path as given to `load`, alone. `save error` `paths`: the resolved paths handed to
the writer, in batch order. `lost update error` `paths`: only the conflicting files, in batch order. `diagnostic
error` keeps `diagnostic`; `bad text error` keeps `diagnostics` and builds its message from them (spec 2.8).

### 4.2 The class tree in each binding

Generated from `error groups` in [schema/api.json](schema/api.json): each class with the fields it keeps.

<!-- generated: class tree (tools/gen-api.py docs) -->
TypeScript:

```text
Error
└─ KnoblyError  (expected outcomes)
   ├─ DiagnosticError  (diagnostic)
   ├─ ReadError  (paths, cause)
   ├─ BadTextError  (diagnostics)
   └─ SaveError  (paths, cause)
      └─ LostUpdateError  (paths)

program bugs, not under KnoblyError:
DetachedError extends ReferenceError  (detached error)
TypeError  (argument type error)
MisuseError extends Error  (misuse error)
RangeError  (index out of range)
```

Python:

```text
Exception
└─ KnoblyError  (expected outcomes)
   ├─ DiagnosticError  (diagnostic)
   ├─ ReadError  (paths, __cause__)
   ├─ BadTextError  (diagnostics)
   └─ SaveError  (paths, __cause__)
      └─ LostUpdateError  (paths)

program bugs, not under KnoblyError:
DetachedError subclass of ReferenceError  (detached error)
TypeError  (argument type error)
ValueError  (misuse error)
IndexError  (index out of range)
```

C++:

```text
std::runtime_error
└─ knobly_error  (expected outcomes)
   ├─ diagnostic_error  (diagnostic)
   ├─ read_error  (paths, std::nested_exception (std::rethrow_if_nested))
   ├─ bad_text_error  (diagnostics)
   └─ save_error  (paths, std::nested_exception (std::rethrow_if_nested))
      └─ lost_update_error  (paths)

program bugs, not under knobly_error:
detached_error derives from std::logic_error  (detached error)
argument_type_error derives from std::logic_error  (argument type error)
misuse_error derives from std::invalid_argument  (misuse error)
index_out_of_range derives from std::out_of_range  (index out of range)
```
<!-- end generated -->

- There is no `EditError` (milestone 4): it was never raised, so `BadTextError` sits directly under the base.
  Python's `BadTextError` is no longer a `ValueError`: `except ValueError` now catches only misuse, a bug.
- `DetachedError` extends `ReferenceError` in both languages (in Python the error a dead `weakref` proxy raises; in
  TypeScript the error for a name that cannot be reached): a detached handle is a reference that no longer leads
  anywhere, and a program bug.
- TypeScript's `MisuseError` is the package's own class because JavaScript has no `ValueError`; it is outside
  `KnoblyError` like the native classes, and it is not a `TypeError`, so a misuse and an argument type error
  are told apart.
- `no set line error` is gone: `set` and `rename` exist only on the variable kinds where they can succeed (spec
  6.7), so there is nothing left to refuse at run time.
- `save (writer)` raises an `argument type error` before it collects anything when `writer` is not a document
  writer (no callable `write`), so a plain function passed as a writer is not reported as a writer that failed.

### 4.3 Which edits a detached or a mistyped call reaches

Every member of a detached handle except `kind` raises `detached error` first, before any type check (spec 6.1);
then the type check of each text parameter (spec 6.9); then everything else. One exception: the check of an
override (`load`'s `overrides`, `set override`) checks the name (a misuse error) before the text's type, in the
order spec 6.3 gives.

Conformance: the written cases `detached` (a detached handle's edit) and every `["error", "BadTextError", ...]`
output. The class tree itself is not in a shared case (a case cannot name a class); each binding tests it, and its
public-name check reads the `parent` of each group in the schema.

## 5. Adapters

Each adapter is named after its medium and the port it fills: `memory`, `file` or `fetch`, then `source` or
`writer`. Every binding MUST ship the memory and file adapters for both ports. The fetch adapters are optional
(MAY): a binding whose emitter has no `fetch` module has none.

The adapters, generated from the schema (each is a free function returning a port) and each binding's emitter (its
import paths):

<!-- generated: adapters (tools/gen-api.py docs) -->
| Spec name | Port | TypeScript | Python | C++ |
|---|---|---|---|---|
| `memory source` | document source | `memorySource(files)` from `knobly` | `memory_source(files)` from `knobly` | `memory_source(files)` from `knobly` |
| `memory writer` | document writer | `memoryWriter(files)` from `knobly` | `memory_writer(files)` from `knobly` | `memory_writer(files)` from `knobly` |
| `file source` | document source | `fileSource()` from `knobly/node` | `file_source()` from `knobly.files` | `file_source()` from `knobly::files` |
| `file writer` | document writer | `fileWriter()` from `knobly/node` | `file_writer()` from `knobly.files` | `file_writer()` from `knobly::files` |
| `fetch source` | document source | `fetchSource(fetch)` from `knobly/browser` | none | none |
| `fetch writer` | document writer | `fetchWriter(fetch, options)` from `knobly/browser` | none | none |
<!-- end generated -->

- **The memory pair shares one map.** `memory source (files)` reads the map it is given at every call, never a
  copy made when it was created; `memory writer (files)` writes each batch into the map it is given. Given the same
  map, a save is visible to the next `load` or `read`: a program keeps its texts in one place (TypeScript: a plain
  `Record<string, string>`; Python: a `MutableMapping[str, str]`, such as a `dict`).
- **Every writer refuses a lost update through one check**, `check lost updates (files, current)` (spec 4.2; its
  spelling in each binding is in the glossary's generated io table): the memory
  writer with each file's text in the map (absent when the key is), the file writer with each file's text on disk,
  the fetch writer with each URL's `GET` body, then a `PUT` with `If-Match` on the `GET`'s ETag (a `412` is a lost
  update). The memory writer's batch is all or nothing, since nothing can fail part way.
- Factories keep each binding's present convention (lowercase functions in both); the binding guide's rule 3
  (Python classes such as `MemorySource()`) is still a proposal pending the owner.

Conformance: none shared (the adapters use `memory source` throughout; L4 has no shared cases yet, and spec 9 lists
the adapters as tested per binding).

## 6. What this page does not cover

- Error values for languages without exceptions, and cancellation: the proposals in spec 2.8 and 4.1 stand.
- Invalid UTF-8 in a binding whose strings are bytes: spec 2.1's proposal stands.
- The address text's escaping of a lone surrogate (spec 7.4's known gap).
- Shared cases for the adapters (L4): [conformance.md](conformance.md) section 7.
