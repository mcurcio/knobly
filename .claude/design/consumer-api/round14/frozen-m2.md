# Milestone 2, frozen for the binding lanes (beads vil-0vz, vil-9fy, vil-5ya, vil-gxu)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 2. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical): `spec/spec.md` 2.10 (kinds and variants), 6.5 to 6.7 and 6.10 (the low level), 7 (the
rendered tree), `spec/contract.md` (the edges) and `spec/schema/api.json` (every name). This page is the exact
types, the old-to-new list and the per-binding mechanics. Where it and `spec/` differ, `spec/` wins and the
difference is an erratum.

Scope: round 13 root causes 3 (the types carry the kinds) and 4 (the contract at the edges), the rendered layer on
the public low level only (vil-9fy), the line-break bug in values texts (vil-5ya), the reader names and list shape
(vil-gxu), and Python's `List` and `String` at the package root. Not in scope: the shared corpora and the shared
conformance driver (milestone 3), the `I` prefix (binding guide rule 2), Python factory classes (rule 3), blocks as
sequences and the walk generator (rule 5, spec 7.5), the docs pages (section 15).

## The owner's answers this rests on

- 2026-10-29: "The low level shouldn't "depend on" the middle layer — they should have different domain objects.
  The middle layer of objects can build on the lower layer domains".
- 2026-10-29, "Yes" to: the rendered layer builds only on the low level's public objects (today `render` reads the
  binding through a package-internal accessor and checks `instanceof DocumentGraph` / calls `graph.binding()`); the
  low level makes public what each set reaches and what wins over it (he asked on 2026-10-28 that consumers "see
  ... what variables exist, and where they were overloaded"); render uses only that public surface.
- Milestone 1's answers stand: "A overrides"; "A Keep text only, make misuse impossible" (a `TypeError` for anything
  but text); "Can "set_values" become simply "set"?".

Everything else on this page is a design choice of this milestone (revisable), not his words: the variant names,
`expand ()` and the expansion types, the reader names, the number rules, the error tree, the people forms, the
adapter names, and moving Python's value classes off the package root.

## 1. Types per variant

`kind` on every variant holds its own value of the generated list (section 3). TypeScript: `readonly kind: "set"`
(a member of `StatementKind`), and one compile-time test per union that `Union["kind"]` equals the list (less
`except`). Python: a read-only `kind` property (not a dataclass field, so constructors and `__match_args__` are
unaffected) returning the `StrEnum` member, typed `Literal[StatementKind.SET]`. Python unions are
`X: TypeAlias = A | B | ...` so `isinstance(x, X)` works. A binding MAY share a private base class or interface
(`IStatementBase`, `IValueBase` stay as they are in TypeScript); no public base class exists in Python.

### 1.1 Statements (low level; `spec 6.5`)

| Spec name | `kind` | TypeScript | Python | Python `__match_args__` |
|---|---|---|---|---|
| `statement` (union) | | `type Statement = IWrittenDirective \| IExtensionLine \| ISetLine \| ISnippetLine \| IUseLine \| IUnreadableLine` | `Statement: TypeAlias = WrittenDirective \| ExtensionLine \| SetLine \| SnippetLine \| UseLine \| UnreadableLine` | |
| `written directive` | `directive` | `IWrittenDirective` | `WrittenDirective` | `("name", "values", "block")` |
| `extension line` (new) | `extension` | `IExtensionLine` | `ExtensionLine` | `("name", "values", "block")` |
| `set line` | `set` | `ISetLine` | `SetLine` | `("variable", "values")` |
| `snippet line` | `snippet` | `ISnippetLine` | `SnippetLine` | `("name", "parameters", "block")` |
| `use line` | `use` | `IUseLine` | `UseLine` | `("snippet_name", "values")` |
| `unreadable line` | `unreadable` | `IUnreadableLine` | `UnreadableLine` | `("text",)` |

```ts
// ts/src/written/model.ts
export interface IStatementBase {
  readonly kind: StatementKind;
  readonly document: IDocument;
  readonly parent: IWrittenDirective | IExtensionLine | ISnippetLine | undefined;
  readonly place: IPlace;
  readonly text: string;
  copies(): readonly ICopy[];
  replaceWithText(text: string): readonly Statement[];
  remove(): void;
  insertBefore(text: string): readonly Statement[];   // new: block.insertStatements(indexOf(this), text)
  insertAfter(text: string): readonly Statement[];    // new: block.insertStatements(indexOf(this) + 1, text)
}
export interface IWrittenDirective extends IStatementBase {
  readonly kind: "directive";
  readonly name: string;
  readonly values: readonly WrittenValue[];
  readonly block: IWrittenBlock | undefined;
  rename(name: string): void;
  set(text: string): void;
}
export interface IExtensionLine extends IStatementBase {   // new; no rename
  readonly kind: "extension";
  readonly name: string;
  readonly values: readonly WrittenValue[];
  readonly block: IWrittenBlock | undefined;
  set(text: string): void;
}
export interface ISetLine extends IStatementBase { readonly kind: "set"; readonly variable: ISetVariable; readonly values: readonly WrittenValue[]; set(text: string): void; }
export interface ISnippetLine extends IStatementBase { readonly kind: "snippet"; readonly name: string; readonly parameters: readonly IParameter[]; readonly block: IWrittenBlock; }
export interface IUseLine extends IStatementBase {
  readonly kind: "use"; readonly snippetName: string; readonly snippet: ISnippetLine | undefined;
  snippets(): readonly IResolution<ISnippetLine>[]; readonly values: readonly WrittenValue[]; set(text: string): void;
}
export interface IUnreadableLine extends IStatementBase { readonly kind: "unreadable"; }
// IWrittenBlock.directives(name?) returns readonly IWrittenDirective[] (kind "directive" only, as today).
```

