# Designing a villanelle language binding

This page is about **how** to design a binding: the goals, the naming and structure rules, what may
differ between languages and what may not, and the steps from an empty package to passing every
shared case. **What** a binding must do (every concept, operation, order and error) is in
[spec.md](spec.md); this page does not repeat it. TypeScript (`ts/`) and Python (`py/`) are the
worked examples.

Status: the goals in section 1 are the owner's words. The naming and structure rules in section 2
come from the round 13 review ([review.md](../.claude/design/consumer-api/round13/review.md)); each
rule says whether milestone 1 (bead vil-fy4) or milestone 2 (bead vil-0vz) adopted it, or it is still **proposed,
pending the owner**. Section 4 shows the names before milestone 1, with each milestone's new name, and where they
still break those rules. API
shape changes need the owner's approval; nothing is locked (2026-10-27: "Nothing is locked until I
see user APIs that I like").

## 1. Goals, in the owner's words

Each quote is dated and taken from
[requirements.md](../.claude/design/consumer-api/requirements.md), which keeps the owner's words
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
8. **Each layer has its own types; an upper layer builds on a lower one, never the reverse.** Round
   13 gate page, 2026-10-29: the owner first picked "B graph.render()", then clarified: "The low level shouldn't "depend on" the middle layer — they should have different domain objects. The middle layer of objects can build on the lower layer domains". So `render(graph)` is the rendered
   layer's function, and every other operation is a method on the object you hold. Spec 6.2 and
   7.0 hold the rule.
9. **Values going in are text, and misuse is impossible to miss.** 2026-10-29: "A Keep text only,
   make misuse impossible" (spec 6.9). The edit that replaces values is `set`: "Can "set_values"
   become simply "set"?" (2026-10-29, spec 6.5). The word for values a program passes in is `override`:
   "A overrides" (spec 6.2).

## 2. Naming and structure rules

These are the review's rules ([review.md, "Naming and structure rules across languages"](../.claude/design/consumer-api/round13/review.md#naming-and-structure-rules-across-languages)).
Rules 1, 6 and 8 are adopted by milestone 1 (the glossary and the operation homes rest on them); rule 4 by
milestone 2 (types carry their kinds, spec 2.10), with rule 8's second check (the rendered layer uses only public
low-level members); rules 2 and 5, and rule 9 (one namespace per layer), by milestone 6 (owner, 2026-10-29, "Yes,
rename now"); rules 3 and 7 are **proposed, pending the owner** (milestone 2 applies rule 3's medium-and-port names to
the adapters, nothing more). A new binding should follow all of them;
where TypeScript or Python break one, section 4 says so.

1. **Spec names change only in casing** (adopted). The words are in [glossary.md](glossary.md). The spec names each concept, member and kind value once in
   lowercase words. A binding applies its language's casing and nothing else. Two exceptions, each
   for a language's own rule: factories follow rule 3, and a type name MAY drop a layer word its
   module already gives (Go `written.Directive` for `written directive`, since Go's linters flag
   `written.WrittenDirective` as a stutter; TypeScript and Python keep the full name, since their
   users import names unqualified):

   | Spec | TypeScript | Python | Go (example only) |
   |---|---|---|---|
   | type `document graph` | `DocumentGraph` | `DocumentGraph` | `DocumentGraph` |
   | member `replace with text` | `replaceWithText` | `replace_with_text` | `ReplaceWithText` |
   | kind value `set` | `"set"` | `StatementKind.SET` (value `"set"`) | `StatementKindSet` |
   | factory `make processor` | `villanelle(...)` (rule 3) | `Processor(...)` | `NewProcessor(...)` |

2. **No language prefixes on type names** (adopted, milestone 6). No `I` on interfaces: `DocumentGraph`,
   `WrittenDirective`, `Rendered`. Where a short name would clash with a built-in, the module gives the context
   (`written.String`, `written.List`), not a prefix. A binding derives every name from its spec name with its
   casing rule; the generator does it once for every binding (codegen.md section 3), so no binding stores a
   spelling.
