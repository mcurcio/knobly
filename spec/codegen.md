# Generating each binding's declarations from one schema

**Status.** Milestone 6 (beads kno-umh.9, kno-umh.10, kno-umh.11, kno-umh.13) makes the schema the source of every
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

Milestone 7 (beads kno-umh.16, kno-umh.17, kno-umh.18) finishes three leftovers of milestone 6: Python's generated
types name the binding's public classes (section 4), the schema holds no per-language fact (sections 3 and 10), and
each schema entry's user doc is split from its rationale (section 3, "Docs and rationale"). What each binding builds
against is [frozen-m7.md](../.claude/design/consumer-api/round15/frozen-m7.md).

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
  api/stub.py         a third binding in miniature, loaded by --check to prove a binding needs no schema edit
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
JSON Schema refuses any character outside the grammar's alphabet. Each closed list (traits, natures, `passed`,
error sorts, found-by, code layers, adapter modules, and the emitter-facing factory forms and root forms) has one
home, the enum in `api.schema.json`, which the loader reads (`closed`); the layers are `api.json`'s own `layers`
list, with its `registry layer` (the error groups and the diagnostic code type) and its `adapter layer` (the one
whose concepts may sit in an adapter module). Every emitter, the docs tables and the stub loop over that list, and
`tools/gen-api.py --check` renders a schema copy with one more layer to prove each emitter gives it a module.

```text
type      = union
union     = postfix { " or " postfix }
postfix   = primary { "[]" }                            a list, in order
primary   = "(" type ")"
          | "function" [ " of " item { " and " item } ] " to " postfix
          | [ "writable " ] "map of " item [ " to " item ]            one argument: text keys
          | name [ " of " item { " and " item } ]                     type arguments of a generic concept
item      = a postfix that is not a function, map or generic with arguments, unless in parentheses
name      = "text" | "integer" | "number" | "boolean" | "nothing" | "absent"
          | a concept | a kind list | "diagnostic code" | an error group | a type parameter in scope
```

A name a type can use holds no word of the grammar (`or`, `of`, `to`, `and`, `map`, `function`, `writable`,
`tuple`), so a type parses one way: the loader refuses a concept, kind list or type parameter named so, and an error
group named so (`index out of range`, a program bug's class) is simply not a type name. Two more rules keep every
form reading one way: an `or` straight after a function's result or a map's value is refused (write `function to
(text or absent)` or `(function to text) or absent`), and an item of an `of ... and ...` list that takes arguments
itself (a generic, a function, a map) must be in parentheses (`block of (resolution of text) and directive`).

Examples: `written block or absent`, `(resolution of snippet line)[]`, `map of directive to address`, `function of
directive to (text or absent)`, `block of statement and written directive`. `absent` is a type, so "may be absent" is
part of the type (`statement or absent`), not a flag beside it. A map keeps insertion order in every binding.

Prior art: the Language Server Protocol's `metaModel.json`, which describes LSP's types as data (`or`, `array`,
`map`, `reference`, `base` kinds) for its TypeScript, Python, Rust and C# generators. knobly writes the same tree
as short text because the owner reads the schema; the loader parses it into the metaModel's shape.

The loader also checks what a shape check cannot see:

- every name resolves, in the right scope (a type parameter only inside its concept or member), and takes exactly as
  many type arguments as it has type parameters (none for a kind list, an error group, a builtin or a type
  parameter);
- **the layer direction** (spec 5): a member type names only its own layer or one its layer may import, so the low
  level cannot name a rendered type even in a signature;
- every union's variants cover its kind list (less `except`), each variant names its union, each kind list's
  `variants` map back;
- the error groups form a tree on spec 2.8's two sorts: every expected outcome under the base, no program bug under
  any group, each root with a per-language base;
- every option parameter has an options record, every trait is from the closed list, every limit a message names
  exists, every `found by` is from its closed list;
- no two public names derive the same identifier in one namespace, no concept lists a member twice or has two that
  spell one identifier in either casing, and no kind list has two values that do (the casing rule stays one-to-one);
- an error group's template names a field that is a list (its items are joined), or `<field> message`;
- a pattern is an **I-Regexp** (RFC 9485, the interoperable regex subset) between `^` and `$`: no shorthand class
  (`\s`, `\w`, `\d`, `\b`: write the class out), no backreference, lookaround, lazy quantifier or inner anchor, and a
  character outside printable ASCII written as itself (a JSON escape), not as a regex escape. Each emitter renders
  it in its engine's dialect (RFC 9485 section 5: `.` as `[^\n\r]`, each such character as the engine's escape);
  an emitter whose engine lacks a construct the subset has (Python's `re` has no `\p{..}`) refuses it there.

Each check is planted: `tools/gen-api.py --check` breaks a copy of the schema 29 ways (an unresolved type, a broken
type, a layer-direction breach, a free-text type, a missing variant, a wrong kind, a bad parent, a bug under the
base, an unknown trait, a spelling collision, an unknown found-by, a bad protocol type, three wrong type-argument
counts, a grammar word in a name, a member spelling collision, a member listed twice, a kind value collision, two
patterns outside the subset, a template on a non-list, a bead id, a milestone and a language's name in a doc, a
milestone in a protocol doc, a bead id in a parameter doc, a union after a function's result, a generic in an
argument list) and a copy of an emitter's `Language` 4 ways (a root error group without a class, a left-out
concept still in use, an unknown module, a kept native type without a platform type), and fails unless each is
refused, the newer ones for their own reason. `tools/api/validate.py` does the same for the JSON Schema (a
per-language spelling, a per-language error base, a language list, a `note` in place of `doc` in `api.json` and
in `protocol.json`, a free-text type, an unknown trait, a `spell` note, an unknown found-by).