```python
# villanelle/written/model.py: every statement class has kind, document, parent, place, text, copies(),
# replace_with_text(text, /), remove(), insert_before(text, /), insert_after(text, /)
class WrittenDirective:   # kind -> Literal[StatementKind.DIRECTIVE]
    __match_args__ = ("name", "values", "block")
    name: str; values: tuple[WrittenValue, ...]; block: WrittenBlock | None
    def rename(self, name: str, /) -> None: ...
    def set(self, text: str, /) -> None: ...
class ExtensionLine:      # kind -> Literal[StatementKind.EXTENSION]; no rename
    __match_args__ = ("name", "values", "block")
    name: str; values: tuple[WrittenValue, ...]; block: WrittenBlock | None
    def set(self, text: str, /) -> None: ...
class SetLine:            __match_args__ = ("variable", "values")       # variable: SetVariable; set(text)
class SnippetLine:        __match_args__ = ("name", "parameters", "block")  # parameters: tuple[Parameter, ...]
class UseLine:            __match_args__ = ("snippet_name", "values")   # snippet, snippets(), set(text)
class UnreadableLine:     __match_args__ = ("text",)
```

(The fields are read-only properties on handles; the class body lines above show the shape, not dataclasses.)

### 1.2 Written values (low level; spec 6.6)

| Spec name | `kind` | TypeScript | Python (from `villanelle.written` only) | `__match_args__` |
|---|---|---|---|---|
| `written value` (union) | | `WrittenValue` (as today) | `WrittenValue: TypeAlias` | |
| `word` | `word` | `IWord` | `Word` | `("text",)` |
| `string` | `string` | `IString` | `String` | `("text",)` |
| `list` | `list` | `IList` (`items: readonly WrittenValue[]`) | `List` (`items: tuple[WrittenValue, ...]`) | `("items",)` |
| `slice` | `slice` | `ISlice` (`name`, `start`, `end`: `IWord \| IReference \| undefined`) | `Slice` | `("name", "start", "end")` |
| `index` | `index` | `IIndex` (`name`, `index`: `IWord \| IReference`) | `Index` | `("name", "index")` |
| `reference` | `reference` | `IReference` (`declaration: ISetVariable \| IParameter \| undefined`) | `Reference` | `("name",)` |

Common to all six: `kind`, `text`, `place`, `statement`, `list`, `replace with text (text)`, `remove ()` (as today).

### 1.3 Variables (low level; spec 6.7)

| Spec name | `kind` | TypeScript | Python | `__match_args__` | Members beyond the common ones |
|---|---|---|---|---|---|
| `variable` (union) | | `type Variable = ISetVariable \| IParameter \| IOverrideVariable` | `Variable: TypeAlias = SetVariable \| Parameter \| OverrideVariable` | | common: `kind`, `name`, `references ()`, `wins ()`, `shadowed at ()` |
| `set variable` | `set` | `ISetVariable` | `SetVariable` | `("name",)` | `place: IPlace`, `line: ISetLine`, `rename(name)`, `set(text)` |
| `parameter` | `parameter` | `IParameter` | `Parameter` | `("name",)` | `place: IPlace`, `line: ISnippetLine`, `rename(name)` |
| `override variable` | `override` | `IOverrideVariable` | `OverrideVariable` | `("name",)` | none |

`graph.variables(name?)` returns `readonly Variable[]` / `list[Variable]` (order unchanged).
`IReferenceResolution.winner: Variable | undefined`, `shadowed: readonly Variable[]` (`Resolution[Variable]` in
Python). `IVariable` / the one `Variable` class is deleted.

### 1.4 Expanded values (shared; spec 2.9)

| Spec name | `kind` | TypeScript | Python | `__match_args__` | Adds |
|---|---|---|---|---|---|
| `expanded value` (union) | | `type ExpandedValue = IExpandedWord \| IExpandedString \| IExpandedList \| IExpandedSlice \| IExpandedIndex` | `ExpandedValue: TypeAlias = ...` | | |
| `expanded word` | `word` | `IExpandedWord` | `ExpandedWord` | `("text",)` | |
| `expanded string` | `string` | `IExpandedString` | `ExpandedString` | `("text",)` | |
| `expanded list` | `list` | `IExpandedList` | `ExpandedList` | `("items",)` | `items: readonly ExpandedValue[]` / `tuple[ExpandedValue, ...]` |
| `expanded slice` | `slice` | `IExpandedSlice` | `ExpandedSlice` | `("name", "start", "end")` | `name: string`, `start`, `end: number \| undefined` / `int \| None` |
| `expanded index` | `index` | `IExpandedIndex` | `ExpandedIndex` | `("name", "index")` | `name: string`, `index: number` / `int` |

Common to all five (`ts/src/value.ts`, `villanelle/value.py`): `kind`, `text`, `origin`, the readers `word()`,
`string()`, `number()`, `integer()`, `boolean()`, `list()`, `slice()`, `plain()` (section 9), and
`error(message, code)` (Python `error(message, *, code)`). `IExpandedValue` (the one interface) and the one Python
`ExpandedValue` class are deleted; the name `ExpandedValue` is now the union. TypeScript's internal class
`ExpandedValue` in `ts/src/value.ts` is renamed (internal; any name).

### 1.5 Arguments (rendered; spec 7.3)

