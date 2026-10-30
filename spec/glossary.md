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
  (a rendered `directive` builds on a `directive expansion` and holds its `expanded value`s).
- **Kind values** are lowercase words (`"set"`, `"override"`), the same strings in every binding (token kinds,
  the grammar's names, aside).
- **Variants** (spec 2.10): a kind list whose members differ in shape gives one type per member; its spec name is
  the kind word when that is unambiguous in its layer (`word`, `added`), else the kind word plus the concept
  (`set variable`, `extension line`, `expanded list`). The union keeps the concept's word
  (`statement`, `variable`, `expanded value`, `change`).

## The words

Only the words that a reader could confuse, or that milestone 1 changed. Each spec name is written
in lowercase words; the TypeScript and Python spellings follow from the casing rule.

| Word | Means | Replaces (before milestone 1) |
|---|---|---|
| `block` | the statements inside `{ }`, and a file's top level, in every layer, with one shape in every layer (spec 2.11): iterated and indexed in order, `directives (name)`, and a depth-first `walk`. The written block holds statements (and adds the edits `insert statements`, `add statements`), the expansion block directive expansions, the rendered block directives | `body` (document, rendered directive, rendered tree) |
| `values` | a line's values, in every layer | `args` (rendered directive, extension use) |
| `written` | the link from an expanded or rendered thing to the low-level handle behind it, on **the same line**: a directive expansion's (and so a rendered directive's) line, an unreadable expansion's statement, an expanded value's same-line value (the `$name` it came through, or the value itself). The one name of that link in every family (milestone 4) | a rendered value's `written`, which used to be the end of its chain; `statement` on a directive or unreadable expansion (before milestone 4) |
| `definition` | the written value at the end of a variable chain (the value in the `set` line) | the old rendered value `written` |
| `chain` | an expanded value's steps along its variable chain, as reference resolutions, its own line first | the rendered value's `resolutions` |
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
| `reason` | why a statement copy could not be read (an unreadable expansion's); its list is `unreadable reason` | the rendered unreadable's `kind`, and the `unreadable kind` list |
| `kind` | which variant of a closed list a thing is, and nothing else | (`kind` no longer holds a reason) |
| `diagnostics` | the located problems, a property on the graph and on the render | `graph.diagnostics ()` (a method) |
| `text` | the parameter of every member that takes new villanelle text (typed `config text` since milestone 5) | (mixed parameter names) |
| `set (text)` | replace a statement's or a variable's values with `text`, or (milestone 5) a written value with one value, keeping its handle (owner: "Can "set_values" become simply "set"?"). Not the language's `@set` statement: it never makes a `set` line | `set values (text)` |
| `expanded value` | one value after expansion, with its readers and its links (`written`, `definition`, `chain`): what an extension use holds, a directive expansion's values, and a rendered directive's values (the same objects) | the rendered `argument`, which an extension use used to hold; since milestone 4 also `value expansion` and the `argument` family |
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
| `list ()` | the reader that asks for a list (every value variant; E4002 otherwise) | the reader `items ()` |
| `items` | a list's items, a property of the list variants (written `list`, `expanded list`) | `items ()` on a rendered value |
| `expand ()`, `expansion` | the graph's method, and the snapshot it returns: every copy as read, values expanded and linked, what `render (graph)` builds on (spec 6.10) | the package-internal binding render used to read |
| `directive expansion`, `unreadable expansion` | the parts of an expansion: a directive copy, a copy that could not be read (the rendered tree lists the same unreadable expansions since milestone 4; `value expansion` merged into `expanded value`) | (internal: TypeScript `BoundItem`, `Bound`; Python `BoundItem`, `BoundValue`) |
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

The type names after milestone 6: both bindings spell a type the same way, with no prefix (binding guide rule 2;
owner, 2026-10-29, "Yes, rename now"), and each name is imported from its layer's path (rule 9: the shared and io
rows below from `villanelle`, the syntax layer from `villanelle/syntax` / `villanelle.syntax`, the low level from
`villanelle/written` / `villanelle.written`, the rendered tree from `villanelle/rendered` / `villanelle.rendered`).
Every name is generated from its spec name ([codegen.md](codegen.md)). "Union" means a TypeScript union type, or a
Python `X: TypeAlias = A | B | ...` over classes (so `isinstance(x, X)` works). Every kind list is a TypeScript
`as const` object with its derived string-literal type, and a Python `StrEnum`, of the same name (spec 2.10).

