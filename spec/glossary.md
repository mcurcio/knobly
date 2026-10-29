# Glossary

One word per concept, one meaning per word, the same in every layer and every binding. A binding
changes only the casing of a word (`camelCase` members and `PascalCase` types in TypeScript,
`snake_case` members and `PascalCase` types in Python); everything else about a name is a defect
unless [binding-guide.md](binding-guide.md) section 3 lists it as an allowed difference.

This page holds the words. What each concept does is in [spec.md](spec.md); the machine-readable
list of concepts and members is [schema/api.json](schema/api.json), which wins where the two differ.

Where the words come from:
- The round 13 review's glossary ([review.md, root cause 1](../.claude/design/consumer-api/round13/review.md#root-cause-1-no-shared-glossary-so-each-layer-named-things-on-its-own)),
  adopted by milestone 1 (bead vil-fy4). These are design choices, not the owner's words.
- The owner's answers on the round 13 gate page, 2026-10-29: on where `render` lives, first "B
  graph.render()", then "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"; "A overrides" (the word for values a program
  passes in); "A Keep text only, make misuse impossible" (values going in); and "Can "set_values"
  become simply "set"?" (the edit that replaces values).
- Milestone 2 (beads vil-0vz, vil-9fy, vil-5ya, vil-gxu): the round 13 review's root causes 3 and 4, and the
  owner's "Yes" of 2026-10-29 to the rendered layer building only on the low level's public objects. The new words
  below are design choices, not his words.

## Rules

- **One word, one meaning.** A word below means only what its row says, in every layer.
- **Properties and methods.** A fact the object holds, or can work out cheaply on its own, is a
  property. Anything worked out across the whole graph, that can fail, or that takes arguments, is
  a method. The same concept is the same kind of member in every layer. (Exception, from the review's
  own example: `diagnostics` is a property on the graph as on the render, so that
  `graph.diagnostics.length > 0` means what it says; errata, 2026-10-29.)