## 3. Idiom as typed traits, spellings derived

The schema stores no binding spelling and names no language. Every identifier is derived from a spec name by the
casing rule (binding
guide rule 1), written once in `tools/api/loader.py` (`words`, `pascal`, `camel`, `snake`, `upper_snake`) and used by
every emitter, the names module and the adapters' spelling table: types `PascalCase` in both (no prefix: rule 2);
members `camelCase` / `snake_case`; enum members `PascalCase` / `UPPER_SNAKE_CASE`; constants `UPPER_SNAKE_CASE`.

Where the languages' idioms differ, the schema says what the member **is**, from a closed list, and each emitter
knows its language's form. Milestone 5's 31 prose `spell` notes are gone. Each binding's column below is its
emitter's `trait_forms` and its other `Language` facts (a members table, section 6).

<!-- generated: members: traits (tools/gen-api.py docs) -->
| Trait or field | TypeScript | Python | C++ | Means |
|---|---|---|---|---|
| `trait: people form` | `toString()` | `__str__` | `to_string(x)`, a free function (`<knobly/format.hpp>` adds `std::format` and `<<`) | the text a person reads (contract 2) |
| `trait: iterate` | `[Symbol.iterator]()` | `__iter__` | `begin()` and `end()`: a range | the items in order |
| `trait: count` | `length` | `__len__` | `size()` | how many |
| `trait: index` | `at(i)`, absent out of range | `__getitem__`, `IndexError` out of range | `at(i)`, `index_out_of_range` out of range | the item at an index |
| `trait: walk` | `walk(visit)`, callback returns `WalkControl` | `walk(*, descend=None)`, a generator | `walk(descend)`, a `walk_view` range; `descend(item)` says whether to enter its block | depth-first visit (spec 7.5) |
| `trait: collect` | `collect(read)` | `collecting()`, a context manager | `collect(read)`, returning `std::optional` | run reads, record a diagnostic error |
| `io: true` | returns a `Promise` | a plain call | a plain call | goes through a port |
| `passed: keyword` | positional | keyword-only | positional | an argument named at the call |
| `passed: option` (with the member's `options` record) | one options object (`load(path, { overrides })`) | keyword-only (`load(path, *, overrides=None)`) | an options aggregate (`load(path, {.overrides = ...})`) | an optional setting |
| `factory` (`{"of": concept}`; the form is the emitter's `factory_forms`, default `constructor`) | `knobly(...)`, `new Diagnostics(...)` | `Processor(...)`, `Diagnostics(...)` | `processor(...)`, `diagnostics(...)` | how a concept is made |
| `nature: named type`, `brand` | a branded string | a `NewType` of `str` | a class of its own holding the text (`config_text`) | a string with its own type (spec 6.9) |
| `nature: named type`, `template` | a template literal type (`${string}/${string}`) | `str` | a class checked when made (a `program_code` literal is checked at compile time) | text of a stated form (`{text}/{text}`; the `pattern` checks it at run time) |
| `nature: named type`, `is: native` | `platform fetch`: `typeof globalThis.fetch` | none | none | the platform's own type: the emitter's `LANGUAGE.native`; the loader refuses a kept native type without one, and a binding that keeps no native type leaves out the module that holds them |
| list `[]` | `readonly T[]` | `tuple[T, ...]` as a result, `Sequence[T]` as a parameter | `knobly::sequence<T>`, an immutable shared list | in order |
| `map` | `ReadonlyMap` as a result, `Readonly<Record>` as a parameter or an options record's property (`writable`: `Record`) | `Mapping` (`writable`: `MutableMapping`) | `knobly::ordered_map<K, V>` (`writable`: held by `std::shared_ptr`, shared with the caller) | keyed, ordered |
| `module` (`files`, `fetch`, `include`; the path is the emitter's `modules`) | `files`: `knobly/node`, `fetch`: `knobly/browser`, `include`: `knobly/include` | `files`: `knobly.files`, `fetch`: none, `include`: `knobly.include` | `files`: `knobly::files`, `fetch`: none, `include`: `knobly::extensions` | an adapter module, named for what it holds; a module the emitter leaves out does not exist there, nor its functions and concepts |
| what a binding leaves out (the emitter's `omit`, and any module it does not map) | nothing | `load options`, `processor options`, `key options`, `walk control`, the `fetch` module | `walk control`, the `fetch` module | exists in some bindings only (a left-out module takes its functions and concepts with it) |
| a trait's own public names (the emitter's `trait_names`) | none | `Collecting` | `sequence`, `ordered_map`, `walk_view` | a class or type a trait's idiom adds, public beside the concept with the trait |
| a root error group's class (the emitter's `error_roots`) | `knobly error`: `Error`, `detached error`: `ReferenceError`, `argument type error`: `TypeError`, `misuse error`: `Error`, `index out of range`: `RangeError` | `knobly error`: `Exception`, `detached error`: `ReferenceError`, `argument type error`: `TypeError`, `misuse error`: `ValueError`, `index out of range`: `IndexError` | `knobly error`: `std::runtime_error`, `detached error`: `std::logic_error`, `argument type error`: `std::logic_error`, `misuse error`: `std::invalid_argument`, `index out of range`: `std::out_of_range` | the root's base, or the language's own class (spec 2.8's and contract 4.2's generated tables) |
| the argument type error's message (the emitter's `argument_type_message`; the schema keeps its rule and placeholders) | `{member}(): argument "{parameter}" must be a string, not {got}; knobly edits take config text: quote() a program string, text() one already written as knobly text, String() a number first` | `{member}() argument '{parameter}' must be str, not {got}; knobly edits take config text: quote() a program string, text() one already written as knobly text, str() a number first` | `{member}(): argument '{parameter}' must be a live object, not {got}` | a whole sentence, because it names the language's own conversion and type words (spec 6.9's generated table) |
<!-- end generated -->