| Spec name | `kind` | TypeScript | Python | `__match_args__` |
|---|---|---|---|---|
| `argument` (union) | | `type Argument = IWordArgument \| IStringArgument \| IListArgument \| ISliceArgument \| IIndexArgument` | `Argument: TypeAlias = ...` | |
| `word argument` | `word` | `IWordArgument extends IExpandedWord, IArgumentLinks` | `WordArgument(ExpandedWord)` | `("text",)` |
| `string argument` | `string` | `IStringArgument extends IExpandedString, IArgumentLinks` | `StringArgument(ExpandedString)` | `("text",)` |
| `list argument` | `list` | `IListArgument extends IExpandedList, IArgumentLinks` (`items: readonly Argument[]`) | `ListArgument(ExpandedList)` (`items: tuple[Argument, ...]`) | `("items",)` |
| `slice argument` | `slice` | `ISliceArgument extends IExpandedSlice, IArgumentLinks` | `SliceArgument(ExpandedSlice)` | `("name", "start", "end")` |
| `index argument` | `index` | `IIndexArgument extends IExpandedIndex, IArgumentLinks` | `IndexArgument(ExpandedIndex)` | `("name", "index")` |

```ts
// ts/src/rendered/model.ts
interface IArgumentLinks {                       // not exported, or exported as a helper type: lane's choice
  readonly written: WrittenValue;
  readonly definition: WrittenValue | undefined;
  readonly chain: readonly IReferenceResolution[];
}
export interface IListArgument extends IExpandedList, IArgumentLinks {
  readonly items: readonly Argument[];
  list(): readonly Argument[];                   // each argument variant redeclares list() so it returns arguments
}
```

`IDirective.values: readonly Argument[]` / `Directive.values: tuple[Argument, ...]`. `IArgument` / the one
`Argument` class is deleted; the name `Argument` is now the union.

### 1.6 Places, changes, expansion records

| Spec name | `kind` | TypeScript | Python | `__match_args__` |
|---|---|---|---|---|
| `place` | `file` | `IPlace` (adds `toString()`) | `Place` (adds `kind`, `__str__`) | `("resolved_path", "span")` |
| `override` | `override` | `IOverride` (adds `toString()`) | `Override` (adds `kind`, `__str__`) | `("variable",)` |
| `added` | `added` | `IAdded` (`after`) | `Added` (adds `kind`) | `("address", "after")` |
| `removed` | `removed` | `IRemoved` (`before`) | `Removed` (adds `kind`) | `("address", "before")` |
| `changed` | `changed` | `IChanged` (`before`, `after`) | `Changed` (adds `kind`) | `("address", "before", "after")` |
| `unknown` | `unknown` | `IUnknown` (`before`) | `Unknown` (adds `kind`) | `("address", "before")` |
| `directive` (rendered) | | `IDirective` | `Directive` | `("name", "values", "block")` (unchanged) |
| `unreadable` (rendered) | | `IUnreadable` | `Unreadable` | `("reason",)` |
| `step` | | `IStep` (adds `toString()`) | `Step` (adds `__str__`) | dataclass default |
| `diagnostic`, `located diagnostic` | | `IDiagnostic`, `ILocatedDiagnostic` (add `toString()`) | `Diagnostic`, `LocatedDiagnostic` (add `__str__`) | dataclass default |

The expansion types are in section 4.

## 2. Which operations live on which variant

`●` present, `·` absent. Absent means the member does not exist: TypeScript does not compile the call, Python
raises `AttributeError` like any missing attribute. Nothing raises a villanelle error for a missing member.

| Operation | written directive | extension line | set line | snippet line | use line | unreadable line |
|---|---|---|---|---|---|---|
| `replace with text`, `remove`, `copies`, `insert before`, `insert after` | ● | ● | ● | ● | ● | ● |
| `name` | ● | ● | · | ● | · | · |
| `values` | ● | ● | ● | · | ● | · |
| `block` | ● (may be absent) | ● (may be absent) | · | ● (always) | · | · |
| `rename (name)` | ● | · | · | · | · | · |
| `set (text)` | ● | ● | ● | · | ● | · |
| `variable` / `parameters` | · | · | `variable` | `parameters` | · | · |
| `snippet name`, `snippet`, `snippets ()` | · | · | · | · | ● | · |

| Operation | set variable | parameter | override variable |
|---|---|---|---|
| `kind`, `name`, `references ()`, `wins ()`, `shadowed at ()` | ● | ● | ● |
| `place`, `line` | ● (`set line`) | ● (`snippet line`) | · |
| `rename (name)` | ● | ● | · |
| `set (text)` | ● | · | · |

| Member | word | string | list | slice | index | (written only) reference |
|---|---|---|---|---|---|---|
| readers `word` ... `plain`, `error` (expanded and argument variants) | ● | ● | ● | ● | ● | n/a |
| `items` | · | · | ● | · | · | · |
| `name`, `start`, `end` | · | · | · | ● | · | · |
| `name`, `index` | · | · | · | · | ● | · |
| `name`, `declaration`, `resolutions ()` (written) | · | · | · | · | · | ● |
| `written`, `definition`, `chain` (argument variants) | ● | ● | ● | ● | ● | n/a |

The readers stay on every value variant by design: a value of the wrong kind is a problem in the config text, which
the program learns as a located E4002 (spec 2.9, 2.10).

## 3. Kind lists: one generated spelling

`tools/gen-api.py` (already updated on this branch) writes, for every list in `spec/schema/api.json` `kinds`, and
for `token kind` from `grammar/Villanelle.g4`:

- TypeScript `ts/src/gen/api/kinds.ts`: `export type TokenKind = "BOM" | ...;`, `NodeKind`, `StatementKind`,
  `ValueKind`, `VariableKind`, `StepKind`, `PlaceKind`, `UnreadableReason`, `ChangeKind`: string-literal types
  only. **No constant objects.** Re-export each type from `"villanelle"` (`export type { ... }`).
- Python `py/src/villanelle/_api/kinds.py`: a `StrEnum` of the same name for each (`StatementKind.SET = "set"`,
  `TokenKind.BAD_CHAR = "BAD_CHAR"`). **No `Literal` aliases.** Export each from `villanelle`.

