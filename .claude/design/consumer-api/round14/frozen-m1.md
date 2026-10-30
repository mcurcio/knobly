# Milestone 1, frozen for the binding lanes (bead vil-fy4)

This page is what the TypeScript lane (`ts/`) and the Python lane (`py/`) build in milestone 1. It
is frozen: a lane that finds it wrong reports the finding (append to `.claude/errata.md`) and does
not diverge silently. The rules themselves live in `spec/` (canonical); this page is the exact
old-to-new list, the signatures, and the per-binding mechanics. Where this page and `spec/` differ,
`spec/` wins and the difference is an erratum.

Scope: round 13 root cause 1 (one word per concept), root cause 2 (where each operation lives) and
the schema and generator half of root cause 5. Root causes 3 (types carry the kinds) and 4 (the
contract at the edges), the new corpora and the shared conformance driver are later milestones:
everything marked "Proposed (pending owner)" in `spec/` stays out.

## The owner's answers this rests on

Round 13 gate page, 2026-10-29 (the dates are as the gate page records them):

1. **Where `render` lives.** He first picked "B graph.render()", then clarified: "The low level
   shouldn't "depend on" the middle layer — they should have different domain objects. The middle
   layer of objects can build on the lower layer domains". So: the low level never imports, names
   or returns anything from the rendered layer and has no render method; the rendered layer has its
   own types and builds on the low level through `render(graph)`. Everything else in root cause 2
   stays: the processor only loads; `read()` and `save(writer)` are graph methods; `diff` is a
   method on a render; the run-time ownership check (round 12 D27) is retired; the graph keeps its
   injected document source (the core still does no I/O).
2. **The word for values a program passes in:** "A overrides".
3. **Values going in:** "A Keep text only, make misuse impossible", and "Can "set_values" become
   simply "set"?". So every edit that takes new values takes villanelle text only, raises a clear
   `TypeError` for anything else, names that parameter `text`, and the edit that replaces values is
   `set(text)` everywhere, with no alias.

Design choices made here, not his words (each revisable): `spec/` is the canonical home (resting on
his 2026-10-27 "Within villanelle I want the spec to win over a reference language"); the new word
`expanded value` (below); where the generated lists go and that the public-name check fails the
build (spec/codegen.md); the case names renamed in `conformance/`.

## 1. Rename table: every public symbol touched

