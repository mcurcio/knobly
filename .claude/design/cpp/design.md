# The C++ binding: public API design, header-only revision

Status: for the owner's gate. Layer: **binding** (feature level). The concepts, operations, orders and errors are fixed
by `spec/` and `spec/schema/api.json`; this page decides only how they look in modern C++. Nothing here is locked until
the owner likes the user code in section 4 (2026-10-27: "Nothing is locked until I see user APIs that I like").

This revision answers the owner's pick of 2026-10-29: option A, **header-only with no ANTLR runtime**, "but with as
much auto codegen as possible to unify with typescript and python". It starts from `cpp-final.md` (the design revised after two
integrator reviews) and changes only what ANTLR or a compiled library drove; section "What changed for header-only"
lists every change. Everything else survived review and is carried over word for word.

Built against: an export of `main` (`spec/`, `spec/schema/api.json` version 3, `tools/api/`, `grammar/Knobly.g4`).
The parser part rests on a working probe, `design/rd-probe/` (section 1.5): a 653-line Python generator that turns
`Knobly.g4` into a header-only C++ lexer and parser, which reproduces all 168 syntax conformance cases byte for byte.

Earlier history: two integrators wrote real programs against the first draft (a rasl port with reload-on-change, and a
linter with quick fixes) and compiled probes of its shapes under AddressSanitizer; `cpp-final.md` took their findings,
and section 6 lists the ones refused, with the reason.

## The owner's goals this answers (quoted, not widened)

- 2026-10-29, asked whether the C++ binding can be header-only so knobly ships no libraries: he picked option A,
  header-only with no ANTLR runtime, "but with as much auto codegen as possible to unify with typescript and python".
- 2026-10-28: a "clean, easy to comprehend API design", "idiomatic in each language", "consistent across layers",
  and codegen "so we dont have to maintain n languages by hand".
- 2026-10-25: "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be
  optional extensions rather than core." The C++ binding now has **no run-time dependency at all** beyond the C++
  standard library: no ANTLR runtime, nothing to link. A test framework is a development dependency only (2.6).
- 2026-10-23: "Don't commit the generated code, just the source": the generated headers and the generated parser
  are made at build time from a git checkout and shipped inside the release source archive (2.5).
- 2026-10-28, on two bindings that mixed their inspirations: "They are trying to combine the inspirations rather than
  choosing one model" (binding guide goal 2). The one C++ model here: **every object the library hands out is a small
  value that shares ownership of what it shows** (a handle, a snapshot, a list, a map, a walk). Nothing the library
  returns can dangle, in any layer.

## What changed from the draft

| Draft | Now | Why (finding) |
|---|---|---|
| lists out as `std::vector`, maps as `ordered_map` with `at`/`find` returning references | lists out as `knobly::sequence<T>` and maps as `ordered_map<K, V>`: shared, immutable, cheap to copy; every element access returns **by value** | `field.values().at(0)` bound by reference was a heap-use-after-free in the draft's own example (ASan, both reviews) |
| `program_code` with a `consteval` constructor on a class owning a `std::string` | holds a `string_view`; a literal points at its static text, a run-time code at a shared owned copy | the draft form failed to compile for codes longer than the small-string buffer (review 1) |
| implicit `operator std::string_view()` on `config_text` and `program_code` | `view() const&`, the rvalue overload deleted | dangled on a temporary; let `config_text` slip into any `string_view` parameter (both reviews) |
| edits non-`const` ("deep const") | edits are `const` members (shallow const, as `std::span` and `std::shared_ptr`) | the draft's analogy was backwards and the rule cost `mutable` lambdas for no guarantee (review 2) |
| views hold an aliasing `std::shared_ptr` (two pointers) | one pointer to the node; the node's graph core carries an intrusive atomic count | half the size; same safety (review 1, partly taken: section 6) |
| a stale variant view raised `std::bad_variant_access` | raises `knobly::misuse_error` | `bad_variant_access` sat outside both error sorts (review 1) |
| misuse and index errors were plain `std::invalid_argument` / `std::out_of_range` | `knobly::misuse_error` and `knobly::index_out_of_range`, deriving from those | a program can tell knobly's apart from its own `std::stoi` or `vector::at` (review 1) |
| `std::formatter` and `operator<<` in the core header | opt-in `<knobly/format.hpp>` | keeps `<format>` out of every translation unit (review 1) |
| records had no constructors shown | every record has a public constructor | a linter must build its own `located_diagnostic` and `place` (review 2) |
| an optional trailing parameter as `std::optional<X> = std::nullopt` | an overload without it | `format_diagnostic(d)` and `directives()` read as plain calls (review 2) |
| an anonymous union whose arms are all variants of one union as `std::variant` | that union's view class | `place()`, `text()` and `kind()` without a `std::visit` (review 2, partly taken: section 6) |
| walk and block iteration rules unstated | stated: they own their data; an edit never invalidates them | range-for over `tree.block().walk()` and edits during a walk (both reviews) |
| a program built with `-fno-exceptions` "can still link" | it cannot use knobly; said plainly; Q2 is a real choice for that audience | review 1 |
| build from git as the main path | the release source archive (generated files included) is the documented path | game-studio consumption without Java or network (review 1) |

## What changed for header-only (this revision)