### Shared

<!-- generated: names: shared (tools/gen-api.py docs) -->
| Spec name | TypeScript | Python | C++ |
|---|---|---|---|
| `config text` | `ConfigText` | `ConfigText` | `config_text` |
| `source position` | `SourcePosition` | `SourcePosition` | `source_position` |
| `source span` | `SourceSpan` | `SourceSpan` | `source_span` |
| `place` | `Place` | `Place` | `place` |
| `override` | `Override` | `Override` | `override` |
| `step` | `Step` | `Step` | `step` |
| `origin` | `Origin` | `Origin` | `origin` |
| `directive origin` | `DirectiveOrigin` | `DirectiveOrigin` | `directive_origin` |
| `diagnostic` | `Diagnostic` | `Diagnostic` | `diagnostic` |
| `program code` | `ProgramCode` | `ProgramCode` | `program_code` |
| `located diagnostic` | `LocatedDiagnostic` | `LocatedDiagnostic` | `located_diagnostic` |
| `locatable` | `Locatable` | `Locatable` | `locatable` |
| `diagnostics` | `Diagnostics` | `Diagnostics` | `diagnostics` |
| `block` | `Block<Item, Directive>` | `Block[Item, Directive]` | `block<Item, Directive>` |
| `step kind` (kind list) | `StepKind` (as-const object and type) | `StepKind` (`StrEnum`) | `step_kind` (`enum class`) |
| `place kind` (kind list) | `PlaceKind` (as-const object and type) | `PlaceKind` (`StrEnum`) | `place_kind` (`enum class`) |
| `walk control` (kind list) | `WalkControl` (as-const object and type) | none | the walk's descend predicate |
| `diagnostic code` | `DiagnosticCode` (as-const object and type) | `DiagnosticCode` (`StrEnum`) | `diagnostic_code` (`enum class`) |
| `villanelle error` (error group) | `VillanelleError` | `VillanelleError` | `villanelle_error` |
| `diagnostic error` (error group) | `DiagnosticError` | `DiagnosticError` | `diagnostic_error` |
| `read error` (error group) | `ReadError` | `ReadError` | `read_error` |
| `bad text error` (error group) | `BadTextError` | `BadTextError` | `bad_text_error` |
| `save error` (error group) | `SaveError` | `SaveError` | `save_error` |
| `lost update error` (error group) | `LostUpdateError` | `LostUpdateError` | `lost_update_error` |
| `detached error` (error group) | `DetachedError` | `DetachedError` | `detached_error` |
| `argument type error` (error group) | `TypeError` | `TypeError` | `argument_type_error` |
| `misuse error` (error group) | `MisuseError` | `ValueError` | `misuse_error` |
| `index out of range` (error group) | `RangeError` | `IndexError` | `index_out_of_range` |
| `quote` (free function) | `quote` | `quote` | `quote` |
| `text` (free function) | `text` | `text` | `text` |
| `make diagnostics` (free function) | `new Diagnostics(...)` | `Diagnostics(...)` | `diagnostics(...)` |
| `program code` (constant) | `PROGRAM_CODE` | `PROGRAM_CODE` | `is_program_code` |
<!-- end generated -->

### Syntax layer

<!-- generated: names: syntax (tools/gen-api.py docs) -->
| Spec name | TypeScript | Python | C++ |
|---|---|---|---|
| `token range` | `TokenRange` | `TokenRange` | `token_range` |
| `token` | `Token` | `Token` | `token` |
| `node` | `Node` | `Node` | `node` |
| `syntax` | `Syntax` | `Syntax` | `syntax` |
| `token kind` (kind list) | `TokenKind` (as-const object and type) | `TokenKind` (`StrEnum`) | `token_kind` (`enum class`) |
| `node kind` (kind list) | `NodeKind` (as-const object and type) | `NodeKind` (`StrEnum`) | `node_kind` (`enum class`) |
| `parse` (free function) | `parse` | `parse` | `parse` |
| `span of` (free function) | `spanOf` | `span_of` | `span_of` |
| `text of` (free function) | `textOf` | `text_of` | `text_of` |
| `max nesting` (constant) | `MAX_NESTING` | `MAX_NESTING` | `max_nesting` |
<!-- end generated -->

