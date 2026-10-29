# Generating each binding's declarations from one schema

**Status.** Milestone 6 (beads vil-umh.9, vil-umh.10, vil-umh.11, vil-umh.13) makes the schema the source of every
public signature. The owner's answers it rests on, quoted:

- Q3 of the round 15 review (2026-10-29), "Should the schema become the source of every public signature?": he picked
  "Yes, with idiom expressed as typed per-language traits; start after the scoping and layer decisions" (those landed
  in milestones 4 and 5).
- Enumerations (2026-10-29): "Yes, generate both": TypeScript `as const` objects with derived string-literal types,
  Python internals comparing enum members, one generated keyword list and dispatch table, a lint against comparing
  `.kind`, `.reason` or `.code` with a string literal.
- Namespaces (2026-10-29): "Yes, rename now": one namespace per layer, no `I` prefix, one block shape.
- His first ask (2026-10-28): a "clean, easy to comprehend API design", "idiomatic in each language", "consistent
  across layers", and codegen "so we dont have to maintain n languages by hand".

Earlier milestones generated only the fixed lists (milestone 1: codes, kinds, limits; milestone 2: one spelling per
list); milestone 3 wrote the shared conformance driver by hand. What each binding builds against is
[frozen-m6.md](../.claude/design/consumer-api/round15/frozen-m6.md).

## 1. What comes from where

```text
spec/schema/
  api.json            concepts with typed members, kind lists, keywords, limits, patterns, error groups, free functions
  diagnostics.json    the diagnostic codes: name, layer, found by, reason, message, meaning, summary, placement
  protocol.json       the adapter protocol's requests, results and dump shapes (spec/conformance.md 4)
  api.schema.json     the JSON Schema (2020-12) all three must match
tools/
  gen-api.py          the command: ts | py | docs | --check
  api/loader.py       reads and checks the three files into one language-neutral model
  api/emit_ts.py      the TypeScript emitter
  api/emit_py.py      the Python emitter
  api/emit_docs.py    the Markdown tables
  api/validate.py     the JSON Schema check (tools/check.sh runs it through uv, with jsonschema)
  lint/               the kind lint: kind-rule.mjs (ESLint selectors), kind_lint.py (Python ast)
```

`tools/gen.sh ts|py` runs the parser generator, then `tools/gen-api.py ts|py`; every TypeScript package script and
`py/tests/conftest.py` run `tools/gen.sh` first, so generated code is never stale and never committed (owner,
2026-10-23: "Don't commit the generated code, just the source"). The one committed output is the docs tables
(section 6).

## 2. The closed type grammar

Every type in `api.json` (a property's `type`, a method's `returns`, a parameter's `type`, an `extends`, an error
field) is text in this grammar, and every name in it must resolve: a free-text type cannot pass the loader, and the
JSON Schema refuses any character outside the grammar's alphabet.

```text
type      = union
union     = postfix { " or " postfix }
postfix   = primary { "[]" }                            a list, in order
primary   = "(" type ")"
          | "function" [ " of " postfix { " and " postfix } ] " to " type
          | [ "writable " ] "map of " postfix [ " to " postfix ]      one argument: text keys
          | name [ " of " postfix { " and " postfix } ]               type arguments of a generic concept
name      = "text" | "integer" | "number" | "boolean" | "nothing" | "absent"
          | a concept | a kind list | "diagnostic code" | an error group | a type parameter in scope
```

Examples: `written block or absent`, `(resolution of snippet line)[]`, `map of directive to address`, `function of
directive to text or absent`, `block of statement and written directive`. `absent` is a type, so "may be absent" is
part of the type (`statement or absent`), not a flag beside it. A map keeps insertion order in every binding.

Prior art: the Language Server Protocol's `metaModel.json`, which describes LSP's types as data (`or`, `array`,
`map`, `reference`, `base` kinds) for its TypeScript, Python, Rust and C# generators. villanelle writes the same tree
as short text because the owner reads the schema; the loader parses it into the metaModel's shape.

The loader also checks what a shape check cannot see:

- every name resolves, in the right scope (a type parameter only inside its concept or member);
- **the layer direction** (spec 5): a member type names only its own layer or one its layer may import, so the low
  level cannot name a rendered type even in a signature;
- every union's variants cover its kind list (less `except`), each variant names its union, each kind list's
  `variants` map back;
- the error groups form a tree on spec 2.8's two sorts: every expected outcome under the base, no program bug under
  any group, each root with a per-language base;
- every option parameter has an options record, every trait is from the closed list, every limit a message names
  exists, every `found by` is from its closed list;
- no two public names derive the same identifier in one namespace (the casing rule stays one-to-one).