| `cpp-final.md` | Now | Why |
|---|---|---|
| the parser from ANTLR's C++ target, linked against the ANTLR 4.13.2 C++ runtime | a header generated from `grammar/Knobly.g4` by knobly's own parser generator (`tools/parser/`, Python standard library only), plus about 300 hand-written lines of recovery and error codes (1.5) | the owner's 2026-10-29 pick; the probe proves it on the whole syntax corpus |
| a compiled library (`src/*.cpp`), static or shared, hidden visibility | every definition is an `inline` function in `include/knobly/detail/`; an optional **compiled mode** compiles them once in one file of the program (2.5) | header-only; compiled mode is the established cure for header-only compile time (toml++, spdlog, fmt) |
| a CMake library target with the ANTLR runtime found or fetched at configure time | one CMake `INTERFACE` target, no dependency, no network | nothing to link |
| Java and Python to build from git | Python 3.9 or later only, standard library, no network | the generator replaces ANTLR's Java tool |
| two ANTLR runtimes in one static program collide (an ODR violation) | gone; the remaining case, two knobly versions in one program, is handled by a versioned inline namespace (2.5) | standard header-only practice (nlohmann/json, toml++) |
| ANTLR's own `CharStream` over a decoded `std::u32string` with an offset table | the generated lexer reads the UTF-8 bytes directly through the one decode function; positions are byte offsets with no table (2.4) | less code, one place for the UTF-8 rule |
| "exceptions are required": the ANTLR runtime threw inside the library | nothing inside the library needs exceptions or RTTI (the probe's parser is built with `-fno-exceptions -fno-rtti`); header-only code is compiled with the program's own flags, so Q2 is reshaped (2.2, 5.3) | the old forcing reason is gone, a new header-only one appears |
| `collect`'s `try` hidden in the compiled library | in the header, compiled only when exceptions are on (2.2) | there is no compiled library |
| layer direction enforced by one link target per layer | enforced at compile time by a generated test that compiles each layer with its forbidden layers' include guards set (1.4) | header-only has no per-layer link step |
| release archive carries the ANTLR output | release archive carries the generated headers; also a **single-header file** as a release asset (2.5) | header-only consumers often copy one file |
| milestone 1: ANTLR target in `tools/gen.sh cpp` | milestone 1: the parser generator, `emit_cpp.py`, `syntax::parse` and the adapter (7) | |
| (not seen before) | the C++ parser follows spec 3.2 where the TypeScript and Python recovery does not (F16, F17) | found by the probe's differential test |

## Reading guide

| Section | What it settles |
|---|---|
| 0 | One C++ program first |
| 1 | The C++ `Language` descriptor: type forms, names, namespaces, headers, with prior art; 1.5 the generated parser |
| 2 | Seven decisions, each with a recommendation and the alternative's cost |
| 3 | Header sketches for the main public types of every layer |
| 4 | Three real programs written against the sketches |
| 5 | Costs, findings against the spec, two questions for the owner, every other default |
| 6 | Integrator findings refused, and why |
| 7 | Milestone outline for building the binding |
| 8 | A separate, optional proposal: the same generated parser for TypeScript and Python (not planned) |

### New terms

Every other noun on this page is a glossary term or a C++ standard term.

| Term | Means | Why needed | Existing term it could be |
|---|---|---|---|
| view class | a small copyable C++ object standing for one handle or snapshot; copying it copies the reference, never the thing; `==` compares identity | C++ has no garbage collector, so "one object per written thing" (spec 6.1) needs a stated form | `handle` (spec 6.1): a view class is how C++ spells a handle |
| `sequence<T>` | the binding's one list type: immutable, shared, random access, elements returned by value | the schema's `X[]` results must not dangle when returned from a call (section 2.3) | the schema's list type form `X[]` |
| `ordered_map<K, V>` | the binding's one map type: insertion order kept, lookup by key, shared until changed | the schema's `map` is ordered (codegen 2); the standard library has no insertion-ordered map | the schema's `map` type form |
| `walk_view` | the range a block's `walk` returns | C++20 ships no generator | the `walk` trait (codegen 3) |
| parser generator | knobly's own program (`tools/parser/`) that reads `grammar/Knobly.g4` and writes the lexer and parser as code | the owner ruled out the ANTLR runtime for C++; something must still turn the grammar into a parser | ANTLR's tool, which it replaces for C++ only |
| lookahead machine | for one choice point in the grammar, a small table the generator computes that reads the next tokens and names the alternative to take, or the token where no alternative fits | how a generated recursive parser decides without backtracking | ANTLR's "prediction" |
| compiled mode | a switch (`KNOBLY_HEADER_ONLY=0`) with which the program compiles knobly's definitions once, in one of its own files, instead of in every file that includes knobly | header-only code costs compile time in every file that includes it | none: header-only libraries call it the same (toml++, spdlog) |
| single-header file | the whole binding concatenated into one `knobly.hpp`, a release asset | some C++ projects vendor one file | the release source archive, of which it is a copy |

## 0. User code first

The rasl task, from `fixtures/rasl/split`, in C++ (section 4 has the full programs):

```cpp
#include <knobly/knobly.hpp>   // shared and io: quote, text, diagnostics, errors, ports
#include <knobly/files.hpp>        // file_source, file_writer
#include <knobly/extensions.hpp>   // include
#include <knobly/written.hpp>      // the low level
#include <knobly/rendered.hpp>     // render

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    vw::document_graph graph = config.load("main.conf", {
        .overrides = {{"leds_host", vl::quote("10.0.70.1")}},
    });

    // change $pixels itself: every place that reads it changes
    for (vw::variable v : graph.variables("pixels")) {
        if (auto set = v.as<vw::set_variable>()) {
            set->set(vl::text("2400"));
        }
    }
    graph.save(vl::files::file_writer());   // writes main.conf only; refuses a lost update

    vr::rendered tree = vr::render(graph);
    for (vr::directive d : tree.block().walk()) {          // the walk owns its data: safe on a temporary block
        if (d.name() == "max_count" && !d.values().empty()) {
            std::int64_t count = d.values().at(0).integer();   // a located diagnostic_error if not an integer
        }
    }
}
```

## 1. The C++ Language descriptor

### 1.1 The descriptor itself (`tools/api/emit_cpp.py`)

Every fact about C++ lives here, never in `spec/schema/` (codegen 10):

```python
LANGUAGE = Language(
    key="cpp",
    name="C++",
    sep="::",                         # knobly::written::processor
    function_case=snake,              # std style: replace_with_text, format_diagnostic
    code_case=snake,                  # diagnostic_code::unterminated_string (value 1001, printed "E1001")
    public_kind=lambda model, c: "type" if c is None or c.nature != "free function" else "value",
    enum_form="`enum class`",
    generic=lambda name, params: f"{name}<{', '.join(params)}>",
    construct=lambda name: f"{name}(...)",
    extends_word="derives from",
    cause_field="std::nested_exception (std::rethrow_if_nested)",
    error_roots={
        "knobly error": {"base": "std::runtime_error"},
        "detached error": {"base": "std::logic_error"},
        "argument type error": {"base": "std::logic_error"},
        "misuse error": {"base": "std::invalid_argument"},          # knobly::misuse_error
        "index out of range": {"base": "std::out_of_range"},        # knobly::index_out_of_range
    },
    argument_type_message="{member}(): argument '{parameter}' must be a live object, not {got}",
    modules={"files": "files", "include": "extensions"},   # no fetch adapter (spec 4.3: MAY)
    factory_forms={},                 # constructors: written::processor(...), knobly::diagnostics(...)
    omit=lambda name, nature: name == "walk control",
    omitted_as=lambda name, nature: "the walk's descend predicate" if name == "walk control" else "none",
    pattern_form=lambda constant: f"is_{snake(constant)}",   # written::is_variable_name, knobly::is_program_code
    # needs the loader hook of finding F2: a member may not share the name of its class, its own or inherited
    member_spelling=lambda cls, member: member + "_" if snake(member) == snake(cls) else member,
    trait_names=lambda model: [
        ("knobly", "sequence", "the list type form"),
        ("knobly", "ordered_map", "the map type form"),
        ("knobly", "walk_view", "the range a block's walk returns"),
    ],
)
```

### 1.2 Names, casing and namespaces

**Casing: the standard library's style.** Types, members, functions, enumerators and constants are all `snake_case`:
`document_graph`, `replace_with_text`, `statement_kind::set`, `max_nesting`. Template parameters are `PascalCase`.

- Prior art: the standard library, Boost.JSON (`value::kind()`, `object::if_contains`), nlohmann/json, toml++,
  simdjson (`dom::element::get_int64()`).
- Alternative: Google/Abseil (`DocumentGraph`, `ReplaceWithText()`, `kMaxNesting`) or LLVM style. Cost: fits one house
  style and clashes with the standard library every program also uses.

**Rule 1 holds with one C++ exception: a member may not share its class's name.** The language reserves the name for
constructors ([class.mem]), and an inherited member of that name is hidden by the injected class name (review 2
compiled `l.list()` on `written::list` and got "cannot refer to type member 'list'"). Two schema members hit it:
`written::index::index` and `written::list::list` (inherited from `written_value`). The emitter appends `_`
(`index_()`, `list_()`) through the `member_spelling` hook, checking inherited members too (finding F2).

**Full spec names, no dropped layer word.** `written::written_directive`, `written::written_value`, as in TypeScript
and Python. Dropping it would give `written::directive` beside `rendered::directive`. Cost: it stutters when written
qualified; a namespace alias (`namespace vw = knobly::written;`) is the cure, and the README recommends aliases
over `using namespace` (below).

**Types and accessors share names** (`place place()`, `origin origin()`, `syntax::syntax syntax()`), as
`std::filesystem::directory_entry::path()` does. Two consequences, both handled:

- The generated headers spell every type fully qualified from the global namespace (`::knobly::place place()
  const;`), so GCC's "declaration changes meaning" error cannot fire inside a knobly header.
- In user code, `using namespace std;` with `using namespace knobly::written;` makes `string` and `list`
  ambiguous, and a user class holding `vl::place place;` then naming the type hits the same GCC error. The README's
  first page says: alias the namespaces, never a using-directive for them. No API change; Python kept these classes
  out of its package root for the same reason.

**One namespace per layer, one header per namespace** (rule 9):

| Layer or module | Namespace | Header |
|---|---|---|
| shared, io | `knobly` | `<knobly/knobly.hpp>` |
| syntax | `knobly::syntax` | `<knobly/syntax.hpp>` |
| written (the low level) | `knobly::written` | `<knobly/written.hpp>` |
| rendered | `knobly::rendered` | `<knobly/rendered.hpp>` |
| file adapters (`files`) | `knobly::files` | `<knobly/files.hpp>` |
| include extension (`include`) | `knobly::extensions` | `<knobly/extensions.hpp>` |
| people forms for `std::format` and streams (opt-in) | (specializations in `std`) | `<knobly/format.hpp>` |
| fetch adapters | none (MAY, spec 4.3) | |

### 1.3 How each schema type form maps

| Schema form (codegen 2, 3) | C++ | Prior art | Alternative and its cost |
|---|---|---|---|
| `text` as a parameter | `std::string_view` | the standard library since C++17 | `const std::string&`: an allocation per literal |
| `text` as a result | `std::string`, by value | `std::filesystem::path::string()`, `std::error_code::message()` | a borrowed `string_view`: dangles after the next edit of a live handle |
| `integer` | `std::int64_t` (contract 3) | simdjson `get_int64()`, toml++ | `int`: too small for 2^53-1 |
| a position, token index or occurrence | `std::int64_t` until the schema names them (F13), then `std::size_t` | `std::string::substr` | keep `int64_t` and document the `-Wsign-conversion` cost |
| `number` | `double` | every JSON library | |
| `boolean`, `nothing` | `bool`, `void` | | |
| `absent`, `X or absent` | `std::optional<X>` | C++17 | a null pointer: says nothing in the type |
| a trailing parameter `X or absent` that defaults to absent | an overload without it: `directives()` and `directives(std::string_view)` | the standard library's overload sets (`std::string::find`) | `std::optional<X> = std::nullopt`: an unusual parameter form; an optional view by value defeats argument-dependent lookup |
| list `X[]`, result or parameter | `knobly::sequence<X>`: immutable, shared, a `std::ranges::random_access_range`; `at(i)`, `front()`, `back()` and iteration return `X` **by value**; built from a `std::vector<X>` or a braced list | Qt's implicitly shared containers, Swift's copy-on-write `Array`, `std::views::iota` (a random-access range of prvalues) | `std::vector` by value: its `at()` returns a reference into the temporary, the heap-use-after-free both reviews hit; `std::span` borrowed: dangles after an edit |
| `map of V` (text keys), `map of K to V` (`addresses`) | `knobly::ordered_map<K, V>`: insertion order, lookup, shared until changed (copy on write); `at(k)` returns `V` by value, `find(k)` returns `std::optional<V>` | Python `dict`, LLVM `MapVector`, Boost.JSON `object`, Qt implicit sharing | `std::map`: sorted, so spec 6.2's override order is lost |
| `writable map of text` (`memory writer`) | `std::shared_ptr<ordered_map<std::string, std::string>>` | the shared state of `std::shared_future` | a reference: dangles if the map dies first |
| an anonymous union whose arms are all variants of one named union | that union's view class, narrowed with `as<V>()`: `statement::parent()` is `std::optional<statement>`, `slice::name()` is `written_value`, `reference::declaration()` is `std::optional<variable>` | TypeScript reads a union's shared members directly | `std::variant` of the arms: every shared member needs a `std::visit` (review 2) |
| any other anonymous union `A or B` | `std::variant<A, B>` (`origin::place()` is `std::variant<place, override>`) | the standard library's closed sum type | a hand-named class: a name the schema lacks |
| `function of A to R` (key rule, `closest`'s predicate, walk's `descend`) | `std::function<R(const A&)>` | the standard type-erased callable | `std::function_ref` (C++26); a template parameter cannot sit in an options record |
| `config text` (brand) | `knobly::config_text`, made only by `quote` and `text`; read through `view() const&` (the rvalue overload deleted) | Chromium `base::StrongAlias`, `std::filesystem::path`, the trusted-types idea spec 6.9 cites | an implicit `string_view` conversion: dangled on a temporary and let the brand leak into any text parameter |
| `program code` (template `{text}/{text}`) | `knobly::program_code`: a `consteval` constructor from a literal (a code without `/` does not compile, at any length) and an explicit run-time constructor (`misuse_error`); it holds a `string_view` to the literal's static text or to a shared owned copy | `std::format_string`'s `consteval` literal check | a plain string checked only at run time |
| `diagnostic code` | `enum class diagnostic_code : std::uint16_t { unterminated_string = 1001, ... }` plus `to_string(code)` giving `"E1001"` | `std::errc` | a string |
| a kind list | `enum class statement_kind : std::uint8_t { ... }` plus `to_string` | `std::filesystem::file_type` | a plain `enum`: `set`, `list`, `string` would collide; `token_kind` keeps the grammar's names (spec 2.10) |
| a pattern constant | a generated matcher `bool is_<name>(std::string_view)` over code points: `written::is_variable_name`, `knobly::is_program_code` | | `std::regex`: matches bytes, so the Unicode white-space class cannot be written (F5) |
| `record` | an immutable value class: a public constructor taking its properties (in match-args order, then the rest), a `const` accessor per property, defaulted `operator==` | `std::source_location`, `std::filesystem::directory_entry` | an aggregate with public fields: one access form for records, another for handles |
| `snapshot` | a view class over immutable shared data | `std::shared_future`, simdjson `dom::element` | a deep copy: breaks `parent` |
| `handle` | a view class over a node the graph owns (decision 2.3) | pugixml `xml_node`, `boost::intrusive_ptr` | references into the graph (LLVM, clang's AST): question Q1 |
| a union over a variant set (`statement`, `written value`, `variable`, `expanded value`, `change`) | a view class with the shared members, `kind()`, `as<V>()` (constrained to that union's variants) and `visit(f)`; each variant class derives from it | LLVM `isa`/`dyn_cast`, Boost.JSON `value::kind()` with `if_object()` | `std::variant` alone: the shared members need a visit |
| `port` | an abstract class, held as `std::shared_ptr<Port>` | `std::pmr::memory_resource`, LLVM `vfs::FileSystem` | a type-erased value: a bespoke mechanism for three interfaces |
| `interface` (`locatable`) | a C++20 `concept` | `std::ranges::range` | an abstract base: a vtable on every snapshot for one member |
| `shape` (`block of item and directive`) | the class template `block<Item, Directive>` over a `sequence<Item>`; `written_block` derives from it and adds the edits | `std::ranges::view_interface` | three unrelated block classes |
| `options` record | an aggregate with designated initializers: `load("main.conf", {.overrides = ...})` | C++20; Abseil tip #173 | overloads per option |
| `callback` (`key rule`) | `using key_rule = std::function<std::optional<std::string>(const directive&)>;` | | |
| `factory` | the class's constructor; adapters return `std::shared_ptr<Port>` | `std::thread(...)` | `make_processor(...)` |
| `io: true` | a plain blocking call | `std::filesystem`, Python's binding | futures or coroutines: no standard executor or async files |
| `passed: keyword` | positional | | |
| an error group | an exception class (decision 2.2) | | |

**Traits** (codegen 3):

| Trait | C++ | Prior art |
|---|---|---|
| `people form` | a free `to_string(x)` found by argument-dependent lookup, generated for every concept with the trait (`place`, `override`, `step`, `diagnostic`, `located_diagnostic`, `address`, each kind list and `diagnostic_code`); `<knobly/format.hpp>` adds a `std::formatter` and `operator<<` that call it | `std::to_string`; `std::chrono`'s formatters |
| `iterate` | `begin()`/`end()`: a block, a `sequence` and the sink are ranges (`for (auto s : block)`, `block \| std::views::filter(...)`) | every standard container |
| `count` | `size()` returning `std::size_t`, and `empty()` | every standard container |
| `index` | `at(i)`, raising `index_out_of_range` | `std::vector::at` |
| `walk` | `walk()` and `walk(descend)` return a `walk_view<Item>`, an input range; `descend` is asked of each item after it is visited and before its block; `break` stops | `std::filesystem::recursive_directory_iterator::disable_recursion_pending()` |
| `collect` | `template <std::invocable F> auto collect(F&& read)`: `std::optional<R>` (`bool` for a `void` read); its `try`/`catch` is in the header, compiled only when exceptions are on (2.2) | TypeScript's `collect(read)` |

**Equality** (spec 2.9): `operator==` on `expanded_value` compares `text()`, with a matching `std::hash`. On every other
view class `==` is identity. Records compare member by member.

### 1.4 Header layout and what is generated

```text
cpp/
  CMakeLists.txt                     one INTERFACE target, knobly::knobly; in a git checkout, a step that runs
                                     tools/gen.sh cpp (Python 3.9+, standard library only)
  include/knobly/
    support/                         hand-written, committed: the trait support templates
      sequence.hpp  ordered_map.hpp  walk_view.hpp  block.hpp  view.hpp (the node pointer and count)
      config.hpp                     the switches: KNOBLY_HEADER_ONLY, exceptions on or off, the inline namespace
    detail/                          hand-written, committed: every definition, all inline
      text_in.hpp                    the one UTF-8 policy function for every text entry point (2.4)
      syntax/parse.hpp               token loop, tree hooks, per-statement recovery, error codes (1.5)
      shared/ io/ written/ rendered/ files/ extensions/
    implementation.hpp               compiled mode: the one file a program compiles once (2.5)
  conformance/adapter.cpp  conformance/json.hpp
  tests/
generated (never committed; made by tools/gen.sh cpp; shipped inside the release source archive):
  include/knobly/knobly.hpp  syntax.hpp  written.hpp  rendered.hpp  files.hpp  extensions.hpp  format.hpp
  include/knobly/kinds.hpp  codes.hpp  limits.hpp  errors.hpp  patterns.hpp
  include/knobly/detail/syntax/parser.gen.hpp   lexer tables and parser, from grammar/Knobly.g4 (1.5)
  conformance/shapes.hpp
  tests/api_contract.cpp             PUBLIC_NAMES, and a use of every member
  tests/layers.cpp                   the layer-direction check, from "may import"
```

**The emitter writes the public headers whole; hand code writes the inline definitions in `detail/`.** Each generated
class declares every schema member, with its `doc` as a Doxygen comment, and holds one private node pointer. Each
generated public header ends by including its layer's `detail/` definitions, unless compiled mode is on. A member
that drifts from the schema fails to compile; a member never written fails to link, because `api_contract.cpp`
takes the address of every member and calls every free function (an `inline` function declared and never defined
is still an undefined reference). Prior art: `protoc`'s `.pb.h`, gRPC's generated service bases, and toml++'s split
of declarations from `impl/*.inl` files. Alternative: hand-written headers checked by generated `static_assert`s;
cost: every signature written twice.

**Include budget** (an estimate, to measure in slice 1): `knobly.hpp` declares with `<cstdint> <string>
<string_view> <optional> <variant> <memory> <functional> <initializer_list> <concepts> <iterator> <compare>`. In
header-only mode the definitions add their own (`<vector> <atomic> <charconv> <algorithm>`); in compiled mode they
stay in the one implementation file. `<filesystem>` only through `files.hpp`; `<format>` and `<ostream>` only
through `format.hpp`; `<regex>` never. Measured on the probe: a file including the syntax layer's header takes 0.07 s
longer to compile than one including just `<string>` and `<vector>` (AppleClang 21, `-O2 -fsyntax-only`).

**Layer direction is enforced at compile time, in the test build** (rule 8). Header-only has no per-layer library to
link, so the check moves: every header has a classic include guard (generated), and the generated `tests/layers.cpp`
compiles each layer's headers once with the guards of the layers it may not import already defined. A forbidden
include then leaves that layer's names undeclared, and the test fails to compile. Each public header is also compiled
on its own (a self-contained header check). Cost: a program never runs this check; every test build does.

### 1.5 The parser: generated by knobly's own generator

**What.** `tools/parser/` (Python 3.9+, standard library only, like `tools/api/`) reads `grammar/Knobly.g4` and
writes `detail/syntax/parser.gen.hpp`: the 21 token kinds, the lexer as constant tables, and one function per
grammar rule. `tools/gen.sh cpp` runs it beside `tools/gen-api.py cpp`. TypeScript and Python keep ANTLR (section 8
is a separate proposal to change that).

**How, and the prior art for each step.**

| Step | How | Prior art |
|---|---|---|
| read the grammar | the `.g4` subset knobly uses: literals, character sets and their negation, fragments, `( \| )`, `?`, `*`, `+`, `EOF` | ANTLR's own grammar notation; anything else is refused by name |
| lexer | each token rule becomes an automaton over code-point ranges; the automata are merged into one deterministic table; the longest match wins, ties go to the rule written first | flex, re2c and Ragel (the same subset construction); ANTLR's lexer rule (longest match, first rule on a tie) |
| choice points | for each alternative, `?`, `*` and `+`, the generator computes a lookahead machine from the grammar. 32 of the 37 choice points need one token; `value` and `bounds` need two; `rest`, `items` and `valuesText` read past any run of spaces, line breaks and comments (a machine with a loop) | ANTLR 3's LL(*) analysis (Parr and Fisher, PLDI 2011); past the end of a rule it uses every place the rule is called from, as ANTLR 4's first prediction stage (SLL) does |
| errors | a choice point whose machine finds no alternative reports the error at the token where the last alternative died, the same token ANTLR reports | the "correct prefix" property of LL parsers |
| tree | the rules annotated `cst: kind` (`document`, `directive`, `block`, `slicedWord`, `list`) open a node; the rest are transparent | the `cst:` annotations of `grammar/knobly.ebnf` (finding F19: move them into the `.g4`) |
| refusals | a grammar the generator cannot turn into a parser without guessing is refused: two alternatives with the same continuation (an SLL conflict), a lookahead machine over 400 states, semantic predicates, actions, lexer modes, left recursion | Bison's conflict report; ANTLR 3's "not LL(*)" error |

The grammar's shape makes this small: no predicates, no lexer modes, no actions, no left recursion; tokens are
pairwise disjoint (`tools/g4overlap.py` proves it), so the longest match is unambiguous; every token stays on the
default channel, so spaces and comments are in the token list and the tree is lossless with no extra work.

**What stays hand-written** (`detail/syntax/parse.hpp`, about 300 lines; the probe's is 254 without its comparison
switch):

| Part | Lines in the probe (about) | Why by hand |
|---|---|---|
| the UTF-8 decode function | 20 | the open owner question on invalid UTF-8 (2.4) lands here |
| the token loop | 15 | calls the generated longest match; an undecodable byte becomes one `BAD_CHAR` |
| error codes (spec 2.4: which code for which situation) | 45 | a policy table over token kinds, not grammar; ported line for line from `classify_error` |
| per-statement recovery (spec 3.2: what ends a bad statement, what a stray `}` does) | 90 | spec policy; the generated parser calls `recover_document`, `recover_statements`, `recover_block` |
| tree hooks (a failed directive without its block becomes part of the error node) | 40 | spec 3.2 policy |
| the nesting guard (E2010) | 12 | counts the blocks and lists the parser opens, in its `open_node` hook (since 3d759bc; before, a pre-scan that ran before parsing) |

TypeScript and Python each carry about 550 lines of ANTLR glue for the same job (`parse`, `recovery`, `walk`):
ANTLR's error strategy must be bent into spec 3.2's recovery, and its parse tree walked into the CST. A generated
parser calls the recovery directly and builds the CST as it goes.

**Evidence: the probe** (`design/rd-probe/`; `gen_cpp.py` 653 lines, generated header 574 lines, hand-written
`syntax.hpp` 284 lines including a 30-line ANTLR-comparison switch).

- `python3 gen_cpp.py grammar/Knobly.g4 grammar/knobly.ebnf knobly_gen.hpp`: "lexer DFA 45 states;
  {'ll1': 32, 'llstar': 5, 'dfa_states': 57}". No refusal.
- Built with AppleClang 21, `-std=c++20 -Wall -Wextra -Werror -fno-exceptions -fno-rtti`, AddressSanitizer and
  UndefinedBehaviorSanitizer on: `run_l0.py` gives "L0 syntax corpus: 168 of 168 cases byte-identical to
  conformance/expected", through the driver's own printer (`conformance/driver/encode.py`). A planted wrong error
  code drops it to 157 of 168, so the comparison bites.
- Differential test against the Python binding's ANTLR parser (`fuzz_diff.py`, 20,000 random and mutated inputs):
  tokens identical in all; tree or diagnostics differ in 1,586. With a switch that copies two ANTLR habits
  (`-DKNOBLY_ANTLR_COMPAT`), 19,997 of 20,000 are identical. Both habits contradict spec 3.2 (F16, F17), so the
  binding follows the spec, not the habit.
- Speed: a 2 MB file (100,000 directives, the `max directives` limit) parses and prints in 0.63 s; not tuned.

**Size of the real generator: 800 to 1,000 lines** (the probe's 653, plus entry-rule entry points, line-numbered
refusal messages, the planted-grammar checks and tests). It is written once and serves every grammar change; a
grammar change that needs a construct it refuses (a predicate, a lexer mode) means growing the generator, where
ANTLR would just have worked: the main cost of this route.

**Checks it adds to `tools/check.sh`**: the generator runs on the grammar and must not refuse it (beside the Bison
check, which proves the grammar unambiguous; the generator proves it needs no guessing); each planted grammar in a
new `tools/planted-parser/` (a predicate, an SLL conflict, left recursion) must be refused.

## 2. Decisions

### 2.1 C++ standard: C++20 (recommended)

| Option | Gives | Costs |
|---|---|---|
| **C++20** (recommended) | concepts, ranges, designated initializers, `consteval`, defaulted `operator==` | `walk_view` is a hand-written iterator with an explicit stack (about 80 lines) |
| C++23 | `std::generator`, `std::expected`, the range-for temporary lifetime fix (P2718) | Apple's libc++ does not ship `std::generator`; only matters for Q2 B |
| C++17 | the floor of toml++ and most header-only libraries (nlohmann/json: C++11); the widest reach | no concepts, ranges, designated initializers or `consteval`: the options records lose `.source = ...` (section 0), `program_code` loses its compile-time check, `locatable` becomes a documented convention |

Header-only does not change the pick: the floor was set by the API's own shapes, never by ANTLR (whose C++17 floor
was lower). It does make every user file compile knobly's code with the user's own standard flag, so the headers
are tested under C++20 and C++23 both.

Toolchain floor: GCC 12, Clang 16, AppleClang 16, MSVC 19.34. **macOS deployment target 13.3 or later**: libc++
marks floating-point `std::to_chars` (used by `std::format` of a `double`, so by `format.hpp`) unavailable before it.
To verify in slice 1: the libc++ version that completed floating-point `std::from_chars`, which the `number` reader
uses, and whether that raises the floor further.

### 2.2 Errors: exceptions mirroring the error tree (recommended; question Q2)

**The diagnostics model is unchanged.** Problems in the config text are never thrown: `load` returns a graph whose
`diagnostics()` lists every one, and `render` returns a tree with the same list. Exceptions carry only spec 2.8's
groups. The class tree, generated from `error groups`:

```text
std::exception
├─ std::runtime_error
│  └─ knobly::knobly_error        (expected outcomes; one catch clause catches them all and no bug)
│     ├─ diagnostic_error                  diagnostic()
│     ├─ read_error                        paths(); thrown with std::throw_with_nested (the port's failure is nested)
│     ├─ bad_text_error                    diagnostics()  (positions in bytes of the text the edit was given)
│     └─ save_error                        paths(); nested cause as read_error
│        └─ lost_update_error              paths(); no cause
└─ std::logic_error                        (program bugs, never a knobly_error)
   ├─ knobly::detached_error           a detached handle's member
   ├─ knobly::argument_type_error      a null port or an empty callable
   ├─ std::invalid_argument
   │  └─ knobly::misuse_error          a bad name or code, a stale variant view's own member
   └─ std::out_of_range
      └─ knobly::index_out_of_range    at(i) outside a block or sequence; at(k) on a missing key
```

- Prior art: the standard library's `runtime_error`/`logic_error` split, `std::filesystem::filesystem_error`,
  nlohmann/json's tree, `std::throw_with_nested`. Deriving `misuse_error` from `std::invalid_argument` keeps existing
  `std` catch clauses working while letting a program tell knobly's error from `std::stoi`'s.
- **Exception safety.** Every edit gives the strong guarantee for knobly's errors (spec 2.8: an edit that raises
  `bad_text_error` leaves every document unchanged) and at least the basic guarantee for `std::bad_alloc`: the graph
  stays usable and every handle still valid or detached. A sequence of edits is not atomic: the earlier edits stay
  when a later one fails.
- **Nothing inside the library needs exceptions.** ANTLR's runtime threw inside the library; the generated parser
  returns success or failure and `syntax::parse` is total (the probe builds with `-fno-exceptions -fno-rtti`). The
  API throws only spec 2.8's groups, through user frames: readers, `at()`, `detached_error`, `load`'s `read_error`.
- **Header-only code compiles with the program's flags.** A program built with `-fno-exceptions` cannot compile a
  `throw` or a `try`. `support/config.hpp` detects the mode (`__cpp_exceptions`, `_HAS_EXCEPTIONS`), and each throw
  site calls one function: with exceptions it throws; without, it prints the error's message and calls
  `std::abort()`. This is what the standard library itself does under `-fno-exceptions` (libc++ and libstdc++ abort
  in `std::vector::at`), and what Boost (`boost::throw_exception`) and nlohmann/json (`JSON_NOEXCEPTION`) do. Such a
  program compiles and uses everything that cannot fail (parse, load of readable files, walks, rendering); an expected
  failure ends it. `collect`'s `try` is compiled only with exceptions on; without, a failing read ends the program.
  Only an error-value API (Q2 B) lets those programs recover, many of them game engines and embedded builds.
- `error(message, code)` returns a `diagnostic_error` by value (spec 7.1); a program writes `throw d.error(...)` or
  hands it to the sink.

### 2.3 Handles and results: values that share ownership (recommended; question Q1)

A **view class** is the C++ form of a handle (spec 6.1):

- It holds **one pointer** to its node; the node points at its graph's core, which carries an intrusive atomic count
  (as `boost::intrusive_ptr` and LLVM's `ThreadSafeRefCountedBase` do). Copying a view bumps the count; the graph
  lives while any view of it does.
- **Identity**: asking twice gives views that compare `==` and hash alike, so a view can key an `unordered_map`.
- **Detached**: an edit marks the nodes it removes as detached; the graph keeps them until it dies. Every member but
  `kind()` of a detached view raises `detached_error`, before any other check (contract 4.3). A dangling view is
  impossible, not documented.
- **Const is shallow**, as with `std::span` and `std::shared_ptr`: every member, edits included, is `const`. A `const
  written_directive&` can still be edited through. A copyable handle could not have enforced read-only access anyway.
- **A value whose kind changes under `set`** (spec 6.1): the node takes the new kind, so `kind()` and `as<V>()` on
  the `written_value` view follow it. A view of the old variant class keeps its shared members; a member only the old
  variant has raises `misuse_error` (F4).

**Every result the library hands out shares ownership the same way**, so nothing returned can dangle:

- `sequence<T>` and `ordered_map<K, V>` hold one shared pointer to immutable storage; their element access returns by
  value. `const auto& v = field.values().at(0);` binds a temporary whose life is extended: safe (probe below).
- A snapshot's lists (a render's `values()`, `directives()`) are its stored sequences: no allocation per call. A live
  handle's lists (a written directive's `values()`) build one snapshot per call.
