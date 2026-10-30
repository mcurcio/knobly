# Milestone 6, frozen for the binding lanes (beads kno-umh.9, kno-umh.10, kno-umh.11, kno-umh.13)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 6. It is frozen: a lane
that finds it wrong appends the finding to `.claude/errata.md` and does not diverge silently. The rules live in
`spec/` (canonical); where this page and `spec/` differ, `spec/` wins and the difference is an erratum.

## What this rests on

The owner's answers of 2026-10-29, quoted, not widened:

- **Q3** on the round 15 review page, "Should the schema become the source of every public signature?": "Yes, with
  idiom expressed as typed per-language traits; start after the scoping and layer decisions". The scoping and layer
  decisions landed in milestones 4 and 5. Beads kno-umh.9 (type the schema) and kno-umh.10 (generate the
  declarations, errors, diagnostics and tables; delete the hand copies and most of the name tests).
- **Enumerations**: "Yes, generate both": TypeScript `as const` objects plus derived string-literal unions (this
  reverses spec 2.10's milestone 2 rule, rewritten); Python internals compare enum members; one generated keyword
  list and dispatch table; a lint refuses `.kind`, `.reason` or `.code` compared with a string literal. Bead
  kno-umh.11.
- **Namespaces**: "Yes, rename now": per-layer namespaces, TypeScript subpath exports `knobly/syntax`,
  `knobly/written`, `knobly/rendered` with no `I` prefix on types; Python subpackages as the namespace; one
  block shape (iterate, index, `directives(name)`, walk) in every layer. Bead kno-umh.13. No aliases or re-exports of
  old names.
- His first ask (2026-10-28): "clean, easy to comprehend API design", "idiomatic in each language", "consistent
  across layers", and codegen "so we dont have to maintain n languages by hand".

Not in this milestone: the open question kno-umh.15 (may `:` start a word; the grammar is unchanged) and the high
level (kno-xlo).

Design calls of this milestone (revisable; each in "Behaviour changes" or the errata): the package root holds the
shared and io layers; `walk` moves onto the block (not kept on the render and the directive); the block shape is
given to the written, expansion and rendered blocks, not to syntax nodes; the docs tables are the one committed
generated output; `MAX_SAFE_INTEGER` generated in TypeScript too; snapshots generated as `eq=False` dataclasses in
Python; positional-only parameters in the Python Protocols; `diagnostic` moved to the shared layer.

**Prior art per mechanism.** The generator: protoc's compiler-plugin split (one front end into a neutral descriptor,
one back end per language), with the LSP `metaModel.json` as the shape of the model and Smithy traits as the shape
of per-language idiom (spec/codegen.md section 9 says why none of them is used as is). The type grammar: the LSP
metaModel's `or` / `array` / `map` / `reference` kinds, written as text. The schema check: JSON Schema 2020-12. The
enumerations: TypeScript's `as const` object pattern (the handbook's alternative to `enum`), Python's `StrEnum`. The
lint: ESLint `no-restricted-syntax` selectors, and a stdlib `ast` scan as `py/tests/test_layers.py` already does.
Namespaces: Node package `exports` subpaths, Python subpackages. The block: ES2022 `Array.prototype.at` and
`Iterable`, Python's `collections.abc.Sequence`. The committed docs tables: `cog`-style generated regions with a
freshness check.

## 1. What landed outside `ts/src` and `py/src` (this lane, done)