- **Where an operation lives** ([spec.md 6.2](spec.md#62-processor)): the processor only loads;
  every later operation is a method on the object the program holds, within its layer; going up a
  layer is the upper layer's free function, `render (graph)`.
- **Layer direction** (owner, 2026-10-29: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains"): each layer has its own types. A lower layer never
  imports, names or returns an upper layer's type; an upper layer's type may build on a lower one's
  (an `argument` builds on an `expanded value`).
- **Kind values** are lowercase words (`"set"`, `"override"`), the same strings in every binding (token kinds,
  the grammar's names, aside).
- **Variants** (spec 2.10): a kind list whose members differ in shape gives one type per member; its spec name is
  the kind word when that is unambiguous in its layer (`word`, `added`), else the kind word plus the concept
  (`set variable`, `extension line`, `expanded list`, `list argument`). The union keeps the concept's word
  (`statement`, `variable`, `expanded value`, `argument`, `change`).

## The words

Only the words that a reader could confuse, or that milestone 1 changed. Each spec name is written
in lowercase words; the TypeScript and Python spellings follow from the casing rule.

| Word | Means | Replaces (before milestone 1) |
|---|---|---|
| `block` | the statements inside `{ }`, and a file's top level, in every layer. The word is shared; the shape is not: the low level's `written block` is an object (`statements`, `directives (name)`, `insert statements`, `add statements`), while a rendered `block` is a plain read-only sequence of directives (filter it by `name`, or `walk`) | `body` (document, rendered directive, rendered tree) |
| `values` | a line's values, in every layer | `args` (rendered directive, extension use) |
| `written` | the low-level handle behind a rendered thing, on **the same line**: a rendered directive's line, an unreadable statement, a rendered value's same-line value (the `$name` it came through, or the value itself) | a rendered value's `written`, which used to be the end of its chain |
| `definition` | the written value at the end of a variable chain (the value in the `set` line) | the old rendered value `written` |
| `chain` | a rendered value's steps along its variable chain, as reference resolutions, its own line first | the rendered value's `resolutions` |
| `resolutions ()` | on a written reference: one resolution per copy of its statement | (kept; now its only meaning) |
| `place` | a file and a span; also the field that says where text was written or a step happened (`origin.place`, `step.place`, `located diagnostic.place`). An origin's `place` may be an `override` instead of a file place | `origin.written`, `step.at`, `located diagnostic.at` |
| `place kind` | the closed list `file`, `override` | (new list; the values existed) |
| `via` | how text got here: the steps, innermost first | (unchanged) |
| `source` | the document source: the reader port a program injects | (kept; no longer also the saved text) |
| `saved text` | a document's text as last read or saved, and a file write's copy of it | `document.source`, `file write.source` |
| `override` | a value the program passes in at load, by variable name (owner: "A overrides"); also the variable kind and the place kind of such a value, and the type of an origin's place when the text came from one | `variables` (load option), `handed` (graph property, variable kind, origin kind, `set handed`) |
| `overrides` | the load option, and the graph's ordered map from name to text | `variables` (load option), `graph.handed` |
| `set override` | add, change or remove one override on a loaded graph | `set handed` |
| `winner` | in a resolution: the definition that wins | (kept) |
| `shadowed` | in a resolution: every other definition visible there, next first | a resolution's `overridden` |
| `wins ()` | a variable's resolutions where it wins | `reaches ()` |
| `shadowed at ()` | a variable's resolutions where another variable wins | `overridden ()` |
| `reason` | why a rendered statement could not be read; its list is `unreadable reason` | the rendered unreadable's `kind`, and the `unreadable kind` list |
| `kind` | which variant of a closed list a thing is, and nothing else | (`kind` no longer holds a reason) |
| `diagnostics` | the located problems, a property on the graph and on the render | `graph.diagnostics ()` (a method) |
| `text` | the parameter of every member that takes new villanelle text | (mixed parameter names) |
| `set (text)` | replace a statement's or a variable's values with `text` (owner: "Can "set_values" become simply "set"?"). Not the language's `set` keyword: it never makes a `set` line | `set values (text)` |
| `expanded value` | one value after expansion, with its readers: what an extension use holds and what a rendered argument builds on | the rendered `argument`, which an extension use used to hold |
| `render (graph)` | the rendered layer's free function that makes a graph's rendered tree; the low level has no render member | `processor.render (graph)` |
| `read ()` | the graph's method that reads what `unread ()` names | `processor.read (graph)` |
| `save (writer)` | the graph's method that hands changed documents to a writer | the free function `save (graph, writer)` |
| `diff (after, key?)` | a render's method comparing it (the before) with another render | `processor.diff (before, after, key?)` |

The words milestone 2 adds or changes (new terms, each a design choice; their definitions and reasons are in the
table at the end):

| Word | Means | Replaces (before milestone 2) |
|---|---|---|
| `extension line` | a statement whose name an extension owns (an include line): kind `extension`, its own type | a `written directive` of kind `extension` |
| `set variable`, `parameter`, `override variable` | the three variable types, one per `variable kind` | `variable`, one type for all three |
| `expanded word` ... `expanded index` | the five expanded value types, one per value kind but `reference` | `expanded value`, one type |
| `word argument` ... `index argument` | the five rendered value types, each building on the expanded type of its kind | `argument`, one type |
| `list ()` | the reader that asks for a list (every value variant; E4002 otherwise) | the reader `items ()` |
| `items` | a list's items, a property of the list variants in every layer (written `list`, `expanded list`, `list argument`) | `items ()` on a rendered value |
| `expand ()`, `expansion` | the graph's method, and the snapshot it returns: every copy as read, values expanded and linked, what `render (graph)` builds on (spec 6.10) | the package-internal binding render used to read |
| `directive expansion`, `unreadable expansion`, `value expansion` | the parts of an expansion: a directive copy, a copy that could not be read, one expanded value with its links | (internal: TypeScript `BoundItem`, `Bound`; Python `BoundItem`, `BoundValue`) |
| `insert before (text)`, `insert after (text)` | insert statements next to this statement in its block | `insert statements (index, text)` with a worked-out index |
| `people form` | the text a person reads, a binding's to-text conversion: an address's, and now a place's, an override's, a step's and a diagnostic's (contract 2) | (an address's only) |
| `villanelle error` | the base class of every error class the package defines (contract 4) | (none) |
| `memory writer`, `file writer` | the writers named after their medium and port (contract 5) | (no memory writer); `fs writer` |

Words a program might expect but villanelle does not use: `handed` (now `override`), `args`,
`body`, `reaches`, `overridden` (as a member name), `set values` (now `set`), `no set line error` (gone),
`items ()` (now `list ()`), `as_int` and the other `as_` readers (now the spec words), `fs writer` (now `file
writer`). A new meaning for any word on this page needs
the owner's approval.

## Types per layer and binding

The type names after milestone 2. TypeScript keeps its `I` prefix on interfaces until the owner
answers the binding guide's rule 2 (proposed: drop it, so both bindings spell a type the same way);
unions have no prefix. "Union" means a TypeScript union type, or a Python `X: TypeAlias = A | B | ...` over classes
(so `isinstance(x, X)` works). Every kind list is a TypeScript string-literal type and a Python `StrEnum` of the
same name (spec 2.10).

### Shared

| Spec name | TypeScript | Python |
|---|---|---|
| `source position` | `ISourcePosition` | `SourcePosition` |
| `source span` | `ISourceSpan` | `SourceSpan` |
| `place` (kind `file`) | `IPlace` | `Place` |
| `override` (kind `override`, as an origin's place) | `IOverride` | `Override` |
| `place kind` | `PlaceKind` | `PlaceKind` |
| `step`, `step kind` | `IStep`, `StepKind` | `Step`, `StepKind` |
| `origin` | `IOrigin` | `Origin` |
| `directive origin` | `IDirectiveOrigin` | `DirectiveOrigin` |
| `diagnostic` | `IDiagnostic` | `Diagnostic` |
| `located diagnostic` | `ILocatedDiagnostic` | `LocatedDiagnostic` |
| `program code` | `ProgramCode` (a template literal type) | `str` (checked at run time) |
| `diagnostic code` | `DiagnosticCode` (constant object and type) | `DiagnosticCode` (`StrEnum`) |
| `diagnostics` (the sink) | `Diagnostics` | `Diagnostics` |
| `locatable` | `ILocatable` | `Locatable` (`Protocol`) |
| `expanded value` | `ExpandedValue` (union) | `ExpandedValue` (union) |
| `expanded word`, `expanded string`, `expanded list`, `expanded slice`, `expanded index` | `IExpandedWord`, `IExpandedString`, `IExpandedList`, `IExpandedSlice`, `IExpandedIndex` | `ExpandedWord`, `ExpandedString`, `ExpandedList`, `ExpandedSlice`, `ExpandedIndex` |
| `value kind` | `ValueKind` | `ValueKind` |
| `slice value`, `index value` | `ISliceValue`, `IIndexValue` | `SliceValue`, `IndexValue` |
| `plain value` | `PlainValue` | `PlainValue` |
| `quote` (free function: a plain string as villanelle text) | `quote`, in `ts/src/text.ts` | `quote`, in `villanelle/_text.py`, exported from `villanelle` |
| errors (contract 4) | `VillanelleError`, `DiagnosticError`, `ReadError`, `SaveError`, `EditError`, `BadTextError`, `DetachedError` | the same class names |

### Syntax layer

| Spec name | TypeScript | Python |
|---|---|---|
| `syntax` | `ISyntax` | `Syntax` |
| `token` | `IToken` | `Token` |
| `node` | `INode` | `Node` |
| `token range` | `ITokenRange` | `TokenRange` |
| `token kind`, `node kind` | `TokenKind`, `NodeKind` | `TokenKind`, `NodeKind` |

### Ports and extensions

| Spec name | TypeScript | Python |
|---|---|---|
| `document source` | `IDocumentSource` | `DocumentSource` (`Protocol`) |
| `load context` | `ILoadContext` | `LoadContext` |
| `document writer` | `IDocumentWriter` (in `ts/src/source.ts`) | `DocumentWriter` (`Protocol`, in `villanelle/source.py`) |
| `file write` | `IFileWrite` (in `ts/src/source.ts`) | `FileWrite` (in `villanelle/source.py`) |
| `memory source`, `memory writer` | `memorySource`, `memoryWriter` | `memory_source`, `memory_writer` |
| `file source`, `file writer` | `fileSource`, `fileWriter` (`villanelle/node`) | `file_source`, `file_writer` (`villanelle.files`) |
| `fetch source`, `fetch writer` | `fetchSource`, `fetchWriter` (`villanelle/browser`) | none |
| `extension` | `IExtension` | `Extension` (`Protocol`) |
| `extension use` | `IExtensionUse` | `ExtensionUse` |

### Low level (written)

| Spec name | TypeScript | Python |
|---|---|---|
| `processor` | `IProcessor` (made by `villanelle(...)`) | `Processor` |
| load options | `ILoadOptions` (`overrides`) | keyword `overrides=` |
| `document graph` | `IDocumentGraph` | `DocumentGraph` |
| `document` | `IDocument` | `Document` |
| `document edge` | `IDocumentEdge` | `DocumentEdge` |
| `copy` | `ICopy` | `Copy` |
| `statement`, `statement kind` | `Statement` (union), `StatementKind` | `Statement` (union), `StatementKind` |
| `written directive`, `extension line` | `IWrittenDirective`, `IExtensionLine` | `WrittenDirective`, `ExtensionLine` |
| `set line`, `snippet line`, `use line`, `unreadable line` | `ISetLine`, `ISnippetLine`, `IUseLine`, `IUnreadableLine` | `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine` |
| `written block` | `IWrittenBlock` | `WrittenBlock` |
| `written value` | `WrittenValue` (union) | `WrittenValue` (union) |
| `word`, `string`, `list`, `slice`, `index`, `reference` | `IWord`, `IString`, `IList`, `ISlice`, `IIndex`, `IReference` | `Word`, `String`, `List`, `Slice`, `Index`, `Reference`, from `villanelle.written` only |
| `variable`, `variable kind` | `Variable` (union), `VariableKind` | `Variable` (union), `VariableKind` |
| `set variable`, `parameter`, `override variable` | `ISetVariable`, `IParameter`, `IOverrideVariable` | `SetVariable`, `Parameter`, `OverrideVariable` |
| `resolution` | `IResolution<T>` | `Resolution[T]` |
| `reference resolution` | `IReferenceResolution` | `ReferenceResolution` |
| `expansion` | `IExpansion` | `Expansion` |
| `directive expansion`, `unreadable expansion`, `value expansion` | `IDirectiveExpansion`, `IUnreadableExpansion`, `IValueExpansion` | `DirectiveExpansion`, `UnreadableExpansion`, `ValueExpansion` |
| `format diagnostic` (free function; reads the source line from a graph) | `formatDiagnostic`, in `ts/src/written/format.ts` | `format_diagnostic`, in `villanelle/written/format.py` |

The low level's public entry is one module in each binding: `ts/src/written/index.ts` (new) and the package
`villanelle.written` (its `__all__`). The rendered layer imports the low level from there and nowhere else
(binding guide rule 8).

### Rendered tree

| Spec name | TypeScript | Python |
|---|---|---|
| `render (graph)` (entry point) | `render(graph)` in `ts/src/rendered/`, re-exported by `"villanelle"` | `render(graph)` in `villanelle.rendered`, re-exported as `villanelle.render` |
| `rendered` | `IRendered` | `Rendered` |
| `directive` | `IDirective` | `Directive` |
| `argument` | `Argument` (union) | `Argument` (union) |
| `word argument`, `string argument`, `list argument`, `slice argument`, `index argument` | `IWordArgument extends IExpandedWord`, ... `IIndexArgument extends IExpandedIndex` | `WordArgument(ExpandedWord)`, ... `IndexArgument(ExpandedIndex)` |
| `unreadable` | `IUnreadable` | `Unreadable` |
| `unreadable reason` | `UnreadableReason` | `UnreadableReason` (`StrEnum`) |
| `address`, `address step` | `IAddress`, `IAddressStep` | `Address`, `AddressStep` |
| `key rule` | `KeyRule` | `KeyRule` |
| key options | `IKeyOptions` (`key`) | keyword `key=` |
| `change` | `Change` (union of `IAdded`, `IRemoved`, `IChanged`, `IUnknown`) | `Change` (union of `Added`, `Removed`, `Changed`, `Unknown`) |
| `change kind` | `ChangeKind` | `ChangeKind` |

## New terms in milestone 1

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `override` | a value a program passes in at load, by variable name | one word going in and coming out (owner: "A overrides") | `handed`, which it replaces |
| `definition` | the value at the end of a variable chain | `written` now always means the same line | the old rendered `written` |
| `chain` | a rendered value's variable steps, as resolutions | `resolutions` kept one meaning (per copy) | the old rendered `resolutions` |
| `saved text` | the text as last read or saved | `source` names the reader port | `document.source` |
| `shadowed`, `shadowed at ()` | visible but not winning | `overridden` would collide with `override` | `overridden` |
| `wins ()` | resolutions a variable wins | pairs with `shadowed at ()` | `reaches ()` |
| `reason`, `unreadable reason` | why a statement could not be read | `kind` means only the type | `unreadable.kind`, `unreadable kind` |
| `set (text)` | replace a statement's or variable's values | the owner asked for the short name (2026-10-29) | `set values`, which it replaces |
| `expanded value` | one value after expansion, with kind, canonical text, origin and readers; no low-level handle | the low level must not name the rendered `argument` (owner, 2026-10-29), yet an extension reads expanded values | the rendered `argument`, which now builds on it |
| `argument type error` | the error group for an argument of the wrong type (`TypeError` in both bindings) | answer 3: misuse of text-only edits raises a clear `TypeError`, which in Python is not the misuse group's `ValueError` | misuse error |
| `place kind` | the list `file`, `override` | a place says which of the two it is | none (the values existed as `"file"`, `"handed"`) |

## New terms in milestone 2

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `extension line` | a statement whose name an extension owns | include lines get their own type, without `rename` (round 13 root cause 3) | `written directive`, which no longer covers kind `extension` |
| `set variable`, `override variable` | the variable a `set` line declares; an override as a variable | each variable kind is its own type, so `set` exists only where it succeeds | `variable` (now the union); `parameter` keeps its word |
| `expanded word` (and string, list, slice, index) | an expanded value of that kind | each value kind is its own type | `expanded value` (now the union) |
| `word argument` (and string, list, slice, index) | a rendered value of that kind | the same, in the rendered layer | `argument` (now the union) |
| `expansion`, `expand ()` | the graph's public account of every copy as read, and the method that makes it | the rendered layer may use only public low-level members (owner, 2026-10-29, "Yes") | the package-internal binding (not a public term) |
| `directive expansion`, `unreadable expansion`, `value expansion` | an expansion's directive copy, unreadable copy, and value with its links | the same | none public |
| `insert before`, `insert after` | insert statements next to a statement | the review's PostCSS-style edits (root cause 4) | `insert statements` at a worked-out index |
| `villanelle error` | the package's base error class | one class to catch (root cause 4) | none |
| `memory writer` | a writer into the map a memory source reads | every binding ships both ports in memory (root cause 4) | none |
| `list ()` | the reader that asks for a list | `items` became the list variants' property, the same in both layers (vil-gxu) | `items ()` |

## New terms in milestone 3

These are words of the conformance tooling, not of the API: no binding exports them.

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `conformance adapter` | the small program each binding writes that answers the driver's requests through its public API ([conformance.md](conformance.md)); "the adapter" on that page | the review's root cause 5: "a binding writes one small adapter" | the per-binding conformance runner, which it replaces. Not the source and writer adapters of spec 4.3 (memory, file, fetch), which keep the word unqualified |
| `driver` | `conformance/driver/run.py`, the one program that runs every case and compares | the same | the runners |
| `conformance level` (L0 to L4) | how much of the spec a binding claims to meet, cumulative | a binding climbs them in order, and CI checks the claim | the `needs` tokens, which stay as a record |
| `key rule data` | a key rule written as data in `conformance/keys.json` | a case cannot hold a function (root cause 5: "the "rasl" key rule becomes data") | the `"rasl"` rule each runner wrote by hand |
| `dump` | the neutral JSON shape of a binding object the adapter sends | the driver finds targets and compares; the adapter only describes | none |