Delete the hand-written `TokenKind` in `ts/src/syntax/tokens.ts` and `py/src/villanelle/syntax/tokens.py`; import
the generated one. Every `ValueKind.List`, `NodeKind.Block`, `TokenKind.Word`, `StepKind.Variable`,
`ChangeKind.Added`, `UnreadableReason.Syntax` in TypeScript becomes the literal (`"list"`, `"block"`, `"WORD"`, ...).
`DiagnosticCode` keeps its constant object in TypeScript and its `StrEnum` in Python (codes are a registry, not a
kind list).

## 4. The rendered layer on the public low level (vil-9fy)

### 4.1 New public low-level surface

```ts
// ts/src/written/model.ts
export interface IDocumentGraph {
  // ... as after milestone 1, plus:
  /** The current texts and overrides after expansion (spec 6.10). Pure: reads no file. */
  expand(): IExpansion;
}
export interface IExpansion {
  readonly block: readonly IDirectiveExpansion[];
  readonly unreadable: readonly IUnreadableExpansion[];
  /** Syntax diagnostics, then everything the expansion found, render codes included: rendered.diagnostics. */
  readonly diagnostics: readonly ILocatedDiagnostic[];
}
export interface IDirectiveExpansion {
  readonly statement: IWrittenDirective;
  readonly origin: IDirectiveOrigin;                 // the name's place, the copy's via
  readonly values: readonly IValueExpansion[];
  readonly block: readonly IDirectiveExpansion[] | undefined;
  readonly unreadable: readonly IUnreadableExpansion[];
}
export interface IUnreadableExpansion {
  readonly statement: Statement;
  readonly reason: UnreadableReason;
  readonly origin: IDirectiveOrigin;                 // the statement's own tokens, the copy's via
}
export interface IValueExpansion {
  readonly value: ExpandedValue;
  readonly written: WrittenValue;
  readonly definition: WrittenValue | undefined;
  readonly chain: readonly IReferenceResolution[];
  readonly items: readonly IValueExpansion[];        // a list's items; empty for every other kind
}
```

```python
# villanelle/written/model.py (exported from villanelle.written and villanelle)
class DocumentGraph:
    def expand(self) -> Expansion: ...

@dataclass(frozen=True, slots=True)
class Expansion:
    block: tuple[DirectiveExpansion, ...]
    unreadable: tuple[UnreadableExpansion, ...]
    diagnostics: tuple[LocatedDiagnostic, ...]

@dataclass(frozen=True, slots=True, match_args=False)
class DirectiveExpansion:
    __match_args__ = ("statement", "values", "block")
    statement: WrittenDirective
    origin: DirectiveOrigin
    values: tuple[ValueExpansion, ...]
    block: tuple[DirectiveExpansion, ...] | None
    unreadable: tuple[UnreadableExpansion, ...]

@dataclass(frozen=True, slots=True, match_args=False)
class UnreadableExpansion:
    __match_args__ = ("statement", "reason")
    statement: Statement
    reason: UnreadableReason
    origin: DirectiveOrigin

@dataclass(frozen=True, slots=True, match_args=False)
class ValueExpansion:
    __match_args__ = ("value", "written", "definition")
    value: ExpandedValue
    written: WrittenValue
    definition: WrittenValue | None
    chain: tuple[ReferenceResolution, ...]
    items: tuple[ValueExpansion, ...]
```

The graph works the binding out once and caches it as today; `expand()` returns a snapshot built from that one
working-out (a new snapshot after an edit). The private `binding()` accessor, `BoundItem`, `Bound` /
`BoundValue`, `asDocument`, `syntaxDiagnostics()` stay package-internal to the low level, and the rendered layer
stops using them.

### 4.2 `render(graph)`

`render(graph: IDocumentGraph): IRendered` / `render(graph: DocumentGraph, /) -> Rendered` reads only
`graph.expand()` and `graph.root.resolvedPath` / `graph.root.resolved_path`:

- each `IDirectiveExpansion` gives an `IDirective` (`written` = its `statement`, `origin` = its `origin`, `values` =
  its values as arguments, `block` and `unreadable` recursively, `parent` from the recursion);
- each `IValueExpansion` gives the `Argument` variant of `value.kind`, with `value`'s data, the expansion's
  `written`, `definition` and `chain`, and for a list its `items` from the expansion's `items`;
- each `IUnreadableExpansion` gives an `IUnreadable` (`reason`, `origin`, `written` = its `statement`);
- the rendered `origin` is `{ kind: "file", resolvedPath: graph.root.resolvedPath, span: 0:0 to 0:0 }` with `via`
  empty; `diagnostics` is `expansion.diagnostics`.

Remove TypeScript's `if (!(graph instanceof DocumentGraph)) throw new TypeError(...)`: `render` accepts any object
with the document graph's public members.

### 4.3 The checks (binding guide rule 8, second check)

