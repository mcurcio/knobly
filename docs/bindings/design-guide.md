# Designing a villanelle language binding

This page is about **how** to design a binding: the goals, the naming and structure rules, what may
differ between languages and what may not, and the steps from an empty package to passing every
shared case. **What** a binding must do (every concept, operation, order and error) is in
[spec.md](spec.md); this page does not repeat it. TypeScript (`ts/`) and Python (`py/`) are the
worked examples.

Status: the goals in section 1 are the owner's words. The naming and structure rules in section 2
come from the round 13 review ([review.md](../../.claude/design/consumer-api/round13/review.md)) and
are **proposed, pending the owner**. Section 4 shows the current names and where they break those
rules. API shape changes need the owner's approval; nothing is locked (2026-10-27: "Nothing is
locked until I see user APIs that I like").

## 1. Goals, in the owner's words

Each quote is dated and taken from
[requirements.md](../../.claude/design/consumer-api/requirements.md), which keeps the owner's words
with their sources.

1. **Idiomatic in each language.** "Both, idiomatic in each language. Python should take
   inspiration from pydantic, as that's the natural Python configuration mechanism." (2026-10-24)
   "The goal is code that is idiomatic to each language." (2026-10-27)
2. **One model per language, followed all the way.** On two bindings that mixed their
   inspirations: "They are trying to combine the inspirations rather than choosing one model, and
   the results are two APIs that are not intuitive. They are close; they are on the right
   trajectory; but they lack the elegance of a strong API" (2026-10-28).
3. **Layers you can build on.** "An EBNF gives a language independent syntax. And then parsers can
   be written against it, and then finally language-specific idiomatic sugar APIs can be layered on
   top" (2026-10-21). On the low level and the rendered tree: "i like this layered approach, because
   it allows consumers to build on top of any of the APIs" (2026-10-28).
4. **The spec wins over a reference language.** "Within villanelle I want the spec to win over a
   reference language" (2026-10-27). TypeScript is not the template; [spec.md](spec.md) is.
5. **A native extension point, no framework in the core.** "there should be an idiomatic SPI for
   each supported language, *and optionally* additional integration APIs for common languages
   frameworks" (2026-10-26). "I don't want villanelle dependent on third party libraries
   (including pydantic) so any shims must be optional extensions rather than core." (2026-10-25),
   amended: "And third party libraries are ok for things like reflect-metadata" (2026-10-28).
6. **Include is an extension.** "I think it's a first-party plugin/extension." (2026-10-25)
7. **Lead with user code.** The owner judges an API by the code a user writes against it, so a
   binding's docs open with a complete program (rule 2.7), not with type listings.

## 2. Naming and structure rules (proposed, pending owner)

These are the review's rules ([review.md, "Naming and structure rules across languages"](../../.claude/design/consumer-api/round13/review.md#naming-and-structure-rules-across-languages)).
A new binding should follow them; where TypeScript or Python break one today, section 4 says so.

1. **Spec names change only in casing.** The spec names each concept once in lowercase words. A
   binding applies its language's casing and nothing else:

   | Spec | TypeScript | Python | Go (example only) |
   |---|---|---|---|
   | type `document graph` | `DocumentGraph` | `DocumentGraph` | `DocumentGraph` |
   | member `set values` | `setValues` | `set_values` | `SetValues` |
   | kind value `set` | `"set"` | `StatementKind.SET` (value `"set"`) | `StatementKindSet` |

2. **No language prefixes on type names.** No `I` on interfaces. Where a short name would clash with
   a built-in, the module gives the context (`written.String`), not a prefix.
3. **One factory convention per binding.** TypeScript: lowercase nouns, no `create`
   (`fileSource()`, `include()`). Python: public classes (`FileSource()`, `Include()`), as jinja2's
   `FileSystemLoader`.
4. **One model per language, used in every layer.** Each binding names its model in its README:
   - TypeScript: discriminated unions, read-only objects, generators for iteration, options objects.
   - Python: the standard `ast` style: a class per kind with `__match_args__` in the same field
     order in every layer, frozen slotted records, generators, keyword-only options, tuples for
     results, a `MutableMapping` where the user edits a map.
5. **Containers have one shape.** A block can be iterated and indexed in every layer, and both
   layers offer the same walk (spec 7.5).