### Ports and extensions

<!-- generated: names: io (tools/gen-api.py docs) -->
| Spec name | TypeScript | Python | C++ |
|---|---|---|---|
| `load context` | `LoadContext` | `LoadContext` | `load_context` |
| `document source` | `DocumentSource` | `DocumentSource` | `document_source` |
| `file write` | `FileWrite` | `FileWrite` | `file_write` |
| `document writer` | `DocumentWriter` | `DocumentWriter` | `document_writer` |
| `fetch writer options` | `FetchWriterOptions` (`villanelle/browser`) | keyword arguments | none |
| `platform fetch` | the platform's own | none | none |
| `memory source` (free function) | `memorySource` | `memory_source` | `memory_source` |
| `memory writer` (free function) | `memoryWriter` | `memory_writer` | `memory_writer` |
| `file source` (free function) | `fileSource` (`villanelle/node`) | `file_source` (`villanelle.files`) | `file_source` (`villanelle::files`) |
| `file writer` (free function) | `fileWriter` (`villanelle/node`) | `file_writer` (`villanelle.files`) | `file_writer` (`villanelle::files`) |
| `fetch source` (free function) | `fetchSource` (`villanelle/browser`) | none | none |
| `fetch writer` (free function) | `fetchWriter` (`villanelle/browser`) | none | none |
| `check lost updates` (free function) | `checkLostUpdates` | `check_lost_updates` | `check_lost_updates` |
<!-- end generated -->

### Low level (written)