Python methods take their parameters positional-only (`/`): a hand-written class that also accepts them by keyword
still satisfies the Protocol, so the generated signature never forbids what a binding allows.

Layout is not idiom an emitter carries: each `Language` names its language's standard formatter (`formatter`, a
`Formatter`: the suffix of the files it takes and the commands that run it), and the generated files go through it
before they are written (section 4). An emitter writes each statement plainly and deterministically, and wraps only
what no formatter splits: docstrings, doc comments and long string literals, to the line length. Owner, 2026-10-30, Q3
of the C++ review page: "A", run each language's standard formatter on generated code, pinned to exact versions,
instead of hand layout in emitters.

### Docs and rationale

Each concept, member, parameter, kind list, error group and free function, and each protocol shape and request
(whose request carries a `doc` and a `params doc`), carries a `doc` and an optional `rationale`. The `doc` is for the
binding's users: each emitter writes it as the declaration's doc comment (JSDoc, a docstring), as a sentence
(capitalized, ending in a stop), and it reaches every binding, so it says what the thing is and does, in spec terms:
what it returns or raises, and an example where one helps. A member's or free function's comment
also holds its `order` ("Order: walk order."), each parameter's doc (`@param`; a docstring's `Args:` section; the walk trait's parameter differs per binding, so its
doc is the emitter's: TypeScript's `visit` and Python's `descend` say how to skip a block and how to stop) and each
error group in its `errors` (`@throws {ReadError}`; `Raises:`). An `errors` entry is a group's name, or
`{"group", "when"}` saying why this member raises it; the comment gives the entry's `when`, else the group's `raised
when`, so a catch-all group (argument type error, misuse error) states the member's own case, not every case the
group covers. A doc that names an error group must list it in `errors` or return it (a port's members, which the
program implements, aside): the loader refuses one that does not, so the emitted `Raises:` and `@throws` never leave
out an error the doc promises. An error class's and a kind list's comment holds the group's or list's `doc`.
**Every concept, member, free function and kind list has a doc**: the loader refuses one without (each form planted
in `tools/gen-api.py --check`), so nothing ships undocumented; a parameter's doc stays optional (the member's doc names its parameters). The `rationale` is for the people who maintain the schema: history (renames, what a milestone
changed), the owner's words, bead ids, and anything true of one language only. No emitter reads it.