No aliases, no deprecated exports, no shims: each old name simply goes (global rule, "No backwards
compatibility"). "same" means the name does not change.

### Processor, graph, documents, I/O

| Old TypeScript | Old Python | New TypeScript | New Python |
|---|---|---|---|
| `ILoadOptions.variables` | `Processor.load(..., variables=)` | `ILoadOptions.overrides` | `Processor.load(..., overrides=)` |
| `IProcessor.read(graph)` | `Processor.read(graph)` | `IDocumentGraph.read()` | `DocumentGraph.read()` |
| `IProcessor.render(graph)` | `Processor.render(graph)` | `render(graph)`, exported from `ts/src/rendered/` and re-exported by `"villanelle"` | `villanelle.rendered.render(graph)`, re-exported as `villanelle.render` |
| `IProcessor.diff(before, after, options?)` | `Processor.diff(before, after, key=)` | `IRendered.diff(after, options?)` | `Rendered.diff(after, key=)` |
| `save(graph, writer)` (free function) | `save(graph, writer)` (free function) | `IDocumentGraph.save(writer)` | `DocumentGraph.save(writer)` |
| `IDocumentGraph.handed` | `DocumentGraph.handed` | `IDocumentGraph.overrides` | `DocumentGraph.overrides` |
| `IDocumentGraph.setHanded(name, text)` | `DocumentGraph.set_handed(name, text)` | `IDocumentGraph.setOverride(name, text)` | `DocumentGraph.set_override(name, text)` |
| `IDocumentGraph.diagnostics()` (method) | `DocumentGraph.diagnostics()` (method) | `IDocumentGraph.diagnostics` (property) | `DocumentGraph.diagnostics` (property) |
| `IDocument.source` | `Document.source` | `IDocument.savedText` | `Document.saved_text` |
| `IDocument.body` | `Document.body` | `IDocument.block` | `Document.block` |
| `IFileWrite.source` | `FileWrite.source` | `IFileWrite.savedText` | `FileWrite.saved_text` |
| `IExtensionUse.args` (`readonly IArgument[]`) | `ExtensionUse.args` (`tuple[Argument, ...]`) | `IExtensionUse.values` (`readonly IExpandedValue[]`) | `ExtensionUse.values` (`tuple[ExpandedValue, ...]`) |

### Statements, values, variables

| Old TypeScript | Old Python | New TypeScript | New Python |
|---|---|---|---|
| `IWrittenDirective.setValues(text)` | `WrittenDirective.set_values(text)` | `IWrittenDirective.set(text)` | `WrittenDirective.set(text)` |
| `ISetLine.setValues(text)` | `SetLine.set_values(text)` | `ISetLine.set(text)` | `SetLine.set(text)` |
| `IUseLine.setValues(text)` | `UseLine.set_values(text)` | `IUseLine.set(text)` | `UseLine.set(text)` |
| `IVariable.setValues(text)` | `Variable.set_values(text)` | `IVariable.set(text)` | `Variable.set(text)` |
| `IVariable.kind` value `"handed"` | `Variable.kind` value `"handed"` | `"override"` | `"override"` |
| `IVariable.reaches()` | `Variable.reaches()` | `IVariable.wins()` | `Variable.wins()` |
| `IVariable.overridden()` | `Variable.overridden()` | `IVariable.shadowedAt()` | `Variable.shadowed_at()` |
| `IResolution.overridden` | `Resolution.overridden` | `IResolution.shadowed` | `Resolution.shadowed` |

### Shared records

| Old TypeScript | Old Python | New TypeScript | New Python |
|---|---|---|---|
| `IHanded` (`kind: "handed"`, `variable`) | `Handed` (`variable`) | `IOverride` (`kind: "override"`, `variable`) | `Override` (`variable`; no `kind` yet: root cause 3) |
| `IOrigin.written` | `Origin.written` | `IOrigin.place` | `Origin.place` |
| `IDirectiveOrigin.written` | `DirectiveOrigin.written` | `IDirectiveOrigin.place` | `DirectiveOrigin.place` |
| `IStep.at` | `Step.at` | `IStep.place` | `Step.place` |
| `ILocatedDiagnostic.at` | `LocatedDiagnostic.at` | `ILocatedDiagnostic.place` | `LocatedDiagnostic.place` |
| (none) | (none) | `IExpandedValue` (new) | `ExpandedValue` (new) |
| `ValueKind` without `Reference` | `ValueKind` without `REFERENCE` | `ValueKind` with `Reference: "reference"` (generated from the one `value kind` list); an expanded value's `kind` is `Exclude<ValueKind, "reference">` | `ValueKind` with `REFERENCE`; an expanded value's `kind` is never it |
| `UnreadableKind` | `UnreadableKind` | `UnreadableReason` | `UnreadableReason` |

### Rendered tree

| Old TypeScript | Old Python | New TypeScript | New Python |
|---|---|---|---|
| `IRendered.body` | `Rendered.body` | `IRendered.block` | `Rendered.block` |
| `IDirective.args` | `Directive.args` | `IDirective.values` | `Directive.values` |
| `IDirective.body` | `Directive.body` | `IDirective.block` | `Directive.block` |
| (match args) | `Directive.__match_args__ = ("name", "args", "body")` | | `("name", "values", "block")` |
| `IArgument.written` (end of the chain) | `Argument.written` (end of the chain) | `IArgument.definition` | `Argument.definition` |
| (none) | (none) | `IArgument.written` (new meaning: the value on the same line, never absent) | `Argument.written` (same) |
| `IArgument.resolutions` | `Argument.resolutions` | `IArgument.chain` | `Argument.chain` |
| `IArgument` (stand-alone) | `Argument` (stand-alone) | `interface IArgument extends IExpandedValue` | `class Argument(ExpandedValue)` |
| `IUnreadable.kind` (the reason) | `Unreadable.kind` | `IUnreadable.reason` | `Unreadable.reason` |
| (method already) | `walk(node, descend=)` (free function) | same (`walk(visit)` on `IRendered` and `IDirective`) | `Rendered.walk(*, descend=)`, `Directive.walk(*, descend=)` |

### Modules

| Old TypeScript | Old Python | New TypeScript | New Python |
|---|---|---|---|
| `ts/src/load/` (rendered tree, processor and shared pieces mixed) | `villanelle.processor`, `villanelle.directives`, `villanelle._render` | `ts/src/rendered/` (rendered), `ts/src/written/processor.ts` (processor), shared modules in `ts/src/` (below) | `villanelle.rendered` (package: rendered), `villanelle.written.processor` (processor), shared modules in `villanelle/` |

The package entry points do not change: TypeScript keeps `"villanelle"`, `"villanelle/include"`,
`"villanelle/node"` and `"villanelle/browser"`, and `"villanelle"` re-exports every public name it
does today under its new name, plus `render` and `IExpandedValue`. Python's `villanelle` keeps
re-exporting everything, plus `render`, `ExpandedValue`, `Override` and `UnreadableReason`; the
old module paths `villanelle.processor` and `villanelle.directives` go with no stub module left.

Internal names follow the words too (`HandedVariable` becomes `OverrideVariable`, `handedTexts`
becomes `overrideTexts`, and so on); they are not listed because no program sees them. Comments and
docstrings that say "handed-in" say "override".

Every name in `spec/schema/api.json` is the spec name of one of the above; the public-name check
(section 6) reads it.

## 2. New signatures

### TypeScript

```ts
// ts/src/written/processor.ts (low level)
export function villanelle(options: IProcessorOptions): IProcessor;   // unchanged
export interface IProcessor {
  /** The processor's only operation. */
  load(path: string, options?: ILoadOptions): Promise<IDocumentGraph>;
}
export interface ILoadOptions {
  /** By name without `$`, each villanelle text; checked one by one, in order, with the check of an override. */
  readonly overrides?: Readonly<Record<string, string>>;
}

// ts/src/written/model.ts (low level)
export interface IDocumentGraph {
  readonly root: IDocument;
  readonly documents: ReadonlyMap<string, IDocument>;
  readonly overrides: ReadonlyMap<string, string>;
  readonly diagnostics: readonly ILocatedDiagnostic[];
  setOverride(name: string, text: string | undefined): void;
  read(): Promise<readonly string[]>;                       // the resolved paths this call read, in read order
  save(writer: IDocumentWriter): Promise<readonly string[]>; // the resolved paths handed over; SaveError when the writer rejects
  edges(): readonly IDocumentEdge[];
  unread(): readonly IDocumentEdge[];
  variables(name?: string): readonly IVariable[];
}
// on IWrittenDirective, ISetLine, IUseLine and IVariable:
set(text: string): void;

// ts/src/value.ts (shared)
export interface IExpandedValue {
  readonly kind: Exclude<ValueKind, "reference">;
  readonly text: string;
  readonly origin: IOrigin;
  word(): string;
  string(): string;
  number(): number;
  integer(): number;
  boolean(): boolean;
  items(): readonly IExpandedValue[];
  slice(): ISliceValue | IIndexValue;
  plain(): PlainValue;
  error(message: string, code: ProgramCode): DiagnosticError;
}

// ts/src/extension.ts (shared)
export interface IExtensionUse {
  readonly values: readonly IExpandedValue[];
  readonly origin: IDirectiveOrigin;
}

// ts/src/rendered/ (rendered)
export function render(graph: IDocumentGraph): IRendered;
export interface IArgument extends IExpandedValue {
  readonly written: WrittenValue;               // the same line; never absent
  readonly definition: WrittenValue | undefined; // the end of the chain; undefined for an override
  readonly chain: readonly IReferenceResolution[];
  items(): readonly IArgument[];
}
export interface IRendered {
  readonly block: readonly IDirective[];
  // unreadable, origin, diagnostics, graph, walk, error, addresses: as today
  diff(after: IRendered, options?: IKeyOptions): readonly Change[];
}
```

### Python

```python
# villanelle/written/processor.py (low level)
class Processor:
    def __init__(self, *, source: DocumentSource, extensions: Sequence[Extension] = ()) -> None: ...  # unchanged
    def load(self, path: str, *, overrides: Mapping[str, str] | None = None) -> DocumentGraph: ...

# villanelle/written/model.py (low level)
class DocumentGraph:
    @property
    def overrides(self) -> Mapping[str, str]: ...          # read-only view, in order
    @property
    def diagnostics(self) -> tuple[LocatedDiagnostic, ...]: ...
    def set_override(self, name: str, text: str | None, /) -> None: ...
    def read(self) -> list[str]: ...
    def save(self, writer: DocumentWriter, /) -> list[str]: ...
    # root, documents, edges(), unread(), variables(name=None): as today

# on WrittenDirective, SetLine, UseLine and Variable:
    def set(self, text: str, /) -> None: ...

# villanelle/value.py (shared)
class ExpandedValue:
    __match_args__ = ("kind", "text")
    kind: ValueKind        # never REFERENCE
    text: str
    origin: Origin
    def as_word(self) -> str: ...
    def as_str(self) -> str: ...
    def as_number(self) -> int | float: ...
    def as_int(self) -> int: ...
    def as_bool(self) -> bool: ...
    def as_list(self) -> tuple[ExpandedValue, ...]: ...
    def as_slice(self) -> SliceValue | IndexValue: ...
    def plain(self) -> PlainValue: ...
    def error(self, message: str, *, code: str) -> DiagnosticError: ...

# villanelle/extension.py (shared)
@dataclass(frozen=True, slots=True)
class ExtensionUse:
    values: tuple[ExpandedValue, ...]
    origin: DirectiveOrigin

# villanelle/rendered/ (rendered)
def render(graph: DocumentGraph, /) -> Rendered: ...
class Argument(ExpandedValue):
    written: WrittenValue              # the same line; never None
    definition: WrittenValue | None    # the end of the chain; None for an override
    chain: tuple[ReferenceResolution, ...]
    def as_list(self) -> tuple[Argument, ...]: ...
class Rendered:
    block: tuple[Directive, ...]
    def diff(self, after: Rendered, /, *, key: KeyRule | None = None) -> list[Change]: ...
    def walk(self, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]: ...
class Directive:
    __match_args__ = ("name", "values", "block")
    def walk(self, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]: ...
```

(Python's reader names keep their `as_` prefixes in milestone 1; the binding guide's proposal to keep
`as_` only where a built-in would be shadowed is root cause 4.)

**Python trap with `set`:** inside a class body that defines `def set(...)`, a later annotation
`set[str]` resolves to the method (mypy reports it). Write `builtins.set[str]` there, or
`AbstractSet[str]`.

## 3. Text-only edits and the TypeError

Every member below takes villanelle text, only text. It runs, in this order: the detached check
(spec 2.8: a detached handle raises `DetachedError` before anything else); then the type check of
each text parameter; then everything else. The type check is `typeof value !== "string"` in
TypeScript and `not isinstance(value, str)` in Python, and raises the language's own `TypeError`.

| Member | Parameter checked |
|---|---|
| `set(text)` on a written directive, set line, use line, variable | `text` |
| `replaceWithText(text)` / `replace_with_text(text)` on a statement, a written value, a document | `text` |
| `insertStatements(index, text)` / `insert_statements(index, text)` | `text` |
| `addStatements(text)` / `add_statements(text)` | `text` |
| `setOverride(name, text)` / `set_override(name, text)` | `name` (a misuse error if not letters, digits, `_`, as today), then `text` (`undefined` / `None` allowed: it removes) |
| `rename(name)` on a written directive, a variable | `name` |
| `quote(text)` | `text` |
| `load(path, { overrides })` / `load(path, overrides=...)` | each value, as `overrides["<name>"]` |

The message has one home per binding (one helper) and the exact format is in
`spec/schema/api.json`, `argument type error message`:

```text
Python:     TypeError: set() argument 'text' must be str, not int; villanelle edits take text: quote() a program string, str() a number
TypeScript: TypeError: set(): argument "text" must be a string, not number; villanelle edits take text: quote() a program string, String() a number
```

`member` is the member as the caller wrote it in that binding (`set`, `replace_with_text`,
`setOverride`, `load`...); `parameter` is `text`, `name`, or `overrides["port"]`. Python's
`stmt.set(2400)` raises it and never fails inside the library (before: `set_values(2400)` crashed
in `written/model.py`). Docs and docstrings call the parameter `text` and show `quote()` beside the
first edit they teach. Each binding tests one member of each row with a number and with `null` /
`None` (and TypeScript with an array), since no conformance case can carry a non-string.

**One check of an override** (answer 2's fix, spec 6.3). Today `load` and `setHanded` check override
text two ways and disagree on `"1;"`: TypeScript `ts/src/written/bind.ts` `readHanded` (accepts it,
throws `TypeError` with no position) against `ts/src/written/graph.ts` `handedValues` (refuses it
with a located `BadTextError`); Python `written/_bind.py` `read_handed` (`ValueError`) against
`written/_graph.py` `set_handed` (`BadTextError`). Milestone 1 keeps one function per binding, in
the low level, used by both `load` and `set override`: name (misuse error), type (`TypeError`
above), then the text as the values of `x <text>` (`BadTextError` located in the text: syntax
diagnostics; else `E2001` at the first token beyond values, at a `$name`, or at 0:0 for none; else
`E4003` or `E4001`). So `load` now raises `BadTextError` for `{ a: "1;" }` (E2001 at 0:1) where it
used to accept it: a behaviour change the owner's answer asks for. The written case `set-override`
covers `set override`; each binding adds its own test for `load` refusing `"1;"` (no load case
format carries a load error).

## 4. Keeping the low level free of the rendered layer

The rule (spec 5, "Layer direction"; binding guide rule 8): nothing outside the rendered layer and
the package entry point imports, names or returns a rendered type, not even in a type-only import.

**Where things move.**

| Concept | TypeScript | Python |
|---|---|---|
| shared: place, override, step, origin | `ts/src/origin.ts` (from `load/origin.ts`) | `villanelle/origin.py` (as today) |
| shared: located diagnostic, program code, the diagnostics sink, locatable | `ts/src/report.ts` (from `load/report.ts`) | `villanelle/report.py` |
| shared: document source, load context, memory source | `ts/src/source.ts` (from `load/source.ts`) | `villanelle/source.py` |
| shared: extension, extension use | `ts/src/extension.ts` (from `load/processor.ts`) | `villanelle/extension.py` (from `processor.py`) |
| shared: value kind, slice and index value, plain value, expanded value and its readers | `ts/src/value.ts` | `villanelle/value.py` |
| shared helpers (anatomy, value decoding, located errors) | `ts/src/anatomy.ts`, `values.ts`, `locate.ts` (from `load/`) | `_anatomy.py`, `_values.py` (as today) |
| generated lists | `ts/src/gen/api/` | `villanelle/_api/` |
| low level, with the processor | `ts/src/written/` (+ `processor.ts`) | `villanelle/written/` (+ `processor.py`) |
| `format diagnostic` (takes a graph) | low level: `ts/src/written/format.ts` or kept in `report.ts` importing only written types | low level, or `report.py` importing `DocumentGraph` under `TYPE_CHECKING` |
| rendered tree: `render`, rendered, directive, argument, unreadable, address, key rule, change, diff | `ts/src/rendered/` (from `load/directive.ts`, `tree.ts`, `render.ts`, `diff.ts`, and `IRendered`, `Change`, `IKeyOptions` from `load/processor.ts`) | `villanelle/rendered/` (from `directives.py`, `_render.py`, and `Rendered`, the change classes from `processor.py`) |
| the include extension | `ts/src/include.ts`: imports `IExpandedValue` and shared helpers only | `villanelle/include.py`: the same |

`ts/src/load/` disappears.

**How the low level gets expanded values without the rendered layer.** Today the binder
(`ts/src/written/bind.ts`, `py/.../written/_bind.py`) builds rendered `Argument` objects and uses
`UnreadableKind`. In milestone 1 it builds shared expanded values (and per-value facts the rendered
layer needs to add `written`, `definition` and `chain`: the reference resolutions it already has),
and its unreadable reasons come from the generated `unreadable reason` list in the shared kinds
module. `render(graph)` in the rendered layer turns those into `Argument`s, `Directive`s and
`Unreadable`s. The rendered layer MAY read the graph's binding results through a package-internal
accessor (so nothing is worked out twice); no low-level module ever calls into it.

**The check, in each binding** (the owner asked for one, in both bindings):

- **TypeScript:** in `ts/eslint.config.js`, a block with ESLint's core `no-restricted-imports`:

  ```js
  {
    files: ["src/**/*.ts"],
    ignores: ["src/rendered/**", "src/index.ts", "src/**/*.test.ts"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [{
        group: ["**/rendered", "**/rendered/**"],
        message: "Only the rendered layer and the package entry import the rendered layer (spec 5, Layer direction).",
      }] }],
    },
  }
  ```

  The core rule reports `import type` and `export ... from` too, so a type name cannot leak. It runs
  in `pnpm lint`, which CI runs. Add one planted check: a test or a lint fixture showing the rule
  fires on `import type { IRendered } from "../rendered/..."` from `src/written/`, so the check is
  known to bite.
- **Python:** `py/tests/test_layers.py`: read every `*.py` under `src/villanelle/` with `ast`
  (`_api/` and `_gen/` included); for every module outside `villanelle/rendered/` and other than
  `villanelle/__init__.py`, fail when it has `import villanelle.rendered[...]`, `from
  villanelle.rendered[...] import ...`, `from villanelle import rendered`, or the relative
  equivalent (resolve `level` against the module's package), `if TYPE_CHECKING:` blocks included.
  Include one planted case (a source string with a forbidden import) to show the test bites. It runs
  in `pytest`, which CI runs.

Both are allow-lists (every module but the rendered ones and the entry point), so an indirect import
through a shared module is caught as well. Prior art is import-linter's layers contract and
eslint-plugin-boundaries; the smaller tools give the same guarantee here with no new dependency.

Costs: Python still loads the rendered package whenever any part of `villanelle` is imported,
because `villanelle/__init__.py` re-exports it; the rule governs what the low level's code depends
on, not import-time loading. The check does not police shared-to-written imports; the module table
above keeps them clean by placement only.

## 5. What is removed

- `IProcessor.read`, `IProcessor.render`, `IProcessor.diff`; `Processor.read`, `Processor.render`,
  `Processor.diff`, `Processor._check`.
- The round 12 ownership check (D27): TypeScript's `graphs` and `renders` `WeakSet`s and `own()` in
  `villanelle()`; Python's `DocumentGraph(..., owner)` parameter and `graph._owner is not self`. No
  "takes only graphs this processor loaded" error remains anywhere.
- The free `save(graph, writer)` in both bindings (and TypeScript's `asSaved` duck-typing helper:
  `save` is a graph method that can reach the document's private setter directly).
- `setHanded` / `set_handed`, `handed`, and every `handed` word in public names.
- `setValues` / `set_values` everywhere.
- Python's free `walk(node, descend=)`.
- The second override check (`readHanded` / `read_handed` or `handedValues` / `set_handed`'s own
  copy: one stays, section 3).
- `UnreadableKind`, the hand-written diagnostic code registries and message tables, and the
  hand-written limit, reserved-name and variable-name constants (replaced by generated modules,
  section 6).
- The low level's imports of `load/tree.js` `Argument`, `load/directive.js` `UnreadableKind`, and
  Python's `villanelle.directives` `Argument` and `UnreadableKind` in `written/_bind.py`.

Kept (later milestones): `NoSetLineError` (root cause 3 deletes it), the `I` prefix on TypeScript
interfaces (binding guide rule 2), factory names such as `createFileSource` and `file_source` (rule 3),
the walk callback in TypeScript (spec 7.5's proposal), `quote` as a free function, `parse`,
`spanOf` / `span_of` and `textOf` / `text_of` as free functions (pure helpers).

## 6. Generated files: where they go, and not committed

**Decision: not committed.** The owner's rule covers it: "Don't commit the generated code, just
the source" (2026-10-23, recorded in `tools/gen.sh` and `AGENTS.md`). The repo's precedent is the
parser: `tools/gen.sh ts|py` writes git-ignored output, every TypeScript package script (`build`,
`test`, `typecheck`, `lint`) and `py/tests/conftest.py` run it first, and CI builds from a clean
checkout that way. The lists follow the same path, so a stale copy cannot exist and no freshness
check is needed. (Committing with a `tools/check.sh` freshness check would also work, but it would
go against his stated rule for no gain.)

- **Generator:** one script, Python 3 standard library only (CI's runners and the owner's Mac have
  it), reading `spec/schema/api.json` and `spec/schema/diagnostics.json`, called by `tools/gen.sh`
  after the parser for the requested target.
- **TypeScript output:** `ts/src/gen/api/codes.ts` (`DiagnosticCode` constant object and type,
  `MESSAGES`), `kinds.ts` (constant object and type for node kind, value kind, step kind,
  unreadable reason, change kind; union types for statement kind, variable kind, place kind),
  `limits.ts` (`MAX_NESTING`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `RESERVED`, `VARIABLE_NAME`). Under
  `src/gen/`, already ignored by git and ESLint, still typechecked (no `@ts-nocheck`).
- **Python output:** `py/src/villanelle/_api/codes.py`, `kinds.py` (`StrEnum`s; `Literal` aliases for
  the three inline lists), `limits.py`. A new folder, not `_gen/`, because mypy skips
  `villanelle._gen` (`follow_imports = "skip"`) and would see the enums as `Any`. Add `_api/` to
  `py/.gitignore` and to both hatchling `artifacts` lists (as `_gen/`), and keep ruff and mypy
  checking it (the generator emits clean code).
- The binding's public `DiagnosticCode` stays where users import it today (re-exported from the
  generated module). Messages keep `{nesting depth}` filled from the limit.
- **Public-name check** (both bindings, reads `spec/schema/api.json` directly): every member the
  schema lists for a concept exists on a real object of that concept's type under the binding's
  casing or the member's `spell`, as a property or a method as the schema says; it fails the
  build. TypeScript makes the objects from a loaded memory-source graph and its render (interfaces
  do not exist at run time); Python checks the classes. The reverse direction (a public name the
  schema lacks) is a later milestone.

Lane ownership: `tools/gen.sh` and the generator script are shared; the TypeScript lane writes the
generator and the TypeScript output, the Python lane adds the Python output to the same script (or
one lane writes both; they must not fork it). CI (`.github/workflows/ci.yml`) needs no change: each
job already runs `tools/gen.sh` through the package scripts.

## 7. Conformance: what changed, and which runner code follows

Changed in this commit (data and format pages; expected outputs changed only where a renamed token
is printed):

- `conformance/written/cases.json`: op `"setValues"` is now `"set"`; op `"setHanded"` is now
  `"setOverride"`; the target `["handed", name]` is now `["override", name]`; the needs token
  `"handed"` is now `"override"`; the case key `"variables"` is now `"overrides"`.
- `conformance/load/cases.json`: the case key `"variables"` is now `"overrides"`.
- Printed tokens in `conformance/*/expected/`: an origin or variable text `handed <name>` is now
  `override <name>`, and the variable text `"handed"` is now `"override"` (9 files).
- Case names, with their expected files renamed: `set-values-bad` to `set-bad`,
  `directive-set-values` to `directive-set`, `use-set-values` to `use-set`, `handed-no-set-line` to
  `override-no-set-line`, `set-handed` to `set-override`, `set-handed-bad-bound` to
  `set-override-bad-bound`, `overridden-next-first` to `shadowed-next-first`,
  `load-var-handed-wins` to `load-var-override-wins`, `load-snippet-param-beats-handed` to
  `load-snippet-param-beats-override`.
- `conformance/written/format.md` and `conformance/load/format.md` describe the new names: the
  `["render"]` step prints each argument's `definition` (it printed the old `written`, which meant
  the same thing, so no expected file changed for it) and walks its `chain`; `["rendered", ...]`
  targets reach `values[arg].chain[step]`; `["texts"]` compares with `saved text`; `["save"]` calls
  the graph's `save (writer)`; the load format's second render is compared with `first.diff(second)`
  and its unreadable column is the `reason`.

Runner code that must follow (owned by the lanes):

- TypeScript `ts/src/written-conformance.test.ts`: the needs list (`"override"` for `"handed"`),
  the `override` target, the `set` and `setOverride` ops, `c.overrides` into
  `load(root, { overrides })`, variable text `override <name>` / `"override"`, and the new members
  (`graph.save(writer)`, `graph.diagnostics`, `wins()`, `shadowedAt()`, `shadowed`, `savedText`,
  `block`, `render(graph)`, `definition`, `chain`).
- TypeScript `ts/src/load-conformance.test.ts`: `c.overrides`, `render(graph)`,
  `first.diff(second, { key })`, `override <name>` in origin texts, `place` for `written` / `at`,
  `reason`.
- Python `py/tests/test_written_conformance.py` and `py/tests/test_load_conformance.py`: the same.

## 8. Not in this milestone, and follow-ups

- The reference pages `docs/low-level-api.md` and `docs/rendered-tree.md` still teach the old names
  (each now says so at the top), as do `ts/README.md` and `py/README.md`. Each lane updates its
  README; the two docs pages are rewritten in one docs pass after both lanes land, since they show
  both languages side by side.
- Everything marked "Proposed (pending owner)" in `spec/`: kinds that narrow types (root cause 3),
  the edge contract (root cause 4: positions per language, numbers, error base classes, memory
  writer, adapter names), the walk generator in TypeScript, `MutableMapping` overrides in Python,
  dropping the `I` prefix, the new corpora and the shared driver.
- No plural `setOverrides`: one setter, one override per call (a loop sets several).

## 9. How each lane proves it is done

1. Its package's checks pass (TypeScript: `corepack pnpm test`, `typecheck`, `lint`, `build`;
   Python: `uv run --locked pytest`, `ruff check`, `ruff format --check`, `mypy`), with every
   conformance case passing byte for byte and none skipped.
2. The layer check fails on a planted forbidden import and passes on the tree.
3. The public-name check passes against `spec/schema/api.json`.
4. No old name from section 1 remains in the package's public surface, docstrings or tests
   (`grep -rn` for `handed`, `setValues`, `set_values`, `reaches`, `overridden`, `UnreadableKind`,
   `.args`, `.body` comes back empty but for prose that explains the rename).
5. The TypeError tests of section 3 pass.