<!-- generated: names: written (tools/gen-api.py docs) -->
| Spec name | TypeScript | Python | C++ |
|---|---|---|---|
| `extension` | `Extension` | `Extension` | `extension` |
| `extension use` | `ExtensionUse` | `ExtensionUse` | `extension_use` |
| `load options` | `LoadOptions` | keyword arguments | `load_options` |
| `processor options` | `ProcessorOptions` | keyword arguments | `processor_options` |
| `processor` | `Processor` | `Processor` | `processor` |
| `document graph` | `DocumentGraph` | `DocumentGraph` | `document_graph` |
| `document` | `Document` | `Document` | `document` |
| `document edge` | `DocumentEdge` | `DocumentEdge` | `document_edge` |
| `copy` | `Copy` | `Copy` | `copy` |
| `statement` | `Statement` (union) | `Statement` (union) | `statement` (union) |
| `written directive` | `WrittenDirective` | `WrittenDirective` | `written_directive` |
| `extension line` | `ExtensionLine` | `ExtensionLine` | `extension_line` |
| `set line` | `SetLine` | `SetLine` | `set_line` |
| `snippet line` | `SnippetLine` | `SnippetLine` | `snippet_line` |
| `use line` | `UseLine` | `UseLine` | `use_line` |
| `unreadable line` | `UnreadableLine` | `UnreadableLine` | `unreadable_line` |
| `written block` | `WrittenBlock` | `WrittenBlock` | `written_block` |
| `written value` | `WrittenValue` (union) | `WrittenValue` (union) | `written_value` (union) |
| `word` | `Word` | `Word` | `word` |
| `string` | `String` | `String` | `string` |
| `list` | `List` | `List` | `list` |
| `slice` | `Slice` | `Slice` | `slice` |
| `index` | `Index` | `Index` | `index` |
| `reference` | `Reference` | `Reference` | `reference` |
| `variable` | `Variable` (union) | `Variable` (union) | `variable` (union) |
| `set variable` | `SetVariable` | `SetVariable` | `set_variable` |
| `parameter` | `Parameter` | `Parameter` | `parameter` |
| `override variable` | `OverrideVariable` | `OverrideVariable` | `override_variable` |
| `resolution` | `Resolution<T>` | `Resolution[T]` | `resolution<T>` |
| `reference resolution` | `ReferenceResolution` | `ReferenceResolution` | `reference_resolution` |
| `expansion` | `Expansion` | `Expansion` | `expansion` |
| `expansion block` | `ExpansionBlock` | `ExpansionBlock` | `expansion_block` |
| `directive expansion` | `DirectiveExpansion` | `DirectiveExpansion` | `directive_expansion` |
| `unreadable expansion` | `UnreadableExpansion` | `UnreadableExpansion` | `unreadable_expansion` |
| `slice value` | `SliceValue` | `SliceValue` | `slice_value` |
| `index value` | `IndexValue` | `IndexValue` | `index_value` |
| `expanded value` | `ExpandedValue` (union) | `ExpandedValue` (union) | `expanded_value` (union) |
| `expanded word` | `ExpandedWord` | `ExpandedWord` | `expanded_word` |
| `expanded string` | `ExpandedString` | `ExpandedString` | `expanded_string` |
| `expanded list` | `ExpandedList` | `ExpandedList` | `expanded_list` |
| `expanded slice` | `ExpandedSlice` | `ExpandedSlice` | `expanded_slice` |
| `expanded index` | `ExpandedIndex` | `ExpandedIndex` | `expanded_index` |
| `statement kind` (kind list) | `StatementKind` (as-const object and type) | `StatementKind` (`StrEnum`) | `statement_kind` (`enum class`) |
| `value kind` (kind list) | `ValueKind` (as-const object and type) | `ValueKind` (`StrEnum`) | `value_kind` (`enum class`) |
| `variable kind` (kind list) | `VariableKind` (as-const object and type) | `VariableKind` (`StrEnum`) | `variable_kind` (`enum class`) |
| `unreadable reason` (kind list) | `UnreadableReason` (as-const object and type) | `UnreadableReason` (`StrEnum`) | `unreadable_reason` (`enum class`) |
| `format diagnostic` (free function) | `formatDiagnostic` | `format_diagnostic` | `format_diagnostic` |
| `make processor` (free function) | `villanelle(...)` | `Processor(...)` | `processor(...)` |
| `include` (free function) | `include` (`villanelle/include`) | `include` (`villanelle.include`) | `include` (`villanelle::extensions`) |
| `max depth` (constant) | `MAX_DEPTH` | `MAX_DEPTH` | `max_depth` |
| `max directives` (constant) | `MAX_DIRECTIVES` | `MAX_DIRECTIVES` | `max_directives` |
| `max safe integer` (constant) | `MAX_SAFE_INTEGER` | `MAX_SAFE_INTEGER` | `max_safe_integer` |
| `reserved` (constant) | `RESERVED` | `RESERVED` | `reserved` |
| `variable name` (constant) | `VARIABLE_NAME` | `VARIABLE_NAME` | `is_variable_name` |
<!-- end generated -->

The low level's public entry is one module in each binding: `ts/src/written/index.ts` (new) and the package
`villanelle.written` (its `__all__`). The rendered layer imports the low level from there and nowhere else
(binding guide rule 8).

### Rendered tree

<!-- generated: names: rendered (tools/gen-api.py docs) -->
| Spec name | TypeScript | Python | C++ |
|---|---|---|---|
| `rendered` | `Rendered` | `Rendered` | `rendered` |
| `directive` | `Directive` | `Directive` | `directive` |
| `rendered block` | `RenderedBlock` | `RenderedBlock` | `rendered_block` |
| `key rule` | `KeyRule` | `KeyRule` | `key_rule` |
| `key options` | `KeyOptions` | keyword arguments | `key_options` |
| `address step` | `AddressStep` | `AddressStep` | `address_step` |
| `address` | `Address` | `Address` | `address` |
| `change` | `Change` (union) | `Change` (union) | `change` (union) |
| `added` | `Added` | `Added` | `added` |
| `removed` | `Removed` | `Removed` | `removed` |
| `changed` | `Changed` | `Changed` | `changed` |
| `unknown` | `Unknown` | `Unknown` | `unknown` |
| `change kind` (kind list) | `ChangeKind` (as-const object and type) | `ChangeKind` (`StrEnum`) | `change_kind` (`enum class`) |
| `render` (free function) | `render` | `render` | `render` |
<!-- end generated -->

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