Each check is planted: `tools/gen-api.py --check` breaks a copy of the schema twelve ways (an unresolved type, a
broken type, a layer-direction breach, a free-text type, a missing variant, a wrong kind, a bad parent, a bug under
the base, an unknown trait, a spelling collision, an unknown found-by, a bad protocol type) and fails unless each is
refused. `tools/api/validate.py` does the same for the JSON Schema (a per-language spelling, a free-text type, an
unknown trait, a `spell` note, an unknown found-by).

## 3. Idiom as typed traits, spellings derived

The schema stores no binding spelling. Every identifier is derived from a spec name by the casing rule (binding
guide rule 1), written once in `tools/api/loader.py` (`words`, `pascal`, `camel`, `snake`, `upper_snake`) and used by
every emitter, the names module and the adapters' spelling table: types `PascalCase` in both (no prefix: rule 2);
members `camelCase` / `snake_case`; enum members `PascalCase` / `UPPER_SNAKE_CASE`; constants `UPPER_SNAKE_CASE`.

Where the languages' idioms differ, the schema says what the member **is**, from a closed list, and each emitter
knows its language's form. Milestone 5's 31 prose `spell` notes are gone.

| Trait or field | Means | TypeScript | Python |
|---|---|---|---|
| `trait: people form` | the text a person reads (contract 2) | `toString()` | `__str__` |
| `trait: iterate` | the items in order | `[Symbol.iterator]()` | `__iter__` |
| `trait: count` | how many | `length` | `__len__` |
| `trait: index` | the item at an index | `at(i)`, absent out of range | `__getitem__`, `IndexError` out of range |
| `trait: walk` | depth-first visit (spec 7.5) | `walk(visit)`, callback returns `WalkControl` | `walk(*, descend=None)`, a generator |
| `trait: collect` | run reads, record a diagnostic error | `collect(read)` | `collecting()`, a context manager |
| `io: true` | goes through a port | returns a `Promise` | a plain call |
| `passed: keyword` | an argument named at the call | positional | keyword-only |
| `passed: option` (with the member's `options` record) | an optional setting | one options object (`load(path, { overrides })`) | keyword-only (`load(path, *, overrides=None)`) |
| `factory` | how a concept is made | `package function` (`villanelle(...)`) or `constructor` | `constructor` (`Processor(...)`) |
| `nature: named type`, `brand` | a string with its own type (spec 6.9) | a branded string | a `NewType` of `str` |
| `nature: named type`, `pattern` | text of a stated form | a template literal type (`${string}/${string}`) | `str` |
| list `[]` | in order | `readonly T[]` | `tuple[T, ...]` as a result, `Sequence[T]` as a parameter |
| `map` | keyed, ordered | `ReadonlyMap` as a result, `Readonly<Record>` as a parameter (`writable`: `Record`) | `Mapping` (`writable`: `MutableMapping`) |
| `module` (io only) | an adapter's own import path | `villanelle/node`, `villanelle/browser`, `villanelle/include` | `villanelle.files`, `villanelle.include` |
| `languages` | exists in some bindings only | options records, `WalkControl`, `fetch` | `Collecting` |
| error group `ts` / `py` | the root's base, or the language's own class | `{"base": "Error"}`, `{"builtin": "TypeError"}` | `{"base": "Exception"}`, `{"builtin": "ValueError"}` |

Python methods take their parameters positional-only (`/`): a hand-written class that also accepts them by keyword
still satisfies the Protocol, so the generated signature never forbids what a binding allows.

## 4. What each emitter generates

**TypeScript** (`ts/src/gen/api/`, git-ignored, typechecked, not linted; `ts/conformance/shapes.ts`, git-ignored,
typechecked and linted with the adapter):

| Module | Holds |
|---|---|
| `kinds.ts` | every kind list as an `as const` object plus the union derived from it (spec 2.10); `Keyword`, `STATEMENT_OF_KEYWORD`, `statementOfKeyword(word)` |
| `codes.ts` | `DiagnosticCode` (`as const` object and union), `MESSAGES`, `CODE_FACTS` (name, layer, found by, reason, typed per code), `ReasonOf<C>`, `describe(code, detail?)` |
| `limits.ts` | the rules module: `MAX_NESTING`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `VARIABLE_NAME`, `PROGRAM_CODE` |
| `errors.ts` | the error class tree (spec 2.8): each class's base, fields, constructor, message and `name`; `argumentTypeMessage(member, parameter, got)` |
| `shared.ts`, `syntax.ts`, `io.ts`, `written.ts`, `rendered.ts` | per layer: one interface per handle, port, record and snapshot (each variant with every member of its union, `kind` a literal); union types; callback types; options objects; the generic `Block<TItem, TDirective>`; a `<Module>Functions` interface per import path listing its free functions |
| `names.ts` | `PUBLIC_NAMES` (every public name per import path, values and types apart) and `ERROR_GROUP_OF_CLASS` |
| `ts/conformance/shapes.ts` | every request, result and dump of the adapter protocol as a type; `PROTOCOL`; `SPELLING` (each spec name the driver sends, in camelCase) |

**Python** (`py/src/villanelle/_api/`, git-ignored, checked by ruff and `mypy --strict`; `py/conformance/shapes.py`,
git-ignored, checked the same):

| Module | Holds |
|---|---|
| `kinds.py` | every kind list as a `StrEnum`; `Keyword`, `STATEMENT_OF_KEYWORD`, `statement_of_keyword(word)` |
| `codes.py` | `DiagnosticCode`, `MESSAGES`, `CodeFacts`, `CODE_FACTS`, `Described`, `describe(code, detail=None)` |
| `limits.py` | the rules module, as TypeScript's (patterns end in `\Z`, the text's end) |
| `errors.py` | the error class tree; `argument_type_message(member, parameter, got)` |
| `shared.py`, `syntax.py`, `io.py`, `written.py`, `rendered.py` | per layer: a `Protocol` per handle, port and interface (variants with `kind: Literal[...]`); a frozen slotted `@dataclass` per plain record or snapshot (only properties: `eq=False` for a snapshot, field order the match args, a fixed `kind` as a property); union and callback `TypeAlias`es; `ConfigText`; the generic `Block` Protocol; a `<Module>Functions` Protocol per module |
| `names.py` | `PUBLIC_NAMES` (each module's `__all__`), `ERROR_GROUP_OF_CLASS`, `MATCH_ARGS` |
| `py/conformance/shapes.py` | the protocol's `TypedDict`s, `PROTOCOL`, `SPELLING` (in snake_case) |

How a binding uses them (frozen-m6.md has the per-file list):

- **TypeScript:** each layer's public entry (`villanelle/syntax`, `villanelle/written`, `villanelle/rendered`, and
  the package root for the shared and io layers) re-exports the generated interfaces as its public types; each
  hand-written class `implements` its interface, so a drifted or missing member is a compile error. The
  hand-written interface files go.