- **TypeScript.** Add `ts/src/written/index.ts`: re-export exactly the low level's public names (what
  `ts/src/index.ts` exports from `written/` today, plus `IExtensionLine`, `ISetVariable`, `IParameter`,
  `IOverrideVariable`, `Variable`, the expansion types), and make `ts/src/index.ts` re-export from it. In
  `ts/eslint.config.js`:

  ```js
  {
    files: ["src/rendered/**/*.ts"],
    ignores: ["src/**/*.test.ts"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [{
        group: ["**/written/*", "!**/written/index.js"],
        message: "The rendered layer builds only on the low level's public API: import ../written/index.js (spec 7.0).",
      }] }],
      "no-restricted-syntax": ["error",
        { selector: "TSAsExpression[typeAnnotation.type='TSUnknownKeyword']", message: "No cast through unknown in the rendered layer (spec 7.0)." },
        { selector: "TSAsExpression > TSAsExpression", message: "No double cast in the rendered layer (spec 7.0)." },
      ],
    },
  }
  ```

  The milestone 1 block's `no-restricted-imports` ignores `src/rendered/**`, so the two blocks do not overlap; no
  other block sets `no-restricted-syntax` today. `ts/src/rendered/testing.ts` is not a test file: it follows the rule (or moves to a `*.test.ts` helper). Add a
  planted fixture (as milestone 1's layer check has) showing each of the three patterns is reported: an import of
  `../written/bind.js`, `graph as unknown as X`, `(x as A) as B`.
- **Python.** Extend `py/tests/test_layers.py`: for every module under `villanelle/rendered/`, fail on any import of
  the low level other than `from villanelle.written import <names>` with every name in `villanelle.written.__all__`
  (so `from villanelle.written import _document`, `from villanelle.written._bind import ...`,
  `from villanelle.written.model import ...`, `import villanelle.written._graph` and the relative forms all fail),
  on an `ast.Attribute` whose `attr` starts with one `_` (dunders aside) unless its value is the name `self` or
  `cls`, and on `getattr(x, "<literal starting with _>")`. Rendered code reads another rendered object through its
  public members (`after.block`, not `after._block`). Add planted sources for each failure. Today's offenders, all
  in `rendered/_render.py`: `from villanelle.written import _document, _graph`, `from villanelle.written._bind
  import ...`, `from villanelle.written.model import ...`, `statement._doc`, `._node`, `._value_list`,
  `doc._syntax`, `doc._path`, `directive._contents()`, `directive._freeze()`, `after._block`, `after._unreadable`;
  and in `_tree.py` the `TYPE_CHECKING` import of `villanelle.written.model`.

## 5. Error classes (contract 4)

```text
TypeScript (ts/src/errors.ts new, shared)        Python (villanelle/errors.py new, shared)
class VillanelleError extends Error               class VillanelleError(Exception)
  DiagnosticError    diagnostic                     DiagnosticError(VillanelleError)    diagnostic
  ReadError          paths, cause                   ReadError(VillanelleError)          paths, __cause__
  SaveError          paths, cause                   SaveError(VillanelleError)          paths, __cause__
  EditError                                         EditError(VillanelleError, ValueError)
    BadTextError     diagnostics                      BadTextError(EditError)           diagnostics
  DetachedError                                     DetachedError(VillanelleError, ReferenceError)
native: TypeError (argument type, misuse),        native: TypeError (argument type), ValueError (misuse),
        RangeError (index)                                IndexError (index)
```

- `VillanelleError` is exported from `"villanelle"` and `villanelle`. Every class above sets `name` (TypeScript)
  to its class name.
- `ReadError`: `paths` = `[path]` (the root path as given to `load`); cause: the source's rejection (absent when
  the source resolved no file or several; the message says how many). No `diagnostic`, no code: E3004 is no longer
  used for the root. TypeScript `new ReadError(message, paths, { cause })`; Python `raise ReadError(message,
  paths) from error`.
- `SaveError`: `paths` = the resolved paths handed to the writer, in batch order, replacing `files`; cause: the
  writer's failure.
- `save(writer)` checks first that `writer` has a callable `write`, else the argument type error: TypeScript
  `TypeError: save(): argument "writer" must be a document writer (an object with a write method), not function`;
  Python `TypeError: save() argument 'writer' must be a document writer (an object with a write method), not
  function` (`got` as the milestone 1 helper computes it).
- `NoSetLineError` is deleted in both, with every raise site (the members it guarded are gone, section 2).
- Order of checks on every member stays: detached first (`DetachedError`), then the type of each text parameter,
  then the rest.

## 6. Positions and people forms (contract 1, 2)

- **Python** counts every `offset` and `column` in code points: `parse` (drop the UTF-16 conversion in
  `syntax/parse.py`; ANTLR's Python runtime already indexes code points), every `SourcePosition` the low level and
  the rendered tree make, a `BadTextError`'s diagnostics, `span_of`, `format_diagnostic` (drop its `units` logic:
  one caret and one pad character per code point, tabs kept). `span.py`'s docstring says so.
- **TypeScript** keeps UTF-16 code units.
- **Lines:** a lone `"\r"` never ends a line. TypeScript's `formatDiagnostic` changes its line-end search from
  `/\r\n|\n|\r/u` to `/\r?\n/u` (the bug: it cut the source line at a lone `"\r"`). Python's `split("\n")` with
  `removesuffix("\r")` is already right; keep it, never `splitlines()`.
- **People forms**, one helper per binding (one home), used by `format diagnostic` too:

  | Type | TypeScript `toString()` / Python `__str__` |
  |---|---|
  | place | `` `${resolvedPath}:${line + 1}:${column + 1}` `` (span start) |
  | override | `` `override ${variable}` `` |
  | step | `` `${kind} ${name} at ${String(place)}` `` |
  | located diagnostic | `` `${String(place)}: ${code}: ${message}` `` |
  | diagnostic | `` `${line + 1}:${column + 1}: ${code}: ${message}` `` (span start) |

  TypeScript records that are object literals today (`IPlace`, `IOverride`, `IStep`, `IDiagnostic`,
  `ILocatedDiagnostic`) need a `toString` the interface declares: make them small classes with read-only fields
  (keep them plain data otherwise), or build them through one factory each. Python: `__str__` on the frozen
  dataclasses. `repr` is unchanged.
- **Runners:** every Python conformance runner converts code points to UTF-16 before printing a position (a helper
  over the text the position counts in), in the syntax, written, load and contract runners.

## 7. Numbers (contract 3)