3. **One factory convention per binding, the language's own constructor idiom** (proposed). TypeScript:
   lowercase nouns, no `create` (`fileSource()`, `include()`). Python: lowercase functions for the ports and
   extensions (`file_source()`, `memory_source()`, `include()`), and the class itself where the schema marks a
   factory a `constructor` (`Processor(...)`, `Diagnostics(...)`), as jinja2's `Environment(...)`. Go: `New` plus the concept
   (`NewMemorySource`, `NewProcessor`), since a Go type and function cannot share a name. Rust:
   `Type::new`. Java: constructors or a static `of`. A spec name that starts with `make` (`make
   processor`, `make diagnostics`) names the factory of the concept after it.
4. **One model per language, used in every layer** (adopted for kinds by milestone 2, spec 2.10; the owner's goal
   2 is his). Each binding names its model in its README:
   - TypeScript: discriminated unions narrowed on `kind`, one interface per variant, kind lists as `as const`
     objects with the string-literal union derived from them (milestone 6, spec 2.10), read-only objects, options
     objects, blocks iterable with `for...of` and indexed with `at`, `walk` with a callback (spec 2.11).
   - Python: the standard `ast` style: a class per variant with `kind` and `__match_args__` in the same field
     order in every layer, unions as `TypeAlias`, kind lists as `StrEnum`s, frozen slotted records, keyword-only
     options, tuples for results (a `MutableMapping` where the user edits a map: proposed).
   - Every variant carries `kind`; an operation exists only on the variants where it can succeed; run-time errors
     are kept for problems in the user's text (the readers' E4002), never for a type the checker could have caught.

   Models for languages without unions or generators (proposed, not yet tried by a binding):
   - Go (1.23 or later, the `go/ast` style): a sealed interface per kind list (an unexported method)
     with one struct per kind, matched by a type switch; kind lists as typed string constants in a
     `const` block; handles as pointers (identity is pointer equality), snapshots and records as
     structs passed by value; `iter.Seq` for lists worked out on demand and for `walk` (descend
     asked after each yield, spec 7.5); functional options (`WithKey(rule)`); errors as values,
     matched with `errors.Is` and `errors.As` (spec 2.8 and section 3); `context.Context` first on
     every call that does I/O.
   - Rust: an `enum` per kind list with data on its variants, matched with `match`; handles as
     reference-counted or arena-indexed types; iterators; builder structs for options;
     `Result<T, E>` with one error `enum` per group sort.
   - Java (21 or later): `sealed interface` plus `record` per kind, matched with `switch` patterns;
     `Stream` or `Iterable`; builders for options; unchecked exceptions for program bugs and checked
     ones (or a result type) for expected outcomes.
5. **Containers have one shape** (adopted, milestone 6). A block can be iterated and indexed in every layer, has
   `directives (name?)` and `walk`, and nothing else is a container's own member (spec 2.11): the written block, the
   expansion block and the rendered block. `walk` lives on the block (spec 7.5), not on the render or a directive.
6. **Properties and methods** (adopted). A fact the object holds, or can work out cheaply on its
   own, is a property. Anything worked out across the whole graph, that can fail, or that takes
   arguments, is a method. The same concept is the same kind of member in every layer. The graph's
   `diagnostics` is a property, as on the render ([glossary.md](glossary.md), "Rules").
7. **A required first-hour example** (proposed). Each binding's docs open with the rasl task as one complete,
   running program with its imports, kept as a test: list the files and the include line that
   pulled each in; list every variable with where it is used and overridden; change `$pixels`; make
   `max_count` stop using it; add a line in `sink.conf`; save; render. A binding is not done until
   that program reads naturally in its language.