The loader refuses, in every text an emitter writes as a doc (each `doc`, `params doc` and `order`, an error group's
`raised when`, a constant's `means`, a code's `meaning`), a bead id (`kno-` and three characters), `milestone N`, an
`owner, <date>` quote and the name of any emitter's language (`TypeScript`, `Python`): each is planted in
`tools/gen-api.py --check`. The hand-written public docs are held to the same rule by each binding's name test
(`test_public_docs_carry_no_history`; TypeScript's "public docs carry no maintainer history"), which reads every doc
a program sees on hover or in `help()` and refuses those words, a private module path and a test path: maintainer
notes go in comments.
Prior art: the split between API reference text and design notes in an architecture decision record, and Smithy's
`@documentation` trait beside comments that never reach generated code.

**The schema's doc is the one home of each public doc**: no hand-written class, member or function carries a doc
the schema has. What a program reads is the generated doc, in each binding:

- **TypeScript:** the public types are the generated interfaces, so hovering any member shows its doc, and a
  hand-written class member that implements one inherits its doc in the language service (a class member with no
  JSDoc of its own takes its interface's). Each public function and constructor is a constant typed by its generated
  signature (`export const parse: SyntaxFunctions["parse"] = parser.parse`; `export const Diagnostics:
  DiagnosticsConstructor`, beside `export type Diagnostics`), so hovering a call shows that signature's doc, in the
  built declarations too. A union's doc is on its type alias. The names test ("public declarations carry the
  schema's docs") reads every export of every entry and every member of an exported interface through the compiler
  API and fails on one without a doc.
- **Python:** each hand-written public class subclasses its generated Protocol, and `knobly._docs.document`,
  called at the end of each public module, gives the class, and each function or property it implements, its
  Protocol's docstring, and gives each public function and constructed class's `__init__` the docstring of its
  `<Module>Functions` or `<Class>Constructor` Protocol (`_api/docs.py` names them by dotted path, imported only for
  the module being documented, so the table breaks no layer direction). Prior art: numpy's `add_newdoc`, which gives
  functions their docstrings from a table at import; a docstring the hand-written code already has is kept, so the
  names test sees it. `help()` and `__doc__` then show the schema's doc. A generated record (a frozen dataclass) is
  slotted by hand: its `__slots__` is a dict from each field to its doc, which `help()` and `inspect.getdoc` show for
  the field (a `slots=True` dataclass's slots cannot hold one), and it extends `SlottedRecord`, whose `__reduce__`
  copies and pickles it field by field as `slots=True` would have. The names test
  (`test_public_docs_are_the_schema_docs`) compares every public class's, member's and function's doc with its
  Protocol's and fails on any of them whose source holds a docstring, even one that copies the schema's word for word;
  `test_generated_records_show_their_field_docs` fails on a generated record or field without a doc.

## 4. What each emitter generates

**TypeScript** (`ts/src/gen/api/`, git-ignored, typechecked, not linted; `ts/conformance/shapes.ts`, git-ignored,
typechecked and linted with the adapter):

| Module | Holds |
|---|---|
| `kinds.ts` | every kind list as an `as const` object plus the union derived from it (spec 2.10); `Keyword`, `STATEMENT_OF_KEYWORD`, `statementOfKeyword(word)` |
| `codes.ts` | `DiagnosticCode` (`as const` object and union), `MESSAGES`, `CODE_FACTS` (name, layer, found by, reason, typed per code), `ReasonOf<C>`, `describe(code, detail?)` |
| `limits.ts` | the rules module: `MAX_NESTING`, `MAX_EXPANDED_NESTING`, `MAX_DEPTH`, `MAX_DIRECTIVES`, `MAX_SAFE_INTEGER`, `RESERVED`, `VARIABLE_NAME`, `PROGRAM_CODE` |
| `errors.ts` | the error class tree (spec 2.8): each class's base, fields, constructor, message and `name`; `argumentTypeMessage(member, parameter, got)` |
| `shared.ts`, `syntax.ts`, `io.ts`, `written.ts`, `rendered.ts` (one per layer `api.json` lists) | per layer: one interface per handle, port, record and snapshot; each union's shared members once on `<Union>Common`, which each variant extends with `kind` a literal; union types; callback types; options objects; the generic `Block<TItem, TDirective>` (a block that adds nothing is a type alias of it); a `<Module>Functions` interface per import path listing its free functions, which types each public function; a `<Class>Constructor` interface (`new (...)`) per constructor factory, which types each public constructor |
| `ts/conformance/shapes.ts` | every request, result and dump of the adapter protocol as a type; `PROTOCOL`; `SPELLING` (each spec name the driver sends, in camelCase); `ERROR_GROUP_OF_CLASS` |
| `ts/test/api-contract.ts` (git-ignored, typechecked by `tsc -p test`) | `PUBLIC_NAMES` (every public name per import path, values and types apart), outside `src/`, so the published package never ships it |

**Python** (`py/src/knobly/_api/`, git-ignored, checked by ruff and `mypy --strict`; `py/conformance/shapes.py`
and `py/tests/api_contract.py`, git-ignored, checked the same). The generated files go through ruff before they are
written, as ruff's docs order it: its import sorting (`ruff check --select I --fix`), then `ruff format`, both with
`py/pyproject.toml`'s settings, so `ruff check` and `ruff format --check` pass on them as on hand code.

| Module | Holds |
|---|---|
| `kinds.py` | every kind list as a `StrEnum`; `Keyword`, `STATEMENT_OF_KEYWORD`, `statement_of_keyword(word)` |
| `codes.py` | `DiagnosticCode`, `MESSAGES`, `CodeFacts`, `CODE_FACTS`, `Described`, `describe(code, detail=None)` |
| `limits.py` | the rules module, as TypeScript's (patterns end in `\Z`, the text's end) |
| `errors.py` | the error class tree; `argument_type_message(member, parameter, got)` |
| `shared.py`, `syntax.py`, `io.py`, `written.py`, `rendered.py` (one per layer `api.json` lists) | per layer: a `Protocol` per handle, port and interface (variants with `kind: Literal[...]`, and the schema's `__match_args__`, which a class implementing it inherits); a frozen `@dataclass` per plain record or snapshot, slotted by hand with a `__slots__` dict of each field's doc, extending `SlottedRecord` (only properties: `eq=False` for a snapshot, field order the match args, `match_args=False` and an explicit `__match_args__` when the schema's are fewer than the fields, a fixed `kind` as a property); each member's doc as its docstring; callback `TypeAlias`es; a union `TypeAlias` only over generated records (`Change`); `ConfigText`; the generic `Block` Protocol (the index trait states `Sequence`'s read methods); a `<Module>Functions` Protocol per module and a `<Class>Constructor` Protocol (`__call__`) per constructor factory, whose docstrings the public functions and constructors take (section 3). Every annotation that names a concept the binding implements by hand names its public class (below) |
| `docs.py` | `FUNCTIONS` (each public module's `<Module>Functions` Protocols) and `CONSTRUCTORS` (each constructed class's `<Class>Constructor`), by dotted path: what `knobly._docs` reads (section 3) |
| `record.py` | `SlottedRecord`, the base of every generated record: its `__reduce__` copies and pickles a record slotted by hand (section 3) |
| `py/conformance/shapes.py` | the protocol's `TypedDict`s, `PROTOCOL`, `SPELLING` (in snake_case), `ERROR_GROUP_OF_CLASS` |
| `py/tests/api_contract.py` | what the tests check the binding against, every type named through its public module: `PUBLIC_NAMES` (each module's `__all__`), `MATCH_ARGS`, `UNIONS` (each public union's variant classes); and a type checker's block (`if TYPE_CHECKING:`) that mypy checks and nothing runs: each module assigned to its generated `<Module>Functions`, each constructed class to its `<Class>Constructor`, and each hand-written public class (a handle, or a snapshot or record with methods) to `type[<its generated Protocol>]`, so a member that drifts from the schema fails mypy even in a class that forgot to subclass its Protocol |

**C++** (`cpp/include/knobly/`, every header directly in it generated and git-ignored; `cpp/conformance/shapes.hpp`
and `cpp/tests/generated/`, git-ignored). Header-only: every type is spelled fully qualified from `::knobly`; every
name follows the standard library's casing (snake_case, template parameters PascalCase); a member that would share
its class's name, own or inherited, takes a trailing underscore (`written::index::index_()`, `written::list::list_()`).
What the generator writes whole is inline in the header; every free function and every handle's or snapshot's member
is declared `KNOBLY_API` and defined by the hand code in `detail/` (inline in header-only mode; compiled once in
compiled mode, through `implementation.hpp`). The generated files go through the pinned clang-format with
`cpp/.clang-format`.

| Header | Holds |
|---|---|
| `kinds.hpp` | every kind list as `enum class <name> : std::uint8_t` in namespace `knobly` (token kinds keep the grammar's names, in grammar order; the others snake_case) and a `constexpr to_string` per list giving the spec's value; the generated parser includes it |
| `codes.hpp` | `enum class diagnostic_code : std::uint16_t` (each value its code's number), `to_string(code)` (`"E1001"`), `message(code)`, `code_facts` and `facts_of(code)`, `described` and `describe(code)` / `describe(code, detail)` |
| `limits.hpp` | the limits and the reserved names as `inline constexpr` values, each in its layer's namespace (`knobly::syntax::max_nesting`, `knobly::written::reserved`) |
| `errors.hpp` | the error class tree (spec 2.8): each class under its parent or its root's standard class (`std::runtime_error`, `std::logic_error`, `std::invalid_argument`, `std::out_of_range`), with default visibility, a constructor taking the message (when given) then its fields, a `const` accessor per own field, the message built from the template; `detail::argument_type_message`. The classes hold the shared layer's records, so `knobly.hpp` includes it after them |
| `knobly.hpp` (the package's layers: shared, io), `syntax.hpp`, `written.hpp`, `rendered.hpp` (one per layer with its own namespace) | per layer, in its namespace: an immutable class per record (one constructor taking its fields in Python's dataclass field order, a `const` accessor per property, defaulted `operator==`); a view class per handle and snapshot (one `detail::view`, members declared for the hand code, `const` throughout), a union's view class with `kind()`, `as<V>()` and `visit(f)` and each variant deriving from it (a record union too, so a sequence of it never slices); an abstract class per port, held as `std::shared_ptr`; a C++20 `concept` per interface; an aggregate per options record; `using` aliases for callbacks (`std::function`) and for a block that adds nothing (`block<Item, Directive>`, the hand-written support template); `config_text` (made only by `quote` and `text`) and `program_code` (a literal checked at compile time); each pattern's `constexpr` matcher over code points (`knobly::is_program_code`, `written::is_variable_name`); each people form as a free `to_string` found by argument-dependent lookup; the free functions, a trailing optional parameter or options record as an overload without it; each layer's `detail/<layer>/definitions.hpp` at the end in header-only mode |
| `files.hpp`, `extensions.hpp` (one per adapter module the binding has) | the module's free functions in `knobly::files` and `knobly::extensions` |
| `format.hpp` | opt-in, written whole: for every type with a `to_string` (each people form, each kind list, `diagnostic_code`) a `std::formatter` (formatting the `to_string` as a string, so width, fill and alignment apply) and an `operator<<` in the type's namespace, both calling that `to_string` |
| `implementation.hpp` | compiled mode's one implementation file: every public header, then every `detail/<x>/definitions.hpp` (the schema's layer list) |
| `cpp/conformance/shapes.hpp` | `adapter::shapes::protocol`, `spelling(spec_name)` (snake_case), `error_group_of(exception)` (the most specific group first) |
| `cpp/tests/generated/api_contract_<header>.cpp` | a `main` that odr-uses every hand-defined function and member of one header through volatile function pointers, so a declaration without a definition fails to link |
| `cpp/tests/generated/layers_<header>.cpp` | the layer-direction check: the include guards of every header the header's layers may not import (and of every adapter module's header) defined first, so a forbidden include leaves its names undeclared and the file fails to compile |

How a binding uses them (frozen-m6.md has the per-file list):

- **TypeScript:** each layer's public entry (`knobly/syntax`, `knobly/written`, `knobly/rendered`, and
  the package root for the shared and io layers) re-exports the generated interfaces as its public types; each
  hand-written class `implements` its interface, so a drifted or missing member is a compile error. The
  hand-written interface files go.
- **Python:** each hand-written handle class subclasses its generated `Protocol` (PEP 544's explicit form, so mypy
  checks every member at the class), and `api_contract`'s type checker's block checks it structurally too, from the
  schema's list of concepts, so no test keeps a hand list of classes or modules to check; records and snapshots are the generated dataclasses, re-exported; the error
  tree, kinds, codes and rules are imported from `_api`. **The public types and the generated types are one**
  (milestone 7): wherever a generated annotation names a concept the binding implements by hand (a Protocol
  concept, or a union over them), it names the binding's public class, `knobly.rendered.Directive`, imported for
  the type checker only (`if TYPE_CHECKING: import knobly.rendered`; the cycle exists only for the checker, PEP
  563 keeps annotations unevaluated). A concept the generator writes whole (a record, a named type, a callback, a
  union of records) is named by its generated class, which is the public one. So `def key(d: rendered.Directive)`
  is a `rendered.KeyRule`, a record's field read into a function annotated with a public class needs no narrowing,
  and a hand class returns and takes its own public types. Where the module runs a name (a base class, a callback
  alias's parameters), it stays the generated class or a string. A union over the binding's own classes
  (`written.Statement`) is written by hand and is the only one: the generator writes no second union of the same
  name, and the names test compares its members with `api_contract.UNIONS`, by class identity. A module is checked
  against its `<Module>Functions` Protocol (`_syntax_functions: knobly._api.syntax.SyntaxFunctions = knobly.syntax`, mypy's
  modules-as-protocols), and a constructed class against its `<Class>Constructor`, both in `api_contract`'s
  generated type checker's block. Nothing outside the package (tests, adapter, docs) imports `knobly._api`, but
  for that block, which imports the generated Protocols for the type checker only. Every
  implementation module is private (`_model.py`), so each name has one import path (rule 9).
- **Both:** the public-name test is one comparison per import path, both ways, against `PUBLIC_NAMES` (TypeScript
  reads a module's exports, types included, through the compiler API; Python compares `__all__`). Test-only tables
  live on the test side in both: `PUBLIC_NAMES` in the generated contract beside the tests, `ERROR_GROUP_OF_CLASS` in
  the adapter's generated shapes; nothing in either package ships them. The adapters read `SPELLING` and
  `ERROR_GROUP_OF_CLASS` instead of writing the casing rule or matching class names by regex.

Prior art for the Python choice: typeshed's and `lsprotocol`'s practice of annotating with the concrete public
classes a package exports, with `TYPE_CHECKING` imports for cycles (PEP 484, "Runtime or type checking?"). The
alternative, making the Protocols the public names, was rejected: `match` and `isinstance` need the binding's
classes, and two public types per concept is the confusion this removes.

### Formatting the generated code

After an emitter renders a binding, `tools/gen-api.py` hands every file to the binding's formatter
(`tools/api/formatter.py`): it writes them into a fresh temporary folder, runs each command of the `Language`'s
`Formatter` once over all of them from the repository root, and reads them back, so each finished file still moves
into place in one step. Each formatter is pinned to an exact version where its binding pins its tools, so the output
is byte-identical between runs, and a formatter upgrade is a generator change:

| Binding | Formatter | Pinned in | Run as |
|---|---|---|---|
| TypeScript | Prettier, its defaults with a print width of 120 (`--no-config`: the options are the emitter's, and the hand-written code's editors pick up none) | `ts/package.json` and `ts/pnpm-lock.yaml`, exact | `ts/node_modules/.bin/prettier`, installed by `pnpm install` |
| Python | ruff (import sorting, then `ruff format`) | `py/pyproject.toml` and `py/uv.lock`, exact | `uv run --project py --locked ruff`, with `--config py/pyproject.toml` |
| C++ | clang-format, `cpp/.clang-format` (Google style, a column limit of 120, C++20) | `CLANG_FORMAT` in `tools/api/emit_cpp.py`, as a PyPI wheel version, exact (the `clang-format` package ships the binary, so no system install) | `uv tool run --quiet --from clang-format==<version> clang-format -i --style=file:cpp/.clang-format` |

A new binding adds its formatter the same way: one `Formatter` in its `Language` and nothing in `tools/gen-api.py`.
`tools/gen-api.py --check` renders without formatting, since it checks the schema and the emitters, not the layout;
the bindings' builds format, and their linters check the result.

**The one exception to `tools/`' standard-library rule:** `tools/` is Python 3.9 standard library only, and its one
exception is invoking these pinned formatter executables (as subprocesses, through `uv` and the binding's
`node_modules`): building a binding needs its own toolchain anyway, Node for TypeScript and uv for Python.

## 5. The adapter protocol

`protocol.json` holds every request (parameters, which are optional, the result, the level), every result and dump
shape (fields, fields by `kind`, tuples, exactly-one-of), the edit members and the readers. Its types use the same
grammar with the wire's own atoms (`text`, `integer`, `number`, `boolean`, `json`, `id`, `null`, `position`), quoted
literals (`"utf-16"`) and `tuple of A and B`. Keys are the wire's own spellings (`savedText`, `includedBy`): data,
not a binding's names. spec/conformance.md 4.1 and 4.2 are generated from it; each request's prose (`params doc`,
`doc`) and each shape's `doc` stay with it, under the same rule as every emitted doc (section 3; history goes in
`rationale`), and the loader refuses a `params doc` that does not name each parameter.

A shape with fields `by kind` lists the rest of its kinds as `other kinds`, and is generated as a discriminated
union: one alternative per kind with that kind's fields required (TypeScript object types; a `TypedDict` per kind in
Python). The driver does not yet check every dump against these shapes (spec/conformance.md 7); the generated types
make an adapter's dumps checked by its own compiler instead, a missing per-kind field included.

## 6. The docs tables: the one committed output

Generated between `<!-- generated: NAME (tools/gen-api.py docs) -->` and
`<!-- end generated -->`: the code registry in spec 2.4, the rules list in spec 2.5, the error groups in spec 2.8,
the class tree in contract 4.2, the glossary's names per layer, the error-code table in docs/site/pages/diagnostics.md, and the
adapter's requests and dumps in spec/conformance.md 4.1 and 4.2. They are committed, unlike the code, because GitHub
shows the spec and READMEs as they are, and the user guide's site is built from its pages as written. `python3 tools/gen-api.py docs` rewrites them and
`tools/check.sh` fails when one is stale, so no table can drift from its source (round 15 found three copies of the
code table disagreeing on 8 of 32 meanings and 14 of 32 found-by entries). Prior art: `cog` and the "generated
section" markers of rustfmt's and Prettier's option docs.

**Members tables.** A hand-written page's table with a column per binding (the processor, readers, addresses and
sources tables, the graph, document and variable members, errors and writers tables in the user guide's pages under
docs/site/pages/; README.md's entry points; section 3's trait table) is generated too, between
`<!-- generated: members: NAME (tools/gen-api.py docs) -->` and `<!-- end generated -->`. Its rows' one home is
`docs/tables.json`, keyed by NAME: `{"file": page, "first": [the column before the bindings], "last": [the columns
after], "rows": [...]}`. Each row has `what` (the first column), `ref` (a schema name, or a list of them joined with
commas), `last` (the cells after the bindings), and may have `receiver` (written before a member: `graph.read()`),
`names` (an entry point's exports, listed after its path) and `cells` (by binding key: the text for that binding only,
where the schema cannot spell it). A `ref` is `<concept>.<member>` (spelled by `member_spelling` or `function_case`; a
property through `property_form`, a method with its parameters through `call_params`, a trait member through
`trait_forms`), `<concept>`, `<free function>` (its call and import path), `<error group>` (its class and the fields a
program reads), `<kind list>`, `layer: <layer>` or `module: <module>` (an import path; a bare name too when it names
nothing else), or `trait: <trait or field>` (section 3's table: `trait_forms`, or the binding's own `factory_forms`,
`native`, `modules`, `omit`, `trait_names`, `error_roots` and `argument_type_message` for `factory`, `native`,
`module`, `omit`, `names`, `error roots` and `argument type message`). A `ref` naming nothing, or two things, fails
`tools/gen-api.py docs` and `--check`, so a renamed member cannot leave a stale row; the third-binding stub gets a
column in every members table, and `--check` asserts it. Each hand `cells` entry is a cost: today four, all in the
addresses table (the people form called on an address in each of the three bindings, which a trait's documentation
text does not spell as a call, and Python's hashable `Address`).

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
it (`emit_ts.py`, `emit_py.py`, like `protoc-gen-<lang>` plugins). A new binding adds one emitter and no schema data (section 10). Its data model follows the **LSP `metaModel.json`** (a typed, language-neutral description that feeds
`vscode-languageserver-types` and `lsprotocol`), its traits follow **Smithy traits** (facts about a shape that each
code generator reads its own way), and the registry follows TypeScript's `diagnosticMessages.json` and Babel's
`@babel/types` definitions, both generated into declarations and docs.

Why not one of those tools as is:

| Tool | Why not |
|---|---|
| JSON Schema or OpenAPI generators (quicktype, openapi-generator, datamodel-code-generator) | They generate data shapes: no methods, handles, ports, generics, traits or error trees, and they own the output's idiom. The JSON Schema is used for what it is good at, checking the schema files' shape (`api.schema.json`) |
| Smithy | A service model (operations over a network) with a Java toolchain; knobly's API is in-process handles. Its trait idea is used |
| Protocol Buffers | Wire messages with a runtime library each binding must ship, against the owner's no-third-party-dependency rule (2026-10-25). Its plugin architecture is used |
| TypeSpec | Its core is protocol-neutral, but a custom emitter is written in TypeScript against its compiler, a Node toolchain for the Python-only `tools/`, and the per-language idiom would still be written by hand in each emitter |
| LSP metaModel generators | Written for LSP's own model (requests and notifications), not reusable outside it. Its model shape is used |

So the bespoke part is small: about 1,400 lines of loader and 640 to 1,000 lines per emitter, in Python's standard
library (the same toolchain as the driver and the grammar checks; the pinned formatters it runs are section 4's one
exception), for a schema of 78 concepts, 10 kind lists, 34
codes and 13 protocol requests.

## 10. A new binding

A new binding is **one emitter, one adapter and one name test** (binding guide section 5), with no edit to
`spec/schema/` (which names no language), to the loader or to the docs emitter. Every file it touches:

- `tools/api/emit_<lang>.py`, rendering the loader's model in the language's idiom (each trait of section 3, the
  casing rule's output, the error tree, one module per layer of `api.json`, the protocol shapes), with `render`,
  `render_shapes` and `render_contract`, and its `LANGUAGE`: the loader's `Language` descriptor, which holds every
  fact about the language:
  - `key`, `name`, `sep` (between module parts), `function_case`, `code_case` (a diagnostic code's member),
    `public_kind` (a type, a value or both), and `trait_names` (the public names a trait's idiom adds, as Python's
    `Collecting`);
  - `error_roots`: each root error group (one without a parent) to the class it extends, `{"base": ...}`, or is,
    `{"builtin": ...}` (spec 2.8); every root must be given and nothing else;
  - `argument_type_message`: the argument type error's whole sentence, with `{member}`, `{parameter}` and `{got}`;
  - `modules`: each adapter module it has (`files`, `fetch`, `include`, the closed list in `api.schema.json`) to its
    import path under the package; a module left out does not exist there, nor its functions and concepts;
  - `factory_forms`: how it makes a concept a factory function makes (`constructor`, the default, or `package
    function`);
  - `native`: the platform's own type for each native named type it keeps;
  - `omit` and `omitted_as`: a concept or kind list its idiom has no use for (Python leaves out the options records
    and `walk control`), and what the glossary says stands in for it;
  - how the docs tables spell it: `enum_form`, `generic`, `construct`, `extends_word`, `cause_field`, and for the
    members tables (section 6) `trait_forms` (the documentation text of every trait the schema uses and of each
    typed field section 3's table lists; the loader refuses a language missing one), `property_form` (a property
    read: its name; C++ an accessor call) and `call_params` (a call's parameters, given each one's name, how it is
    passed and whether it is optional). Every docs table builds one column per `Language`, so the binding is a column
    with no edit to `emit_docs.py` or `docs/tables.json`;
  - the hooks for a language whose names differ from the default, each defaulting to what TypeScript and Python
    spell: `type_case` (a type's public name: PascalCase; C++ snake_case), `constant_case` (a limit's or the reserved
    names': UPPER_SNAKE; C++ snake_case), `pattern_form` (a pattern's public name: the constant's; C++ a matcher,
    `is_<name>`), `member_spelling` (a member's identifier in a class, given the class's and the member's spec names:
    none; C++ appends `_` to a member spelled as its class; the loader refuses any member, own or inherited, that a
    language spells as its class's type name)
    and `kinds_in_package` (every kind list in the package's namespace rather than its layer's: C++, whose one
    `kinds.hpp` the generated parser includes). `Model.public`, the name-collision checks and the docs tables spell
    every name through them.
- Its regex dialect, in the emitter: a schema pattern is an I-Regexp (section 2); the emitter renders it (the
  loader's `pattern_body` does RFC 9485's mapping given the engine's escape for one character) and refuses a
  construct its engine lacks.
  - `formatter`: the language's standard formatter, pinned (section 4, "Formatting the generated code").
- `tools/gen-api.py` (`EMITTERS`, `OUT`: the code folder, the adapter's shapes folder, the test contract's folder)
  and `tools/gen.sh` (the output directory).
- The binding's name test, hand-written once against its generated contract (as `py/tests/test_api_names.py` and
  `ts/test/api-names.test.ts` are): each import path's exports against `PUBLIC_NAMES`, the match args and unions,
  and the public docs' hygiene. The list of names, modules, constructors and Protocols to check comes from the
  contract, so the test never changes when the schema does.

The loader checks each `Language` against the schema as it checks the schema: a root without a class, a class for a
group that is not a root, an unknown module or factory, a left-out concept that a kept member still uses, or a kept
native type without a platform type is refused, and `tools/gen-api.py --check` plants each. It also loads
`tools/api/stub.py`, a third binding in miniature (a made-up language with its own error classes and one adapter
module), beside the real ones: it renders one module per layer, every concept's members through a trivial printer
of every type form, the error tree, and every docs table with the stub as a third column. So a schema change that
would need a new binding to edit the schema, the loader or the docs emitter fails the check.

The adapter (spec/conformance.md 6) is then written against the generated shapes and spelling table.

Prior art: `protoc` plugins and Smithy code generators keep every target language's facts in the generator (a
plugin's options, a Smithy codegen's `symbolProvider`), never in the model; the LSP `metaModel.json` names no target
language either.

## 11. Costs

- The schema is bigger than the lists it was: every member is typed, and a change to a public signature is a schema
  change first. That is the point (the schema is the one home), but it is a step a binding author must not skip.
- Generated TypeScript variants extend `<Union>Common` (an extra name per union in `gen/api`, never exported).
- Python records are generated dataclasses: a hand-written record with private fields must move them out or become a
  handle with a Protocol.
- Behaviour is not in the schema: the spec and the shared cases still carry it.
- Each language's facts (which class each root error group extends, its adapter modules' paths, its factory forms,
  the argument type sentence, what it leaves out) are Python data in its emitter, not schema the owner reads; the
  generated tables in spec 2.8 and contract 4.2 still show them, from the emitters, so they stay reviewable.
- Python's generated Protocols and records name the binding's public classes, so the generated modules import the
  public modules for the type checker (a cycle mypy follows; at run time PEP 563 leaves the annotations as text, and
  `typing.get_type_hints` on a generated class needs the public module imported first). A generated union over hand
  classes no longer exists: the binding's union is the one, checked against `UNIONS`.
- A doc may not name a language, so a fact true of one binding only (TypeScript's template type for a program code)
  goes in `rationale` or the emitter, and no binding's users read it in their doc comments.
- A schema pattern is an I-Regexp: a character outside printable ASCII is written as itself in the JSON, so the
  pattern reads less plainly in `api.json` than a `\u` escape would (the generated rules list shows it escaped), and
  the subset has no shorthand classes.
- Two type forms need parentheses that once read without them (`function of directive to (text or absent)`).
- A doc is written once per concept member, so where one implementation serves two concepts' members (a written
  directive's and an extension line's `values`, `block` and `set`, one Python function each), the schema states the
  same doc twice: the names test fails when the two differ, since one function holds one docstring.
- Python gives its hand-written objects their docs at import (section 3): `help()` and `__doc__` show them, but a
  tool that reads the source without running it sees a public function's doc nowhere and a member's only through its
  Protocol; a hand-written frozen dataclass's field (a `slots=True` slot) cannot hold a doc, so its doc is its
  Protocol's property alone; a union alias (`written.Statement`) cannot hold one. A generated record's field doc is
  in its `__slots__` dict, read by `help()`, while an editor reads the attribute docstring under the field: the
  generator writes both from the one schema doc.
- In TypeScript a class's own doc is not inherited from its interface, so the one exported class, `Diagnostics`,
  is a constant typed by its generated constructor beside a type alias of its interface: hovering a call shows the
  constructor's doc, hovering the alias shows none. Likewise, hovering a public function's bare name or its import
  (`import { parse }`, `const f = parse`) shows no doc: the constant has none of its own, and its doc is on its
  generated call signature, shown on a call and in signature help.
- Every generation runs a formatter (section 4): building TypeScript needs `pnpm install` first (Prettier), and
  building Python runs ruff through `uv`. That is the one exception to `tools/`' standard-library rule. Each run
  starts the formatter once per command (under a second for each binding), and the layout is the formatter's, so a
  formatter upgrade changes generated code. Docstrings, doc comments and long strings are still wrapped by the
  emitter, since no formatter splits them. `--check` does not format, so a layout a formatter would refuse shows up
  in the binding's build, not in `tools/check.sh`.
- The driver checks dumps only as far as it reads them; the generated shapes move the rest of that check to each
  adapter's compiler, not to the driver (spec/conformance.md 7).