| Reader | TypeScript | Python |
|---|---|---|
| `number` | `Number(word)`; `!Number.isFinite(n)` gives E4004; return `n === 0 ? 0 : n` | `int(word)` when no fraction or exponent and within ±(2^53-1); else `f = float(word)`, `math.isinf(f)` gives E4004, return `0.0 if f == 0 else f` |
| `integer` | E4005 outside ±(2^53-1) (as today); return `n === 0 ? 0 : n` | as today (`int("-0")` is already `0`) |
| `plain` | a word that `number` would accept is its `number()`; a word beyond the double range is text | the same |

`1e-400` reads as `0` (an underflow is not refused). The print rule for the contract cases is in
`conformance/contract/format.md`.

## 8. Adapters (contract 5)

| Spec name | TypeScript (old -> new) | Python (old -> new) |
|---|---|---|
| `memory source` | `memorySource(files)` (same name; reads `files` live, no copy) | `memory_source(files)` (same; reads `files` live) |
| `memory writer` | new: `memoryWriter(files: Record<string, string>): IDocumentWriter`, from `"villanelle"` | new: `memory_writer(files: MutableMapping[str, str], /) -> DocumentWriter`, from `villanelle` |
| `file source` | `createFileSource()` -> `fileSource()` (`villanelle/node`) | `file_source()` (same) |
| `file writer` | `createFsWriter()` -> `fileWriter()` (`villanelle/node`) | `fs_writer()` -> `file_writer()` (`villanelle.files`) |
| `fetch source` | `createFetchSource(fetch)` -> `fetchSource(fetch)` (`villanelle/browser`) | none |
| `fetch writer` | `createFetchWriter(fetch, options)` -> `fetchWriter(fetch, options)`; `IFetchWriterOptions` unchanged | none |

`memorySource`'s parameter stays `Readonly<Record<string, string>>` in TypeScript and `Mapping[str, str]` in
Python, but it reads that object at each `resolve` and `read` instead of copying it into a `Map` / `dict` at
creation. `memory writer` checks every file's current text in the map (`""` when absent) against `savedText`
first, failing with an `Error` naming the lost paths and writing nothing, then sets every file.

## 9. Reader names and list items (vil-gxu)

| Spec name | TypeScript (old -> new) | Python (old -> new) |
|---|---|---|
| `word` | `word()` | `as_word()` -> `word()` |
| `string` | `string()` | `as_str()` -> `string()` |
| `number` | `number()` | `as_number()` -> `number()` |
| `integer` | `integer()` | `as_int()` -> `integer()` |
| `boolean` | `boolean()` | `as_bool()` -> `boolean()` |
| `list` | `items()` -> `list()` | `as_list()` -> `list()` |
| `slice` | `slice()` | `as_slice()` -> `slice()` |
| `plain` | `plain()` | `plain()` |

The settlement: readers are methods (they can fail, binding guide rule 6), spelled with the spec word and only the
casing changed (rule 1). A method named `list`, `string` or `slice` shadows nothing for the caller; inside the
class body, annotate the builtins as `builtins.list` / `builtins.slice`, as for `set`. **List items have one
shape in both layers:** `items`, a property, a `readonly` array in TypeScript and a `tuple` in Python, on the
written `list`, the `expanded list` and the `list argument`.

## 10. The line break in a values text (vil-5ya)

Red first, in both bindings: a test that `stmt.set("1\n2")` on `port 80;` raises `BadTextError` with one E2001 at
1:0 and leaves the text unchanged (it fails today: the text becomes `port 1\n2;`). Then the fix, in the one home of
the check: TypeScript `valuesTextProblems(text, inList)` in `ts/src/written/document.ts`, Python
`values_text_problems(text, in_list=...)` in `written/_document.py`. When `inList` is false, after the syntax
diagnostics and the existing checks, refuse the first `NEWLINE` token at list depth 0: E2001 at the first token after
it that is not `SPACE`, `COMMENT` or `NEWLINE`, or at the `NEWLINE` itself when only those follow. The check of an
override uses the same function, so Python's separate second-statement test in `override_text_problems` goes (one
home) and TypeScript's override check gets the same rule from the shared function. Values inside a list (`inList`
true, or a line break inside `[ ]`) are unaffected.

## 11. Python exports (item E)

`Word`, `String`, `List`, `Slice`, `Index` and `Reference` are exported from `villanelle.written` only: remove them
from `villanelle/__init__.py`'s imports and `__all__`. The glossary keeps the words (spec 6.6), so the module gives
the context (`from villanelle import written; written.List`). `WrittenValue` stays at the root. TypeScript keeps
`IWord` ... `IReference` at its root (no clash there; per-layer entry points are binding guide rule 8's module
layout proposal, not this milestone). This is a stated difference between the bindings, for Python's `import *`. New root exports in Python: `VillanelleError`, `StatementKind`, `VariableKind`, `PlaceKind`,
`ChangeKind`, `ExtensionLine`, `SetVariable`, `Parameter`, `OverrideVariable`, the expanded and argument variants,
the expansion types, `memory_writer`. In TypeScript, the same names (`I`-prefixed interfaces, the literal types).

## 12. Removals