6. **Properties and methods.** A fact the object holds, or can work out cheaply on its own, is a
   property. Anything worked out across the whole graph, that can fail, or that takes arguments, is
   a method. The same concept is the same kind of member in every layer.
7. **A required first-hour example.** Each binding's docs open with the rasl task as one complete,
   running program with its imports, kept as a test: list the files and the include line that
   pulled each in; list every variable with where it is used and overridden; change `$pixels`; make
   `max_count` stop using it; add a line in `sink.conf`; save; render. A binding is not done until
   that program reads naturally in its language.
8. **Module layout.** One module per layer, the same short names in every binding, and a small top
   level (`villanelle/written`, `villanelle/rendered`, `villanelle/file`).

## 3. What may differ, and what must not

**May differ**, each for the stated reason. Any other difference is a defect.

| Difference | TypeScript | Python | Why |
|---|---|---|---|
| Casing | `camelCase` members, `PascalCase` types | `snake_case` members, `PascalCase` types | the language's style |
| I/O | `load`, `read`, `save`, sources and writers are async | plain calls | the language's I/O habit. `render` and `diff` are always plain calls |
| Absent | `undefined` | `None` | the language's no-value |
| Misuse errors | `TypeError`, `RangeError` | `ValueError`, `IndexError` | the language's own classes (spec 2.8) |
| How a kind list is spelled | a string-literal type (today: constant objects) | a `StrEnum` | narrowing without an import, against `match` and enums |
| Options | an options object (`{ key }`) | keyword-only arguments (`key=`) | the language's habit |
| Iteration | iterators and `for...of` (today: a walk callback) | generators and `for` | the language's habit |
| Reader names | `word()`, `integer()` | `as_` only where the bare name would shadow a built-in (`as_int`, `as_str`, `as_bool`, `as_list`) | not shadowing `int`, `str` (today Python prefixes all of them) |
| Chained errors | `cause` | `__cause__` | the language's mechanism |

**Must not differ:**

- the set of concepts and operations, and their spec names (only casing changes);
- every stated order (documents, walk order, diff order, variables);
- which error group is raised when, and every diagnostic code;
- the canonical value text and the address text, byte for byte;
- what a handle is: one object per written thing, detached handles raising (spec 6.1);
- every conformance output, byte for byte.

**Positions** are a special case. Today every binding reports UTF-16 units. The review proposes that
each reports its own string unit and the runners convert (spec 2.1, Proposed).

## 4. Concept map: TypeScript and Python today

The names on PR 4. A mark in the last column shows a break with section 2 or a difference not in
section 3, with the review finding that names it ([findings.json](../../.claude/design/consumer-api/round13/findings.json)).

### Processor and I/O

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `make processor` | `villanelle({ source, extensions })` returns `IProcessor` | `Processor(source=..., extensions=...)` | |
| `load` | `await processor.load(path, { variables })` | `processor.load(path, variables=...)` | handed-in word: question 2 |
| `read` | `await processor.read(graph)` | `processor.read(graph)` | proposed: `graph.read()` |
| `render` | `processor.render(graph)` | `processor.render(graph)` | proposed: `render(graph)` in the rendered module |
| `diff` | `processor.diff(a, b, { key })` | `processor.diff(a, b, key=...)` | proposed: `a.diff(b, ...)` |
| `save` | `await save(graph, writer)` (free function) | `save(graph, writer)` | proposed: `graph.save(writer)` |
| `quote` | `quote(text)` | `quote(text)` | |
| `document source` | `IDocumentSource` | `DocumentSource` (a `Protocol`) | rule 2: `I` prefix |
| `load context` | `ILoadContext` | `LoadContext` | rule 2 |
| `memory source` | `memorySource(files)` | `memory_source(files)` | rule 3 (Python: a class) |
| `file source` | `createFileSource()` from `villanelle/node` | `file_source()` from `villanelle.files` | rule 3 |
| `file writer` | `createFsWriter()` from `villanelle/node` | `fs_writer()` | rule 3; medium named `fs` here, `file` in the source |
| `fetch source`, `fetch writer` | `createFetchSource(fetch)`, `createFetchWriter(fetch, options)` from `villanelle/browser` | none | MAY in spec 4.3 |
| `document writer` | `IDocumentWriter` | `DocumentWriter` (a `Protocol`) | rule 2 |
| `file write` | `IFileWrite` | `FileWrite` | |
| `extension` | `IExtension` | `Extension` (a `Protocol`) | |
| `extension use` | `IExtensionUse` (`args`) | `ExtensionUse` (`args`) | `args` against the low level's `values` |
| include extension | `include()` from `villanelle/include` | `include()` from `villanelle.include` | rule 3 (Python: a class) |