## New terms in milestone 4

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `lost update error` | a `save error` for a file that changed since it was read; `paths` are the conflicting files | round 15: the spec named the lost update but gave it no error (vil-umh.5) | `save error`, which it refines |
| `check lost updates` | the one function every writer calls to find a lost update | one shared check, not one per writer (vil-umh.5) | the per-writer comparisons it replaces |
| `entry rule` | a grammar rule a binding parses a given text with (`valuesText`, `itemsText`, `boundText`, `nameText`) | the rules that depend only on the text live in the grammar (vil-umh.3) | the check of a values text (its probe and scanner) |
| `misuse error` (`MisuseError` in TypeScript) | the program-bug group for a bad value, every bad name included | one group for every bad name, told apart from an argument type error (vil-umh.7) | TypeScript's `TypeError` for misuse |
| `unread` (an `unreadable reason`), E3007 `unread copy` | an extension copy not read yet | a render and a diff must show it (vil-umh.4) | none: it rendered as nothing |
| definition, environment, walk, candidate | the words of [expansion.md](expansion.md) | the scoping and precedence rules have one home (vil-umh.2) | the prose of `docs/language.md` |
| `INTEGER`, `DIGIT_WORD`, `BAD_ESCAPE` (token kinds) | an integer word, every other word starting with a digit or `-`, a string with a bad escape | directive names cannot start with a digit or `-` (owner Q1); bounds and escapes are checked by the grammar (vil-umh.3) | `WORD` (split in three); E4003 found at render |

Removed in milestone 4: `value expansion`, `argument` and its five variants, the rendered `unreadable`, `edit
error`, and `statement` as the name of the link on a directive or unreadable expansion (now `written`).

