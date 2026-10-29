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
- **Kind values** are lowercase words (`"set"`, `"override"`), the same strings in every binding.

## The words

Only the words that a reader could confuse, or that milestone 1 changed. Each spec name is written
in lowercase words; the TypeScript and Python spellings follow from the casing rule.

| Word | Means | Replaces (before milestone 1) |
|---|---|---|
| `block` | the statements inside `{ }`, and a file's top level, in every layer | `body` (document, rendered directive, rendered tree) |
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

Words a program might expect but villanelle does not use: `handed` (now `override`), `args`,
`body`, `reaches`, `overridden` (as a member name), `set values` (now `set`). A new meaning for any word on this page needs
the owner's approval.

## Types per layer and binding

The type names after milestone 1. TypeScript keeps its `I` prefix on interfaces until the owner
answers the binding guide's rule 2 (proposed: drop it, so both bindings spell a type the same way);
that rename is not part of milestone 1. "Union" means a TypeScript union type or a Python
`TypeAlias` over classes.

### Shared

| Spec name | TypeScript | Python |
|---|---|---|
| `source position` | `ISourcePosition` | `SourcePosition` |
| `source span` | `ISourceSpan` | `SourceSpan` |
| `place` (kind `file`) | `IPlace` | `Place` (no `kind` field yet: root cause 3) |
| `override` (kind `override`, as an origin's place) | `IOverride` | `Override` |
| `step` | `IStep` | `Step` |
| `origin` | `IOrigin` | `Origin` |
| `directive origin` | `IDirectiveOrigin` | `DirectiveOrigin` |
| `diagnostic` | `IDiagnostic` | `Diagnostic` |
| `located diagnostic` | `ILocatedDiagnostic` | `LocatedDiagnostic` |
| `program code` | `ProgramCode` (a template literal type) | `str` (checked at run time) |
| `diagnostic code` | `DiagnosticCode` (constant object and type) | `DiagnosticCode` (`StrEnum`) |
| `diagnostics` (the sink) | `Diagnostics` | `Diagnostics` |
| `locatable` | `ILocatable` | `Locatable` (`Protocol`) |
| `expanded value` | `IExpandedValue` | `ExpandedValue` |
| `slice value`, `index value` | `ISliceValue`, `IIndexValue` | `SliceValue`, `IndexValue` |
| `plain value` | `PlainValue` | `PlainValue` |
| errors | `DiagnosticError`, `ReadError`, `EditError`, `BadTextError`, `DetachedError`, `NoSetLineError`, `SaveError` | the same class names |

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
| `document writer` | `IDocumentWriter` | `DocumentWriter` (`Protocol`) |
| `file write` | `IFileWrite` | `FileWrite` |
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
| `statement` | `Statement` (union) | `Statement` (union) |
| `written directive` | `IWrittenDirective` | `WrittenDirective` |
| `set line`, `snippet line`, `use line`, `unreadable line` | `ISetLine`, `ISnippetLine`, `IUseLine`, `IUnreadableLine` | `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine` |
| `written block` | `IWrittenBlock` | `WrittenBlock` |
| `written value` | `WrittenValue` (union) | `WrittenValue` (union) |
| `word`, `string`, `list`, `slice`, `index`, `reference` | `IWord`, `IString`, `IList`, `ISlice`, `IIndex`, `IReference` | `Word`, `String`, `List`, `Slice`, `Index`, `Reference` |
| `variable` | `IVariable` | `Variable` |
| `resolution` | `IResolution<T>` | `Resolution[T]` |
| `reference resolution` | `IReferenceResolution` | `ReferenceResolution` |

### Rendered tree

| Spec name | TypeScript | Python |
|---|---|---|
| `render (graph)` (entry point) | `render(graph)` in `ts/src/rendered/`, re-exported by `"villanelle"` | `render(graph)` in `villanelle.rendered`, re-exported as `villanelle.render` |
| `rendered` | `IRendered` | `Rendered` |
| `directive` | `IDirective` | `Directive` |
| `argument` (builds on `expanded value`) | `IArgument extends IExpandedValue` | `Argument(ExpandedValue)` |
| `unreadable` | `IUnreadable` | `Unreadable` |
| `unreadable reason` | `UnreadableReason` | `UnreadableReason` (`StrEnum`) |
| `address`, `address step` | `IAddress`, `IAddressStep` | `Address`, `AddressStep` |
| `key rule` | `KeyRule` | `KeyRule` |
| key options | `IKeyOptions` (`key`) | keyword `key=` |
| `change` | `Change` (union of `IAdded`, `IRemoved`, `IChanged`, `IUnknown`) | `Change` (union of `Added`, `Removed`, `Changed`, `Unknown`) |
| `change kind` | `ChangeKind` | none yet (classes without `kind`: root cause 3) |
| `value kind`, `step kind` | `ValueKind`, `StepKind` | `ValueKind`, `StepKind` |

The kind lists' current spellings differ between the bindings (constant objects and inline literal
unions in TypeScript; `StrEnum`s, literal strings and classes in Python). [schema/api.json](schema/api.json)
records each one; unifying them is root cause 3, a later milestone.

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