| Removed | Replaced by |
|---|---|
| `NoSetLineError` (both) | nothing: the members are absent where they cannot succeed |
| `IVariable` (TS), the one `Variable` class (Py) | `Variable` union of three types |
| `IExpandedValue`, `IArgument` (TS); the one `ExpandedValue` and `Argument` classes (Py) | the unions `ExpandedValue`, `Argument` and their variants |
| `IWrittenDirective` / `WrittenDirective` of kind `extension`; `rename` on include lines | `IExtensionLine` / `ExtensionLine`, no `rename` |
| `items()` reader (TS), `as_list()` (Py) | `list()`; `items` property on list variants |
| `as_word`, `as_str`, `as_number`, `as_int`, `as_bool`, `as_slice` (Py) | `word`, `string`, `number`, `integer`, `boolean`, `slice` |
| constant objects `NodeKind`, `ValueKind`, `StepKind`, `UnreadableReason`, `ChangeKind`, `TokenKind` (TS) | string-literal types of the same names |
| `Literal` aliases for statement, variable and place kinds (Py); hand-written `TokenKind` (both) | generated `StrEnum`s / literal types |
| `ReadError extends DiagnosticError` and its `diagnostic` (both) | `ReadError` under `VillanelleError`, `paths` |
| `SaveError.files` (both) | `SaveError.paths` |
| `DetachedError` under `EditError` (both) and `ValueError` (Py) | under `VillanelleError` (Py: and `ReferenceError`) |
| `createFileSource`, `createFsWriter`, `createFetchSource`, `createFetchWriter` (TS); `fs_writer` (Py) | `fileSource`, `fileWriter`, `fetchSource`, `fetchWriter`; `file_writer` |
| `render`'s `instanceof DocumentGraph` check and `graph.binding()` use (TS); `rendered/_render.py`'s private imports and attributes (Py) | `graph.expand()` |
| Python's UTF-16 conversion in `parse`, positions and `format_diagnostic` | code points |
| `Word`, `String`, `List`, `Slice`, `Index`, `Reference` at Python's package root | `villanelle.written` only |
| `"later"` markers in `spec/schema/api.json` and the checks' skipping of them | nothing: the checks are strict |
| conformance case `override-no-set-line` and the token `NoSetLineError` | none (absence is a type test per binding) |

No aliases, no deprecated exports, no shims: each old name simply goes.

## 13. Conformance

**Added** (expected results hand-derived; a runner that disagrees reports it):

| File | Cases | Proves |
|---|---|---|
| `conformance/written/cases.json` + `expected/<name>.json` | `set-line-break`, `set-line-break-trailing`, `set-line-break-leading`, `set-line-break-in-list`, `value-replace-line-break`, `set-override-trailing-line-break` | vil-5ya, the check of a values text (spec 2.8) |
| same | `set-bad-astral` | a bad text error's column after an astral character, printed in UTF-16 by every runner (contract 1) |
| same | `insert-before-after`, `insert-after-nested` | `insert before`, `insert after` (ops `"insertBefore"`, `"insertAfter"`, needs `blocks`) |
| `conformance/contract/cases.json` (new; format `conformance/contract/format.md`) | readers: `zero-integer`, `zero-number`, `zero-plain`, `zero-number-fraction`, `zero-number-exponent`, `int-max`, `int-min`, `int-beyond`, `int-beyond-negative`, `int-overflow`, `number-max-safe`, `number-beyond-2-53`, `plain-beyond-2-53`, `number-overflow`, `number-overflow-negative`, `plain-overflow`, `number-underflow`, `number-underflow-negative`, `number-exponent-form`, `number-large` | contract 3 |
| same | `position-astral-value`, `position-astral-print` | contract 1: native slicing, UTF-16 conversion, native columns in the people form |
| same | `print-place`, `print-override`, `print-step`, `print-located-diagnostic`, `print-syntax-diagnostic` | contract 2 |
| same | `format-lone-cr`, `format-via` | `format diagnostic`: a lone `"\r"` stays in the source line; the via line |

**Removed:** `conformance/written/cases.json` `override-no-set-line` and its expected file; the token
`"NoSetLineError"` in `conformance/written/format.md`.

**Runners (lanes):** a new contract runner in each binding (`ts/src/contract-conformance.test.ts`,
`py/tests/test_contract_conformance.py`); the written runners add `insertBefore` and `insertAfter` and drop
`NoSetLineError`; every Python runner converts positions to UTF-16; the load and written runners print argument
kinds and `kind`s as before (the values did not change). No other expected file changes: the kind strings, the
printed places (UTF-16) and the case formats are unchanged.

**Per-binding tests (no shared case can carry them):** absence of each member section 2 marks `·` (TypeScript
`// @ts-expect-error` lines in a type test; Python `not hasattr(...)`); the error class tree and `paths`; `save`
refusing a non-writer; the memory writer and its lost-update refusal; `match` on each low-level variant with the
section 1 patterns; `isinstance(x, Statement)` on each union alias; the layer checks' planted cases.

**Public-name checks** (`ts/src/api-names.test.ts`, `py/tests/test_api_names.py`) read the schema's new shape
(`spec/codegen.md`, "Milestone 2"): variants inherit their union's members; each variant's `kind` equals the
schema's; Python's `__match_args__` equal `py match args` in snake_case; `py module` concepts are found there and
absent from the root; error `parent`s form the tree; no skipping (the `later` handling is deleted).

## 14. Behaviour changes

Each is allowed by this milestone; none is the owner's word, each follows from the rules above.

1. **Python positions count code points** (were UTF-16 code units): every `offset` and `column` from `parse`, the
   low level, the rendered tree, `BadTextError.diagnostics`, `span_of`, and `format_diagnostic`'s column and
   carets. Text with no character above U+FFFF gives the same numbers as before.
2. **TypeScript `formatDiagnostic` no longer ends the source line at a lone `"\r"`.**
3. **Every place, override, step, diagnostic and located diagnostic has a people form**: `String(place)` is
   `main.conf:4:5` (was `[object Object]`); Python `str(place)` is `main.conf:4:5` (was the dataclass repr).
4. **No reader returns negative zero:** TypeScript `integer()`, `number()` and `plain()` of `-0` (and of `-0.0`,
   `-0e5`) give `0` (were `-0`); Python `as_number("-0.0")` gave `-0.0`, `number()` gives `0.0`.