## New terms in milestone 5

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `config text` (`ConfigText`) | villanelle text a program hands to an edit or an override, a type of its own, made only by `quote` or `text` | the owner picked "Yes, its own type" (2026-10-29, vil-umh.6): a plain string there is a type error | `text`, the parameter's name, which stays |
| `text (raw)` | the free function that takes plain text as config text, unchanged | config text needs a second maker besides `quote` (owner: "made only by quote() or an explicit text(...)") | `quote`, which writes a string; `text` writes nothing |
| raw string | a single-quoted string: its text exactly as typed, no escapes (TOML's literal string) | the owner said "yes" to single quotes as raw strings (vil-umh.14) | `string`: still the value kind `string`; only the spelling's rule differs |
| slice name | the word or `$name` before a slice's `[` (grammar `sliceName`) | a variable may be subscripted (vil-umh.14: "yes") | a slice's `name`, which it is |
| language statement, extension statement | a statement written `@name`: `@set`, `@snippet`, `@use`, or an extension's (`@include`) | the statements behind one sigil (vil-umh.14: "yes"); no directive name is reserved | the reserved words at a line's start |
| `AT_WORD`, `TILDE` (token kinds) | a word that starts with `@`; the `~` between a slice's bounds | the grammar tells a statement's keyword from a directive's name, and the separator is outside the word alphabet | `WORD` (split); `COLON` (replaced) |
| E3008 `unknown extension`, E4007 `bad slice name` | an `@name` no extension owns; a slice's `$name` that does not hold one word | the two new failures of `@` statements and subscripted variables | E3001 (a file not found), E4001 (a bound) |

Removed in milestone 5: `plain` (the reader) and `plain value`; the `COLON` token kind; reserved directive names;
escapes in a single-quoted string.

## New terms in milestone 6

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| block (the shape) | what every block has: iterate, count, `at (index)`, `directives (name?)`, `walk` (spec 2.11) | the owner's "one block shape (iterate, index, directives(name), walk) in every layer" (2026-10-29) | `written block`, which is now one of three |
| `expansion block`, `rendered block` | the block of directive expansions (6.10) and of rendered directives (7.1) | the expansion's and the render's blocks were plain lists, so they had no `directives` or `walk` | a list of directives, which they replace |
| `walk control` (TypeScript only) | what a walk's callback returns: `skip` or `stop` | TypeScript's walk takes a callback; the values were a bare string type | the `"skip" \| "stop"` union it names |
| keyword, `Keyword` | a language statement's word after `@` (`set`, `snippet`, `use`), one generated list with its dispatch table to the statement kind | "one generated keyword list and dispatch table" (owner, 2026-10-29) | the `reserved names` words, which are now read from it |
| type grammar, trait | the closed grammar every schema type is written in, and the typed facts that say how a member looks in each language ([codegen.md](codegen.md) 2, 3) | the owner's "idiom expressed as typed per-language traits" (Q3, 2026-10-29) | `spell`, the prose notes they replace |
| rules module | the generated limits, reserved words and patterns, exported by the layer that owns each (spec 2.5) | the round 15 finding that the validation rules were not exported | the generated `limits` file, which it is |

Removed in milestone 6: every TypeScript `I` prefix; the written block's `statements` member; `walk` on the render
and on a directive (now `block.walk`); the one flat namespace of each binding.

## New terms in milestone 3

These are words of the conformance tooling, not of the API: no binding exports them.

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `conformance adapter` | the small program each binding writes that answers the driver's requests through its public API ([conformance.md](conformance.md)); "the adapter" on that page | the review's root cause 5: "a binding writes one small adapter" | the per-binding conformance runner, which it replaces. Not the source and writer adapters of spec 4.3 (memory, file, fetch), which keep the word unqualified |
| `driver` | `conformance/driver/run.py`, the one program that runs every case and compares | the same | the runners |
| `conformance level` (L0 to L4) | how much of the spec a binding claims to meet, cumulative | a binding climbs them in order, and CI checks the claim | the `needs` tokens, which stay as a record |
| `key rule data` | a key rule written as data in `conformance/keys.json` | a case cannot hold a function (root cause 5: "the "rasl" key rule becomes data") | the `"rasl"` rule each runner wrote by hand |
| `dump` | the neutral JSON shape of a binding object the adapter sends | the driver finds targets and compares; the adapter only describes | none |

## New terms in milestone 7

These are words of the schema and its generator ([codegen.md](codegen.md)), not of the API: no binding exports them.

| Term | Definition | Why it is needed | Existing term it could be |
|---|---|---|---|
| `doc` | a schema entry's text for the binding's users (a concept, member, parameter, kind list, error group, free function, protocol shape or request), which every emitter writes as the declaration's doc comment (JSDoc, a docstring); it may not carry a bead id, `milestone N`, an `owner, <date>` quote or a language's name ([codegen.md](codegen.md) 3, "Docs and rationale") | one `note` held both user docs and maintainer history, and the history reached generated code | `note`, which it and `rationale` replace |
| `rationale` | a schema entry's text for the people who maintain the schema: history, the owner's words, bead ids, one language's notes; no emitter reads it | the same | `note` |
| adapter module (`files`, `fetch`, `include`) | a module a binding may have beside its layer namespaces, named for what it holds: `files` the filesystem source and writer, `fetch` the fetch source and writer, `include` the include extension. Each emitter maps it to its own import path or leaves it out (its `LANGUAGE.modules`); the generated contract 5 table and the glossary's io table show each binding's path | the schema named the TypeScript paths (`node`, `browser`), a per-language fact | `node` and `browser`, the schema's old module names. Not the source and writer adapters themselves (spec 4.3), nor the conformance adapter |
| `registry layer`, `adapter layer` | the layer that holds the error groups and the diagnostic code type, and the one layer whose concepts may sit in an adapter module (`api.json`) | the loader named `shared` and `io` in code, so a renamed or added layer needed a loader edit | none |
| I-Regexp | the interoperable regular expression subset of RFC 9485; every schema pattern is one, between `^` and `$`, and each emitter writes it in its engine's dialect | a pattern must mean the same in every binding's engine, not only JavaScript's and Python's | the "no `\s`, `\w`, `\d`, `\b`" rule it replaces |
