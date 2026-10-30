# Milestone 5, frozen for the binding lanes (beads kno-umh.6, kno-umh.12 rest, kno-umh.14)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 5. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical); where this page and `spec/` differ, `spec/` wins and the difference is an erratum.

## What this rests on

The owner's answers of 2026-10-29, quoted, not widened:

- Smaller language fixes (kno-umh.14), each put to him in plain words:
  1. single quotes become raw strings (TOML), double quotes keep the escapes: "yes";
  2. delete the `plain()` reader: "agreed. the raw strings are raw/plain/tokens until some schema-aware layer decides
     "this one is a number" or "this is a string"" (the typed readers stay: they are the program deciding);
  3. a slice separator outside the word alphabet, so `:` is legal in every word again, and a subscript on a variable
     anywhere a name can stand, a snippet parameter included (`$src[0..3]`); proposed `..`: "yes";
  4. language statements behind one sigil, `@set`, `@snippet`, `@use` and extension statements such as `@include`;
     no directive name reserved; an unknown `@name` a located error ('no extension for @name'); a directive name
     cannot start with `@`: "yes".
- The value-level set (kno-umh.12): "the natural loop should work. i figured that they were references anyway, so
  both nodes essentially held the same pointer and editing either was fine".
- Config text (kno-umh.6): he picked "Yes, its own type": made only by `quote()` or an explicit `text(...)`; a
  TypeScript branded string, a Python `NewType`; every edit and override parameter takes it.

Not in this milestone (approved for the next one; do not start them, do not make them harder): the typed schema and
generated declarations (kno-umh.9, .10), generated enumerations, TS `as const` objects and a no-raw-string lint
(.11), per-layer namespaces and their renames (.13).

Design calls of this milestone (revisable; each in "Behaviour changes" and in the errata): `~` for the separator
(`..` cannot lex), `:` not a word's first character, `AT_WORD` still a value and a slice name, the slice name as a
written value, a handle that changes kind under a value's `set`, the extension name check at `make processor`, the
step name `include` without `@`, and the three milestone 4 leftovers (G).

Prior art per mechanism: TOML literal strings (A); TypeScript's narrowing on a fixed kind, kept by dropping the
guessing reader (B); Rust and Ruby ranges for the proposed `..`, with `~` outside the word alphabet when `..` cannot
lex (C); a keyword sigil, as CSS at-rules (`@import`, `@media`) and Sass directives put the language's statements
behind `@` so every other name is the user's (D); the DOM's `textContent` / lxml `element.text` and a spreadsheet
cell, edits that keep the node whatever it holds, with Python Cookbook recipe 8.19's `__class__` state pattern for a
kind change (E); TypeScript branded types (the handbook's and Zod's `.brand()`), PEP 484 `NewType`, and the
browser's Trusted Types (a string accepted by a sink only from a named factory) (F); spec rules on the entry rule's
tree instead of a second copy of the value rules in the grammar (G1).

## 1. What landed outside `ts/` and `py/` (this lane, done)

