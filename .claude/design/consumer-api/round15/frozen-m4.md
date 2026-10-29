# Milestone 4, frozen for the binding lanes (beads vil-umh.1 to vil-umh.8, vil-umh.12)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 4. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical); where this page and `spec/` differ, `spec/` wins and the difference is an erratum.

## What this rests on

The owner's answers of 2026-10-29 on the round 15 review page (`review.md` in this folder), quoted, not widened:

- Q1 "How should a statement end?": "';' is required and a line break is plain whitespace (nginx); directive names
  cannot start with a digit or '-'".
- Q2 "Which variables may a program override, and what does an included file see?": "Keep today's model and write
  it down in the spec". So no scoping or override behaviour changes; `spec/expansion.md` writes today's model down.
- Q3 (the schema as the source of every signature): "Yes ... start after the scoping and layer decisions". That is
  the next milestone. Nothing here starts the typed schema or new generation.

Not in this milestone (each needs its own owner OK): config text as its own type (vil-umh.6), the typed schema and
generation (vil-umh.9, .10), generated enumerations and reversing spec 2.10 (.11), the value-level set that keeps its
handle (part of .12), per-layer namespaces (.13), raw single quotes, `plain`, the slice `:`, reserved words (.14).

Everything else on this page is a design choice of this milestone (revisable), each with its prior art: the token
split and entry rules (ANTLR's multiple start rules; a Bison start symbol per entry, the textbook way to check them),
one error node per broken statement (Roslyn's skipped-tokens trivia, LibCST's error recovery), HTTP conditional
requests for the lost update (RFC 9110 13.1.1), the two error sorts (Midori / Joe Duffy's "bugs are not
recoverable errors"; Rust's panic against `Result`), and the low level owning expansion (LibCST and Roslyn attach
derived facts to one tree).

## 1. What landed outside `ts/` and `py/` (this lane, done)

| Path | What |
|---|---|
| `grammar/Villanelle.g4` | `directive : header (';' \| block)`; `NEWLINE` is a `gap`; no `lastDirective`; tokens `WORD`, `INTEGER`, `DIGIT_WORD`, `BAD_ESCAPE`; `bound : INTEGER \| VARIABLE`; entry rules `valuesText`, `itemsText`, `boundText`, `nameText` |
| `grammar/villanelle.ebnf` | kept in step by hand (errata: derive or retire) |
| `tools/g4bison.py`, `tools/planted/entry-gap.g4` | every entry rule is checked: one Bison start with a marker token per entry; a planted ambiguous entry rule proves it bites |
| `tools/gen-api.py` | the retired-code check reads `code` from each retired record (it compared whole records before) |
| `spec/expansion.md` (new) | the normative scoping and precedence rules (Q2) |
| `spec/spec.md`, `contract.md`, `conformance.md`, `glossary.md`, `binding-guide.md`, `README.md` | every item below |
| `spec/schema/diagnostics.json` | E1005 and E3007 added; E2008 and E4003 retired; E2001, E2007, E4001 meanings; render codes moved to the low level |
| `spec/schema/api.json` | the concepts, kinds, layers, error groups, free functions and `removed in milestone 4` of this page |
| `conformance/` | every source given its `;`; 152 syntax expected files; new syntax, load and written cases (each item's "Pinned by"); driver: written steps `saveTo` and `diff`, error tokens `MisuseError`, `LostUpdateError` |
| `docs/`, `README.md`, `.claude/skills/villanelle-binding/SKILL.md` | the new rules; `docs/language.md` links to the spec instead of being the source |

`bash tools/check.sh` passes (0 conflicts for the document and the four entry rules; 20 token kinds, 0 overlapping;
9 planted grammars caught; `gen-api.py --check`; the driver's self-test). `tools/gen.sh ts` and `tools/gen.sh py` run.

**Both bindings fail every shared case until their lane lands**: with the new grammar the Python binding stops at
import (`grammar has no rule "lastDirective"`), and the TypeScript one the same way once rebuilt. A scratch copy of
the Python binding with the grammar changes of A plus the one-list diagnostics of G (outside the repo) passes every
case except the 25 written cases of items C to F, which is the red set those lanes turn green.

## 2. Per item

### A. Statement ending (vil-umh.1; spec 3.1, 3.2; Q1)

- **Grammar entry rule the parser calls:** `document` (unchanged name). The CST concept table loses
  `lastDirective`: `document`, `directive`, `block`, `slicedWord`, `list`.
- **Token kinds** (generated `TokenKind` list, from the grammar): `BOM SPACE NEWLINE COMMENT VARIABLE WORD INTEGER
  DIGIT_WORD STRING LBRACE RBRACE LBRACK RBRACK SEMI COMMA COLON UNTERMINATED_STRING BAD_ESCAPE LONE_DOLLAR
  BAD_CHAR`. `WORD`, `INTEGER` and `DIGIT_WORD` all build the written value kind `word` (anatomy, binding, shapes:
  everywhere a `WORD` token was a value). A directive's name, a `snippet`'s name and a `use`'s snippet name are
  whatever the grammar lets through (`header : WORD rest`; `snippet` and `use` names keep accepting any word token).
- **Recovery** (spec 3.2), in `ts/src/syntax/recovery.ts` and `py/.../syntax/_recovery.py`:
  - delete the E2008 branch of the classifier;
  - the values-touch rule treats `INTEGER` and `DIGIT_WORD` as words; the slice-bracket rule stays "a `[` right
    after a `WORD`";
  - `BAD_ESCAPE` classifies as E1005, like the other error tokens;
  - skipping a bad statement ends at a `;` outside brackets and braces, or after the `}` that closes a block it
    opened; never at a `NEWLINE`. At the top level a stray `}` is consumed and ends the statement. Inside a block,
    stop before the `}` that closes it (unchanged);
  - the tree walk folds a `directive` context that holds a recognition error and has no `block` child into its
    statement's one `error` node (with the error tokens recovery consumed after it). A directive whose block was
    entered keeps its node (an unclosed block at the end is E2003, its statements read).
- **Codes:** E2008 deleted from the generated registry (retired). A missing `;` is E2001 at the token where it was
  due (the end of the text, or the `}`).
- **Delete:** E2008 everywhere; `lastDirective` in the CST tables; every test that asserts a line break ends a
  statement (TypeScript `ts/src/written/line-break.test.ts` as written; Python's line-break tests); every fixture or
  test text without its `;`.
- **Pinned by:** syntax `wrapped-line` (the red case: `ranges 0.0627⏎ 0.922;` is one directive with two values),
  `wrapped-line-comment`, `digit-name` (`0.922;` is E2001), `dash-name`, `last-no-semi`, `last-no-semi-in-block`,
  `newline-is-space`, `brace-next-line`, `block-on-next-line`, `rec-brace-own-line`, `rec-brace-own-line-indent`,
  every `rec-*` case and the 152 re-derived expected files; load `load-wrapped-line`, `load-missing-semicolon`.

### B. Expansion semantics (vil-umh.2; `spec/expansion.md`; Q2)

- **No behaviour change.** Both bindings already follow the page: the six new load cases pass against TypeScript as
  built before this milestone and against Python. If a lane finds a difference, it follows `spec/expansion.md` and
  records an erratum.
- **Code:** a binding's doc comments that state a scoping or precedence rule point to `spec/expansion.md` instead of
  restating it (Python `_bind._pick`, TypeScript's `pick` in `ts/src/written/bind.ts`). Nothing else.
- **Pinned by** (one or more per row of its precedence table): `load-snippet-param-beats-override`,
  `load-include-block-param` (rank 1); `load-var-override-wins`, `load-override-beats-include-block`,
  `load-scope-set-nearer-than-param`, `load-override-free` (rank 2); `load-include-block-wins`,
  `load-include-block-wins-inner` (rank 3); `load-var-basic`, `load-var-shadow`, `load-snippet-lexical` (rank 4);
  and for environments: `load-include-sees-includer`, `load-include-twice-same-block`, `load-snippet-sees-later-set`,
  `load-include-exports`, `load-snippet-exports-nothing`.

### C. The text-only rules in the grammar (vil-umh.3; spec 2.8, 3.3, 6.3)

- **Entry rules each binding calls** with the generated parser and the same recovery and classifier, reporting the
  first error only, placed in the given text (spec 2.8):

  | Text | Entry rule | Then (binding code, unchanged) |
  |---|---|---|
  | `set (text)` on a written directive, extension line, set line, use line, set variable | `valuesText` | the text-alone rules (E5002, E5005, E5009 to E5011); E5009 for an empty `set` line |
  | a value's `replace with text`, not a list item | `valuesText` | as above |
  | a list item's `replace with text` | `itemsText` | as above |
  | a slice or index bound's `replace with text` | `boundText` | none |
  | a directive's `rename (name)` | `nameText` | reserved and extension names (misuse, item F) |
  | `set override`, each override `load` takes | `valuesText` | E2001 at a `$name`, at 0:0 for no value |
  | statements texts (`replace with text`, `insert ...`, `add statements`) | `document` | the text-alone rules |

  TypeScript: the generated `VillanelleParser` has `valuesText()`, `itemsText()`, `boundText()`, `nameText()`
  methods; Python the same names. Each parses a fresh token stream of the given text alone.
- **Lexical:** a string escape other than the six is the `BAD_ESCAPE` token, E1005 (`bad escape`, layer syntax,
  found by parse, reason `syntax`); a literal bound that is not `INTEGER` is a syntax error E2007. E4001 stays for a
  bound through a variable and for a literal `INTEGER` beyond ±(2^53-1) (the grammar cannot check the range).
- **Codes:** add `E1005` (`BadEscape` / `BAD_ESCAPE`). Retire `E4003`: the generated constant `BadEscape` /
  `BAD_ESCAPE` now has the value `"E1005"`, and no code `E4003` exists.
- **Delete** (once the grammar does the job): TypeScript `ts/src/written/document.ts` `valuesTextProblems`,
  `moreThanValues`, `boundTextProblems`, `shifted`, `LINE_TRIVIA` and the probe texts `x [` / `x ` with their
  closers; Python `py/src/villanelle/written/_document.py` `values_text_problems`, `_line_break_problem`,
  `_bound_text_problems`, `_shifted`, `_GAP`; Python `_bind.override_value_problem` and the bind-time escape check
  (`_values.has_only_known_escapes` raising E4003), with their TypeScript twins in `bind.ts` / `override.ts`; the
  override check's old step 4 (E4003 or E4001 from an override reader).
- **Keep** `grammar/villanelle.ebnf` in step (this lane did; errata asks whether to derive or retire it).
- **Pinned by:** syntax `edge-bad-escape`, `edge-bad-escape-single`, `edge-six-escapes`, `edge-integer-words`,
  `edge-word-bound`, `edge-float-bound`, `edge-digit-word-slice`, `tracer-word-bounds`; load `load-bad-escape`,
  `load-literal-bound`, `load-var-long-bound`; written `set-override-bad-bound`, `set-line-break`,
  `set-line-break-trailing`, `set-line-break-leading`, `value-replace-line-break`, `set-override-line-break`,
  `set-override-trailing-line-break`, `set-override-blank-line-break`, `set-wrapped-values`, `set-comment`,
  `set-line-comment`, `value-replace-comment`, `list-item-replace-comment`, `set-override-comment`,
  `set-comment-line-break`, `set-comment-after-line-break`, `set-comment-after-syntax-error`,
  `bound-replace-non-integer`, `list-item-replace-trailing-comma`.

### D. An unread include copy (vil-umh.4; spec 6.10, 7.0)

- The expansion turns an extension copy whose edge is in `unread ()` into an `unreadable expansion` with `reason`
  `"unread"`, `origin` at the extension line's own tokens with the copy's `via`, `written` the extension line, and
  adds **E3007** `unread copy` (`UnreadCopy` / `UNREAD_COPY`, layer written, found by the low level) placed on the
  extension line's name. `diff` then reports the copy's old directives as `unknown` by the existing rule (7.6).
- `UnreadableReason` gains `unread` (generated).
- **Pinned by:** written `render-unread-include` (render, edit the include's path, `diff` gives `unknown y`, render
  shows `["", "unread", "main.conf:0:0"]` and E3007, `list` shows E3007).

### E. The lost update error (vil-umh.5; spec 2.8, 4.2, 4.3, 6.8; contract 4, 5)

- **Class:** `LostUpdateError extends SaveError` (TypeScript), `class LostUpdateError(SaveError)` (Python), field
  `paths` (only the conflicting files, batch order), no cause. Message: `lost update: changed since read: <paths
  joined by ", ">`.
- **The one check**, a free function of the io layer, exported from the package root:

  ```ts
  export function checkLostUpdates(files: readonly IFileWrite[], current: readonly (string | undefined)[]): void;
  ```

  ```python
  def check_lost_updates(files: Sequence[FileWrite], current: Sequence[str | None], /) -> None: ...
  ```

  `current[i]` is `files[i]`'s text in the medium now, `undefined` / `None` when there is none (read as `""`). It
  raises `LostUpdateError` with every `files[i].resolvedPath` whose current text differs from `savedText`.
- **Every writer calls it** before writing: `memoryWriter` / `memory_writer` (the map), `fileWriter` /
  `file_writer` (the disk, then the staged write as today), `fetchWriter` (per file: `GET`, check with the body or
  absent on 404, then the method with header `If-Match: <ETag>` when the `GET` had one; a `412` raises
  `LostUpdateError` for that file). `graph.save` raises a `LostUpdateError` from the writer unchanged (not wrapped
  in another `SaveError`); any other failure is wrapped as today.
- **Delete:** the per-writer comparisons and their messages (`node.ts` `lost update: changed on disk ...`,
  `source.ts`, `browser.ts`; Python `source.py` `RuntimeError(... a lost update ...)`, `files.py`'s `OSError`).
- **Conformance adapter:** `save` with `disk` (spec/conformance.md 4.1) and `paths` in `thrown`.
- **Pinned by:** written `save-lost-update` (refused with `["main.conf"]`, nothing saved, then saved against the
  right text), `save-lost-update-paths` (two files changed, one conflicting: `paths` is `["b.conf"]`).

### F. The error classes on the two sorts (vil-umh.7; spec 2.8; contract 4)

```text
TypeScript                                   Python
VillanelleError extends Error                VillanelleError(Exception)
  DiagnosticError    (diagnostic)              DiagnosticError    (diagnostic)
  ReadError          (paths, cause)            ReadError          (paths, __cause__)
  BadTextError       (diagnostics)             BadTextError       (diagnostics)   no longer a ValueError
  SaveError          (paths, cause)            SaveError          (paths, __cause__)
    LostUpdateError  (paths)                     LostUpdateError  (paths)
outside the base:
DetachedError extends ReferenceError         DetachedError(ReferenceError)
MisuseError extends Error                    ValueError
TypeError (argument type)                    TypeError
RangeError (index out of range)              IndexError
```

- **Delete `EditError`** in both (never raised).
- **Every bad name is a misuse error**, through one check per kind of name: the variable name pattern
  (`VARIABLE_NAME`, `^[A-Za-z0-9_]+$`) for `load`'s override names, `setOverride` / `set_override` and a variable's
  `rename`; the `nameText` entry rule plus the reserved words and the registered extension names for a directive's
  `rename`. A variable `rename` that would make a second `set` in its block stays `BadTextError` E5002.
- **Conformance adapter:** report every spec 2.8 group as `thrown` (`misuse error`, `detached error`, `argument
  type error`, `index out of range` included), the most specific group.
- **Pinned by:** written `rename-variable-bad-name`, `set-override-bad-name`, `rename-directive-digit`,
  `rename-kind-refused` (now `MisuseError` for `set` and `a b`), `detached`; the class tree itself by each
  binding's tests (`errors` tests and the public-name check against `api.json` `error groups`).

### G. The low level owns expansion (vil-umh.8; spec 2.9, 5, 6.3, 6.10, 7)

- **One value family.** The expanded value and its five variants carry the links:

  ```ts
  interface IExpandedValueBase {            // in the written layer
    readonly kind: ValueKind; readonly text: string; readonly origin: IOrigin;
    readonly written: WrittenValue;         // same line
    readonly definition: WrittenValue | undefined;
    readonly chain: readonly IReferenceResolution[];
    word(): string; string(): string; number(): number; integer(): number; boolean(): boolean;
    list(): readonly ExpandedValue[]; slice(): ISliceValue | IIndexValue; plain(): PlainValue;
    error(message: string, code: string): DiagnosticError;
  }
  type ExpandedValue = IExpandedWord | IExpandedString | IExpandedList | IExpandedSlice | IExpandedIndex;
  ```

  Python: `ExpandedWord`, `ExpandedString`, `ExpandedList`, `ExpandedSlice`, `ExpandedIndex` (union
  `ExpandedValue`) gain `written`, `definition`, `chain`; `__match_args__` unchanged (`("text",)`, `("items",)`,
  `("name", "start", "end")`, `("name", "index")`).
- **Expansion parts:** `IDirectiveExpansion { written; origin; values: readonly ExpandedValue[]; block?;
  unreadable }`, Python `__match_args__ = ("written", "values", "block")`; `IUnreadableExpansion { reason; written;
  origin }`, Python `("reason", "written")`.
- **Rendered layer builds on these objects:** `IDirective.values` is its expansion's `values` (identity),
  `IDirective.written` and `origin` its expansion's, `IDirective.unreadable` and `IRendered.unreadable` are
  `readonly IUnreadableExpansion[]` (the expansion's objects). The rendered layer adds `name`, `parent`, `walk`,
  `closest`, the address, `diff`, `error`. TypeScript `render.ts` stops copying values (its 46-line copy goes).
- **One diagnostics list:** `graph.diagnostics` is every syntax diagnostic then every problem the binding finds, in
  walk order, render codes included; `expansion.diagnostics` and `rendered.diagnostics` are the same list. Delete
  TypeScript `RENDER_CODES` and its filter (`ts/src/written/graph.ts`), Python `_RENDER_CODES` and its filter
  (`py/src/villanelle/written/_graph.py`).
- **The extension port and the expanded values move into the written layer:** TypeScript `IExtension`,
  `IExtensionUse` (now `ts/src/extension.ts`) and the expanded value types and records (now `ts/src/value.ts`) move
  under `ts/src/written/` and are exported from `ts/src/written/index.ts`; `include()` moves under it too (the
  `villanelle/include` package entry stays). Python `Extension`, `ExtensionUse` (now `villanelle.extension`) and
  `ExpandedWord` ... `ExpandedIndex`, `SliceValue`, `IndexValue`, `PlainValue` (now `villanelle.value`) move into
  `villanelle.written` and its `__all__`; `villanelle.include` stays a module. Both package roots keep re-exporting
  every public name. The shared layer keeps positions, places, origins, diagnostics and the sink, the error classes
  and the kinds. The layer rule is unchanged: nothing below the rendered layer imports it.
- **Delete:** TypeScript `IArgumentLinks`, `IWordArgument`, `IStringArgument`, `IListArgument`, `ISliceArgument`,
  `IIndexArgument`, `Argument`, `IUnreadable` (`ts/src/rendered/model.ts`), `IValueExpansion`
  (`ts/src/written/model.ts`); Python `_Links`, `WordArgument`, `StringArgument`, `ListArgument`, `SliceArgument`,
  `IndexArgument`, `Unreadable` (`py/src/villanelle/rendered/_tree.py`), `ValueExpansion`; and their exports.
- **Conformance adapter:** the `argument` dump is now the `expanded value` dump (same members); `read`'s `value` is
  an expanded value's id.
- **Pinned by:** written `graph-diagnostics-unknown-variable` (`x $nope;` lists E5001 at the low level),
  `declaration-free-and-bound`; every render case (they read the expanded values); the renames by each binding's
  public-name test against `api.json`.

### H. Python correctness (vil-umh.12, less the value-level set; spec 2.8, 2.9, 4.1, 5)

- `Extension.specs(use) -> tuple[str, ...]` and `DocumentSource.resolve(spec, context) -> tuple[str, ...]`
  (Protocols); `read(...) -> str`. At run time the binding refuses a result that is a `str` (or not a sequence of
  `str`): `specs` gives E3006 at the directive, `resolve` and `read` give E3004 (or a `ReadError` for the root),
  message naming the port and the type got. TypeScript applies the same run-time refusal to a non-array result.
- `str(BadTextError)` (and TypeScript `message`): `bad text: ` then each diagnostic's people form
  (`line:col: CODE: message`, from 1) joined by `; `. No probe text can leak, since no probe exists (item C).
- Expanded values: `__eq__` compares `text` (and is `NotImplemented` for a non-expanded value), `__hash__` hashes
  `text`. Written values keep identity (spec 6.1).
- **Pinned by:** Python tests (no shared case can hold a program's port or compare objects): a `specs` returning
  `"dark.conf"` gives E3006; a `resolve` returning a `str` gives E3004; `str(BadTextError)` for `set("1;")` is
  `bad text: 1:2: E2001: ...`; `ExpandedWord("8080") == ExpandedWord("8080")` across two renders.

## 3. Behaviour changes

### Texts that now parse differently

1. A line break no longer ends a statement: `x 1⏎y 2;` is one directive `x` with values `1 y 2` (it was two). A
   forgotten `;` mid-block joins the next line's statement silently (`load-missing-semicolon`).
2. A statement with no `;` before the end of its block or file is E2001 (`x 1` at the end was valid).
3. A directive name that starts with a digit or `-` is E2001 (`0.922;`, `-x 1;`).
4. A `{` on its own line is valid (E2008 is retired): `a⏎{⏎}` is a directive with a block.
5. A literal slice or index bound that is not an integer (`a[i]`, `a[1.5]`, `foo[a:b]`) is E2007 at parse, reason
   `syntax` (it was E4001 at render, reason `value`).
6. A string with an escape other than the six is E1005 at parse, one `BAD_ESCAPE` token, reason `syntax` (it was a
   `STRING` token and E4003 at render, reason `value`).
7. `1[0]` is two touching values, E2009 (it was a slice of the word `1`).
8. Syntax dumps: number-like words are `INTEGER` or `DIGIT_WORD` tokens, not `WORD`.
9. Recovery resumes after the bad statement's `;` or block, not at the next line: an unterminated string, or any
   broken statement without its `;`, hides the statements up to the next `;` (`unterminated`, `rec-two-errors`).
   A broken statement is always one `error` node.
10. Values texts: a line break is allowed anywhere (`set("1\n2")` writes one statement with two values; an
    override `"1\n2"` is two values); a text ending in a comment is refused at the text's end (it was at the
    comment); `"1 # c\n"` is accepted; a list item's text may not end in `,`; a bound's text must be an integer
    word or `$name`.
11. A bad text error carries one diagnostic, the entry rule's first error.

### Public renames and removals

| Before | After | Binding |
|---|---|---|
| `Argument`, `IWordArgument`, `IStringArgument`, `IListArgument`, `ISliceArgument`, `IIndexArgument`, `IArgumentLinks` | `ExpandedValue`, `IExpandedWord`, `IExpandedString`, `IExpandedList`, `IExpandedSlice`, `IExpandedIndex` (with `written`, `definition`, `chain`) | TypeScript |
| `Argument`, `WordArgument`, `StringArgument`, `ListArgument`, `SliceArgument`, `IndexArgument` | `ExpandedValue`, `ExpandedWord`, `ExpandedString`, `ExpandedList`, `ExpandedSlice`, `ExpandedIndex` | Python |
| `IValueExpansion` / `ValueExpansion` | removed: `IDirectiveExpansion.values` are expanded values | both |
| `IUnreadable` / `Unreadable` (rendered), `__match_args__` `("reason",)` | `IUnreadableExpansion` / `UnreadableExpansion`, `("reason", "written")` | both |
| `IDirectiveExpansion.statement`, `IUnreadableExpansion.statement` | `.written` | both |
| `DirectiveExpansion.__match_args__` `("statement", "values", "block")`; `UnreadableExpansion` `("statement", "reason")` | `("written", "values", "block")`; `("reason", "written")` | Python |
| `EditError` | removed | both |
| `BadTextError extends EditError` (Python also `ValueError`) | `BadTextError extends VillanelleError` (not a `ValueError`) | both |
| `DetachedError extends VillanelleError` | `DetachedError extends ReferenceError`, outside `VillanelleError` | both |
| misuse raised as `TypeError` | `MisuseError extends Error` (new export) | TypeScript |
| a bad name in a `rename` as `BadTextError` E2001 | misuse error (`MisuseError` / `ValueError`) | both |
| a lost update as `Error` / `RuntimeError` / `OSError` inside `SaveError` | `LostUpdateError extends SaveError` (new export), `paths` the conflicting files only | both |
| (none) | `checkLostUpdates` / `check_lost_updates` (new export) | both |
| `DiagnosticCode.BraceOnOwnLine` / `BRACE_ON_OWN_LINE` (E2008) | removed | both |
| `DiagnosticCode.BadEscape` / `BAD_ESCAPE` = `"E4003"` | = `"E1005"` | both |
| (none) | `DiagnosticCode.UnreadCopy` / `UNREAD_COPY` = `"E3007"`; `UnreadableReason` `"unread"`; `TokenKind` `INTEGER`, `DIGIT_WORD`, `BAD_ESCAPE` | both |
| `villanelle.extension` (`Extension`, `ExtensionUse`), `villanelle.value` (expanded values) | `villanelle.written` (root re-exports kept) | Python |
| `ts/src/extension.ts`, `ts/src/value.ts` (internal paths) | under `ts/src/written/` (package entries unchanged) | TypeScript |
| `Extension.specs -> Sequence[str]`, `DocumentSource.resolve -> Sequence[str]` | `-> tuple[str, ...]`, a bare `str` refused at run time | Python |
| expanded values compared by identity | `==` and `hash` by `text` | Python |
| `str(BadTextError)` = `bad text: E2001` | `bad text: <people form of each diagnostic>` | Python (TypeScript `message` the same) |

### Behaviour that changes without a rename

- `graph.diagnostics` now includes E5001, E5003, E5004, E5008 and E4001 (`x $nope;` shows E5001 there).
- An unread include copy renders as an unreadable with reason `unread` and E3007; `diff` reports its directives as
  `unknown` (it reported `removed`).
- `save` raises `LostUpdateError` as the writer raised it (not wrapped); the fetch writer makes a `GET` per file and
  sends `If-Match`.
- A port result that is not a list of texts is E3006 (extension) or E3004 (source).

## 4. What each lane runs

TypeScript: `cd ts && corepack pnpm test && corepack pnpm typecheck && corepack pnpm lint && corepack pnpm build`,
then `python3 ../conformance/driver/run.py -- node conformance/adapter.ts`. Python: `cd py && uv run --locked pytest
-q && uv run --locked ruff check && uv run --locked ruff format --check && uv run --locked mypy`, then `python3
../conformance/driver/run.py -- uv run --locked python conformance/adapter.py`. Done when the driver passes every case
at L3 for each binding.

## 5. Not covered, and costs

- No shared case covers H, the class tree beyond the groups an adapter reports, or the fetch writer's precondition
  (L4); each binding tests them.
- The fetch writer's check is a `GET` before the write: a server that sends no ETag leaves a window (spec 4.3).
- The rendered directive still mirrors the directive expansion (one directive type per layer).
- The expected files of the syntax corpus were derived with a scratch binding and checked by hand (errata).