- **Python:** each hand-written handle class subclasses its generated `Protocol` (PEP 544's explicit form, so mypy
  checks every member at the class); records and snapshots are the generated dataclasses, re-exported; the error
  tree, kinds, codes and rules are imported from `_api`. A module is checked against its `<Module>Functions`
  Protocol (`_: SyntaxFunctions = villanelle.syntax`, mypy's modules-as-protocols).
- **Both:** the public-name test is one comparison per import path, both ways, against `PUBLIC_NAMES` (TypeScript
  reads a module's exports, types included, through the compiler API; Python compares `__all__`). The adapters read
  `SPELLING` and `ERROR_GROUP_OF_CLASS` instead of writing the casing rule or matching class names by regex.

## 5. The adapter protocol

`protocol.json` holds every request (parameters, which are optional, the result, the level), every result and dump
shape (fields, fields by `kind`, tuples, exactly-one-of), the edit members and the readers. Its types use the same
grammar with the wire's own atoms (`text`, `integer`, `number`, `boolean`, `json`, `id`, `null`, `position`), quoted
literals (`"utf-16"`) and `tuple of A and B`. Keys are the wire's own spellings (`savedText`, `includedBy`): data,
not a binding's names. spec/conformance.md 4.1 and 4.2 are generated from it; each request's prose (`params note`,
`note`) stays with it, and the loader refuses a note that does not name each parameter.

The driver does not yet check every dump against these shapes (spec/conformance.md 7); the generated types make an
adapter's dumps checked by its own compiler instead.

## 6. The docs tables: the one committed output

Four Markdown tables are generated between `<!-- generated: NAME (tools/gen-api.py docs) -->` and
`<!-- end generated -->`: the code registry in spec 2.4, the error-code table in docs/rendered-tree.md, and the
adapter's requests and dumps in spec/conformance.md 4.1 and 4.2. They are committed, unlike the code, because nothing
builds the docs: GitHub shows the files as they are. `python3 tools/gen-api.py docs` rewrites them and
`tools/check.sh` fails when one is stale, so no table can drift from its source (round 15 found three copies of the
code table disagreeing on 8 of 32 meanings and 14 of 32 found-by entries). Prior art: `cog` and the "generated
section" markers of rustfmt's and Prettier's option docs.

## 7. The kind lint

Inside each binding a `kind`, `reason` or `code` is compared with a generated member, never a string literal (spec
2.10):

- **TypeScript:** `tools/lint/kind-rule.mjs` exports `KIND_RULE`, three `no-restricted-syntax` selectors (an `===`,
  `!==`, `==` or `!=` with `.kind`, `.reason` or `.code` on one side and a literal on the other, either order; a
  `switch` on one of them with a literal `case`). `ts/eslint.config.js` spreads it over `src/**/*.ts` and
  `conformance/*.ts`.
- **Python:** `tools/lint/kind_lint.py PATH...` (standard library `ast`): an `==` or `!=` with a `str` constant,
  an `in` / `not in` with a tuple, list or set holding one, and a `match x.kind:` with a string `case`. The Python
  package's tests run it over `src/` and `conformance/` and fail on any finding. `tools/check.sh` runs its self-test
  (planted comparisons caught, member comparisons left alone).

The rule is for the bindings' own code. A program using a binding may write `s.kind === "set"`: it is checked by
the compiler, and TypeScript narrows on it.

## 8. What stays hand-written

The algorithms (binding variables and snippets, edits and where text goes, expansion, render, addresses, diff),
the parser glue, the I/O adapters, each binding's module layout below its public entries, and docs prose with
examples. Generating these would cost more than writing them, and the owner wants each binding idiomatic: on JSON
Schema as the way to declare configuration, "it can't be the only one because it is not conducive to building
natural APIs that are idiomatic in each target language" (2026-10-26). The traits of section 3 are how idiom is
kept while the shapes are generated.

## 9. Prior art, and why the generator is still bespoke

The generator follows the **compiler-plugin** shape of `protoc`: one front end reads and checks the source into a
neutral descriptor (`tools/api/loader.py`, like protoc's `FileDescriptorSet`), and one back end per language renders
it (`emit_ts.py`, `emit_py.py`, like `protoc-gen-<lang>` plugins). A new binding adds one emitter; nothing else
changes. Its data model follows the **LSP `metaModel.json`** (a typed, language-neutral description that feeds
`vscode-languageserver-types` and `lsprotocol`), its traits follow **Smithy traits** (facts about a shape that each
code generator reads its own way), and the registry follows TypeScript's `diagnosticMessages.json` and Babel's
`@babel/types` definitions, both generated into declarations and docs.

Why not one of those tools as is:

| Tool | Why not |
|---|---|
| JSON Schema or OpenAPI generators (quicktype, openapi-generator, datamodel-code-generator) | They generate data shapes: no methods, handles, ports, generics, traits or error trees, and they own the output's idiom. The JSON Schema is used for what it is good at, checking the schema files' shape (`api.schema.json`) |
| Smithy | A service model (operations over a network) with a Java toolchain; villanelle's API is in-process handles. Its trait idea is used |
| Protocol Buffers | Wire messages with a runtime library each binding must ship, against the owner's no-third-party-dependency rule (2026-10-25). Its plugin architecture is used |
| TypeSpec | Its core is protocol-neutral, but a custom emitter is written in TypeScript against its compiler, a Node toolchain for the Python-only `tools/`, and the per-language idiom would still be written by hand in each emitter |
| LSP metaModel generators | Written for LSP's own model (requests and notifications), not reusable outside it. Its model shape is used |

So the bespoke part is small: about 850 lines of loader and 550 to 700 lines per emitter, in Python's standard
library (the same toolchain as the driver and the grammar checks), for a schema of 79 concepts, 10 kind lists, 34
codes and 13 protocol requests.

## 10. A new binding

A new binding is **one emitter and one adapter** (binding guide section 5): add `tools/api/emit_<lang>.py`
rendering the loader's model in the language's idiom (each trait of section 3, the casing rule's output, the error
tree on the language's own base classes, the protocol shapes), register it in `tools/gen-api.py`, and point
`tools/gen.sh` at its output directory. The adapter (spec/conformance.md 6) is then written against the generated
shapes and spelling table.

## 11. Costs

- The schema is bigger than the lists it was: every member is typed, and a change to a public signature is a schema
  change first. That is the point (the schema is the one home), but it is a step a binding author must not skip.
- Generated interfaces are flat (each variant repeats its union's members), which is plain to read and costs nothing
  at run time.
- Python records are generated dataclasses: a hand-written record with private fields must move them out or become a
  handle with a Protocol.
- Behaviour is not in the schema: the spec and the shared cases still carry it.
- The driver checks dumps only as far as it reads them; the generated shapes move the rest of that check to each
  adapter's compiler, not to the driver (spec/conformance.md 7).