### Low level

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `document graph` | `IDocumentGraph` | `DocumentGraph` | |
| `diagnostics ()` | `graph.diagnostics()` | `graph.diagnostics()` | a method here, a property on the render: rule 6 |
| `set handed` | `graph.setHanded(name, text)` | `graph.set_handed(name, text)` | |
| `document` | `IDocument` (`resolvedPath`, `source`, `text`, `syntax`, `body`, `includedBy()`, `replaceWithText()`) | `Document` (`resolved_path`, ..., `included_by()`, `replace_with_text()`) | `body` against `block`; `source` has two meanings |
| `document edge`, `copy` | `IDocumentEdge`, `ICopy` | `DocumentEdge`, `Copy` | |
| `statement` | `Statement` (union on `kind`) | `Statement` (union of classes, `kind` a literal property) | Python low level has no `__match_args__`: rule 4 |
| `written directive` | `IWrittenDirective` (`kind` `"directive"` or `"extension"`) | `WrittenDirective` | include lines share the type |
| `set line`, `snippet line`, `use line`, `unreadable line` | `ISetLine`, `ISnippetLine`, `IUseLine`, `IUnreadableLine` | `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine` | |
| `written block` | `IWrittenBlock` (`.statements`, `directives()`, `insertStatements()`, `addStatements()`) | `WrittenBlock` (a `Sequence`, `directives()`, `insert_statements()`, `add_statements()`) | rule 5 |
| `written value` | `WrittenValue` (union) of `IWord`, `IString`, `IList`, `ISlice`, `IIndex`, `IReference` | `WrittenValue` of `Word`, `String`, `List`, `Slice`, `Index`, `Reference` | Python's flat namespace makes `List` clash with `typing.List` on `import *` |
| `variable` | `IVariable` (one type, `kind` `"set"`, `"parameter"`, `"handed"`) | `Variable` | `setValues` on all kinds; `NoSetLineError` |
| `resolution`, `reference resolution` | `IResolution<T>`, `IReferenceResolution` | `Resolution[T]`, `ReferenceResolution` | `overridden` here is a list; on a variable it is a method |
| `reaches ()`, `overridden ()` | methods | methods | proposed: `wins()`, `shadowedAt()` |
| `resolutions ()` (on a reference) | method, one per copy | method | the rendered `resolutions` is a property counting chain steps |

### Rendered tree

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `rendered` | `IRendered` (`body`, `unreadable`, `origin`, `diagnostics`, `graph`, `walk()`, `error()`, `addresses()`) | `Rendered` (same, no `walk` method) | |
| `directive` | `IDirective` (`name`, `args`, `body`, `unreadable`, `parent`, `origin`, `written`, `walk()`, `closest()`, `error()`) | `Directive` (`__match_args__`; no `walk` method) | `args`/`values`, `body`/`block` |
| `walk` | `node.walk(visit)`, callback returns `"skip"` or `"stop"` | `walk(node, descend=...)`, a generator | rule 5 |
| `argument` | `IArgument` | `Argument` | `written` is the end of the chain: proposed `definition` |
| readers | `word()`, `string()`, `number()`, `integer()`, `boolean()`, `items()`, `slice()`, `plain()` | `as_word()`, `as_str()`, `as_number()`, `as_int()`, `as_bool()`, `as_list()`, `as_slice()`, `plain()` | section 3 reader row |
| `slice value`, `index value` | `ISliceValue`, `IIndexValue` | `SliceValue`, `IndexValue` | Python names clash with low-level `Slice`, `Index` |
| `unreadable` | `IUnreadable` (`kind` is the reason) | `Unreadable` | proposed: `reason` |
| `address`, `address step` | `IAddress` (`toString()`), `IAddressStep` | `Address` (`str()`), `AddressStep` | |
| `key rule` | `KeyRule` | `KeyRule` | |
| `change` | `Change` union with `kind` | `Added`, `Removed`, `Changed`, `Unknown` classes, no `kind` | rule 4 |