8. **Operation homes and layer direction** (adopted: the owner's answer of 2026-10-29). The
   processor only loads; every later operation is a method on the object the program holds, within
   its layer (spec 6.2); going up a layer is the upper layer's free function, `render(graph)` (spec
   7.0). Nothing below the rendered layer imports, names or returns a rendered type, not even in a
   type-only import: an `extension use` holds the low level's `expanded value`s, and a rendered
   directive holds its `directive expansion`'s own objects (spec 2.9, 7.0). The low level is the one
   owner of expansion: the extension port, expanded values and their readers live in its layer
   (milestone 4). Each binding keeps the layers in their own modules and
   checks the direction mechanically, so a wrong import fails the build:
   - **TypeScript.** The rendered layer lives in `ts/src/rendered/`. ESLint's core
     `no-restricted-imports` rule, in `ts/eslint.config.js`, forbids importing `**/rendered/**`
     from every file under `ts/src/` except `ts/src/rendered/**` and tests (`*.test.ts`). The package entry
     `ts/src/index.ts` is no exception: it holds only the shared and io layers (rule 9). The rule covers `import
     type` too, so even a type name cannot leak.
   - **Python.** The rendered layer is the package `villanelle.rendered`. A test
     (`py/tests/test_layers.py`) reads every module under `src/villanelle/` with `ast` and fails when
     one outside `villanelle/rendered/` (the top-level `villanelle/__init__.py` included) imports
     `villanelle.rendered` or anything in it, absolute or relative, `if TYPE_CHECKING:` imports
     included. Importing `villanelle.written` runs `villanelle/__init__.py`, which loads only the shared
     and io layers.
   - **Go, Rust:** one package or crate per layer; the compiler then refuses a cycle.

   **The second check: the rendered layer builds on the public low level only** (owner, 2026-10-29, "Yes"; spec
   6.10, 7.0). `render(graph)` reads the graph through `expand ()` and the public types, never a package-internal
   module, member, accessor or class check, so a third party could write it.
   - **TypeScript.** `ts/src/written/index.ts` (new) is the low level's public entry: it re-exports exactly the
     written layer's public names (`ts/src/index.ts` holds only the shared and io layers, rule 9). In `ts/eslint.config.js`, a block for
     `files: ["src/rendered/**/*.ts"]`, `ignores: ["src/**/*.test.ts"]`: `no-restricted-imports` with the pattern
     group `["**/written/*", "!**/written/index.js"]`, and `no-restricted-syntax` refusing a cast through `unknown`
     (`TSAsExpression[typeAnnotation.type="TSUnknownKeyword"]` and `TSAsExpression > TSAsExpression`), the one way
     to reach a member the public interface does not declare. A planted lint fixture shows each fires.
   - **Python.** `py/tests/test_layers.py` also reads every module under `villanelle/rendered/` and fails when it
     imports the low level other than `from villanelle.written import <name>` with `<name>` in
     `villanelle.written.__all__` (no submodule such as `villanelle.written._bind` or `.model`, no name starting
     with `_`, relative forms included), or reads an attribute starting with one `_` (dunders aside) on anything but
     `self` or `cls`, `getattr(x, "_name")` included. Rendered code reads another rendered object through its
     public members too. A planted source string shows the test bites.

   Cost: the rule polices imports and syntax, not every way to reach a private (TypeScript's `#private` fields are
   safe; a `Reflect.get` with a string is not caught); review covers the rest.

   Prior art: layered architecture's dependency rule, checked the way
   [import-linter](https://import-linter.readthedocs.io/) and eslint-plugin-boundaries check it. The
   bindings use the smaller tools above because an allow-list check (every module but the rendered
   ones and the entry point) also catches an indirect import, with no new dependency.

9. **One namespace per layer** (adopted, milestone 6; owner, 2026-10-29, "Yes, rename now"). Each layer is its own
   public import path, and every public name has exactly one: the package root holds the shared and io layers
   (positions, places, diagnostics and the sink, error classes, config text, the ports and the memory adapters); the
   syntax, written and rendered layers are their own paths; an adapter keeps its own path (the file and fetch
   adapters, the include extension). A name is never re-exported under a second path, and no old name is kept.

   | Layer | TypeScript | Python |
   |---|---|---|
   | shared, io | `villanelle` | `villanelle` |
   | syntax | `villanelle/syntax` (package subpath export) | `villanelle.syntax` (subpackage) |
   | written (the low level) | `villanelle/written` | `villanelle.written` |
   | rendered | `villanelle/rendered` | `villanelle.rendered` |
   | file adapters | `villanelle/node` | `villanelle.files` |
   | fetch adapters | `villanelle/browser` | none (MAY, spec 4.3) |
   | include extension | `villanelle/include` | `villanelle.include` |

   The exact names per path are generated (`PUBLIC_NAMES`, codegen.md section 4), and each binding's name test
   compares every path's exports with them, both ways. Python users import the subpackage as the namespace (`from
   villanelle import rendered, written`, then `written.Processor`, `rendered.render`), which also keeps
   `written.List` from shadowing `typing.List`.

## 3. What may differ, and what must not

**May differ**, each for the stated reason. Any other difference is a defect.

| Difference | TypeScript | Python | Why |
|---|---|---|---|
| Casing | `camelCase` members, `PascalCase` types | `snake_case` members, `PascalCase` types | the language's style |
| I/O | `load`, `read`, `save`, sources and writers are async | plain calls | the language's I/O habit. `render` and `diff` are always plain calls |
| Absent | `undefined` | `None` | the language's no-value |
| Misuse error | `MisuseError` (outside `VillanelleError`) | `ValueError` | TypeScript has no built-in class for a bad argument value that is not `TypeError`, the argument type error's class (spec 2.8) |
| Index out of range | `RangeError` | `IndexError` | the language's own classes (spec 2.8) |
| Config text (M5) | `ConfigText`, a branded string (`string & { readonly [brand]: true }`, the brand a `unique symbol`) | `ConfigText = NewType("ConfigText", str)` | each language's named-string idiom (spec 6.9); a language with neither (Go) uses a defined type, `type ConfigText string` |
| A value handle that changes kind under `set` (M5) | the same object reports the new `kind`; a narrowed variable is stale | the object's class becomes the new kind's (`__class__` assignment; the six value classes share one slot layout) | spec 6.1: one object, a type per kind; each language keeps both as far as it can |
| How a kind list is spelled | an `as const` object and its derived string-literal union (`StatementKind.Set`, `"set"`) | a `StrEnum` (`StatementKind.SET`) | each language's enumeration that the checker sees through (spec 2.10, milestone 6) |
| How a variant is matched | `switch (x.kind)` or `if (x.kind === StatementKind.Set)` narrows | `match x: case SetVariable(): ...`, `__match_args__` | the language's own pattern |
| Options | an options object (`{ key }`) | keyword-only arguments (`key=`) | the language's habit |
| Iteration | iterators and `for...of` (today: a walk callback) | generators and `for` | the language's habit |
| Reader names | `word()`, `string()`, `number()`, `integer()`, `boolean()`, `list()`, `slice()` (milestone 5 deleted `plain()`) | the same words (casing only, vil-gxu, milestone 2) | not a difference in TypeScript and Python: a method named `list` or `string` shadows nothing for the caller (the only trap is an annotation inside the class body, as for `set`: write `builtins.list`). A name a language's conventions give another meaning does differ: in Go, `String()` is `fmt.Stringer` (the `people form`) and `Error()` is the `error` interface, so the readers become `AsString()` and the like, and `error (...)` becomes `Fail(...)` or similar |
| People form | `toString()` | `__str__` | the language's to-text conversion (contract 2) |
| Positions | UTF-16 code units | code points | the language's string unit (contract 1); conformance stays UTF-16 |
| Chained errors | `cause` | `__cause__` | the language's mechanism |
| A block (rule 5, spec 2.11) | `Iterable` (`for...of`, `[...block]`), `length`, `at(i)` (absent out of range) | a `Sequence` (`for s in block`, `len(block)`, `block[i]`, slices, `in`, `reversed()`, `IndexError` out of range; the generated Protocol states the `Sequence` read methods, as a Protocol cannot extend the ABC) | each language's read-only sequence; a live written block cannot be a frozen array |

**Must not differ:**

- the set of concepts and operations, and their spec names (only casing changes);
- every stated order (documents, walk order, diff order, variables);
- which error group is raised when, and every diagnostic code;
- the canonical value text and the address text, byte for byte;
- what a handle is: one object per written thing, detached handles raising (spec 6.1);
- every conformance output, byte for byte.

**Positions** count the language's own string unit (contract 1): a binding with UTF-8 strings reports bytes, and
its adapter reports them as they are and names its unit in `hello`; the shared driver converts to UTF-16
([conformance.md](conformance.md)).

### For languages unlike TypeScript and Python (proposed, pending owner)

These rows say how a language with error values, no exceptions, no `undefined`, or cancellation
meets the spec. None has been tried by a binding yet; spec 2.8 and 4.1 hold the matching proposals.

| Difference | Go (the worked case) | Why |
|---|---|---|
| Errors | a member that reads a fact returns the bare value (`d.Name()`, `v.Text()`) and panics on a detached handle; every call that can end in an expected outcome (spec 2.8, "two sorts") returns `(T, error)`: edits (a detached handle's edit returns the `detached error`), `Load`, `Read`, `Save`, `Addresses`, `Diff`, the readers. Misuse, index out of range and a detached getter panic (the program-bug sort). Each expected-outcome group is a type usable with `errors.As`; a `lost update error` is matched as a `save error` too | errors as values are Go's habit; a getter returning `(T, error)` cannot be used in an expression, and a detached getter is a program bug |
| Key rule | `func(*rendered.Directive) (key string, ok bool, err error)`: `ok` false is absent, a non-nil `err` ends `Addresses` and `Diff` with that error unchanged | spec 7.1: a key rule may fail |
| Extension failure | a returned error that is not a `diagnostic error` gives E3006; a panic inside `Specs` is not recovered, and the binding says so | spec 5: recovering a panic would hide a bug as a diagnostic |
| Absent and empty | a pointer or a `(T, bool)` pair for absent text; a boolean such as `HasBlock()` beside `Body()` | spec 1: absent and empty differ, and Go's `nil` slice is fragile to rely on |
| Overrides | an ordered input (`[]Override{{Name, Text}}` or a functional option per value), not a `map` | spec 6.2: the order is kept |
| Cancellation | `ctx context.Context` first on `Load`, `Read`, `Save`, `Resolve`, `Read` and `Write`; cancellation returns `ctx.Err()`, never a diagnostic | spec 4.1, Proposed |
| Concurrency | document that a graph is not safe for concurrent use, renders included | spec 4.1 |
| Positions | byte offsets of the UTF-8 string (contract 1); the adapter's `hello` says `"byte"` and the driver converts to UTF-16. A lone surrogate is 3 bytes, its WTF-8 form: a Go `string` holds it, so the `surrogate-*` syntax cases pass with an adapter whose JSON codec keeps `\ud800` escapes (Go's `encoding/json` does not; conformance 3). A Rust `String` cannot hold one, so a Rust binding cannot pass them until spec 2.1's proposal is ruled | contract 1, spec 2.1 |

## 4. Concept map: TypeScript and Python today

The names on PR 4, before milestone 1. A note in the last column shows a break with section 2 or a
difference not in section 3, with the review finding that names it
([findings.json](../.claude/design/consumer-api/round13/findings.json)); "M1:" and "M2:" give the milestone 1 and 2
names. The exact old-to-new tables, with signatures, are the milestones' frozen pages,
`.claude/design/consumer-api/round14/frozen-m1.md` and `frozen-m2.md`. Milestone 6 drops every TypeScript `I` prefix
(`IDocumentGraph` is `DocumentGraph`) and moves each name to its layer's import path (rule 9); its full list is
`.claude/design/consumer-api/round15/frozen-m6.md`, "Behaviour changes".

### Processor and I/O

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `make processor` | `villanelle({ source, extensions })` returns `IProcessor` | `Processor(source=..., extensions=...)` | |
| `load` | `await processor.load(path, { variables })` | `processor.load(path, variables=...)` | M1: `{ overrides }`, `overrides=` |
| `read` | `await processor.read(graph)` | `processor.read(graph)` | M1: `graph.read()` |
| `render` | `processor.render(graph)` | `processor.render(graph)` | M1: `render(graph)`, the rendered module's function |
| `diff` | `processor.diff(a, b, { key })` | `processor.diff(a, b, key=...)` | M1: `a.diff(b, ...)` |
| `save` | `await save(graph, writer)` (free function) | `save(graph, writer)` | M1: `graph.save(writer)` |
| `quote` | `quote(text)` | `quote(text)` | M5: returns `ConfigText` in both |
| `text` (M5) | `text(raw)`, returns `ConfigText`, a branded string | `text(raw)`, returns `ConfigText`, a `NewType` of `str` | spec 6.9: the same concept, each language's idiom for a named string type |
| `document source` | `IDocumentSource` | `DocumentSource` (a `Protocol`) | rule 2: `I` prefix |
| `load context` | `ILoadContext` | `LoadContext` | rule 2 |
| `memory source` | `memorySource(files)` | `memory_source(files)` | rule 3 (Python: a class). M2: reads the map live; new `memoryWriter(files)`, `memory_writer(files)` |
| `file source` | `createFileSource()` from `villanelle/node` | `file_source()` from `villanelle.files` | rule 3. M2: `fileSource()` |
| `file writer` | `createFsWriter()` from `villanelle/node` | `fs_writer()` | rule 3; medium named `fs` here, `file` in the source. M2: `fileWriter()`, `file_writer()` |
| `fetch source`, `fetch writer` | `createFetchSource(fetch)`, `createFetchWriter(fetch, options)` from `villanelle/browser` | none | MAY in spec 4.3. M2: `fetchSource`, `fetchWriter` |
| `document writer` | `IDocumentWriter` | `DocumentWriter` (a `Protocol`) | rule 2 |
| `file write` | `IFileWrite` | `FileWrite` | |
| `extension` | `IExtension` | `Extension` (a `Protocol`) | |
| `extension use` | `IExtensionUse` (`args`, rendered arguments) | `ExtensionUse` (`args`) | M1: `values`, as `expanded value`s |
| include extension | `include()` from `villanelle/include` | `include()` from `villanelle.include` | rule 3 (Python: a class) |

### Low level

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `document graph` | `IDocumentGraph` | `DocumentGraph` | |
| `diagnostics ()` | `graph.diagnostics()` | `graph.diagnostics()` | a method here, a property on the render: rule 6. M1: a property |
| `set handed` | `graph.setHanded(name, text)`, `graph.handed` | `graph.set_handed(name, text)`, `graph.handed` | M1: `setOverride`/`set_override`, `overrides` |
| `document` | `IDocument` (`resolvedPath`, `source`, `text`, `syntax`, `body`, `includedBy()`, `replaceWithText()`) | `Document` (`resolved_path`, ..., `included_by()`, `replace_with_text()`) | `body` against `block`; `source` has two meanings. M1: `block`, `savedText` |
| `document edge`, `copy` | `IDocumentEdge`, `ICopy` | `DocumentEdge`, `Copy` | |
| `statement` | `Statement` (union on `kind`) | `Statement` (union of classes, `kind` a literal property) | Python low level has no `__match_args__`: rule 4. M2: `__match_args__` on every class, `kind` a `StatementKind`, `insert before`/`insert after` |
| `written directive` | `IWrittenDirective` (`kind` `"directive"` or `"extension"`; `setValues`) | `WrittenDirective` (`set_values`) | include lines share the type. M1: `set` on it and on `set line`, `use line`, `variable`. M2: `IExtensionLine` / `ExtensionLine` for kind `extension`, without `rename` |
| `set line`, `snippet line`, `use line`, `unreadable line` | `ISetLine`, `ISnippetLine`, `IUseLine`, `IUnreadableLine` | `SetLine`, `SnippetLine`, `UseLine`, `UnreadableLine` | |
| `written block` | `IWrittenBlock` (`.statements`, `directives()`, `insertStatements()`, `addStatements()`) | `WrittenBlock` (a `Sequence`, `directives()`, `insert_statements()`, `add_statements()`) | rule 5 |
| `written value` | `WrittenValue` (union) of `IWord`, `IString`, `IList`, `ISlice`, `IIndex`, `IReference` | `WrittenValue` of `Word`, `String`, `List`, `Slice`, `Index`, `Reference` | Python's flat namespace makes `List` clash with `typing.List` on `import *`. M2: the six classes from `villanelle.written` only |
| `variable` | `IVariable` (one type, `kind` `"set"`, `"parameter"`, `"handed"`) | `Variable` | `setValues` on all kinds; `NoSetLineError`. M1: kind `"override"`. M2: union `Variable` of `ISetVariable`, `IParameter`, `IOverrideVariable` (Python `SetVariable`, `Parameter`, `OverrideVariable`); `NoSetLineError` gone |
| `resolution`, `reference resolution` | `IResolution<T>`, `IReferenceResolution` | `Resolution[T]`, `ReferenceResolution` | `overridden` here is a list; on a variable it is a method. M1: `shadowed` |
| `reaches ()`, `overridden ()` | methods | methods | M1: `wins()`, `shadowedAt()` |
| `resolutions ()` (on a reference) | method, one per copy | method | the rendered `resolutions` is a property counting chain steps |

### Rendered tree

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `rendered` | `IRendered` (`body`, `unreadable`, `origin`, `diagnostics`, `graph`, `walk()`, `error()`, `addresses()`) | `Rendered` (same, no `walk` method) | M1: `block`, `diff()` |
| `directive` | `IDirective` (`name`, `args`, `body`, `unreadable`, `parent`, `origin`, `written`, `walk()`, `closest()`, `error()`) | `Directive` (`__match_args__`; no `walk` method) | `args`/`values`, `body`/`block`. M1: `values`, `block`, `walk` in Python |
| `walk` | `node.walk(visit)`, callback returns `"skip"` or `"stop"` | `walk(node, descend=...)`, a generator | rule 5. M1: a method in Python too |
| `argument` | `IArgument` | `Argument` | `written` is the end of the chain. M1: `written` (same line), `definition`, `chain`; builds on `expanded value`. M2: union `Argument` of `IWordArgument` ... `IIndexArgument`, each built on its expanded variant; built from `graph.expand()` only. M4: removed: a rendered directive's values are its expansion's `expanded value`s, which carry `written`, `definition`, `chain` |
| readers | `word()`, `string()`, `number()`, `integer()`, `boolean()`, `items()`, `slice()`, `plain()` | `as_word()`, `as_str()`, `as_number()`, `as_int()`, `as_bool()`, `as_list()`, `as_slice()`, `plain()` | section 3 reader row. M2: `word()` ... `list()` ... `plain()` in both; `items` a property of list variants. M5: `plain()` deleted in both (the readers are `word()`, `string()`, `number()`, `integer()`, `boolean()`, `list()`, `slice()`) |
| `slice value`, `index value` | `ISliceValue`, `IIndexValue` | `SliceValue`, `IndexValue` | Python names clash with low-level `Slice`, `Index` |
| `unreadable` | `IUnreadable` (`kind` is the reason) | `Unreadable` | M1: `reason`. M4: removed: `IUnreadableExpansion` / `UnreadableExpansion` (reason `unread` added) |
| `address`, `address step` | `IAddress` (`text`; `toString()` is the `people form`), `IAddressStep` | `Address` (`text`; `str()` is the `people form`), `AddressStep` | |
| `key rule` | `KeyRule` | `KeyRule` | |
| `change` | `Change` union with `kind` | `Added`, `Removed`, `Changed`, `Unknown` classes, no `kind` | rule 4. M2: `kind` on the Python classes |

### Shared pieces

| Spec name | TypeScript | Python | Note |
|---|---|---|---|
| `source position`, `source span` | `ISourcePosition`, `ISourceSpan` | `SourcePosition`, `SourceSpan` | UTF-16 in both. M2: code points in Python |
| `place`, `handed`, `step`, `origin`, `directive origin` | `IPlace`, `IHanded`, `IStep`, `IOrigin`, `IDirectiveOrigin` | `Place`, `Handed`, `Step`, `Origin`, `DirectiveOrigin` | a location is `place`, `written`, `at` or `span`. M1: `override` (`IOverride`, `Override`), and `place` for each |
| kind lists | `TokenKind`, `NodeKind`, `ValueKind`, `StepKind`, `UnreadableKind`, `ChangeKind` (constant objects) | `StrEnum`s, literal strings on the low level, classes for changes | four mechanisms in Python. M2: a generated string-literal type (TypeScript) and `StrEnum` (Python) for every list |
| `diagnostic`, `located diagnostic` | `IDiagnostic`, `ILocatedDiagnostic` | `Diagnostic`, `LocatedDiagnostic` | |
| diagnostic codes | `DiagnosticCode.UnterminatedString` | `DiagnosticCode.UNTERMINATED_STRING` | copied by hand: see codegen.md |
| `diagnostic error`, edit errors, `save error`, `read error` | as spec 2.8 | as spec 2.8; `EditError` is a `ValueError` | no package base error. M2: `VillanelleError` base; `DetachedError` off `EditError` (Python: a `ReferenceError`); `ReadError` not a diagnostic error; `ReadError` and `SaveError` with `paths` (contract 4) |
| `format diagnostic` | `formatDiagnostic(d, graph?)` | `format_diagnostic(d, graph=None)` | |
| diagnostics sink (`make diagnostics`, `add`, `report`, `count`, `collect`) | `new Diagnostics(initial)`, `add`, `report`, `length`, `collect(read)` | `Diagnostics(initial)`, `add`, `report`, `len()`, `with problems.collecting():` | `collect` as a context manager is the Python idiom |
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
   `ts/src/syntax/parse.ts` and `py/src/villanelle/syntax/_parse.py` do. ANTLR 4.13.2 has official targets for Go,
   Java, C#, C++, Swift, PHP, Dart, JavaScript, TypeScript and Python, but not Rust (`antlr4rust` is a third-party
   runtime and lags the official releases). How a binding without an official target gets its parser (a
   third-party runtime, a parser written by hand and held to the syntax corpus, or another generator checked
   against the grammar) is an open question for the owner; ask before choosing.
4. **Write your emitter** ([codegen.md](codegen.md) section 10): `tools/api/emit_<lang>.py`, rendering the
   loader's model in your language: the kind lists, codes, rules, error tree, one declaration per concept (each
   trait of codegen.md section 3 in your idiom), the names table and the adapter's message shapes. Register it in
   `tools/gen-api.py` and `tools/gen.sh`, and keep its output out of git. Every fact about your language (each root
   error group's class, your adapter modules, your factory forms, the argument type error's sentence, what your
   idiom leaves out) goes in the emitter's `LANGUAGE`, never in `spec/schema/`, which names no language. Never type a
   list, a signature or a name by hand: your classes implement the generated declarations.
5. **Write the adapter** ([conformance.md 6](conformance.md#6-what-a-binding-writes)): one small program in your
   language that reads the driver's requests on standard input and answers on standard output, through your public
   API only, typed by your emitter's generated message shapes and spelling table. Start with `hello` (claim L0, name your string unit) and `parse`, then run the driver (the adapter can
   come before step 3: a stub `parse`, or one that delegates to an existing binding, tries the protocol first):
   `python3 conformance/driver/run.py -- <your adapter's command>`. Make every syntax case pass (L0). The driver
   checks the byte rules and converts your positions to UTF-16 (contract 1); your adapter does neither.
6. **Write the ports** (spec 4): the source and writer interfaces in your language's form, and
   `memory source`. The adapter needs nothing else.
7. **Build the low level** (spec 6): load, handles, statements, values, variables, resolutions,
   edits, save, quote. Add `load`, `graph`, `edit`, `save` and `quote` to the adapter and claim L1.
8. **Build the rendered tree** (spec 7) and the include extension (spec 5.1). Add `render`, `diff`, `read`, `print`,
   `format` and `cut`, and the key rule built from data (conformance.md 4.3); claim L2, then L3. The load, rendered
   and contract corpora cover render, addresses, diff order, every reader, people forms and `format diagnostic`.
9. **Test what the shared cases miss** (spec 9 lists it): the sink, `error(...)`, the file and memory adapters (L4
   has no shared cases yet), the error class tree, and that each operation is absent where it cannot succeed.
   Compare with TypeScript and Python, and report any disagreement as a finding. Add the driver with your adapter to
   CI, after your package's tests (`.github/workflows/ci.yml`).
10. **Write the first-hour program** as a test and as the top of your README (rule 2.7). Read it
    as a newcomer to your language would; anything that needs a cast, a helper you never show, or
    a doc lookup to understand is a defect.
11. **Fill in your deviations table** (section 3) and check every row in section 4 has an entry for
    your binding.
12. **Run the repo's checks** for your package, then land through a pull request. API shape changes
    go to the owner first.