5. **`1e400` and `-1e400`:** `number()` raises E4004 (was infinity) in both; `plain()` returns the text `"1e400"`
   (was infinity).
6. **`ReadError` is no longer a `DiagnosticError`:** no `diagnostic`, no E3004; it has `paths` and a cause. A
   program's `except DiagnosticError` / `catch (e instanceof DiagnosticError)` around `load` no longer catches a
   missing root file.
7. **`SaveError.files` is now `SaveError.paths`** (resolved paths, not file writes).
8. **`DetachedError` is no longer an `EditError`** (both), nor in Python a `ValueError`; in Python it is a
   `ReferenceError`. `except EditError` / `except ValueError` no longer catch it.
9. **`VillanelleError` is the base of every package error**, so `except VillanelleError` catches diagnostic, read,
   save, edit, bad text and detached errors (not `TypeError`, `ValueError` misuse or `IndexError`).
10. **`NoSetLineError` is gone:** `set` on a parameter or an override variable, and `rename` on an override
    variable, do not compile in TypeScript; in Python they raise `AttributeError` (were `NoSetLineError`).
11. **`rename` on an include line does not exist** (was `BadTextError` E2001).
12. **A values text with a line break outside a list is refused** (`BadTextError`, E2001): `set`, a value's
    `replaceWithText` / `replace_with_text` (was accepted, and split the statement in two), and an override text
    ending or starting with a line break (`"1\n"`, `"\n1"`: Python accepted these, since its check refused only a
    second statement; `"1\n2"` was already refused).
13. **Readers renamed:** TypeScript `items()` is `list()`; Python `as_word` ... `as_slice` are `word` ... `slice`,
    `as_list` is `list`.
14. **Kinds:** TypeScript's `ValueKind.List` and the other constant objects are gone (use `"list"`); Python's
    statement, variable and place kinds are `StrEnum`s (were plain strings; `stmt.kind == "set"` is still true,
    `type(stmt.kind) is str` is not). Python `Place`, `Override` and the change classes have `kind`.
15. **Types split:** `IVariable`, `IExpandedValue`, `IArgument` become unions; Python's `Variable`,
    `ExpandedValue` and `Argument` become union aliases, so `Variable(...)`-style construction or subclassing them
    no longer works and `isinstance(x, Argument)` checks the union. Include lines are `IExtensionLine` /
    `ExtensionLine`, no longer `IWrittenDirective` / `WrittenDirective`; `isinstance(s, WrittenDirective)` is false
    for them.
16. **Python `match` works on the low level** (it raised `TypeError` for positional patterns).
17. **New members:** `insertBefore` / `insert_before`, `insertAfter` / `insert_after` on every statement;
    `expand()` on the graph; `items`, `name`, `start`, `end`, `index` on the expanded and argument variants.
18. **Adapter names:** `createFileSource`, `createFsWriter`, `createFetchSource`, `createFetchWriter`, `fs_writer`
    are renamed (section 8); `memoryWriter` / `memory_writer` are new.
19. **`memorySource` / `memory_source` reads its map live:** a change a program makes to that object after
    creating the source is now seen by later loads and reads (was ignored).
20. **`save` with something that is not a writer** raises `TypeError` before anything (TypeScript: a rejected
    promise with `TypeError`; was "the writer rejected/raised").
21. **TypeScript `render` accepts any object with the document graph's members** (was `TypeError` for one this
    package did not make).
22. **Python's `Word`, `String`, `List`, `Slice`, `Index`, `Reference` are no longer importable from `villanelle`**
    (only from `villanelle.written`); `from villanelle import *` no longer replaces `typing.List`.

## 15. Not in this milestone, and follow-ups

- **Docs pass:** `docs/low-level-api.md` and `docs/rendered-tree.md` still teach the older names, and their
  examples are copied from tests, so they are rewritten after both lanes land, from the lanes' tests: the three
  casts in `docs/low-level-api.md` (`as ISetLine` at the `set` example, `as IWrittenDirective` twice) become
  `kind` narrowing or a narrowing `filter`; `NoSetLineError` rows go; the reader names, adapters, errors and
  positions follow this page. `ts/README.md` and `py/README.md` are each lane's.
- **Not ruled, noticed while writing the line-break rule:** a values text holding a comment outside a list (`set("1
  # note")`) puts the statement's `;` inside the comment (`port 1 # note;`). The statement still reads as one, but
  the `;` is lost into the comment. No check refuses it; it needs its own bead and an owner call.
- **Proposed, still pending the owner:** the `I` prefix (rule 2), Python factory classes (rule 3), blocks as
  sequences with one walk generator and `statements of (kind, name?)` (rule 5, spec 7.5), the first-hour program
  (rule 7), the conformance levels, the corpora and the shared driver (milestone 3).

## 16. How each lane proves it is done

1. Its package's checks pass (TypeScript: `corepack pnpm test`, `typecheck`, `lint`, `build`; Python:
   `uv run --locked pytest`, `ruff check`, `ruff format --check`, `mypy`), with every conformance case passing,
   the contract cases included, none skipped.
2. Both layer checks fail on their planted cases and pass on the tree; `rendered/` imports nothing private.
3. The public-name check passes against `spec/schema/api.json` with no skipping.
4. The red test of section 10 was seen failing before the fix (say so in the commit or the lane's report).
5. `grep -rn` for `NoSetLineError`, `IVariable\b`, `IArgument\b`, `IExpandedValue`, `as_word`, `as_int`, `as_list`,
   `createFsWriter`, `createFileSource`, `fs_writer`, `.binding()` (in `rendered/`), and in TypeScript only
   `ValueKind\.`, `NodeKind\.`, `TokenKind\.`, `StepKind\.`, `ChangeKind\.`, `UnreadableReason\.`, comes back empty
   in the package but for prose that explains the change.