### Shared pieces

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `source position`, `source span` | `ISourcePosition`, `ISourceSpan` | `SourcePosition`, `SourceSpan` | UTF-16 in both |
| `place`, `handed`, `step`, `origin`, `directive origin` | `IPlace`, `IHanded`, `IStep`, `IOrigin`, `IDirectiveOrigin` | `Place`, `Handed`, `Step`, `Origin`, `DirectiveOrigin` | a location is `place`, `written`, `at` or `span`: one word proposed |
| kind lists | `TokenKind`, `NodeKind`, `ValueKind`, `StepKind`, `UnreadableKind`, `ChangeKind` (constant objects) | `StrEnum`s, literal strings on the low level, classes for changes | four mechanisms in Python |
| `diagnostic`, `located diagnostic` | `IDiagnostic`, `ILocatedDiagnostic` | `Diagnostic`, `LocatedDiagnostic` | |
| diagnostic codes | `DiagnosticCode.UnterminatedString` | `DiagnosticCode.UNTERMINATED_STRING` | copied by hand: see codegen.md |
| `diagnostic error`, edit errors, `save error`, `read error` | as spec 2.8 | as spec 2.8; `EditError` is a `ValueError` | no package base error |
| `format diagnostic` | `formatDiagnostic(d, graph?)` | `format_diagnostic(d, graph=None)` | |
| diagnostics sink | `new Diagnostics(initial)`, `collect(read)` | `Diagnostics(initial)`, `with problems.collecting():` | |
| `error (message, code)` | `error(message, code)` | `error(message, code=...)` | |
| syntax | `parse`, `spanOf`, `textOf`, `IToken`, `INode`, `ISyntax` | `parse`, `span_of`, `text_of`, `Token`, `Node`, `Syntax` | |

## 5. Checklist: a new binding, start to finish

Work in this order. Each step ends with shared cases passing, so progress is measurable.

1. **Read** [spec.md](spec.md) end to end, then this page, then the two `README.md` files in `ts/`
   and `py/` for how each binding is built and tested.
2. **Choose the model.** Name one model from your language's own ecosystem for every layer (rule
   4), and write it in your binding's README with the reason. Get the owner's approval on a short
   page that leads with the first-hour program (rule 2.7) written against the planned API, before
   building the layers.
3. **Generate the parser.** Add your target to `tools/gen.sh` (ANTLR 4.13.2) and keep generated code
   out of git. Wrap the generated parser in an adapter so its types never cross into your API, as
   `ts/src/syntax/parse.ts` and `py/src/villanelle/syntax/parse.py` do.
4. **Copy the fixed lists** from spec 2.4 and 2.5 and section 3 of the spec (token kinds, node
   kinds, codes, limits, reserved names). Until codegen exists ([codegen.md](codegen.md)), add a
   test that compares your lists with the spec's tables.
5. **Write the syntax runner** for `conformance/*.json` ([conformance/format.md](../../conformance/format.md))
   and make every case pass. Check the byte rules (escapes above U+007F, one trailing newline) and
   positions in UTF-16.
6. **Write the ports** (spec 4): the source and writer interfaces in your language's form, and
   `memory source`. The runners need nothing else.
7. **Build the low level** (spec 6): load, handles, statements, values, variables, resolutions,
   edits, save, quote. Write the written runner for `conformance/written/`
   ([format](../../conformance/written/format.md)). Skip by `needs` while you build; finish with an
   assertion that your feature set covers every case.
8. **Build the rendered tree** (spec 7) and the include extension (spec 5.1). Write the load runner
   for `conformance/load/` ([format](../../conformance/load/format.md)), including the `rasl` key
   rule exactly as that page states it.
9. **Test what the shared cases miss** (spec 9 lists it): readers, `address text`, `format
   diagnostic`, the sink, `error(...)`, the file adapters, and the known gaps (`-0`, a lone `"\r"`,
   large numbers). Compare with TypeScript and Python, and report any disagreement as a finding.
10. **Write the first-hour program** as a test and as the top of your README (rule 2.7). Read it
    as a newcomer to your language would; anything that needs a cast, a helper you never show, or
    a doc lookup to understand is a defect.
11. **Fill in your deviations table** (section 3) and check every row in section 4 has an entry for
    your binding.
12. **Run the repo's checks** for your package, then land through a pull request. API shape changes
    go to the owner first.