| Path | What |
|---|---|
| `spec/schema/api.json` (v3) | typed: every member type in the closed grammar, all resolving; spellings gone (derived); typed traits instead of `spell`; error groups with `sort`, typed `fields`, `message` (given or a template), `cause`, per-language `base` / `builtin`; free functions with `factory`, `module`, `options`; new concepts `program code`, `locatable`, `token range`, `block` (shape), `expansion block`, `rendered block`, `key rule`, `key options`, `load options`, `processor options`, `fetch writer options`, `fetch function`, `collecting`; kind list `walk control`; `keywords`; constants named by spec name (`max nesting`, ...); `layers` with `namespace`; `diagnostic` moved to shared; `statement.parent` precise; `node` extends `token range`; `resolution` generic |
| `spec/schema/diagnostics.json` (v2) | `ts`/`py` gone (derived); `found by` from a closed list; meanings reconciled with spec 2.4 (errata); `summary` and `placed at` (the user guide's table) |
| `spec/schema/protocol.json` (new) | the adapter protocol: 31 shapes and results, 13 requests with their prose, edit members, readers |
| `spec/schema/api.schema.json` (new) | JSON Schema 2020-12 for the three files: closed objects, enums for every closed set, the type alphabet |
| `.claude/design/consumer-api/round15/schema-history.json` (new) | `removed in milestone 1/2/4/5` and `disagreements`, moved out of the schema |
| `tools/gen-api.py` | the command (`ts`, `py`, `docs`, `--check`), now a thin front over `tools/api/` |
| `tools/api/loader.py` (new) | casing rule, type grammar parser, model, every structural check, 12 planted breakages |
| `tools/api/emit_ts.py`, `emit_py.py`, `emit_docs.py` (new) | one emitter per language, and the Markdown tables |
| `tools/api/validate.py` (new) | the JSON Schema check with 5 planted breakages |
| `tools/lint/kind-rule.mjs`, `tools/lint/kind_lint.py` (new) | the kind lint, TypeScript selectors and Python `ast` scan |
| `tools/check.sh`, `tools/gen.sh` | check.sh runs the schema check, the meta-schema check and the kind lint's self-test; gen.sh's comments |
| `ts/.gitignore`, `py/.gitignore` (build wiring) | `conformance/shapes.ts`, `conformance/shapes.py`: the generator's two new output paths, ignored |
| `spec/codegen.md` | rewritten: what is generated, the type grammar, the traits, the emitters, the protocol, the docs tables, the lint, prior art, a new binding = an emitter and an adapter |
| `spec/spec.md` | status; 2.4 (generated table, found-by list); 2.5 (the rules module, keywords); **2.10 rewritten** (enumerations); **2.11 new** (blocks); 6.5 written block; 6.10 expansion block; 7.1, 7.2, 7.5 (walk on the block) |
| `spec/binding-guide.md` | rules 2 and 5 adopted, rule 4's TypeScript model, **rule 9 new** (one namespace per layer, the import path table); section 3 rows; section 4 header; checklist step 4 (write an emitter) and 5; the milestone 5 `plain()` leftover |
| `spec/conformance.md` | 4.1 and 4.2 generated from `protocol.json`; section 6 (generated shapes, `SPELLING`, `ERROR_GROUP_OF_CLASS`); section 7 |
| `spec/glossary.md`, `spec/README.md`, `README.md` | no `I` prefix; import paths; milestone 6 terms |
| `docs/language.md`, `docs/low-level-api.md`, `docs/rendered-tree.md` | the milestone 5 leftovers (`@set`); new import lines; no `I` prefix; `written.X` / `rendered.X` in Python; block shape (`[...block]`, `block.at(i)`, `block.walk`); the generated error-code table |
| `.claude/skills/knobly-binding/SKILL.md` | a new binding is an emitter and an adapter; schema first; the new traps |

**Checks at this commit.** `bash tools/check.sh`: green (0 conflicts; 21 token kinds, 0 overlapping; 13 planted
grammars caught; "schema checked; 12 planted breakages caught; ts and py rendered; docs tables current"; "3 files
match api.schema.json; 5 planted breakages caught"; "kind lint: 3 planted comparisons caught, clean code passes"
(4 under Python 3.10+, which reads `match`); the driver's self-test). `tools/gen-api.py ts` and `py` run; with the
output in place: TypeScript `tsc --noEmit`, `tsc -p conformance`, `eslint .`, `tsc -p tsconfig.build.json` pass;
Python `ruff check`, `ruff format --check` and `mypy` (62 files, strict) pass. The shared driver passes all 375 cases
with both adapters (L0 168, L1 60, L2 123, L3 24).

**Red today, and why.** `ts/src/api-names.test.ts` and `py/tests/test_api_names.py` fail to collect: they read
`removed in milestone 5`, `ts`, `py` and `spell`, which the typed schema no longer has. Every other test passes
(TypeScript 222, Python 433). Each lane replaces its test with the names test of section 2.B (it is the first thing
each lane does).

**Evidence the generated interfaces fit the hand code.** A scratch check (not committed) asserted every hand-written
TypeScript type assignable to its generated interface. With the two `ConfigText` brands unified, the only mismatches
are the approved block shape (the written, expansion and rendered blocks, and everything that reaches one) and one
real difference: `ISliceValue`'s optional `start?`/`end?` against the generated `start: number | undefined`
(errata). Python's hand records are other classes than the generated dataclasses, so the same check there only
reports the switch-over itself; mypy checks the Protocols when the lane subclasses them.

## 2. Per item

### A. The typed schema (kno-umh.9)

- **Type grammar** (spec/codegen.md section 2): `type = postfix {" or " postfix}`, `postfix = primary {"[]"}`,
  `primary = (type) | function [of T {and T}] to T | [writable] map of T [to T] | name [of T {and T}]`; names are
  `text integer number boolean nothing absent`, a concept, a kind list, `diagnostic code`, an error group, or a type
  parameter in scope. `absent` is a type (`written block or absent`).
- **Checks** (`tools/api/loader.py`, run by `tools/gen-api.py --check` in `tools/check.sh`): every name resolves; the
  layer direction for every member, parameter, free function and error field; variants cover their kind list;
  `extends` and type arguments; the error tree on the two sorts and each root's base; options records; traits,
  found-by and limit placeholders from closed lists; a request note names each parameter; no two public names derive
  one identifier per path. Planted: unresolved type, type grammar, layer direction, free-text type, variant missing,
  wrong kind, bad parent, bug under the base, unknown trait, spelling collision, bad found-by, protocol type.
- **Traits** (closed list): `people form`, `iterate`, `count`, `index`, `walk`, `collect`; fields `io`, `passed`
  (`position`, `keyword`, `option`), `options`, `factory`, `module`, `languages`, error group `ts`/`py`
  `{base|builtin}`. Their per-language forms are spec/codegen.md section 3's table.
- **Spellings** derived by one casing rule (`tools/api/loader.py`): types `PascalCase`; members `camelCase` /
  `snake_case`; enum members `PascalCase` / `UPPER_SNAKE_CASE` (token kinds keep the grammar's names); constants
  `UPPER_SNAKE_CASE`; free functions `camelCase` / `snake_case`; a `package function` factory is named after the
  package (`knobly`).
- **Error groups** carry `sort` (`base`, `expected outcome`, `program bug`) and each root its per-language base:
  `knobly error` `Error` / `Exception`; `detached error` `ReferenceError` / `ReferenceError`; `misuse error`
  `Error` (class `MisuseError`) / builtin `ValueError`; `argument type error` builtin `TypeError` / `TypeError`;
  `index out of range` builtin `RangeError` / `IndexError`.
- **Moved out:** `removed in milestone N` and `disagreements` to `round15/schema-history.json`; `layer check`, `kind
  rule`, `error fields`, `naming` to the spec pages that already state them (binding guide rule 8, spec 2.10, the
  typed `fields`, spec/codegen.md section 3).

### B. The generator and what each binding does with it (kno-umh.10)

`tools/gen.sh ts` and `tools/gen.sh py` run the loader and the language's emitter. Output paths: TypeScript
`ts/src/gen/api/` (unchanged) and `ts/conformance/shapes.ts` (new); Python `py/src/knobly/_api/` (unchanged) and
`py/conformance/shapes.py` (new). All git-ignored; nothing to commit.

**Generated modules and their exact names** (each name is generated from the schema; doc comments omitted):

| Module | Exported names |
|---|---|
| `ts/src/gen/api/codes.ts` | `DiagnosticCode`, `MESSAGES`, `CodeFacts`, `CODE_FACTS`, `ReasonOf`, `describe` |
| `ts/src/gen/api/errors.ts` | `KnoblyError`, `DiagnosticError`, `ReadError`, `BadTextError`, `SaveError`, `LostUpdateError`, `DetachedError`, `MisuseError`, `argumentTypeMessage` |
| `ts/src/gen/api/io.ts` | `LoadContext`, `DocumentSource`, `FileWrite`, `DocumentWriter`, `FetchWriterOptions`, `IoFunctions`, `BrowserFunctions`, `NodeFunctions` |
| `ts/src/gen/api/kinds.ts` | `TokenKind`, `NodeKind`, `StatementKind`, `ValueKind`, `VariableKind`, `StepKind`, `PlaceKind`, `UnreadableReason`, `ChangeKind`, `WalkControl`, `Keyword`, `STATEMENT_OF_KEYWORD`, `statementOfKeyword` |
| `ts/src/gen/api/limits.ts` | `MAX_NESTING`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `VARIABLE_NAME`, `PROGRAM_CODE` |
| `ts/src/gen/api/names.ts` | `PUBLIC_NAMES`, `ERROR_GROUP_OF_CLASS` |
| `ts/src/gen/api/rendered.ts` | `Rendered`, `Directive`, `RenderedBlock`, `KeyRule`, `KeyOptions`, `AddressStep`, `Address`, `Change`, `Added`, `Removed`, `Changed`, `Unknown`, `RenderedFunctions` |
| `ts/src/gen/api/shared.ts` | `ConfigText`, `SourcePosition`, `SourceSpan`, `Place`, `Override`, `Step`, `Origin`, `DirectiveOrigin`, `Diagnostic`, `ProgramCode`, `LocatedDiagnostic`, `Locatable`, `Diagnostics`, `Block`, `SharedFunctions` |
| `ts/src/gen/api/syntax.ts` | `TokenRange`, `Token`, `Node`, `Syntax`, `SyntaxFunctions` |
| `ts/src/gen/api/written.ts` | `Extension`, `ExtensionUse`, `LoadOptions`, `ProcessorOptions`, `Processor`, `DocumentGraph`, `Document`, `DocumentEdge`, `Copy`, `Statement`, `WrittenDirective`, `ExtensionLine`, `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine`, `WrittenBlock`, `WrittenValue`, `Word`, `String`, `List`, `Slice`, `Index`, `Reference`, `Variable`, `SetVariable`, `Parameter`, `OverrideVariable`, `Resolution`, `ReferenceResolution`, `Expansion`, `ExpansionBlock`, `DirectiveExpansion`, `UnreadableExpansion`, `SliceValue`, `IndexValue`, `ExpandedValue`, `ExpandedWord`, `ExpandedString`, `ExpandedList`, `ExpandedSlice`, `ExpandedIndex`, `IncludeFunctions`, `WrittenFunctions` |
| `ts/conformance/shapes.ts` | `Json`, `PROTOCOL`, `Position`, `PlaceDump`, `OverrideDump`, `StepDump`, `OriginDump`, `SyntaxDiagnosticDump`, `LocatedDiagnosticDump`, `TokenDump`, `NodeDump`, `SyntaxDump`, `VariableReferenceDump`, `ReferencePlaceDump`, `ResolutionDump`, `WrittenValueDump`, `StatementDump`, `BlockDump`, `CopyDump`, `DocumentDump`, `EdgeDump`, `GraphVariableDump`, `GraphDump`, `AddressDump`, `UnreadableDump`, `ExpandedValueDump`, `DirectiveDump`, `RenderDump`, `ChangeDump`, `HandleDump`, `KeyRuleDump`, `ReaderResultDump`, `HelloResultDump`, `LoadedDump`, `EditedDump`, `SavedDump`, `RequestParams`, `RequestResults`, `SPELLING` |

| Module | Public names |
|---|---|
| `py/src/knobly/_api/codes.py` | `DiagnosticCode`, `MESSAGES`, `CodeFacts`, `CODE_FACTS`, `Described`, `describe` |
| `py/src/knobly/_api/errors.py` | `KnoblyError`, `DiagnosticError`, `ReadError`, `BadTextError`, `SaveError`, `LostUpdateError`, `DetachedError`, `argument_type_message` |
| `py/src/knobly/_api/io.py` | `LoadContext`, `DocumentSource`, `FileWrite`, `DocumentWriter`, `IoFunctions`, `FilesFunctions` |
| `py/src/knobly/_api/kinds.py` | `TokenKind`, `NodeKind`, `StatementKind`, `ValueKind`, `VariableKind`, `StepKind`, `PlaceKind`, `UnreadableReason`, `ChangeKind`, `Keyword`, `STATEMENT_OF_KEYWORD`, `statement_of_keyword` |
| `py/src/knobly/_api/limits.py` | `MAX_NESTING`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `VARIABLE_NAME`, `PROGRAM_CODE` |
| `py/src/knobly/_api/names.py` | `PUBLIC_NAMES`, `ERROR_GROUP_OF_CLASS`, `MATCH_ARGS` |
| `py/src/knobly/_api/rendered.py` | `Rendered`, `Directive`, `RenderedBlock`, `AddressStep`, `Address`, `Added`, `Removed`, `Changed`, `Unknown`, `KeyRule`, `Change`, `RenderedFunctions` |
| `py/src/knobly/_api/shared.py` | `ConfigText`, `SourcePosition`, `SourceSpan`, `Place`, `Override`, `Step`, `Origin`, `DirectiveOrigin`, `Diagnostic`, `LocatedDiagnostic`, `Locatable`, `Diagnostics`, `Block`, `ProgramCode`, `SharedFunctions` |
| `py/src/knobly/_api/syntax.py` | `TokenRange`, `Token`, `Node`, `Syntax`, `SyntaxFunctions` |
| `py/src/knobly/_api/written.py` | `Extension`, `ExtensionUse`, `Processor`, `DocumentGraph`, `Document`, `DocumentEdge`, `Copy`, `WrittenDirective`, `ExtensionLine`, `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine`, `WrittenBlock`, `Word`, `String`, `List`, `Slice`, `Index`, `Reference`, `SetVariable`, `Parameter`, `OverrideVariable`, `Resolution`, `ReferenceResolution`, `Expansion`, `ExpansionBlock`, `DirectiveExpansion`, `UnreadableExpansion`, `SliceValue`, `IndexValue`, `ExpandedWord`, `ExpandedString`, `ExpandedList`, `ExpandedSlice`, `ExpandedIndex`, `Statement`, `WrittenValue`, `Variable`, `ExpandedValue`, `IncludeFunctions`, `WrittenFunctions` |
| `py/conformance/shapes.py` | `Json`, `PROTOCOL`, `Position`, `PlaceDump`, `OverrideDump`, `StepDump`, `OriginDump`, `SyntaxDiagnosticDump`, `LocatedDiagnosticDump`, `TokenDump`, `NodeDump`, `SyntaxDump`, `VariableReferenceDump`, `ReferencePlaceDump`, `ResolutionDump`, `WrittenValueDump`, `StatementDump`, `BlockDump`, `CopyDump`, `DocumentDump`, `EdgeDump`, `GraphVariableDump`, `GraphDump`, `AddressDump`, `UnreadableDump`, `ExpandedValueDump`, `DirectiveDump`, `RenderDump`, `ChangeDump`, `HandleDump`, `KeyRuleDump`, `ReaderResultDumpText`, `ReaderResultDumpBoolean`, `ReaderResultDumpNumber`, `ReaderResultDumpSlice`, `ReaderResultDumpIndex`, `ReaderResultDumpValue`, `ReaderResultDumpList`, `ReaderResultDump`, `HelloResultDump`, `LoadedDump`, `EditedDump`, `SavedDump`, `SPELLING` |

Signatures worth quoting exactly (the rest are in the generated files; `python3 tools/gen-api.py ts` and `py`
regenerate them):

```ts
// shared.ts: the one block shape (spec 2.11)
export interface Block<TItem, TDirective> extends Iterable<TItem> {
  readonly length: number;
  at(index: number): TItem | undefined;
  directives(name?: string): readonly TDirective[];
  walk(visit: (item: TItem) => WalkControl | void): void;
}
// written.ts
export interface WrittenBlock extends Block<Statement, WrittenDirective> {
  insertStatements(index: number, text: ConfigText): readonly Statement[];
  addStatements(text: ConfigText): readonly Statement[];
}
export interface ExpansionBlock extends Block<DirectiveExpansion, DirectiveExpansion> {}
// rendered.ts
export interface RenderedBlock extends Block<Directive, Directive> {}
export interface Rendered {
  readonly block: RenderedBlock;
  readonly unreadable: readonly UnreadableExpansion[];
  readonly origin: DirectiveOrigin;
  readonly diagnostics: readonly LocatedDiagnostic[];
  readonly graph: DocumentGraph;
  error(message: string, code: ProgramCode): DiagnosticError;
  addresses(options?: KeyOptions): ReadonlyMap<Directive, Address>;
  diff(after: Rendered, options?: KeyOptions): readonly Change[];
}
// kinds.ts (every list the same way)
export const StatementKind = { Directive: "directive", Extension: "extension", Set: "set", Snippet: "snippet", Use: "use", Unreadable: "unreadable" } as const;
export type StatementKind = (typeof StatementKind)[keyof typeof StatementKind];
export const STATEMENT_OF_KEYWORD: Readonly<Record<Keyword, StatementKind>>;
export function statementOfKeyword(word: string): StatementKind | undefined;
// codes.ts
export function describe<C extends DiagnosticCode>(code: C, detail?: string): { readonly code: C; readonly message: string; readonly reason: ReasonOf<C> };
// errors.ts
export class ReadError extends KnoblyError { constructor(message: string, readonly paths: readonly string[], options?: ErrorOptions) }
export class LostUpdateError extends SaveError { constructor(paths: readonly string[]) }
export function argumentTypeMessage(member: string, parameter: string, got: string): string;
```

```python
# shared.py
class Block(Protocol[ItemT_co, DirectiveT_co]):
    def __iter__(self) -> Iterator[ItemT_co]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int, /) -> ItemT_co: ...
    def directives(self, name: str | None = None, /) -> tuple[DirectiveT_co, ...]: ...
    def walk(self, *, descend: Callable[[ItemT_co], bool] | None = None) -> Iterator[ItemT_co]: ...
# written.py
class WrittenBlock(Block["Statement", "WrittenDirective"], Protocol):
    def insert_statements(self, index: int, text: ConfigText, /) -> tuple[Statement, ...]: ...
    def add_statements(self, text: ConfigText, /) -> tuple[Statement, ...]: ...
class SetLine(Protocol):
    @property
    def kind(self) -> Literal[StatementKind.SET]: ...
    ...  # every member of statement, then its own
@final
@dataclass(frozen=True, slots=True, eq=False)
class Copy:
    statement: Statement
    via: tuple[Step, ...]
# kinds.py
STATEMENT_OF_KEYWORD: Final[Mapping[Keyword, StatementKind]]
def statement_of_keyword(word: str, /) -> StatementKind | None: ...
# codes.py
def describe(code: DiagnosticCode, detail: str | None = None, /) -> Described: ...
# errors.py
class ReadError(KnoblyError):
    paths: tuple[str, ...]
    def __init__(self, message: str, paths: Sequence[str]) -> None: ...
def argument_type_message(member: str, parameter: str, got: str, /) -> str: ...
```

**What each binding does with them, and deletes.**

TypeScript lane:

- Each public entry re-exports the generated types and the hand-written runtime values, and nothing else:
  `ts/src/index.ts` (the package root: shared and io), new `ts/src/syntax/index.ts`, `ts/src/written/index.ts`,
  `ts/src/rendered/index.ts`; `package.json` `exports` gains `./syntax`, `./written`, `./rendered` (beside `.`,
  `./include`, `./node`, `./browser`). The root no longer does `export * from "./written/index.js"` or the rendered
  one.
- Every hand-written class `implements` its generated interface (`class Place implements shared.Place`, the
  statement and value classes their variant, `Diagnostics implements shared.Diagnostics`), and the processor,
  graph, render and blocks likewise.
- **Delete** the hand-written interfaces and their files' type halves: `ts/src/span.ts` (both interfaces),
  `ISourcePosition`/`IPlace`/`IOverride`/`IStep`/`IOrigin`/`IDirectiveOrigin` in `ts/src/origin.ts`,
  `IDiagnostic` in `ts/src/diagnostics.ts`, `ILocatedDiagnostic`/`ILocatable`/`ProgramCode` in `ts/src/report.ts`,
  `ILoadContext`/`IDocumentSource`/`IFileWrite`/`IDocumentWriter` in `ts/src/source.ts`, `IToken` in
  `ts/src/syntax/tokens.ts`, `ITokenRange`/`INode`/`ISyntax`/`ValueRef` (public) in `ts/src/syntax/cst.ts`,
  `IExtension`/`IExtensionUse` in `ts/src/written/extension.ts`, `IProcessorOptions`/`ILoadOptions`/`IProcessor` in
  `ts/src/written/processor.ts`, every interface and union of `ts/src/written/model.ts` (the file keeps nothing
  public), `ISliceValue`/`IIndexValue`/`IExpandedValueBase`/the `IExpanded*` variants and `ExpandedValue` in
  `ts/src/written/value.ts`, every interface of `ts/src/rendered/model.ts` (`IAddressStep`, `IAddress`,
  `WalkControl`, `IDirective`, `KeyRule`, `IKeyOptions`, `IRendered`, `IAdded`, `IRemoved`, `IChanged`, `IUnknown`,
  `Change`), `IFetchWriterOptions` in `ts/src/browser.ts`, `ConfigText` in `ts/src/text.ts`; the error classes of
  `ts/src/errors.ts` (re-export the generated ones) and the argument type message built in `ts/src/text.ts`
  (call `argumentTypeMessage`).
- **Replace** `ts/src/api-names.test.ts` (478 lines) with one test: for each path in `PUBLIC_NAMES`, the module's
  exports (values from `Object.keys(await import(...))`, types through the TypeScript compiler API's
  `getExportsOfModule` on the entry's source) equal `values` and `types`, both ways. Keep `ts/src/types.test.ts`'s
  compile-time checks that are not names (narrowing, the config text brand).
- **Kinds:** every `kind`/`reason`/`code` comparison uses a member (`StatementKind.Set`, `UnreadableReason.Value`,
  `DiagnosticCode.UnknownVariable`); statement classification reads `statementOfKeyword` (no `"@set"` text
  compare). Raise sites build code, message and reason with `describe(code, detail)` where they paired them by hand.
  Today the kind rule finds 68 comparisons (60 in `src/`, 8 in `conformance/adapter.ts`; `written/bind.ts` 16,
  `written/value.ts` 15, `written/document.ts` 6, `written/shape.ts` 6, `written/override.ts` 4, others 1 or 2).
- **Block shape:** the written block loses `statements` and gains `[Symbol.iterator]`, `length`, `at`, `walk`; the
  expansion's and a directive expansion's `block`, the render's and a directive's `block` become block objects;
  `walk` leaves `IRendered` and `IDirective`. `ISliceValue` becomes `start: number | undefined` (errata).
- **Lint:** `ts/eslint.config.js` imports `KIND_RULE` from `../tools/lint/kind-rule.mjs` and adds it to
  `no-restricted-syntax` for `src/**/*.ts` and `conformance/*.ts`, with a planted case in `src/layers.test.ts` as
  for the other rules.
- **Adapter:** `ts/conformance/adapter.ts` types its dumps with `./shapes.ts`, spells members with `SPELLING` and
  names thrown groups with `ERROR_GROUP_OF_CLASS[e.name]` (no regex).

Python lane:

- Public modules: `knobly/__init__.py` exports only the root names of section D; `knobly.syntax`,
  `knobly.written`, `knobly.rendered` export theirs; each `__all__` equals `PUBLIC_NAMES[module]`.
- Each hand-written handle and port class subclasses its generated Protocol (`class Document(_api.written.Document)`,
  the six statement classes their variant, the six value classes theirs, `DocumentGraph`, `Processor`,
  `Diagnostics`, `Rendered`, `Directive`, the three blocks); mypy then checks every member at the class.
- **Delete** and import from `_api` instead: the dataclasses that the generator now writes (`SourcePosition`,
  `SourceSpan` in `span.py`; `Origin`, `DirectiveOrigin` in `origin.py`; `Token` in `syntax/tokens.py`; `Node`,
  `Syntax`, `TokenRange` in `syntax/cst.py`; `LoadContext`, `FileWrite` in `source.py`; `ExtensionUse` in
  `written/extension.py`; `DocumentEdge`, `Copy`, `Resolution`, `ReferenceResolution`, `Expansion`,
  `DirectiveExpansion`, `UnreadableExpansion` in `written/model.py`; `SliceValue`, `IndexValue` in
  `written/value.py`; `AddressStep`, `Added`, `Removed`, `Changed`, `Unknown` in `rendered/_tree.py`) unless one
  holds private state, in which case it becomes a handle class subclassing the Protocol (say which in the errata);
  `DocumentSource`, `DocumentWriter`, `Extension`, `Locatable` Protocols (the generated ones are the public ones);
  `errors.py` (re-export the generated tree); `KeyRule`, `ConfigText`; the argument type message text in
  `_text.py`.
- **Replace** `py/tests/test_api_names.py` (264 lines) with one test: each module's `__all__` equals
  `PUBLIC_NAMES[module]`, every name in it exists, and every class with a `MATCH_ARGS` entry has that
  `__match_args__`.
- **Kinds:** every comparison uses an enum member; `_shape.py` and `_bind.py` dispatch keywords through
  `statement_of_keyword`; raise sites use `describe`. Today the kind lint finds 7 (`written/_bind.py:340,342,344`,
  `written/_document.py:970,972`, `written/_shape.py:105,112`). `py/tests/` gains a test running
  `tools/lint/kind_lint.py` over `src/` and `conformance/` (Python 3.11, so `match` is read) that fails on any
  finding.
- **Block shape:** the written block gains `walk`; the expansion's, a directive expansion's, the render's and a
  directive's `block` become block objects (`Sequence` plus `directives`, `walk`); `walk` leaves `Rendered` and
  `Directive`.
- **Adapter:** `py/conformance/adapter.py` types its dumps with `shapes`, spells with `SPELLING`, names groups with
  `ERROR_GROUP_OF_CLASS[type(e).__name__]`.

### C. Enumerations and the lint (kno-umh.11)

- Spec 2.10 rewritten: TypeScript `as const` object plus derived union under one name; Python `StrEnum`; inside a
  binding, members only. `DiagnosticCode` the same in both forms.
- **The lint rule, exactly.** TypeScript (`tools/lint/kind-rule.mjs`, `no-restricted-syntax`):
  1. `BinaryExpression[operator=/^[!=]==?$/][left.property.name=/^(kind|reason|code)$/][right.type='Literal']`
  2. `BinaryExpression[operator=/^[!=]==?$/][right.property.name=/^(kind|reason|code)$/][left.type='Literal']`
  3. `SwitchStatement[discriminant.property.name=/^(kind|reason|code)$/] > SwitchCase > Literal.test`

  Python (`tools/lint/kind_lint.py PATH...`): an `ast.Compare` with `==`, `!=`, `in` or `not in` between an
  `Attribute` named `kind`, `reason` or `code` and a `str` constant (or a tuple, list or set holding one), either side
  for `==`/`!=`; a `match <attr>:` whose case is a `str` value pattern. Skips `_gen/`. Exit 1 on any finding.
  Self-test: `python3 tools/lint/kind_lint.py --self-test` (in `tools/check.sh`).
- Verified on probes: the TypeScript selectors flag `s.kind === "set"`, `"use" !== s.kind`, `s.reason == "value"`
  and `case "E1001":`, and leave `s.kind === K.Set` and `case K.Set:` alone.

### D. Namespaces and the block shape (kno-umh.13)

**Import paths per layer** (binding guide rule 9): shared and io `knobly`; syntax `knobly/syntax` /
`knobly.syntax`; written `knobly/written` / `knobly.written`; rendered `knobly/rendered` /
`knobly.rendered`; adapters unchanged (`knobly/node`, `knobly/browser`, `knobly/include`;
`knobly.files`, `knobly.include`). Every public name, per path (generated `PUBLIC_NAMES`):

| Import path | TypeScript values | TypeScript types only |
|---|---|---|
| `knobly` | `BadTextError`, `DetachedError`, `DiagnosticCode`, `DiagnosticError`, `Diagnostics`, `LostUpdateError`, `MisuseError`, `PROGRAM_CODE`, `PlaceKind`, `ReadError`, `SaveError`, `StepKind`, `KnoblyError`, `WalkControl`, `checkLostUpdates`, `memorySource`, `memoryWriter`, `quote`, `text` | `ConfigText`, `Diagnostic`, `DirectiveOrigin`, `DocumentSource`, `DocumentWriter`, `FileWrite`, `LoadContext`, `Locatable`, `LocatedDiagnostic`, `Origin`, `Override`, `Place`, `ProgramCode`, `SourcePosition`, `SourceSpan`, `Step` |
| `knobly/browser` | `fetchSource`, `fetchWriter` | `FetchWriterOptions` |
| `knobly/include` | `include` | — |
| `knobly/node` | `fileSource`, `fileWriter` | — |
| `knobly/rendered` | `ChangeKind`, `render` | `Added`, `Address`, `AddressStep`, `Change`, `Changed`, `Directive`, `KeyOptions`, `KeyRule`, `Removed`, `Rendered`, `RenderedBlock`, `Unknown` |
| `knobly/syntax` | `MAX_NESTING`, `NodeKind`, `TokenKind`, `parse`, `spanOf`, `textOf` | `Node`, `Syntax`, `Token`, `TokenRange` |
| `knobly/written` | `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `StatementKind`, `UnreadableReason`, `VARIABLE_NAME`, `ValueKind`, `VariableKind`, `formatDiagnostic`, `knobly` | `Copy`, `DirectiveExpansion`, `Document`, `DocumentEdge`, `DocumentGraph`, `ExpandedIndex`, `ExpandedList`, `ExpandedSlice`, `ExpandedString`, `ExpandedValue`, `ExpandedWord`, `Expansion`, `ExpansionBlock`, `Extension`, `ExtensionLine`, `ExtensionUse`, `Index`, `IndexValue`, `List`, `LoadOptions`, `OverrideVariable`, `Parameter`, `Processor`, `ProcessorOptions`, `Reference`, `ReferenceResolution`, `Resolution`, `SetLine`, `SetVariable`, `Slice`, `SliceValue`, `SnippetLine`, `Statement`, `String`, `UnreadableExpansion`, `UnreadableLine`, `UseLine`, `Variable`, `Word`, `WrittenBlock`, `WrittenDirective`, `WrittenValue` |

| Module | Python `__all__` |
|---|---|
| `knobly` | `BadTextError`, `Collecting`, `ConfigText`, `DetachedError`, `Diagnostic`, `DiagnosticCode`, `DiagnosticError`, `Diagnostics`, `DirectiveOrigin`, `DocumentSource`, `DocumentWriter`, `FileWrite`, `LoadContext`, `Locatable`, `LocatedDiagnostic`, `LostUpdateError`, `Origin`, `Override`, `PROGRAM_CODE`, `Place`, `PlaceKind`, `ProgramCode`, `ReadError`, `SaveError`, `SourcePosition`, `SourceSpan`, `Step`, `StepKind`, `KnoblyError`, `check_lost_updates`, `memory_source`, `memory_writer`, `quote`, `text` |
| `knobly.files` | `file_source`, `file_writer` |
| `knobly.include` | `include` |
| `knobly.rendered` | `Added`, `Address`, `AddressStep`, `Change`, `ChangeKind`, `Changed`, `Directive`, `KeyRule`, `Removed`, `Rendered`, `RenderedBlock`, `Unknown`, `render` |
| `knobly.syntax` | `MAX_NESTING`, `Node`, `NodeKind`, `Syntax`, `Token`, `TokenKind`, `TokenRange`, `parse`, `span_of`, `text_of` |
| `knobly.written` | `Copy`, `DirectiveExpansion`, `Document`, `DocumentEdge`, `DocumentGraph`, `ExpandedIndex`, `ExpandedList`, `ExpandedSlice`, `ExpandedString`, `ExpandedValue`, `ExpandedWord`, `Expansion`, `ExpansionBlock`, `Extension`, `ExtensionLine`, `ExtensionUse`, `Index`, `IndexValue`, `List`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `OverrideVariable`, `Parameter`, `Processor`, `RESERVED`, `Reference`, `ReferenceResolution`, `Resolution`, `SetLine`, `SetVariable`, `Slice`, `SliceValue`, `SnippetLine`, `Statement`, `StatementKind`, `String`, `UnreadableExpansion`, `UnreadableLine`, `UnreadableReason`, `UseLine`, `VARIABLE_NAME`, `ValueKind`, `Variable`, `VariableKind`, `Word`, `WrittenBlock`, `WrittenDirective`, `WrittenValue`, `format_diagnostic` |

**The block shape** (spec 2.11): every block is iterated (`Symbol.iterator` / `__iter__`), counted (`length` /
`len`), indexed (`at(i)`, absent out of range / `block[i]`, `IndexError`), has `directives(name?)` and `walk` (a
callback returning `WalkControl` / a generator with `descend`). Three blocks: `WrittenBlock` (statements; adds
`insertStatements`, `addStatements`), `ExpansionBlock` (directive expansions), `RenderedBlock` (directives). A
written block's `walk` visits every statement at any depth (written directives', extension lines' and snippet lines'
blocks). The syntax layer has no block.

**New terms** (glossary "New terms in milestone 6"): block (the shape), `expansion block`, `rendered block`, `walk
control`, keyword / `Keyword`, type grammar, trait, rules module.

### E. The milestone 5 leftovers

- `docs/language.md` (the `set` lines of "Variables": now `@set`, nine places), `docs/low-level-api.md:408-409`,
  `docs/rendered-tree.md` (the `expansion` reason row, the include block's `@set` lines, the directive paragraph's
  `@set`, `@snippet`, `@use`, `@include`): every statement spelled with `@`.
- `spec/binding-guide.md:282`: the reader row records "M5: `plain()` deleted in both".
- The two name tests' different "removed" lists: gone with the tests; both bindings read the one generated
  `PUBLIC_NAMES`, which has no removed name in it, so a removed name exported anywhere fails the both-ways comparison.
  `PlainValue` (the missing TypeScript type) is caught the same way.

## 3. Behaviour changes

Every public rename and import-path change, generated from the old entry points and the new `PUBLIC_NAMES`; then
every member and type change.

**TypeScript** (every name below was exported by `"knobly"`; it is now exported only by the path heading its row):

| New import path | Renamed (old → new) | Moved unchanged |
|---|---|---|
| `knobly` | `IDiagnostic` → `Diagnostic`, `IDirectiveOrigin` → `DirectiveOrigin`, `IDocumentSource` → `DocumentSource`, `IDocumentWriter` → `DocumentWriter`, `IFileWrite` → `FileWrite`, `ILoadContext` → `LoadContext`, `ILocatable` → `Locatable`, `ILocatedDiagnostic` → `LocatedDiagnostic`, `IOrigin` → `Origin`, `IOverride` → `Override`, `IPlace` → `Place`, `ISourcePosition` → `SourcePosition`, `ISourceSpan` → `SourceSpan`, `IStep` → `Step` | `BadTextError`, `ConfigText`, `DetachedError`, `DiagnosticCode`, `DiagnosticError`, `Diagnostics`, `LostUpdateError`, `MisuseError`, `PlaceKind`, `ProgramCode`, `ReadError`, `SaveError`, `StepKind`, `KnoblyError`, `WalkControl`, `checkLostUpdates`, `memorySource`, `memoryWriter`, `quote`, `text` |
| `knobly/rendered` | `IAdded` → `Added`, `IAddress` → `Address`, `IAddressStep` → `AddressStep`, `IChanged` → `Changed`, `IDirective` → `Directive`, `IKeyOptions` → `KeyOptions`, `IRemoved` → `Removed`, `IRendered` → `Rendered`, `IUnknown` → `Unknown` | `Change`, `ChangeKind`, `KeyRule`, `render` |
| `knobly/syntax` | `INode` → `Node`, `ISyntax` → `Syntax`, `IToken` → `Token`, `ITokenRange` → `TokenRange` | `NodeKind`, `TokenKind`, `parse`, `spanOf`, `textOf` |
| `knobly/written` | `ICopy` → `Copy`, `IDirectiveExpansion` → `DirectiveExpansion`, `IDocument` → `Document`, `IDocumentEdge` → `DocumentEdge`, `IDocumentGraph` → `DocumentGraph`, `IExpandedIndex` → `ExpandedIndex`, `IExpandedList` → `ExpandedList`, `IExpandedSlice` → `ExpandedSlice`, `IExpandedString` → `ExpandedString`, `IExpandedWord` → `ExpandedWord`, `IExpansion` → `Expansion`, `IExtension` → `Extension`, `IExtensionLine` → `ExtensionLine`, `IExtensionUse` → `ExtensionUse`, `IIndex` → `Index`, `IIndexValue` → `IndexValue`, `IList` → `List`, `ILoadOptions` → `LoadOptions`, `IOverrideVariable` → `OverrideVariable`, `IParameter` → `Parameter`, `IProcessor` → `Processor`, `IProcessorOptions` → `ProcessorOptions`, `IReference` → `Reference`, `IReferenceResolution` → `ReferenceResolution`, `IResolution` → `Resolution`, `ISetLine` → `SetLine`, `ISetVariable` → `SetVariable`, `ISlice` → `Slice`, `ISliceValue` → `SliceValue`, `ISnippetLine` → `SnippetLine`, `IString` → `String`, `IUnreadableExpansion` → `UnreadableExpansion`, `IUnreadableLine` → `UnreadableLine`, `IUseLine` → `UseLine`, `IWord` → `Word`, `IWrittenBlock` → `WrittenBlock`, `IWrittenDirective` → `WrittenDirective` | `ExpandedValue`, `Statement`, `StatementKind`, `UnreadableReason`, `ValueKind`, `Variable`, `VariableKind`, `WrittenValue`, `formatDiagnostic`, `knobly` |

Removed from TypeScript, no replacement: `IExpandedValueBase`, `IStatementBase`, `IValueBase`, `IVariableBase`, `ValueRef` (the `*Base` interfaces were the hand-written bases of the unions: the generated variants are flat; `ValueRef` was an internal type that leaked, round 15).

**Python** (each name below was in `knobly.__all__`; it leaves the root and stays only in its subpackage's `__all__`):

| Import from | Names that leave `knobly` |
|---|---|
| `knobly.rendered` | `Added`, `Address`, `AddressStep`, `Change`, `ChangeKind`, `Changed`, `Directive`, `KeyRule`, `Removed`, `Rendered`, `Unknown`, `render` |
| `knobly.syntax` | `Node`, `NodeKind`, `Syntax`, `Token`, `TokenKind`, `TokenRange`, `parse`, `span_of`, `text_of` |
| `knobly.written` | `Copy`, `DirectiveExpansion`, `Document`, `DocumentEdge`, `DocumentGraph`, `ExpandedIndex`, `ExpandedList`, `ExpandedSlice`, `ExpandedString`, `ExpandedValue`, `ExpandedWord`, `Expansion`, `Extension`, `ExtensionLine`, `ExtensionUse`, `IndexValue`, `OverrideVariable`, `Parameter`, `Processor`, `ReferenceResolution`, `Resolution`, `SetLine`, `SetVariable`, `SliceValue`, `SnippetLine`, `Statement`, `StatementKind`, `UnreadableExpansion`, `UnreadableLine`, `UnreadableReason`, `UseLine`, `ValueKind`, `Variable`, `VariableKind`, `WrittenBlock`, `WrittenDirective`, `WrittenValue`, `format_diagnostic` |

Removed from Python: `ValueRef` (internal, leaked).

TypeScript, in `knobly/browser`: `IFetchWriterOptions` → `FetchWriterOptions`. Unchanged paths:
`knobly/include` (`include`), `knobly/node` (`fileSource`, `fileWriter`), `knobly/browser`
(`fetchSource`, `fetchWriter`); Python `knobly.files`, `knobly.include`.

**New public names** (both bindings unless marked): the rules module (`knobly/syntax` `MAX_NESTING`;
`knobly/written` `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `VARIABLE_NAME`; `knobly`
`PROGRAM_CODE`); `ExpansionBlock` (written), `RenderedBlock` (rendered); Python `ProgramCode` (a `str` alias, root).
Each TypeScript kind list name is now a value too (`StatementKind.Set`), and so is `WalkControl`.

**Member and type changes:**

1. A written block has no `statements`: iterate it (`for (const s of block)`, `[...block]`; Python unchanged:
   `for s in block`), index it (`block.at(i)` / `block[i]`), count it (`block.length` / `len(block)`).
2. `walk` leaves the render and the directive: `rendered.walk(v)` → `rendered.block.walk(v)`, `directive.walk(v)` →
   `directive.block?.walk(v)` (Python `rendered.block.walk(descend=...)`, `directive.block.walk(...)` when the block
   is not `None`). Every block walks; a written block's `walk` is new.
3. `rendered.block`, `directive.block`, `expansion.block` and a directive expansion's `block` are blocks, not arrays
   or tuples: TypeScript loses array methods there (`[...rendered.block].filter(...)`, or `directives(name)`); gains
   `at`, `directives(name)`, `walk`. Python keeps every `Sequence` read and gains `directives(name)` and `walk`.
4. TypeScript `SliceValue`'s `start` and `end` are `number | undefined` members, always present (were optional).
5. TypeScript kind lists are values as well as types: `StatementKind.Set`, `TokenKind.WORD`, `WalkControl.Skip`.
   Comparing with `"set"` still compiles and narrows for programs; inside the bindings the lint refuses it.
6. TypeScript `ValueRef`, `IStatementBase`, `IValueBase`, `IVariableBase`, `IExpandedValueBase` are no longer
   exported; Python `ValueRef` likewise.
7. Python's root `knobly` exports only the shared and io names (34 names; was 92): `from knobly import
   render` becomes `from knobly.rendered import render` (or `from knobly import rendered`, then
   `rendered.render`), and so on per the table.
8. Python records generated as dataclasses: a snapshot (`Copy`, `DocumentEdge`, `Resolution`,
   `ReferenceResolution`, `Expansion`, `DirectiveExpansion`, `UnreadableExpansion`) compares by identity
   (`eq=False`); a record (`SourcePosition`, `SourceSpan`, `Origin`, `DirectiveOrigin`, `Token`, `Node`, `Syntax`,
   `TokenRange`, `LoadContext`, `FileWrite`, `ExtensionUse`, `SliceValue`, `IndexValue`, `AddressStep`, `Added`,
   `Removed`, `Changed`, `Unknown`) by its fields. A hand-written class that differed from this is a lane erratum.
9. The diagnostic code table's meanings and "found by" entries changed where spec 2.4 and the schema disagreed
   (errata); no code, name, message or reason changed.

**Unchanged:** every behaviour the shared cases check (all 375 pass before this commit's generated output and with
it), every diagnostic code, name and message, every error class name and tree, every member name except
`statements` and the two `walk`s above, `knobly(...)` and `Processor(...)`.

## 4. Costs, and what this leaves

- Until both lanes land, the two name tests are red (section 1) and the hand-written declarations and the generated
  ones coexist (the generated ones are not yet imported by anything).
- A public signature now changes in `spec/schema/api.json` first; a lane that needs a member the schema lacks
  stops and asks, as for any API change.
- The Python Protocols take parameters positional-only: an implementation may accept more, never less.
- The generated TypeScript interfaces repeat each union's members on every variant (flat, by design: no `*Base`
  names to export).
- The driver still checks dumps only as far as it reads them; the generated shapes move that check into each
  adapter's compiler (spec/conformance.md 7).
- Deferred: the owner's question kno-umh.15 (`:` as a word's first character), the high level (kno-xlo), a
  syntax-layer block view, and generators for `walk` in TypeScript (spec 7.5, still proposed).