| Path | What |
|---|---|
| `grammar/Knobly.g4` | single-quoted `STRING` raw; `BAD_ESCAPE` and `UNTERMINATED_STRING` follow; `COLON` gone, `TILDE : '~'`; `:` in `NAME_CHAR` for every word; `WORD` cannot start with `@`; `AT_WORD : '@' NAME_CHAR*`; `header : (WORD \| AT_WORD) rest`; `value` adds `AT_WORD`; `slicedWord : sliceName '[' bounds ']'`, `sliceName : WORD \| AT_WORD \| VARIABLE`; `bounds` with `'~'`; entry rules `valueText`, `sliceNameText` added; fragment `NUMBER_CHAR` folded into `NAME_CHAR` |
| `grammar/knobly.ebnf` | kept in step by hand |
| `spec/spec.md`, `expansion.md`, `glossary.md`, `binding-guide.md`, `contract.md`, `conformance.md`, `codegen.md`, `README.md` | every item below |
| `spec/schema/diagnostics.json` | E3008 `unknown extension`, E4007 `bad slice name` added; E1005, E2007, E3006 meanings |
| `spec/schema/api.json` | concept `config text`; free function `text`; `quote` returns config text; `render` errors; written value `set`; slice and index `name` a `word or reference`; `plain` gone from expanded value; every edit's and override's `text` typed `config text`; `reserved names` reworded; error groups; argument type error message; `removed in milestone 5` |
| `conformance/` | every source respelled (`@`, `~`; 4 syntax sources adjusted, below); 16 new syntax, 7 new load, 10 new written and 1 new contract case; 10 `plain-*` contract cases deleted; `rename-kind-refused` rewritten; driver: written `["render", target]`, token `TypeError`, a slice's `name` walked as a value, contract `list` results only for the `list` reader |
| `fixtures/rasl/` | `@set`, `@snippet`, `@use`, `@include`, `[a~b]` (commented-out lines too); README |
| `docs/`, `README.md`, `.claude/skills/knobly-binding/SKILL.md` | the new spellings; `text(...)` around every edit argument in examples; the edit loop without a skip list |

`bash tools/check.sh` passes: 0 conflicts for the document and the seven entry rules (`statementsText`, `valuesText`,
`valueText`, `itemsText`, `boundText`, `sliceNameText`, `nameText`); 21 token kinds, 210 pairs, 0 overlapping; 9
planted grammars caught; `gen-api.py --check`; the driver's self-test. `tools/gen.sh ts` and `tools/gen.sh py` run.