- `block`, `walk_view` and their iterators each hold a shared reference to the graph or render core, never a pointer to
  the block object. So `for (auto d : tree.block().walk())` is safe in C++20, although the temporary block dies before
  the loop body (the language fix, P2718, is C++23).

**Edits during iteration** (the reviews found this unstated; spec finding F8):

- Iterating a written block reads a snapshot of its statements taken at `begin()`. A walk takes each block's snapshot
  when it enters that block.
- An edit never invalidates an iterator or a walk. A statement detached after the snapshot is still yielded (its
  `kind()` works; other members raise `detached_error`); a statement detached before the walk enters its block is not
  descended. Statements inserted into a block already entered are not visited.
- Prior art: a snapshot iterator (Java's `CopyOnWriteArrayList`); the alternative, "any edit invalidates", is the
  standard containers' rule, and with handles it would turn a quick-fix loop into a `detached_error` from `++`.

**Snapshots** hold live handles; a render's views keep the render alive. **Concurrency** (spec 4.1): no graph, render
or view is safe for concurrent use, `const` members included, because a render writes the graph's cache. The atomic
count does make it safe to hand a view to another thread and destroy it there. The README says this first.

A probe of these shapes compiled and ran clean under AddressSanitizer and UndefinedBehaviorSanitizer with AppleClang
21 (`/Volumes/Dock/tmp/kno-cpp-design/design/cpp-final-probes/seq.cpp`): a `sequence<std::string>` satisfies
`std::ranges::random_access_range`; `const std::string& v = n.values().at(1);` and a filtered range over a temporary
sequence are both safe.

### 2.4 Strings, positions and paths

- Every text in or out is UTF-8: `std::string_view` in, `std::string` out.
- **Positions** count bytes of UTF-8 (contract 1's row for Go and Rust). The adapter's `hello` says `"unit": "byte"`.
  Byte columns match what GCC and Clang print and LSP 3.17's `utf-8` position encoding, which clangd supports.
  `format_diagnostic`'s carets are one per byte.
- **How bytes reach the lexer**: the generated lexer walks the UTF-8 bytes of the `std::string_view` directly and
  calls the one decode function (`detail/text_in.hpp`) for each code point; token boundaries are byte offsets, so
  every position comes from one place with no decoded copy and no offset table. The decode function decides the
  lone-surrogate rule, not a library. The probe passes the three `surrogate-*` cases this way.
- **Paths are UTF-8 text** in the API (the spec's text), keys of `documents()` and the `path` in every
  `path:line:col`. **The C++ `file_source` resolves to the lexically normal join with `/` separators**:
  `(parent_dir / spec).lexically_normal().generic_u8string()`. A relative root stays relative, as in Python
  (`os.path.normpath`), so `documents().at("sink.conf")` works for a root given as `"main.conf"`. TypeScript resolves
  to absolute paths (`path.resolve`); the spec fixes neither, finding F7. A program arming a file watcher converts with
  `std::filesystem::path(std::u8string_view(...))`; named helpers for both directions are a schema addition (F15).

**The open owner question kno-pol (respected, not decided here).** A `std::string` can hold invalid UTF-8 and a lone
surrogate as WTF-8 bytes, which a JavaScript or Python string cannot: the exposure is new to C++. Every text entry
point goes through **one function** (`detail/text_in.hpp`), so the owner's ruling lands in one place. Provisional
behaviour, marked so in the code and tests:

| Entry point | Provisional behaviour for invalid UTF-8 or WTF-8 surrogate bytes |
|---|---|
| a document's text (`document_source::read`, `memory_source`), `syntax::parse` | decoded: a WTF-8 surrogate becomes that code point (then `BAD_CHAR`, as Go would); any other invalid byte is one `BAD_CHAR` with E1003 (spec 2.1's proposal). `parse` stays total |
| `text(raw)` and every edit taking `config_text` | the same decoding; the edit then refuses the text with `bad_text_error`, as any text that does not parse clean |
| `quote(s)` | `misuse_error`: a program string that is not UTF-8 has no knobly string form yet |
| names: `rename`, `set_override`, override names in `load_options`, `program_code(std::string_view)` | `misuse_error` (the name patterns are matched over code points, so an invalid byte never matches) |
| paths (`load`, port results) | passed through unchanged as bytes; only the file adapters interpret them |

- Path order (spec 4.1, code point order) is free: `std::string`'s `operator<` compares bytes as `unsigned char`, and
  UTF-8 byte order is code point order, WTF-8 surrogates included.

### 2.5 Build and packaging: header-only

- **One include directory, one CMake `INTERFACE` target** `knobly::knobly` (CMake 3.24 or later), carrying
  only `target_include_directories` and `target_compile_features(... cxx_std_20)`. `cmake --install` puts the headers
  and an architecture-independent package config with a version file in place; `find_package(knobly)`,
  `FetchContent`, `add_subdirectory`, a vcpkg overlay port or a Conan recipe all work, and so does copying `include/`
  into a project. No `BUILD_SHARED_LIBS`, no visibility flags, nothing to link, no run-time dependency.
- **Where the code comes from.** The release source archive (made by the repo's automated release flow, beside the npm
  tarball and the Python wheel) carries the generated headers, so a consumer needs neither Python nor network. A git
  checkout has no generated files (owner, 2026-10-23: "Don't commit the generated code, just the source"), so
  `KNOBLY_REGENERATE` defaults `ON` when they are absent and runs `tools/gen.sh cpp`: Python 3.9 or later,
  standard library only. No Java, no download.
- **A single-header file as a second release asset** (`knobly.hpp`, every header concatenated in include order by
  a small standard-library script, as toml++ and nlohmann/json ship theirs). Never committed; a release test compiles
  it alone and runs the syntax corpus through it.
- **Compile time, and how it is kept down.** In header-only mode every file that includes a layer compiles that
  layer's definitions; the written layer is the largest (an estimate: 5,000 to 7,000 lines). Four measures:
  1. **Compiled mode**: define `KNOBLY_HEADER_ONLY=0` for the whole program (the CMake option
     `KNOBLY_COMPILED` does it) and compile `<knobly/implementation.hpp>` in exactly one file. The public
     headers then hold declarations only. Same files, one switch; prior art: toml++ (`TOML_HEADER_ONLY` and
     `TOML_IMPLEMENTATION`), spdlog (`SPDLOG_COMPILED_LIB`), stb's single-file libraries. It ships no library: the
     program compiles the file itself.
  2. **Explicit instantiation** in compiled mode: the few templates (`sequence<T>`, `ordered_map<K, V>`,
     `block<Item, Directive>`, `walk_view<Item>`) are instantiated once for the binding's own element types in the
     implementation file and declared `extern template` in the headers, so other files do not instantiate them again.
  3. **Layer headers include only their layer**: `syntax.hpp` alone is enough to parse; `written.hpp` does not pull
     the rendered layer; heavy standard headers stay behind the opt-in headers (1.4).
  4. **A budget measured in CI** from slice 1: the compile time of one file including each layer, in both modes,
     reported per change.
- **Two knobly versions in one program** (a library and the app each bundling a different one) would define the
  same inline functions differently, an ODR violation. Every name lives in a versioned inline namespace
  (`knobly::v0::written::processor`, spelled `knobly::written::processor` by users), so two versions get
  different symbols and a mismatch fails to link instead of misbehaving. Prior art: nlohmann/json's ABI-tagged inline
  namespace, toml++'s `toml::v3`, libc++'s `std::__1`.
- **Exception classes across shared libraries.** A header-only exception class gets its type information emitted in
  every shared library that uses it; with hidden visibility a `catch` in one library could miss a `throw` from
  another. The generated error classes carry default visibility (`[[gnu::visibility("default")]]` on GCC and Clang),
  as libstdc++'s own exception classes do.

| Option | Gives | Costs |
|---|---|---|
| **header-only by default, optional compiled mode, single-header asset** (recommended) | nothing to build or link; one switch for programs that care about compile time | two configurations to test (CI builds both); every user file compiles knobly's code by default |
| header-only, no compiled mode | one configuration | compile time grows with every file that includes the written layer, with no cure |
| single header as the only form | the simplest copy-in | every including file compiles all layers (about 10,000 lines) even to parse one text; no per-layer header |

### 2.6 Testing the binding's own code: Catch2 v3 (recommended)

- Catch2 v3, fetched only when `KNOBLY_BUILD_TESTS` is on, registered with CTest. Alternatives: GoogleTest,
  doctest, plain CTest executables.
- The shared conformance driver runs from CTest: `python3 conformance/driver/run.py -- $<TARGET_FILE:adapter>`.
- The test leg builds with ASan and UBSan and `-Wall -Wextra -Werror`, plus `-Wdangling` and `-Wsign-conversion` on
  the user programs of section 4 compiled as tests; clang-format and clang-tidy are the lint step.
- The adapter carries its own small JSON codec (about 300 lines): nlohmann/json and Boost.JSON refuse `\ud800`.
- A compile-fail test (a CTest that expects the compiler to refuse) covers what C++ rejects at compile time: a plain
  string as `config_text`, a literal code without `/`, `view()` on a temporary (F1).
- The generated parser's checks (1.5): the generator must not refuse the grammar; each planted grammar must be
  refused; the syntax corpus through the binding's adapter. A differential run against the Python binding
  (`design/rd-probe/fuzz_diff.py` grown into a tool) stays a local check, not CI, until F16 and F17 are settled.
- Both modes in CI: header-only and compiled mode (2.5); the syntax layer also with `-fno-exceptions -fno-rtti`; the
  headers under `-std=c++20` and `-std=c++23`; each public header compiled alone; the layer check of 1.4.

### 2.7 Memory: global `new`, no allocator hook (default D22)

Every node, string and sequence goes through global `operator new`. Game engines ask about this first. An allocator
hook (a `std::pmr::memory_resource*` in `processor_options`) is possible later without changing any signature but
the options record. Listed as a cost and a default the owner can reopen.

## 3. Header sketches

Generated from `api.json` in the real build; shown by hand, shortened where a pattern repeats, every type spelled
short here (the real headers qualify from `::knobly`).

### 3.1 Shared and io: `<knobly/knobly.hpp>`, namespace `knobly`

```cpp
namespace knobly {

// ---- support: one list and one map type for every layer ----

/// An immutable, shared list: copying is one pointer; elements come back by value.
template <class T>
class sequence {
public:
    sequence();
    sequence(std::vector<T> items);                                // implicit: a vector or a braced list
    sequence(std::initializer_list<T> items);
    iterator begin() const;                                        // random access; *it is a T
    iterator end() const;
    std::size_t size() const noexcept;
    bool empty() const noexcept;
    T at(std::size_t index) const;                                 // index_out_of_range
    T front() const;                                               // index_out_of_range when empty
    T back() const;
    friend bool operator==(const sequence&, const sequence&);      // element by element
};

/// Insertion-ordered, lookup by key, shared until changed.
template <class Key, class Value>
class ordered_map {
public:
    using value_type = std::pair<Key, Value>;
    ordered_map() = default;
    ordered_map(std::initializer_list<value_type> items);          // a repeated key keeps its first place, last value
    iterator begin() const;                                        // insertion order; *it is a value_type
    iterator end() const;
    std::size_t size() const noexcept;
    bool empty() const noexcept;
    bool contains(const Key& key) const;
    Value at(const Key& key) const;                                // index_out_of_range when absent
    std::optional<Value> find(const Key& key) const;               // nullopt when absent
    void insert_or_assign(Key key, Value value);                   // copies first if shared; a changed key keeps its place
    bool erase(const Key& key);
};

// ---- values going in (spec 6.9) ----

/// Knobly text a program hands to an edit or an override. Made only by quote() and text().
class config_text {
public:
    std::string_view view() const& noexcept;
    std::string_view view() const&& = delete;                      // would dangle
    friend bool operator==(const config_text&, const config_text&) = default;
private:
    explicit config_text(std::string raw);
    std::string raw_;
    friend config_text quote(std::string_view);
    friend config_text text(std::string_view);
};

config_text quote(std::string_view text);                          // a program string, written as a knobly string
config_text text(std::string_view raw);                            // text already written as knobly text

/// A program's own diagnostic code, "<namespace>/<name>".
class program_code {
public:
    template <std::size_t N>
    consteval program_code(const char (&literal)[N]);              // "lbweight" does not compile; any length works
    explicit program_code(std::string_view code);                  // misuse_error unless is_program_code(code)
    std::string_view view() const& noexcept;
    std::string_view view() const&& = delete;
    friend bool operator==(const program_code&, const program_code&);
private:
    std::shared_ptr<const std::string> owned_;                     // empty for a literal
    std::string_view view_;                                        // the literal's static text, or *owned_
};

bool is_program_code(std::string_view text);                       // the pattern, over code points

// ---- positions, places, origins (spec 2.1, 2.2) ----

class source_position {
public:
    source_position(std::int64_t offset, std::int64_t line, std::int64_t column);
    std::int64_t offset() const noexcept;                          // bytes of UTF-8 from the start
    std::int64_t line() const noexcept;                            // from 0
    std::int64_t column() const noexcept;                          // bytes from the line's start
};

class source_span {
public:
    source_span(source_position start, source_position end);
    source_position start() const noexcept;
    source_position end() const noexcept;                          // half-open
};

class place {                                                      // a file and a span
public:
    place(std::string resolved_path, source_span span);
    place_kind kind() const noexcept;                              // place_kind::file
    std::string resolved_path() const;
    source_span span() const noexcept;
};

class override {
public:
    explicit override(std::string variable);
    place_kind kind() const noexcept;                              // place_kind::override
    std::string variable() const;
};

class step {
public:
    step(step_kind kind, std::string name, knobly::place place);
    step_kind kind() const noexcept;
    std::string name() const;
    knobly::place place() const;
};

class origin {
public:
    origin(std::variant<knobly::place, knobly::override> place, sequence<step> via = {});
    std::variant<knobly::place, knobly::override> place() const;
    sequence<step> via() const;                                    // innermost first
};

class directive_origin { /* place(), via(); constructor (place, via) */ };

// ---- diagnostics (spec 2.3, 7.7) ----

class diagnostic {                                                 // a syntax diagnostic: no file
public:
    diagnostic(diagnostic_code code, std::string message, source_span span);
    diagnostic_code code() const noexcept;
    std::string message() const;
    source_span span() const noexcept;
};

class located_diagnostic {
public:
    located_diagnostic(std::variant<diagnostic_code, program_code> code, std::string message,
                       knobly::place place, sequence<step> via = {});
    std::variant<diagnostic_code, program_code> code() const;
    std::string message() const;
    knobly::place place() const;
    sequence<step> via() const;
};

// people forms, found by argument-dependent lookup
std::string to_string(const place&);                               // "sink.conf:4:5"
std::string to_string(const override&);                            // "override pixels"
std::string to_string(const step&);
std::string to_string(const diagnostic&);                          // "4:5: E1001: unterminated string"
std::string to_string(const located_diagnostic&);                  // "main.conf:7:15: E5001: unknown variable: $pixels"
std::string to_string(diagnostic_code);                            // "E1001"
// ... and one per kind list

/// Anything a program can place a problem on: a render, a rendered directive, an expanded value.
template <class T>
concept locatable = requires(const T& at, std::string_view message, program_code code) {
    { at.error(message, code) } -> std::same_as<diagnostic_error>;
};

/// The one place problems collect.
class diagnostics {
public:
    diagnostics();
    explicit diagnostics(sequence<located_diagnostic> initial);
    void add(located_diagnostic diagnostic);
    template <locatable At>
    void report(const At& at, std::string_view message, program_code code);
    std::size_t size() const noexcept;
    bool empty() const noexcept;
    iterator begin() const;                                        // in the order added
    iterator end() const;
    template <std::invocable F>
    auto collect(F&& read);                                        // std::optional<R>; bool for a void read
};

// ---- the io ports (spec 4) ----

class load_context {
public:
    std::string parent_path() const;                               // empty when the root path is resolved
};

class document_source {
public:
    virtual ~document_source() = default;
    virtual sequence<std::string> resolve(std::string_view spec, const load_context& context) const = 0;
    virtual std::string read(std::string_view resolved_path) const = 0;
};

class file_write {
public:
    file_write(std::string resolved_path, std::string text, std::string saved_text);
    std::string resolved_path() const;
    std::string text() const;                                      // what to write
    std::string saved_text() const;                                // what the file held when read or last saved
};

class document_writer {
public:
    virtual ~document_writer() = default;
    virtual void write(sequence<file_write> files) const = 0;
};

void check_lost_updates(sequence<file_write> files, sequence<std::optional<std::string>> current);   // lost_update_error

std::shared_ptr<document_source> memory_source(std::shared_ptr<const ordered_map<std::string, std::string>> files);
std::shared_ptr<document_writer> memory_writer(std::shared_ptr<ordered_map<std::string, std::string>> files);

}  // namespace knobly
```

Also in this header (generated, not shown): every kind list as an `enum class` with `to_string`;
`diagnostic_code`, `messages`, `code_facts` and `describe`; the limits and `reserved`; the error classes of 2.2; the
support templates `block` and `walk_view`.

```cpp
namespace knobly {

/// The one block shape (spec 2.11). Holds a shared reference to its graph or render, never to a block object.
template <class Item, class Directive>
class block {
public:
    iterator begin() const;                                        // a snapshot of the items, taken here
    iterator end() const;
    std::size_t size() const;
    Item at(std::size_t index) const;                              // index_out_of_range
    sequence<Directive> directives() const;
    sequence<Directive> directives(std::string_view name) const;
    walk_view<Item> walk() const;                                  // depth first
    walk_view<Item> walk(std::function<bool(const Item&)> descend) const;
};

}  // namespace knobly
```

A program using a memory source writes the map type once (a braced list cannot be forwarded through `make_shared`):

```cpp
using files_map = vl::ordered_map<std::string, std::string>;
auto files = std::make_shared<files_map>(files_map{{"main.conf", "pixels 10;\n"}});
vw::processor config({.source = vl::memory_source(files)});
```

### 3.2 Syntax: `<knobly/syntax.hpp>`, namespace `knobly::syntax`

```cpp
namespace knobly::syntax {

class token_range {
public:
    token_range(std::int64_t start, std::int64_t end);
    std::int64_t start() const noexcept;                           // first token index
    std::int64_t end() const noexcept;                             // one past the last
};

class token {
public:
    token_kind kind() const noexcept;                              // token_kind::WORD, token_kind::BAD_CHAR, ...
    std::string text() const;
    source_span span() const noexcept;
};

class node : public token_range {
public:
    node_kind kind() const noexcept;
    sequence<node> children() const;
};

class syntax {                                                     // one text: every byte in exactly one token
public:
    sequence<token> tokens() const;                                // the stored list: O(1) per call
    node root() const;
    sequence<diagnostic> diagnostics() const;
};

syntax parse(std::string_view text);                               // total: never throws for any text
source_span span_of(const syntax& syntax, const token_range& range);   // index_out_of_range
std::string text_of(const syntax& syntax, const token_range& range);   // index_out_of_range

}  // namespace knobly::syntax
```

### 3.3 Written (the low level): `<knobly/written.hpp>`, namespace `knobly::written`

```cpp
namespace knobly::written {

bool is_variable_name(std::string_view text);                      // the pattern: check a typed --set name first

// ---- the processor and the graph (spec 6.2, 6.3) ----

struct processor_options {
    std::shared_ptr<document_source> source;                       // required
    std::vector<std::shared_ptr<extension>> extensions = {};       // in order
};

struct load_options {
    ordered_map<std::string, config_text> overrides = {};          // name without $ to its text, in order
};

class processor {
public:
    explicit processor(processor_options options);                 // argument_type_error, misuse_error
    /// Never fails for anything in the files' text: read graph.diagnostics().
    document_graph load(std::string_view path) const;              // read_error
    document_graph load(std::string_view path, load_options options) const;   // misuse_error for a bad override name
};

class document_graph {
public:
    document root() const;
    ordered_map<std::string, document> documents() const;          // root first, then first-read order
    ordered_map<std::string, config_text> overrides() const;
    void set_override(std::string_view name, std::optional<config_text> text) const;   // nullopt removes it
    sequence<std::string> read() const;                            // the paths this call read
    sequence<std::string> save(std::shared_ptr<document_writer> writer) const;   // save_error, lost_update_error
    sequence<document_edge> edges() const;                         // walk order
    sequence<document_edge> unread() const;
    sequence<variable> variables() const;
    sequence<variable> variables(std::string_view name) const;
    sequence<located_diagnostic> diagnostics() const;              // the one list
    expansion expand() const;                                      // what render(graph) builds on
};

class document {
public:
    std::string resolved_path() const;
    std::string saved_text() const;
    std::string text() const;
    syntax::syntax syntax() const;
    written_block block() const;
    sequence<document_edge> included_by() const;
    void replace_with_text(config_text text) const;
};

class copy { public: written::statement statement() const; sequence<step> via() const; };        // snapshot
class document_edge {                                                                             // snapshot
public:
    written::copy copy() const;
    sequence<std::string> specs() const;
    sequence<std::string> targets() const;
};

// ---- statements (spec 6.5): one union, one class per kind ----

class statement {
public:
    statement_kind kind() const noexcept;                          // works on a detached view too
    written::document document() const;
    std::optional<statement> parent() const;                       // a written_directive, extension_line or snippet_line
    knobly::place place() const;                               // starts at its first owned leading comment
    std::string text() const;
    sequence<written::copy> copies() const;
    sequence<statement> replace_with_text(config_text text) const;
    void remove() const;
    sequence<statement> insert_before(config_text text) const;
    sequence<statement> insert_after(config_text text) const;

    template <std::derived_from<statement> V>
    std::optional<V> as() const;                                   // the variant when this is one
    template <class F>
    decltype(auto) visit(F&& f) const;                             // f is called with the exact variant class
};

class written_directive : public statement {
public:
    std::string name() const;
    sequence<written_value> values() const;
    std::optional<written_block> block() const;
    void rename(std::string_view name) const;                      // misuse_error for a bad name
    void set(config_text text) const;                              // replace its values
};

class extension_line : public statement { /* name(), values(), block(), set(); no rename */ };
class set_line : public statement { public: set_variable variable() const; sequence<written_value> values() const; void set(config_text) const; };
class snippet_line : public statement { public: std::string name() const; sequence<parameter> parameters() const; written_block block() const; };
class use_line : public statement {
public:
    std::string snippet_name() const;
    std::optional<snippet_line> snippet() const;
    sequence<resolution<snippet_line>> snippets() const;
    sequence<written_value> values() const;
    void set(config_text text) const;
};
class unreadable_line : public statement {};

class written_block : public block<statement, written_directive> {
public:
    sequence<statement> insert_statements(std::size_t index, config_text text) const;   // index_out_of_range
    sequence<statement> add_statements(config_text text) const;
};

// ---- values (spec 6.6) ----

class written_value {
public:
    value_kind kind() const noexcept;                              // follows a set() that changes the kind
    std::string text() const;
    knobly::place place() const;
    written::statement statement() const;
    std::optional<written::list> list() const;                     // the list it is an item of
    void set(config_text text) const;                              // keeps this handle (spec 6.1)
    sequence<written_value> replace_with_text(config_text text) const;
    void remove() const;
    template <std::derived_from<written_value> V> std::optional<V> as() const;
    template <class F> decltype(auto) visit(F&& f) const;
};

class word : public written_value {};
class string : public written_value {};                            // text() includes the quotes (F11)
class list : public written_value {
public:
    sequence<written_value> items() const;
    std::optional<written::list> list_() const;                    // the inherited list(), respelled (F2)
};
class slice : public written_value {
public:
    written_value name() const;                                    // a word or a reference
    std::optional<written_value> start() const;
    std::optional<written_value> end() const;
};
class index : public written_value {
public:
    written_value name() const;
    written_value index_() const;                                  // C++: a member cannot share its class's name
};
class reference : public written_value {
public:
    std::string name() const;                                      // without $
    std::optional<variable> declaration() const;                   // a set_variable or a parameter
    sequence<reference_resolution> resolutions() const;            // one per copy, walk order
};

// ---- variables (spec 6.7) ----

class variable {
public:
    variable_kind kind() const noexcept;
    std::string name() const;
    sequence<reference> references() const;
    sequence<reference_resolution> wins() const;
    sequence<reference_resolution> shadowed_at() const;
    template <std::derived_from<variable> V> std::optional<V> as() const;
    template <class F> decltype(auto) visit(F&& f) const;
};
class set_variable : public variable { public: knobly::place place() const; set_line line() const; void rename(std::string_view) const; void set(config_text) const; };
class parameter : public variable { public: knobly::place place() const; snippet_line line() const; void rename(std::string_view) const; };
class override_variable : public variable {};                     // never detached

template <class Definition>
class resolution { public: written::copy copy() const; std::optional<Definition> winner() const; sequence<Definition> shadowed() const; };
class reference_resolution : public resolution<variable> { public: written::reference reference() const; sequence<written_value> values() const; };

// ---- expansion and expanded values (spec 2.9, 6.10) ----

class expanded_value {
public:
    value_kind kind() const noexcept;
    std::string text() const;                                      // canonical text; == compares it
    knobly::origin origin() const;
    written_value written() const;
    std::optional<written_value> definition() const;               // absent for an override
    sequence<reference_resolution> chain() const;
    std::string word() const;                                      // each reader: diagnostic_error on a wrong kind
    std::string string() const;
    double number() const;
    std::int64_t integer() const;
    bool boolean() const;
    sequence<expanded_value> list() const;
    std::variant<slice_value, index_value> slice() const;          // two records, not one union: stays a variant
    diagnostic_error error(std::string_view message, program_code code) const;
    template <std::derived_from<expanded_value> V> std::optional<V> as() const;
    template <class F> decltype(auto) visit(F&& f) const;
    friend bool operator==(const expanded_value&, const expanded_value&);   // by text
};
class expanded_word : public expanded_value {};
class expanded_string : public expanded_value {};
class expanded_list : public expanded_value { public: sequence<expanded_value> items() const; };
class expanded_slice : public expanded_value { public: std::string name() const; std::optional<std::int64_t> start() const; std::optional<std::int64_t> end() const; };
class expanded_index : public expanded_value { public: std::string name() const; std::int64_t index() const; };

class directive_expansion {                                        // snapshot
public:
    written_directive written() const;
    directive_origin origin() const;
    sequence<expanded_value> values() const;
    std::optional<expansion_block> block() const;
    sequence<unreadable_expansion> unreadable() const;
};
using expansion_block = block<directive_expansion, directive_expansion>;

class unreadable_expansion { public: written::statement written() const; unreadable_reason reason() const noexcept; directive_origin origin() const; };
class expansion { public: expansion_block block() const; sequence<unreadable_expansion> unreadable() const; sequence<located_diagnostic> diagnostics() const; };

// ---- the extension port (spec 5) ----

class extension_use { public: sequence<expanded_value> values() const; directive_origin origin() const; };

class extension {
public:
    virtual ~extension() = default;
    virtual std::string directive() const = 0;                     // the name it owns, without @
    virtual sequence<std::string> specs(const extension_use& use) const = 0;   // throw diagnostic_error to place a failure
};

std::string format_diagnostic(const located_diagnostic& diagnostic);                     // no source lines
std::string format_diagnostic(const located_diagnostic& diagnostic, const document_graph& graph);

}  // namespace knobly::written
```

### 3.4 Rendered: `<knobly/rendered.hpp>`, namespace `knobly::rendered`

```cpp
namespace knobly::rendered {

using key_rule = std::function<std::optional<std::string>(const directive&)>;

struct key_options {
    key_rule key = {};                                             // empty: no key rule
};

class directive {                                                  // snapshot
public:
    std::string name() const;
    sequence<written::expanded_value> values() const;              // stored: no allocation per call
    std::optional<rendered_block> block() const;
    sequence<written::unreadable_expansion> unreadable() const;
    std::optional<directive> parent() const;
    directive_origin origin() const;
    written::written_directive written() const;
    std::optional<directive> closest(std::function<bool(const directive&)> predicate) const;
    diagnostic_error error(std::string_view message, program_code code) const;
};
using rendered_block = block<directive, directive>;

class rendered {
public:
    rendered_block block() const;
    sequence<written::unreadable_expansion> unreadable() const;
    directive_origin origin() const;                               // the root file at 0:0
    sequence<located_diagnostic> diagnostics() const;              // the graph's one list
    written::document_graph graph() const;
    diagnostic_error error(std::string_view message, program_code code) const;
    ordered_map<directive, address> addresses() const;             // walk order
    ordered_map<directive, address> addresses(key_options options) const;
    sequence<change> diff(const rendered& after) const;
    sequence<change> diff(const rendered& after, key_options options) const;
};

rendered render(const written::document_graph& graph);             // pure, synchronous

class address_step { public: std::string name() const; std::optional<std::string> key() const; std::int64_t occurrence() const noexcept; };
class address {
public:
    sequence<address_step> steps() const;
    std::string text() const;                                      // the same bytes in every binding
    std::optional<address> parent() const;
};
std::string to_string(const address&);                            // graph > node "leds" > max_count

class change {
public:
    change_kind kind() const noexcept;
    rendered::address address() const;
    template <std::derived_from<change> V> std::optional<V> as() const;
    template <class F> decltype(auto) visit(F&& f) const;
};
class added : public change { public: directive after() const; };
class removed : public change { public: directive before() const; };
class changed : public change { public: directive before() const; directive after() const; };
class unknown : public change { public: directive before() const; };

}  // namespace knobly::rendered
```

### 3.5 Adapters and the opt-in formatting header

```cpp
namespace knobly::files {
std::shared_ptr<document_source> file_source();    // resolved paths: lexically normal join, '/' separators (2.4)
std::shared_ptr<document_writer> file_writer();    // check_lost_updates with the disk, then a staged write
}

namespace knobly::extensions {
std::shared_ptr<written::extension> include();     // @include "path" { @set $name value; }
}

// <knobly/format.hpp>: for every type with a to_string, a std::formatter and an operator<< that call it.
```

## 4. Three programs against the sketch

Each program is written as a user would, with its includes. A local `overloaded` helper (the standard two-line
idiom for `visit` with lambdas) appears where a program matches on kinds. Each compiles as a test in slice 3, with
`-Wdangling` and `-Wsign-conversion`.

### 4.1 An app: load a rasl config with includes and overrides, render it, read values

The rasl split fixture: `main.conf` sets `$pixels` and `$leds_host` and includes `sink.conf` twice. The app takes
`--set name=value` overrides from its command line, reads every sink, and reports every value problem at once.

```cpp
#include <knobly/knobly.hpp>
#include <knobly/files.hpp>
#include <knobly/extensions.hpp>
#include <knobly/written.hpp>
#include <knobly/rendered.hpp>

#include <cstdint>
#include <cstdlib>
#include <format>
#include <iostream>
#include <span>
#include <string>
#include <vector>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

struct sink {
    std::string name;
    std::string host;
    double fps = 0;
    std::int64_t max_count = 0;
};

int main(int argc, char** argv) {
    vw::load_options options;
    for (std::string_view arg : std::span(argv + 1, static_cast<std::size_t>(argc - 1))) {
        auto eq = arg.find('=');
        std::string name(arg.substr(0, eq));
        if (eq == std::string_view::npos || !vw::is_variable_name(name)) {    // a user's typo, not a program bug
            std::cerr << "usage: sinks name=value...\n";
            return 2;
        }
        options.overrides.insert_or_assign(name, vl::text(arg.substr(eq + 1)));
    }

    vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    vw::document_graph graph = [&] {
        try {
            return config.load("main.conf", options);
        } catch (const vl::read_error& e) {        // the root file could not be read: no graph at all
            std::cerr << e.what() << '\n';
            std::exit(2);
        }
    }();

    vr::rendered tree = vr::render(graph);
    vl::diagnostics problems(tree.diagnostics());  // the language's problems first: the graph's one list
    std::vector<sink> sinks;

    // Descend only into "graph" blocks; read every DdpSink node.
    auto descend = [](const vr::directive& d) { return d.name() == "graph"; };
    for (vr::directive node : tree.block().walk(descend)) {
        auto values = node.values();               // one shared list: name it once
        if (node.name() != "node" || values.empty() || values.at(0).text() != "DdpSink") continue;
        if (values.size() < 2) {
            problems.report(node, "a DdpSink node needs an id", "rasl/node-arity");
            continue;
        }
        sink s;
        s.name = problems.collect([&] { return values.at(1).word(); }).value_or("?");
        if (auto body = node.block()) {
            for (vr::directive field : body->directives()) {
                if (field.values().empty()) {
                    problems.report(field, "missing value", "rasl/missing-value");
                    continue;
                }
                vw::expanded_value v = field.values().front();       // by value: nothing to dangle
                if (field.name() == "target") {
                    s.host = problems.collect([&] { return v.string(); }).value_or("");
                } else if (field.name() == "fps") {
                    s.fps = problems.collect([&] { return v.number(); }).value_or(0);   // "20hz": E4004, located
                } else if (field.name() == "max_count") {
                    s.max_count = problems.collect([&] { return v.integer(); }).value_or(0);
                }
            }
        }
        sinks.push_back(std::move(s));
    }

    for (const vl::located_diagnostic& d : problems) {
        std::cerr << vw::format_diagnostic(d, graph) << '\n';   // place, source line, carets, each via step
    }
    for (const sink& s : sinks) {
        std::cout << std::format("{} -> {} ({} leds at {} fps)\n", s.name, s.host, s.max_count, s.fps);
    }
    return problems.empty() ? 0 : 1;
}
```

What the reader sees: overrides typed by a user are checked with the generated `is_variable_name` before `load`
(a bad name there is the misuse sort, a program bug); every list access returns a value; the language's diagnostics
print once, through the sink that starts from them.

### 4.2 An editor: change a variable and a directive's values, save with lost-update protection

The editor changes `$pixels` (one `set` line in `main.conf` that both sinks read) and the `fps` line inside
`sink.conf`, then saves. If someone changed a file on disk since it was read, the writer refuses the whole batch; the
editor reloads, applies its edits again and tries once more.

```cpp
#include <knobly/knobly.hpp>
#include <knobly/files.hpp>
#include <knobly/extensions.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;

struct edits {                                       // kept as data so they can be applied again after a reload
    std::string pixels;
    std::string fps;
};

void apply(const vw::document_graph& graph, const edits& e) {
    for (vw::variable v : graph.variables("pixels")) {
        if (auto set = v.as<vw::set_variable>()) set->set(vl::text(e.pixels));
    }
    // One line in the included file, shared by both include copies. Paths are as written: "sink.conf".
    if (auto sink = graph.documents().find("sink.conf")) {
        for (vw::statement s : sink->block().walk()) {       // editing during a walk is allowed (2.3)
            if (auto d = s.as<vw::written_directive>(); d && d->name() == "fps") {
                d->set(vl::text(e.fps));                     // "fps 20hz;" becomes "fps 30;", comments kept
            }
        }
    }
}

int main() {
    vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const edits wanted{.pixels = "2400", .fps = "30"};

    vw::document_graph graph = config.load("main.conf");
    apply(graph, wanted);

    for (int attempt = 0; attempt < 2; ++attempt) {
        try {
            for (const std::string& path : graph.save(vl::files::file_writer())) std::cout << "saved " << path << '\n';
            return 0;
        } catch (const vl::lost_update_error& e) {
            for (const std::string& path : e.paths()) std::cerr << path << " changed on disk\n";
            graph = config.load("main.conf");        // nothing was written: their changes, then ours again
            apply(graph, wanted);
        } catch (const vl::save_error& e) {
            std::cerr << e.what() << '\n';
            try {
                std::rethrow_if_nested(e);           // the writer's own failure
            } catch (const std::exception& cause) {
                std::cerr << "  because: " << cause.what() << '\n';
            }
            return 1;
        }
    }
    return 1;
}
```

What the sketch makes impossible: `set->set("2400")` does not compile (a plain string is not `config_text`); `set` is
reachable only after `as<vw::set_variable>()` (an override variable has no `set`, spec 6.7); a statement view whose
line was replaced raises `detached_error` instead of reading freed memory; `find` returns a `document` by value, so
`if (auto sink = ...)` holds nothing that can dangle.

### 4.3 A third-party tool: walk blocks for its own schema, report diagnostics with places

A lint for a made-up `upstream` schema: every `upstream` block needs at least one `server`, each `server` takes a host
and a positive integer weight, and a `server` outside an `upstream` is an error.

```cpp
#include <knobly/knobly.hpp>
#include <knobly/format.hpp>                    // std::format of a place and an unreadable reason
#include <knobly/files.hpp>
#include <knobly/written.hpp>
#include <knobly/rendered.hpp>

#include <format>
#include <iostream>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

template <class... F> struct overloaded : F... { using F::operator()...; };

void check_server(const vr::directive& server, vl::diagnostics& problems) {
    if (!server.closest([](const vr::directive& d) { return d.name() == "upstream"; })) {
        problems.report(server, "server outside an upstream block", "lb/server-outside");
        return;
    }
    auto values = server.values();
    if (values.size() < 2) {
        problems.report(server, "server needs a host and a weight", "lb/server-arity");
        return;
    }
    problems.collect([&] { return values.at(0).string(); });
    values.at(1).visit(overloaded{
        [&](const vw::expanded_word& w) {
            if (auto weight = problems.collect([&] { return w.integer(); }); weight && *weight <= 0) {
                problems.report(w, std::format("weight must be positive, got {}", *weight),
                                "lb-upstreams/weight-must-be-positive");   // any length: consteval, checked
            }
        },
        [&](const vw::expanded_value& other) {
            problems.report(other, std::format("weight must be a bare integer, got {}", other.text()), "lb/weight");
        },
    });
}

int main(int argc, char** argv) {
    vw::processor config({.source = vl::files::file_source()});
    vw::document_graph graph = config.load(argc > 1 ? argv[1] : "lb.conf");
    vr::rendered tree = vr::render(graph);

    vl::diagnostics problems(tree.diagnostics());
    for (vr::directive d : tree.block().walk()) {
        if (d.name() == "upstream" && (!d.block() || d.block()->directives("server").empty())) {
            problems.report(d, "upstream has no server", "lb/empty-upstream");
        } else if (d.name() == "server") {
            check_server(d, problems);
        }
    }
    for (vw::unreadable_expansion u : tree.unreadable()) {
        std::cerr << std::format("{}: skipped ({})\n", u.origin().place(), u.reason());
    }
    for (const vl::located_diagnostic& d : problems) {
        std::cout << vw::format_diagnostic(d, graph) << '\n';
        // lb.conf:7:9: lb/weight: weight must be a bare integer, got [1, 2]
        //     server "10.0.0.2" [1, 2];
        //                       ^^^^^^
    }
    return problems.empty() ? 0 : 1;
}
```

A written-layer linter (review 2's quick-fix tool) builds its own diagnostics with the record constructors:
`vl::located_diagnostic("svc/deprecated", "'timeout' is deprecated", field.place())`, prints them with
`format_diagnostic(d, graph)`, and edits through `const` handles captured by value in its fix closures, with no
`mutable`. Written statements are not `locatable` (spec 7.7), so `report()` refuses them; that and a statement's
"name place" are spec questions (F9), not C++ ones.

## 5. Costs, findings, questions, defaults

### 5.1 What this design gives up

- **Generated public headers.** `emit_cpp.py` is likely the largest emitter (an estimate: 1,100 to 1,400 lines, against
  632 for TypeScript and 978 for Python), and a hand-written class cannot hold private helpers.
- **Our own parser generator to keep** (800 to 1,000 lines of Python, 1.5) instead of ANTLR's tool for C++. A grammar
  change that needs a construct it refuses (a predicate, a lexer mode, left recursion) means growing it first.
- **Two parser technologies** while TypeScript and Python stay on ANTLR: the syntax corpus holds them together, and
  the differential run found two places where the ANTLR-based recovery departs from spec 3.2 (F16, F17). Until those
  are fixed, the C++ binding's tree differs from theirs on such inputs (never on tokens).
- **Compile time in every including file** in header-only mode (2.5); compiled mode is the cure, at the price of a
  second configuration to test.
- **Reference-counted views.** One pointer per view, one atomic increment per copy. A render of 100,000 directives
  (the `max directives` limit) holds that many counted references. Detached nodes stay in memory until the graph dies.
- **Two library-owned containers** (`sequence`, `ordered_map`) instead of `std::vector`: a program that wants a vector
  copies (`std::vector<T>(s.begin(), s.end())`); elements are returned by value, so iterating copies each view (one
  pointer and a count bump) and each text. In exchange nothing returned can dangle and a stored list costs nothing per
  call.
- **Text out is a copy** (`std::string`): `d.name() == "node"` may allocate for a long name.
- **No thread safety for `const`**: a `const` graph is not safe to read from two threads, against the standard
  library's convention ([res.on.data.races]); handing views between threads and destroying them anywhere is safe.
- **Expected failures are exceptions** (Q2 A): a program built with `-fno-exceptions` compiles, but an expected
  failure ends it (2.2).
- **Stale variant views** raise `misuse_error` on members only the old variant had.
- **Positions in bytes**: a UTF-16 LSP client converts; no conversion helper is offered.
- **Python 3.9 to build from git** (not from the release archive or the single header).
- **No allocator hook** (2.7): every allocation goes through global `new`.
- **No fetch adapters, no async I/O**: the standard library has neither an HTTP client nor async files.
- **macOS 13.3 deployment floor** at least (2.1).
- **Deferred**: C++20 modules (an `import knobly;` form, once GCC, Clang and MSVC all ship them well); the
  error-value API if Q2 picks A now; the same generated parser for TypeScript and Python (section 8).

### 5.2 Findings against the spec and the generator

Reported, not fixed here (each is a candidate bead for whoever lands the binding):

- **F1. `argument type error` cases assume a dynamically typed binding.** `render-not-a-graph` and every "not text"
  check cannot be written in C++: the compiler refuses the call. Proposal: a `needs` token for run-time type checks,
  with the compile-time refusal covered by the binding's compile-fail tests. Go, Rust and Java hit the same.
- **F2. The `Language` descriptor has no hook for a spelling the language forbids.** `written::index::index` and the
  inherited `written::list::list` cannot be called in C++. Proposal: a `member_spelling(class, member)` hook, checked
  by the loader against each class's own and inherited members. A loader edit, which codegen 10 says a new binding
  should not need.
- **F3. Spec 6.1's "one object" becomes "one node, every view equal"** without a collector; the binding guide's
  "must not differ" list should say identity is the language's identity form.
- **F4. Spec 6.1 does not say what a stale variant view does in a statically typed binding.** Default here: the
  misuse error. The spec should name it.
- **F5. The schema's patterns need a C++ matcher.** `emit_cpp.py` compiles each I-Regexp into a generated matcher
  over code points and refuses any construct it does not support. Alternative: RE2 or PCRE2, third-party dependencies.
- **F6. `memory source`'s map is shared by reference** in TypeScript and Python; contract 5's "the map it is given"
  reads as if a reference were always safe.
- **F7. The resolved path form differs between the bindings.** TypeScript's file source returns absolute paths
  (`path.resolve`), Python's a normalized join (`os.path.normpath`), so relative stays relative. It is the key of
  `documents()` and the `path` of every message; spec 4.1 fixes neither. C++ follows Python here.
- **F8. Edits during iteration of a written block or a walk are unspecified.** C++ states the snapshot rule of 2.3;
  the spec should state one rule for every binding.
- **F9. A written-layer tool cannot place a problem through knobly**: written statements and values are not
  `locatable` (spec 7.7), and a statement's place starts at its leading comment, with no place for its name.
  Proposals: `error(message, code)` on written statements and values; a `name place` on directive-like statements.
- **F10. No way to ask whether a handle is detached** without catching `detached_error` (a program-bug class).
  Proposal for all bindings: a `detached` property that works like `kind` on a detached handle. Until then the docs
  give a safe fix order: value and rename edits first, statement replacements last.
- **F11. The written layer has no reader for a string's content**: `written::string::text()` includes the quotes and
  escapes. Proposal for all bindings, or document reading it through `graph.expand()`.
- **F12. Edits return no replaced range**, so an editor quick fix diffs text to build an LSP edit. Spec candidate.
- **F13. Positions, token indices and occurrences are `integer`.** Proposal: a named type in the schema (`is
  integer`) for them, which C++ maps to `std::size_t` and the other bindings leave unchanged. Until then `int64_t`.
- **F14. No pattern for a directive name**, so `rename`'s misuse error has no matcher a program can call first
  (unlike `is_variable_name`). Proposal: a `directive name` pattern in the schema.
- **F15. A program arming a file watcher converts between the API's UTF-8 paths and `std::filesystem::path`**.
  Proposal: two functions in the `files` module (`to path`, `to text`), omitted by bindings whose paths are already
  strings; not hand-added in C++, because every public name comes from the schema.
- **F16. The TypeScript and Python recovery can hide later statements, against spec 3.2.** Their skip counts brackets
  from the start of the last directive of the current statements context, even one that finished, and a finished
  block directive can hold an unclosed `[` inside a recovered error statement. A later bad statement's `;` is then
  taken as inside brackets, and recovery runs on over the statements after it. Repro (`design/rd-probe/repro.py`):
  `a { b [; }` then `"x" 1;`, `c 2;`, `d ];` on three lines: Python gives one error node over all three lines and two
  diagnostics; spec 3.2 ("a broken statement never hides a later statement after its `;`") and the C++ probe give an
  error node for `"x" 1;`, the directive `c 2;`, an error node for `d ];`, and three diagnostics (E2004 on the last).
  Proposal: count from the bad statement's own first token (what the probe does); add the repro as a `rec-*` case.
  TypeScript is ported line for line from the same code (NOT RUN against it).
- **F17. Adjacent bad statements share one error node in TypeScript and Python.** `];];` gives one error node over
  four tokens with two diagnostics; spec 3.2 says a statement the parser cannot read is one error node, so two. The
  cause is the parse-tree walk (`_walk.py`), which merges a run of error tokens under one parent. Proposal: one node
  per skipped statement; add `];];` as a `rec-*` case.
- **F18. The binding guide (step 3) and `spec/README.md` name ANTLR as the only way to get a parser.** The owner's
  2026-10-29 pick gives C++ a second route, knobly's own generator; the guide's open question about a binding
  with no ANTLR target (Rust) gets a third candidate answer in the same tool. The guide should say both, and which
  checks a generated parser must pass (the corpus, plus the generator's refusals).
- **F19. The tree annotations live only in `grammar/knobly.ebnf`**, which is kept in step with the `.g4` by hand,
  while the `.g4` is the specification. The generator reads them from the `.ebnf` today. Proposal: write them as
  comments in the `.g4` (`// cst: directive`) and have `tools/check.sh` compare the two files' annotations. This also
  frees the open question of deriving or retiring the `.ebnf` (root README) from the generator.

### 5.3 Questions for the owner

**Q1. When the program drops the graph, what happens to the handles and lists it still holds?**

| Option | What it means | Cost |
|---|---|---|
| **A. They keep the graph alive** (recommended) | a handle, a list or a walk is a small shared reference; the graph is freed when the last one goes; a removed line's handle raises `detached_error`; nothing returned can dangle (the reviews' probes found four ways the draft's reference-returning containers did) | one atomic count bump per copy; detached lines stay in memory until the graph goes; two library container types instead of `std::vector` |
| B. They are borrowed | the program owns the graph; handles and lists are plain references valid while it lives (LLVM, clang, pugixml) | fastest, but a handle used after the graph is gone, or a reference kept from a temporary list, is undefined behaviour: a crash or silent garbage, which no compiler warning reliably catches |

Recommendation A: it makes use-after-free impossible instead of documented ("make the failure class impossible"),
and it matches what TypeScript and Python users get from their collectors.

**Q2. Should a failure the program must expect be an exception or a returned value?** (reshaped by header-only)

ANTLR no longer forces exceptions inside the library (2.2). What remains is the API's own model, and one
header-only fact: knobly's code is compiled with each program's own flags.

| Option | What it means | Cost |
|---|---|---|
| **A. Exceptions** (recommended) | the error tree as C++ exception classes, as TypeScript and Python throw; `catch (const knobly::knobly_error&)` catches every expected outcome and no bug. A program built with exceptions off still compiles: each throw prints its message and stops the program, as the standard library itself does | programs built with `-fno-exceptions` (many game engines and embedded builds) cannot recover from an expected failure, such as a value that is not a number; adding a value form later would be a second API, not a switch |
| B. Returned values | `load`, `read`, `save`, the edits and the readers return a result holding the value or the error (`std::expected` in C++23, or a small knobly `result` type in C++20), as spec 2.8 proposes for Go and Rust; works the same with exceptions on or off | every call site checks a result; `collect` takes a different shape; C++ reads unlike TypeScript and Python; spec 2.8's pending proposal would have to be accepted first |

Recommendation A: one model with the other two bindings, plain C++20, the idiom of the standard library and of
`std::filesystem`, and with header-only the exceptions-off case is no longer a compile failure. Choose B if C++ users
who ban exceptions are a target audience; decide now, because the two are different APIs. A switch offering both
(toml++ does this) is not offered: it would be two APIs in one binding to document and test.

### 5.4 Recommended defaults (each can be reopened)

| # | Default | Main alternative |
|---|---|---|
| D1 | C++20; GCC 12, Clang 16, AppleClang 16, MSVC 19.34; macOS deployment 13.3 or later; headers tested under C++20 and C++23 | C++17 for reach (loses designated initializers and the compile-time code check) |
| D2 | `snake_case` everywhere; generated headers fully qualified; README advises namespace aliases, never using-directives | Google/Abseil or LLVM style |
| D3 | full spec names (`written::written_directive`) | drop the layer word |
| D4 | namespaces `knobly`, `::syntax`, `::written`, `::rendered`, `::files`, `::extensions`; one header each; opt-in `format.hpp` | C++20 modules once every compiler supports them well |
| D5 | the emitter writes whole public headers; hand code writes inline definitions in `detail/`; a generated contract odr-uses every member | hand headers checked by generated `static_assert`s |
| D6 | unions as view classes with `kind()`, constrained `as<V>()`, `visit(f)`; an anonymous union of one union's variants as that union's class; others as `std::variant` | `std::variant` for every union |
| D7 | records as immutable classes with public constructors and accessors; options as aggregates with designated initializers | aggregates with public fields |
| D8 | ports as abstract classes held by `std::shared_ptr`; `locatable` as a concept | type-erased port values |
| D9 | text in `std::string_view`, out `std::string`; lists `sequence<T>` and maps `ordered_map<K, V>`, shared, element access by value | `std::vector` results with value-returning wrappers only on maps |
| D10 | `integer` is `std::int64_t`; positions too until F13; `count` is `size()`; `index` is `at(i)` | an unchecked `operator[]` |
| D11 | people form as ADL `to_string`; `std::formatter` and `operator<<` in `format.hpp` | in the core header |
| D12 | `walk()` / `walk(descend)` return an input range that owns its data; iteration snapshots; edits never invalidate | any edit invalidates the walk |
| D13 | `collect(read)` returns `std::optional<R>` (`bool` for a `void` read); its `try` in the header, compiled only with exceptions on | always `bool` |
| D14 | `program_code`: `consteval` literal check, `string_view` to static text or a shared owned copy | a run-time check only |
| D15 | `argument_type_error` for a null port or empty callable only | no such class in C++ |
| D16 | a stale variant view raises `misuse_error` (F4); knobly's own `misuse_error` and `index_out_of_range` classes | the plain `std` classes |
| D17 | one UTF-8 entry function (`detail/text_in.hpp`), also the lexer's decoder; provisional behaviour per entry point (2.4) until kno-pol is ruled | refuse to parse until ruled (breaks "parse is total") |
| D18 | header-only; one `INTERFACE` CMake target; the release source archive with generated headers; `KNOBLY_REGENERATE` on in a git checkout (Python only) | a compiled library (what the owner's pick ruled out) |
| D19 | Catch2 v3, test-only; ASan and UBSan; compile-fail tests; clang-format and clang-tidy | GoogleTest; doctest (header-only, if a header-only test framework is preferred) |
| D20 | the adapter's own JSON codec | a JSON library (none keeps `\ud800`) |
| D21 | no fetch adapters, no cancellation | an optional extension module on a third-party HTTP client |
| D22 | global `new`, no allocator hook | a `std::pmr::memory_resource*` in `processor_options` |
| D23 | views: one pointer and an intrusive atomic count | a non-atomic count (views of a graph then never destroyed on two threads at once) |
| D24 | `file_source` resolves to the lexically normal join with `/` (Python's form, F7) | absolute paths (TypeScript's form) |
| D25 | the parser from knobly's own generator (`tools/parser/`), the recovery and error codes by hand (1.5); C++ only for now | a hand-written parser held to the corpus (no generator to keep, but every grammar change edited by hand in C++) |
| D26 | optional compiled mode (`KNOBLY_HEADER_ONLY=0` plus one file); explicit instantiation of the support templates in it | header-only only |
| D27 | a single-header file as a second release asset, never committed | none, or the single header as the only form |
| D28 | a versioned inline namespace (`knobly::v0`) | none (two versions in one program then misbehave silently) |
| D29 | layer direction checked at compile time by `tests/layers.cpp` (forbidden include guards pre-defined) | a script that scans `#include` lines |
| D30 | under `-fno-exceptions`, a throw site prints the error and aborts (if Q2 is A) | refuse to compile without exceptions |

### 5.5 Checks for this revision

- Ran, header-only round (AppleClang 21, under `/Volumes/Dock/tmp/kno-cpp-design/design/rd-probe/`):
  - `python3 gen_cpp.py ../../grammar/Knobly.g4 ../../grammar/knobly.ebnf knobly_gen.hpp`: wrote 574
    lines; lexer 45 states; 32 one-token choice points, 5 longer ones (57 lookahead states); no refusal.
  - `clang++ -std=c++20 -O1 -Wall -Wextra -Werror -fno-exceptions -fno-rtti -fsanitize=address,undefined` of
    `probe_main.cpp`, then `python3 run_l0.py ../.. ./probe`: "168 of 168 cases byte-identical to
    conformance/expected". With `-DKNOBLY_ANTLR_COMPAT`: also 168 of 168. A planted wrong code: 157 of 168.
  - `uv run --project ref/py python fuzz_diff.py 20000 7 ./probe`: 18,414 of 20,000 identical to the Python binding
    (tokens always; 1,564 trees and 27 diagnostic lists differ); with `./probe_compat`: 19,997 of 20,000. `ref/` is
    a copy of the export's `grammar/`, `tools/`, `spec/`, `py/` and `ts/` with `tools/gen.sh py` and `ts` run in it.
  - `repro.py`: the F16 and F17 inputs, Python against the probe (5.2).
  - Compile cost: `-fsyntax-only -O2` of a file including `syntax.hpp`: 0.36 s; of one including `<string>` and
    `<vector>`: 0.29 s. A 2 MB input: 0.63 s.
- Ran, earlier round: two probes with AppleClang 21 (`-std=c++20 -Wall -Wextra`, ASan, and UBSan for the second), under
  `/Volumes/Dock/tmp/kno-cpp-design/design/cpp-final-probes/`. `code.cpp`: the `program_code` form takes a 60-character
  literal, refuses `"nolash"` at compile time, refuses `view()` on a temporary, and keeps a run-time code valid after
  its source string is cleared. `helper.cpp`: the reviewers' helper-type form does not compile at a call site (section
  6). `seq.cpp`: as in 2.3. All ran clean.
- Read: `ts/src/node.ts` (`path.resolve`) and `py/src/knobly/files.py` (`os.path.normpath`) for F7;
  `spec/schema/api.json` for the records, the `locatable` interface and the two patterns;
  `py/src/knobly/syntax/_recovery.py`, `_parse.py` and `_walk.py`, ported by the probe.
- NOT RUN: GCC and MSVC (none on this Mac); the probe under GCC; the differential run against the TypeScript binding
  (its recovery is a line-for-line port of Python's, so F16 and F17 are expected there too, not seen); the
  generator on the entry rules' entry points (generated, not exercised: no entry-rule cases at L0);
  `tools/check.sh` and the TypeScript, Python and repo checks (this round changed no repo code); the compile cost of
  the written and rendered layers (they do not exist yet); the single-header script; the "to verify in slice 1" items
  (libc++ `from_chars`, the include budget, `-fno-rtti` across the whole API).

## 6. Integrator findings refused, and why

- **"Use the `std::format_string` pattern for `program_code`: a helper with a `consteval` constructor, and an implicit
  `program_code` constructor from the helper"** (review 1). Refused in that form: a string literal then needs two
  user-defined conversions to reach a `program_code` parameter, which C++ never chains, so `report(d, msg,
  "lb/weight")` stops compiling (`helper.cpp`: "no matching function for call to 'report'"). `std::format` avoids this
  only because its parameter *is* the helper type, which would double every member taking a code. The fault is fixed
  another way: `program_code` holds a `string_view` to the literal's static text (nothing to allocate at compile
  time), or to a shared owned copy for a run-time code (`code.cpp`).
- **"Use a non-atomic count"** (review 1). Taken in part: one pointer per view, not two. The count stays atomic: it
  costs a few cycles per copy and makes handing a view to another thread and destroying it there safe, which a
  hot-reload worker or a logging thread does. The other half of the cost the review named, a vector built per call,
  is removed by `sequence`.
- **"Map every anonymous union of one union's variants to that union's class, so `parent->name()` works"** (review
  2). Taken, but it does not give `parent->name()`: `statement` has no `name` (only some of its variants do), so
  reading the parent's name still takes `as<written_directive>()`. TypeScript can read members shared by just the
  listed arms because its types are structural; C++ would need a named class per anonymous union, names the schema
  does not have. The mapping still removes the `std::visit` for `kind()`, `place()` and `text()`; the cost is that
  the type no longer lists which three variants a parent can be (the doc comment does).
- **"Put a one-argument `format_diagnostic` in namespace `knobly`"** (review 2). Refused: the schema places
  `format diagnostic` in the written layer, and the layer of a name is the schema's fact, not the binding's. Taken:
  two overloads in `written` replace the optional parameter.
- **"Add `files::to_path` and `files::to_text`"** and **"a `detached()` member"** (both reviews). Refused as
  hand-added C++ names: every public name comes from the schema, and the generated contract would refuse them. Filed
  as schema candidates F15 and F10, with a documented fix order meanwhile.
- **"Show a matcher for a directive name"** (review 1). The schema has no directive-name pattern, so there is nothing
  to generate; inventing the rule in C++ alone would give the C++ binding a rule the others lack. Filed as F14.
  `is_variable_name` is now shown and used.
- **"An optional-returning accessor by index"** (review 1, offered as a "consider"). Declined: `at(i)` with `size()`
  is the standard containers' form, and TypeScript's `values[1]?.text` has no C++ spelling short of a new member name
  the schema does not have. The 4.1 bug it would have hidden is fixed by checking `size()`.
- **"Keep `std::vector` and `ordered_map` but make only `at`/`find` return values, with `[[clang::lifetimebound]]`"**
  (the reviews' fallback). Not taken: `std::vector::at` would still return a reference into a temporary, and
  `lifetimebound` is a Clang extension that GCC and MSVC ignore; it warns, it does not make the fault impossible.

## 7. Milestone outline for building the binding

Few large slices, each landing green on its own (the implementation-workflow model: tracer first, then vertical
slices). Sizes are rough estimates in hand-written lines, not counting generated code; the TypeScript and Python
bindings are about 5,100 and 5,800 lines.

| Slice | What lands | Proven by | Rough size |
|---|---|---|---|
| **1. Tracer: parser generator, emitter, parse, adapter** | `tools/parser/` (grammar reader, lexer tables, lookahead machines, C++ output, refusals) with its planted grammars in `tools/check.sh`; `emit_cpp.py` (descriptor, enums, codes, limits, records, pattern matchers, the shared and syntax headers, `api_contract.cpp`, `layers.cpp`); the loader's `member_spelling` hook (F2) and the F13 named type in `api.json` if the owner agrees; `tools/gen.sh cpp`; `cpp/CMakeLists.txt` (the `INTERFACE` target, the regeneration step, both modes); `support/` (`sequence`, `ordered_map`, `view.hpp`, `config.hpp`); `text_in.hpp`; `syntax::parse` with the recovery and error codes; the conformance adapter with its JSON codec and `hello` (`"unit": "byte"`) | the shared driver's syntax cases (168) green through the adapter, in header-only and compiled mode, the syntax layer also with exceptions and RTTI off; `tools/check.sh` green, the generator refusing every planted grammar; the compile-time budget recorded | generator 800 to 1,000; emitter 700 to 900; C++ 1,800 to 2,300; adapter 800 |
| **2. Written layer: load, edits, save** | the written header from the emitter; processor and load (sources, `memory_source`, `file_source`, the include extension), the graph, documents, statements, values, variables, resolutions, the expansion and expanded values with their readers, every edit with the strong guarantee, `save` with lost-update checking, `file_writer`, iteration snapshots, `diagnostics` and `collect`, `format_diagnostic`; programs 4.2 as a test; explicit instantiation for compiled mode | the `load`, `written` and `variables` conformance cases; Catch2 tests for iteration during edits, detached handles and stale variant views; ASan and UBSan clean; the compile-time budget per layer | 5,000 to 7,000 |
| **3. Rendered layer** | `render`, rendered directives and blocks, `walk_view` with `descend`, `closest`, `addresses` with key rules, `diff`, `format.hpp`; programs 4.1 and 4.3 compiled and run as tests; compile-fail tests (F1) | the `rendered` and `keys` conformance cases; the full 380-case run green; `emit_docs.py` gains the C++ column | 2,000 to 3,000 |
| **4. CI leg and packaging** | a CI leg (GCC, Clang, AppleClang, MSVC; both modes; ASan and UBSan; clang-format and clang-tidy); `cmake --install` with the package config and version file; the release source archive and the single-header file from the automated release flow; the versioned inline namespace; README (aliases not using-directives, threads, exceptions, compiled mode, path form) | a consumer project builds from the archive with no Python or network, and from the single header alone; `find_package(knobly)` works from an install | 400 to 800 plus CI and CMake config |

Filed with slice 1, not built: the spec findings F1, F3 to F15 and F16 to F19 as beads, each needing the owner's word
where it changes a rule for every binding. F16 and F17 need a fix in TypeScript and Python (or section 8) for the
new `rec-*` cases to pass there.

## 8. A separate, optional proposal: one generated parser for every binding (not planned)

The generator's analysis (lexer tables, lookahead machines, refusals) does not depend on the output language; only
its last step writes C++. A TypeScript and a Python output step (an estimate: 150 to 250 lines each) would let both
bindings drop the ANTLR runtime, their one third-party run-time dependency (the owner, 2026-10-25, on third-party
libraries), and Java from their build. Each would keep a hand-written recovery and error-code port (about 250 lines,
against about 550 lines of ANTLR glue today), so all three bindings would share one recovery shape and F16 and F17
would be fixed by construction. Costs: knobly's generator becomes the only parser source for every binding, so a
generator bug reaches all three at once (the corpus and the differential run guard it); ANTLR's grammar tools stay
usable on the `.g4` but no longer describe the shipped parser; the speed of a generated Python parser against the
ANTLR Python runtime is not measured. This is offered as a direction only; nothing in this design depends on it.