**Red today.** The Python binding at 20acec3 with its parser regenerated from the new grammar fails 84 of 371 cases
(syntax 3, written 29, load 43, contract 9). Every new load, written and contract case is among them. The new syntax
cases of A, C and D pass as soon as the parser is regenerated (they are the grammar's alone) and fail against any
binding built from the milestone 4 grammar; the three recovery cases fail until the classifier changes (item C/D).
TypeScript: NOT RUN against the new corpus (its build needs the lane's changes to the `COLON` references).

## 2. Per item

### A. Raw single quotes (kno-umh.14 point 1; spec 3.1, 2.9)

- **Grammar** (generated, nothing to call): `STRING : '"' (~["\\ ctrl] | ESCAPE)* '"' | '\'' ~[' ctrl]* '\''`;
  `UNTERMINATED_STRING`'s single alternative `'\'' ~[' ctrl]*`; `BAD_ESCAPE` only double-quoted. `\'` stays one of
  the six escapes inside double quotes.
- **Code:** decoding a `STRING` token: a token starting with `'` decodes to its text between the quotes, unchanged;
  only a `"` token decodes the six escapes. TypeScript `decodeString` (`ts/src/values.ts`), Python
  `_values.decode_string`. Canonical text and `quote` are unchanged (always double-quoted): `'C:\new'` is
  `"C:\\new"`.
- **Codes:** E1005 is only ever on a double-quoted string.
- **Delete:** any escape handling for single quotes; tests asserting `'a\nb'` decodes a line break or `'a\x'` is
  E1005.
- **Pinned by:** syntax `raw-single-quote`, `raw-single-backslash-end`, `raw-single-no-quote-inside`,
  `raw-single-unterminated`, `edge-bad-escape-single` (now valid), `edge-escape-quote` (now the string `'c\'` touching
  the word `d`: E2009); load `load-raw-string`; contract `string-raw-single`; written `set-raw-string`.

### B. No `plain` reader (kno-umh.14 point 2; spec 2.9)

- **Signatures:** the expanded value's readers are exactly `word`, `string`, `number`, `integer`, `boolean`, `list`,
  `slice`, `error`. Nothing else reads a value.
- **Delete:** TypeScript `plain()` on the expanded value variants and `PlainValue` (`ts/src/written/value.ts`, its
  export in `ts/src/written/index.ts` and the package root), the test "plain: one rule for every value; quoting means
  text" (`ts/src/rendered/readers.test.ts`); Python `plain()` and `PlainValue` (`knobly/written/value.py`,
  `knobly.written.__all__`, `knobly.__all__`), `test_plain_reads_by_the_one_rule_quoting_means_text`
  (`py/tests/test_readers.py`); each adapter's `plain` reader and the `list`-of-results encoding it needed
  (`{"list": [...]}` is now only the `list` reader's items, each `{"value": text}`).
- **Add (the red check):** each binding's public-name test fails when a name listed in `api.json` `removed in
  milestone 5` is exported (`plain`, `PlainValue`, `COLON`); this is the reverse check for removed names only.
- **Pinned by:** the 10 deleted `plain-*` contract cases (`zero-plain` and `plain-*`), and the public-name tests.

### C. The `~` separator and subscripts on variables (kno-umh.14 point 3; spec 3.1, 2.9, 6.6, expansion.md 8)

- **Grammar entry rules each binding calls** (generated parser, same recovery and classifier, first error only, as
  every entry rule):

  | Text | Entry rule |
  |---|---|
  | a slice or index **name**'s `set` or `replace with text` | `sliceNameText` (`WORD`, `AT_WORD` or `VARIABLE`) |
  | a slice or index bound's `set` or `replace with text` | `boundText` (unchanged) |

- **Tokens:** `TokenKind` loses `COLON`, gains `TILDE` (and `AT_WORD`, item D):
  `BOM SPACE NEWLINE COMMENT VARIABLE WORD AT_WORD INTEGER DIGIT_WORD STRING LBRACE RBRACE LBRACK RBRACK SEMI COMMA
  TILDE UNTERMINATED_STRING BAD_ESCAPE LONE_DOLLAR BAD_CHAR`. A slice's bounds are split at the `TILDE` token (every
  `kind === "COLON"` / `TokenKind.COLON` becomes `TILDE`: TypeScript `ts/src/written/document.ts` (two places),
  `ts/src/written/bind.ts`; Python `written/_document.py` (two), `written/_bind.py`).
- **Recovery** (`ts/src/syntax/recovery.ts` `classifyError`, Python `syntax/_recovery.py` `classify_error`): a `[`
  is a slice bracket when it comes right after a `WORD`, an `AT_WORD` or a `VARIABLE` (was `WORD` only).
- **Written values** (`spec 6.6`): a written `slice`'s and `index`'s `name` is a written value, a `word` or a
  `reference`, built from the slice node's first token like a bound (it has `place`, `text`, `set`, `replace with
  text`; a reference name has `declaration` and `resolutions ()`, and is one of its variable's `references ()`).

  ```ts
  interface ISlice { readonly kind: "slice"; readonly name: IWord | IReference; readonly start: IWord | IReference | undefined; readonly end: IWord | IReference | undefined; }
  interface IIndex { readonly kind: "index"; readonly name: IWord | IReference; readonly index: IWord | IReference; }
  ```

  ```python
  class Slice:  # __match_args__ = ("name", "start", "end")
      @property
      def name(self) -> Word | Reference: ...
  class Index:  # __match_args__ = ("name", "index")
      @property
      def name(self) -> Word | Reference: ...
  ```

  A binding's value index by start token must keep the slice itself as the value at that token (the name shares
  its start); the name is reachable as `slice.name`.
- **Expansion** (`bind.ts` `slice`, Python `_bind._slice`): a `VARIABLE` name is expanded through the variable
  (its reference resolution recorded for the name's reference, as for a bound); exactly one value of kind `word`
  gives the expanded slice's `name` (its text); anything else is **E4007** (`BadSliceName` / `BAD_SLICE_NAME`,
  reason `value`), placed as E4001 is for a bound through a variable: at the value's place via the variable when it
  has one value in a file, else at the `$name`; no value found is E5001 as usual. The expanded slice is read where
  written: `origin` the slice's place, `written` and `definition` the slice, `chain` empty. Canonical text
  `name[start~end]`, `name[i]` (Python `_values.canonical_slice`, TypeScript its twin in `ts/src/values.ts`).
- **Delete:** every `COLON` reference; tests asserting `a[1:3]` is a slice, `07:30` is an error, or `$x[0]` is E2009.
- **Pinned by:** syntax `slices` and every converted slice case, `var-slice-base` (now `x $x[0~3];`, valid),
  `var-subscript-forms`, `at-word-slice`, `slice-colon-refused`, `colon-words`, `colon-start`, `tilde-in-word`,
  `edge-tilde`, `edge-digit-colon` and `ip-port` (now with `;`, valid), `space-before-slice` (now `x a [0~3]`),
  `var-slice-unclosed`, `at-word-slice-unclosed`; load `load-var-subscript`, `load-snippet-param-subscript`,
  `load-var-subscript-not-word`, `load-literal-bound`, `load-var-slice-bound`; written `references-slice-name`,
  `value-set-item-and-bound`, `bound-replace-non-integer`; contract `slice-*`, `string-slice`.

### D. `@` statements, no reserved names (kno-umh.14 point 4; spec 2.5, 5, 6.5)

- **Classification** (TypeScript `ts/src/written/shape.ts`, `bind.ts` `statement`, `document.ts`; Python
  `written/_shape.py`, `_bind.py` `_statement`, `_document.py`): the statement head's **token kind** decides.
  `WORD` is a written directive, whatever its text. `AT_WORD` text `@set`, `@snippet`, `@use` is a set, snippet or
  use line (their text-alone rules E5009 to E5011 unchanged, placed on the `@` token); `@` plus a registered
  extension's name is an extension line; any other `AT_WORD` head is an **unreadable line**, and the low level
  reports **E3008** (`UnknownExtension` / `UNKNOWN_EXTENSION`, layer written, found by the low level, reason
  `extension`) at the `AT_WORD`. An extension block's lines must be `@set` (E5012 otherwise). Value-token sets
  (`ts/src/anatomy.ts` `VALUE_TOKENS`, recovery's values-touch set; Python `_anatomy._VALUE_TOKENS`,
  `_recovery._VALUE_TOKENS`, `_shape._WORDS`) add `AT_WORD`: it is the value kind `word`.
- **Names:** an extension line's `name` is the extension's name without `@` (`include`); a step of kind `extension`
  has `name` `include` and `place` the `@include` token; a use step's place is the `@use` token.
- **Signatures and errors:**
  - `make processor` (TypeScript `knobly({ source, extensions })`, Python `Processor(source=, extensions=)`):
    misuse error (`MisuseError` / `ValueError`) for an extension whose `directive` is in `RESERVED` (`set`,
    `snippet`, `use`), already taken, or refused by the `nameText` entry rule.
  - `IWrittenDirective.rename(name: string): void` / `WrittenDirective.rename(name: str, /) -> None`: misuse error
    when `nameText` refuses it, and for nothing else; delete the reserved and extension-name check
    (`ts/src/written/names.ts`, Python `written/_names.py` `directive_name`).
- **Generated:** `RESERVED` keeps its name and words; its doc comment changes (gen-api).
- **Delete:** classification by a word's text (`name.text === "set"` and the like, `name.text in extensions`); the
  rule-1 "reserved names" tests ("rule 1: reserved names", `ts/src/rendered/rules.test.ts`, and the Python twins).
- **Pinned by:** syntax `at-statements`, `at-value`, `plain-keyword-directives`, `at-word-touch`, `edge-word-chars`,
  `glob-*`, `include-glob`, `var-set`, `var-use`, `var-snippet`; load `load-plain-keyword-directives`,
  `load-include-is-a-directive`, `load-unknown-extension` and every converted load case; written
  `rename-kind-refused` (`@set`, `a b`, `@include`: three misuse errors), `rename-to-keyword-word`,
  `add-unknown-extension`, every converted written case; contract `format-via`, `format-no-graph`, `print-step`.

### E. A written value's `set` keeps its handle (kno-umh.12; spec 6.1, 6.6)

- **Signature** on every written value variant (`word`, `string`, `list`, `slice`, `index`, `reference`):

  ```ts
  interface IWrittenValueBase { set(text: ConfigText): void; /* ... */ }
  ```

  ```python
  class _Value:
      def set(self, text: ConfigText, /) -> None: ...  # annotate the builtin as builtins.set in the class body
  ```

- **Entry rule:** `valueText` (exactly one value: `"1 2"` E2001 at 0:2, `""` E2001 at 0:0, `"1;"` E2001 at 0:1, a
  text ending in a comment E2001 at its end); a slice or index bound takes `boundText`; a slice's name
  `sliceNameText`. Then the text-alone rules, as for `replace with text`. Errors: `BadTextError`, argument type error
  (`TypeError`), `DetachedError` (first, as for every member).
- **Handles** (spec 6.1 row "value `set`"): the edit replaces the value's range; the same object stays where it was
  (its statement's `values`, its list's `items`, its slice's bound or name) and now holds the new value. Its old
  items, bounds and name detach; new ones are new handles. The handle takes the new value's kind: TypeScript, the
  object's `kind` and members are the new kind's; Python, the object's class is reassigned to the new kind's class
  (`self.__class__ = Word`), so the six value classes move their per-kind slots onto the shared base (one layout).
  Setting it again, through any copy that shares it, writes again and raises nothing. Returns nothing.
- **Delete:** the README skip list in `py/README.md` ("keep the handles already edited and skip them" and its
  `edited` set) and in `ts/README.md` if present; the test that encodes it
  (`test_an_edit_loop_edits_a_line_an_included_file_shares_between_two_copies_once`, `py/tests/test_rasl.py`, and
  "edits a line an included file shares between two copies once, keeping the written values already edited",
  `ts/src/rendered/rasl.test.ts`) becomes the plain loop: `value.written.set(text("2400"))` for every `max_count`.
- **Pinned by:** written `value-set-keeps-handle` (`$p` set twice through `["previous"]`, then a word set to a list;
  `references` is empty after), `value-set-one-value`, `value-set-item-and-bound`, `split-value-set-twice` (the
  README loop: two copies, one handle, two sets). Each binding tests the kind change (TypeScript `kind`, Python
  `isinstance` and `match`).

### F. Config text, its own type (kno-umh.6; spec 6.9)

- **Signatures:**

  ```ts
  declare const configTextBrand: unique symbol;            // not exported
  export type ConfigText = string & { readonly [configTextBrand]: true };
  export function quote(text: string): ConfigText;
  export function text(raw: string): ConfigText;           // raw as config text, unchanged and unchecked
  ```

  ```python
  ConfigText = NewType("ConfigText", str)
  def quote(text: str, /) -> ConfigText: ...
  def text(raw: str, /) -> ConfigText: ...                 # ConfigText(raw), after the run-time str check
  ```

  Both from the package root (TypeScript `ts/src/text.ts`, Python `knobly/_text.py`, root `__all__`).
- **Every parameter typed `ConfigText`:** `set(text)` (written directive, extension line, set line, use line, set
  variable, written value), `replaceWithText` / `replace_with_text` (statement, value, document), `insertStatements`
  / `insert_statements`, `addStatements` / `add_statements`, `insertBefore` / `insert_before`, `insertAfter` /
  `insert_after`, `setOverride(name: string, text: ConfigText | undefined)` / `set_override(name: str, text:
  ConfigText | None, /)`, `load(path, { overrides?: Readonly<Record<string, ConfigText>> })` / `load(path, *,
  overrides: Mapping[str, ConfigText] | None = None)`, and the graph's `overrides`: `ReadonlyMap<string,
  ConfigText>` / `Mapping[str, ConfigText]`. Names stay plain text: `rename(name)`, `setOverride`'s `name`.
- **Run time:** unchanged `requireText` / `require_text` on every one, plus `quote` and `text`; the message (api.json
  `argument type error message`) now ends "knobly edits take config text: quote() a program string, text() one
  already written as knobly text, String() a number first" (Python `str()`).
- **Delete:** nothing; every call site in tests, docs examples and the adapters passes `text(...)` or `quote(...)`,
  never a cast (`as ConfigText`, `cast(...)`): the adapters wrap each text the driver sends with `text()`.
- **Pinned by:** each binding's type tests (TypeScript: a `@ts-expect-error` on `statement.set("8080")`; Python: a
  mypy check that `statement.set("8080")` fails and `statement.set(vl.text("8080"))` passes) and the public-name test
  (`config text`, `text`). No shared case can see a type.

### G. The milestone 4 leftovers (design calls; spec 2.8, 7.0)

1. **An override text keeps no entry rule of its own; spec 2.8 is reworded.** The grammar owns a text's shape; the
   text-alone rules (E5002, E5005, E5009 to E5011, the no-value rule below, the override's no-`$name` and
   at-least-one-value rules) are spec rules each binding runs on the entry rule's tree. No code change: the override
   check stays `valuesText` then those two rules (TypeScript `override.ts`, Python `_document.override_text_problems`).
2. **`set (text)` on a statement with no value must be given empty text:** `set("")` clears the values; a text that
   holds no value and is not empty (`"# c\n"`, `"\n"`, `"  "`) is `BadTextError` E2001 at 0:0, checked after
   `valuesText` and before the statement rules (a set line's `""` stays E5009). Pinned by `set-comment-only-refused`;
   `directive-set` keeps `set("")`.
3. **`render(x)` with no callable `expand`** raises the argument type error (`TypeError` in both) before any other
   work: TypeScript `render(): argument "graph" must be a document graph (an object with an expand method), not
   object`; Python `render() argument 'graph' must be a document graph (an object with an expand method), not
   Document`. TypeScript `ts/src/rendered/render.ts`, Python `rendered/_render.py`. The adapters' `render` op passes
   any dumped object through. Pinned by `render-not-a-graph` (`["render", target]` on a document and a statement).

## 3. Behaviour changes

### Texts that now parse differently

1. A single-quoted string is raw: `'C:\new'` is the text `C:\new` (it was a line break); `'a\x'` is valid (it was
   E1005); `'it''s'` is two touching strings (E2009); `'c\'d'` ends at the second `'` (it was one string).
2. `:` is a word character after a word's first character in every word: `07:30`, `127.0.0.1:3000`, `-1:2`, `1:` are
   one word each (they were an error at the `:`).
3. A slice's bounds are separated by `~`: `a[1~3]`, `a[~3]`, `a[1~]`. `a[1:3]` is E2007 (one word `1:3` as a bound);
   `a[:]` and the like are E2007 as before, written `a[~]`.
4. A `~` outside a slice is E2001 (it was `BAD_CHAR`, E1003); a `:` at a word's start is `BAD_CHAR`, E1003 (it was a
   `COLON` token, E2001 or E2007).
5. A variable may be subscripted: `$src[0~3]` and `$s[1]` are slices (they were E2009). The slice name of a `[`
   after a `VARIABLE` or `AT_WORD` makes an unclosed bracket E2007 (it was E2001).
6. `AT_WORD` is a value token: `x @a"b";` is E2009 (it was E2001).
7. `@set`, `@snippet`, `@use` are the language statements and `@<extension>` an extension statement; `set`, `snippet`,
   `use` and `include` without `@` are plain directives in every block (`events { use epoll; }` reads `use epoll`;
   `use x;` was E5003, `set x;` E5009, `snippet y;` E5010; `include "f";` with the include extension was an include).
8. A statement whose head is an `@name` that no extension owns is an unreadable line with E3008 (`@include` without the
   include extension included; `@x 1;` was a directive named `@x`).
9. A slice's `$name` holding anything but one word is E4007 (reason `value`).
10. Syntax dumps: `AT_WORD` and `TILDE` tokens; no `COLON`. A word starting with `@` is `AT_WORD`, not `WORD`.
11. Canonical text of a slice is `name[start~end]` (it was `name[start:end]`).
12. `set (text)` with a text that holds no value and is not empty is refused (E2001 at 0:0): `set("# c\n")` wrote
    `a # c\n;` before.
13. Every column after an inserted `@` moves one place right in the converted corpus, fixtures and docs (the
    expected files say so; no rule about columns changed).

### Public renames and removals

| Before | After | Binding |
|---|---|---|
| `plain()` on every expanded value; `PlainValue` | removed | both |
| `TokenKind` `COLON` | removed; `TILDE`, `AT_WORD` added | both |
| `ISlice.name`, `IIndex.name`: `string` | `IWord \| IReference` | TypeScript |
| `Slice.name`, `Index.name`: `str` | `Word \| Reference` (`match Slice(Word("leds"), ...)`) | Python |
| (none) | written value `set(text)`, keeping the handle | both |
| (none) | `ConfigText`, `text(raw)` (new exports) | both |
| `quote(text): string` / `-> str` | `quote(text): ConfigText` / `-> ConfigText` | both |
| every edit's and override's `text: string` / `str` | `text: ConfigText` (a plain string is a type error) | both |
| `graph.overrides`: `ReadonlyMap<string, string>` / `Mapping[str, str]` | `ReadonlyMap<string, ConfigText>` / `Mapping[str, ConfigText]` | both |
| `load`'s `overrides`: `Record<string, string>` / `Mapping[str, str]` | of `ConfigText` | both |
| directive `rename` refused `set`, `snippet`, `use`, an extension's name | allowed; only `nameText` refuses (so `@x` is a misuse error) | both |
| an extension with any name | misuse error when `nameText` refuses its name | both |
| `render(x)` of a non-graph: TypeScript a native `TypeError` from inside, Python `AttributeError` | the argument type error (`TypeError`), checked first | both |
| (none) | `DiagnosticCode.UnknownExtension` / `UNKNOWN_EXTENSION` = `"E3008"`; `DiagnosticCode.BadSliceName` / `BAD_SLICE_NAME` = `"E4007"` | both |
| E5009, E5010, E5011, E5012 messages (`write set $name value...;` and the like) | the same with `@` (`write @set $name value...;`); generated, so no code change | both |
| the argument type error message's hint | names `quote()` and `text()` | both |

### Behaviour that changes without a rename

- An edit loop over a render that sets each copy's shared `written` value works without a skip list
  (`value.written.set(...)`); `replaceWithText` and `remove()` still detach.
- A written value handle may change kind (and in Python class) under `set`.
- `references()` of a variable now includes a `$name` written as a slice's name.

## 4. What each lane runs

TypeScript: `cd ts && corepack pnpm test && corepack pnpm typecheck && corepack pnpm lint && corepack pnpm build`,
then `python3 ../conformance/driver/run.py -- node conformance/adapter.ts`. Python: `cd py && uv run --locked pytest
-q && uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy`, then `python3
../conformance/driver/run.py -- uv run --locked python conformance/adapter.py`. Done when the driver passes every case
at L3 for each binding, the public-name test passes both ways for `removed in milestone 5`, and the type tests of F
pass.

## 5. Not covered, and costs

- No shared case sees a type: config text (F) and a handle's new class (E) are each binding's tests.
- `plain`'s absence is pinned only by the public-name tests (B).
- `~` can never be a word character; `:` cannot start a word; a single-quoted string cannot hold `'` or a line break.
- A TypeScript variable narrowed on a value's `kind` is stale after that value's `set`; Python's six value classes
  must share one slot layout.
- Every literal edit argument now needs `text(...)`; a cast gets past the checker.
- The expected files of the converted and new cases were derived with a scratch Python binding and checked by hand
  (errata); E's and G's were written by hand.
