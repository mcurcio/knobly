# C++ binding milestone 1 (tracer), frozen for the lanes

This page is what Lane P, Lane A and Slice T build in milestone 1 of the C++ binding. It is frozen: a lane that finds
it wrong appends the finding to `.claude/errata.md` and does not diverge silently. `spec/` is canonical; where this
page and `spec/` differ, `spec/` wins and the difference is an erratum. Where this page and `design.md` differ, this
page wins for milestone 1 (section 9 lists each difference and why).

## 0. What this rests on

The owner's words, quoted, not widened (`answers.md` has the dates and the question numbering):

- 2026-10-28: "clean, easy to comprehend API design", "idiomatic in each language", "consistent across layers", codegen
  "so we dont have to maintain n languages by hand".
- 2026-10-25: "I don't want villanelle dependent on third party libraries (including pydantic) so any shims must be
  optional extensions rather than core."
- 2026-10-29: C++ is header-only with no ANTLR runtime, "but with as much auto codegen as possible to unify with
  typescript and python".
- 2026-10-30, the C++ review page: Q1 A (expected errors throw exceptions mirroring the error tree); Q2, "Are you asking
  about ref counting? Ok" (handles share ownership of the graph, reference counted, never dangle); Q3 A (each
  language's standard formatter on generated code, pinned exactly).
- 2026-10-23: "Don't commit the generated code, just the source".

Everything else on this page is a design call made against `design.md` (approved), revisable through an erratum.

**Milestone 1 delivers:** `syntax::parse` in C++, generated from `grammar/Knobly.g4` by knobly's own parser
generator, with every public declaration generated from `spec/schema/api.json`; the conformance adapter claims level 0
and passes all 168 L0 cases through the shared driver, in header-only and compiled mode, on the CI leg; `tools/check.sh`
and the TypeScript and Python checks stay green and their behaviour does not change.

**Not in milestone 1:** the written and rendered layers' definitions (slices 2 and 3), `format.hpp`, the io adapters'
definitions, install and packaging, the single-header file, the compile-time budget as a gate, the F16/F17 `rec-*`
cases in the shared corpus (TypeScript and Python would fail them; section 7.4).

## 1. Order and ownership

```text
skeleton (landed: this commit) --> Lane P (parser generator) ---\
                               \-> Lane A (C++ API emitter) ------> Slice T (tracer: hand syntax layer, adapter,
                                                                    CMake, CI, gen/check scripts, spec text)
```

Lane P and Lane A run in parallel: their paths are disjoint and each starts from green. Slice T starts when both have
landed. Every lane keeps `bash tools/check.sh`, the TypeScript checks and the Python checks green at its own commit.

### 1.1 Owned paths (exact)

| Owner | Paths |
|---|---|
| **Lane P** | `tools/parser/` (all of it: `gen.py`, `g4.py`, `cpp.py`, and the new `lexer.py`, `lookahead.py`, `test_parser.py`); `tools/planted-parser/` (new); `grammar/Knobly.g4` (the five `// cst:` comments only, F19); the generated `cpp/include/knobly/detail/syntax/parser.gen.hpp` (never committed) |
| **Lane A** | `tools/api/emit_cpp.py`; `tools/api/loader.py`; `tools/gen-api.py`; `tools/api/emit_docs.py`, `tools/api/stub.py`, `tools/api/formatter.py` (only if a loader hook needs them); `tools/api/emit_ts.py` and `tools/api/emit_py.py` (only a one-line descriptor change a new loader hook forces; their output must not change); `spec/schema/api.json` (only a fix an erratum records); `spec/codegen.md`; the generated tables `python3 tools/gen-api.py docs` rewrites (`spec/spec.md`, `spec/glossary.md`, `spec/contract.md`, `spec/conformance.md`, `spec/codegen.md`); `cpp/.clang-format`; the generated `cpp/include/knobly/*.hpp`, `cpp/conformance/shapes.hpp`, `cpp/tests/generated/` (never committed) |
| **Slice T** | `cpp/CMakeLists.txt`; `cpp/.gitignore`; `cpp/include/knobly/support/`; `cpp/include/knobly/detail/` except `detail/syntax/parser.gen.hpp`; `cpp/conformance/adapter.cpp`, `cpp/conformance/json.hpp`; `cpp/tests/compile/`, `cpp/tests/unit/` (new); `cpp/README.md` (new, optional in M1); `.github/workflows/ci.yml`; `tools/gen.sh`; `tools/check.sh`; `spec/binding-guide.md`; `spec/README.md`; `README.md` (root); `.claude/skills/knobly-binding/SKILL.md` |
| skeleton (this commit, then the owners above) | every path in section 1.2 |

Shared rules: no lane edits another lane's paths; a lane that needs a change there writes an erratum and asks the
orchestrator. `.claude/errata.md` is append-only for every lane. Generated files are never committed (each lane checks
`git status` shows none).

### 1.2 What the skeleton committed (all compile or run green)

| Path | State |
|---|---|
| `.claude/design/cpp/design.md`, `gate.md`, `answers.md`, `frozen-m1.md` | the approved design, the owner's page, his answers, this page |
| `spec/schema/api.json` | `argument type error` and `index out of range` gain `"message": {"given": true}` (erratum 2026-10-30, C++ 1); TypeScript, Python and docs output byte-identical (checked by rendering both schemas) |
| `tools/api/loader.py` | `Formatter.suffix` takes one suffix or a tuple (C++ formats `.hpp` and `.cpp`) |
| `tools/api/emit_cpp.py` | the C++ `Language` (as far as today's `Language` takes it), `CLANG_FORMAT`, `render`, `render_shapes`, `render_contract`; `kinds.hpp` real, every other file a placeholder |
| `tools/gen-api.py` | `cpp` target (`TARGETS`), `OUT["cpp"]`; `cpp` is not yet in `EMITTERS`, so `--check` and the docs tables do not see it |
| `tools/parser/gen.py`, `g4.py`, `cpp.py` | entry point, a names-only grammar reader, and a placeholder header with the frozen interface (section 3.2) and stub bodies; output formatted by the pinned clang-format |
| `tools/gen.sh` | `cpp` case: `tools/parser/gen.py cpp` then `tools/gen-api.py cpp`; no Java |
| `tools/check.sh` | check 8: `python3 tools/parser/gen.py --check` |
| `cpp/CMakeLists.txt`, `cpp/.gitignore`, `cpp/.clang-format` | the INTERFACE target, regeneration at configure time, compiled mode, a compile-only check target and the adapter |
| `cpp/include/knobly/support/` | `config.hpp` (whole); `sequence.hpp`, `ordered_map.hpp`, `view.hpp`, `block.hpp`, `walk_view.hpp` (declarations) |
| `cpp/include/knobly/detail/` | `raise.hpp`, `text_in.hpp` (declarations); `<x>/definitions.hpp` for `shared io syntax written rendered files extensions` (empty entry points); `syntax/parse.hpp` (the hook class, declared) |
| `cpp/conformance/adapter.cpp`, `json.hpp` | a `main` that compiles against the public headers and exits 1; the codec declared |
| `cpp/tests/compile/` | `headers.cpp`, `support.cpp`, `parser_hooks.cpp` (explicit instantiation of the generated parser against the hooks), `implementation.cpp` (compiled mode) |

Build of the skeleton (AppleClang 21): `cmake -S cpp -B /Volumes/Dock/tmp/kno-cpp-build/<dir>` then `cmake --build`,
green for header-only, `-DKNOBLY_COMPILED=ON` and `-DCMAKE_CXX_STANDARD=23`.

## 2. The file map after milestone 1

```text
cpp/
  CMakeLists.txt  .gitignore  .clang-format  README.md (optional)                       T, T, A, T
  include/knobly/
    knobly.hpp syntax.hpp written.hpp rendered.hpp files.hpp extensions.hpp         A, generated
    kinds.hpp codes.hpp limits.hpp errors.hpp implementation.hpp                        A, generated
    support/config.hpp sequence.hpp ordered_map.hpp view.hpp block.hpp walk_view.hpp    T, hand
    detail/raise.hpp text_in.hpp                                                        T, hand
    detail/<shared|io|syntax|written|rendered|files|extensions>/definitions.hpp         T, hand (entry points)
    detail/shared/people.hpp                                                            T, hand (to_string bodies)
    detail/syntax/parse.hpp                                                             T, hand
    detail/syntax/parser.gen.hpp                                                        P, generated
  conformance/adapter.cpp json.hpp                                                      T, hand
  conformance/shapes.hpp                                                                A, generated
  tests/compile/*.cpp  tests/unit/*.cpp                                                 T, hand
  tests/generated/api_contract_<header>.cpp  layers_<header>.cpp                        A, generated
tools/parser/gen.py g4.py lexer.py lookahead.py cpp.py test_parser.py                   P
tools/planted-parser/*.g4                                                               P
tools/api/emit_cpp.py (+ loader hooks)                                                  A
```

`<header>` is a public header's stem: `knobly syntax written rendered files extensions`. Every header directly in
`include/knobly/` is generated, so `tools/gen-api.py` owns that folder (it removes a file it no longer writes);
`support/` and `detail/` are hand-written but for `parser.gen.hpp`.

## 3. Lane P: the parser generator

### 3.1 Input and command line

```text
python3 tools/parser/gen.py cpp       writes cpp/include/knobly/detail/syntax/parser.gen.hpp; exit 0, 1 (refused or
                                      failed: one line on stderr naming the rule and line), 2 (usage)
python3 tools/parser/gen.py --check   exit 0 and one stdout line, or 1 with the failure:
  "grammar accepted: lexer <n> states; <a> one-token choice points, <b> longer (<s> lookahead states);
   <p> planted grammars refused; tree annotations agree with knobly.ebnf"
```

- Input: `grammar/Knobly.g4` only (after F19 the `.ebnf` is read by `--check` alone, for the comparison).
- Python 3.9+ standard library; the one exception is the formatter: the output goes through
  `tools/api/formatter.py` with `api.emit_cpp.LANGUAGE.formatter` (the clang-format pin's one home), as `gen.py`
  already does. `--check` does not format.
- **Deterministic:** the same grammar gives byte-identical output.
- **The `.g4` subset** read: literals, character sets and their negation, fragments, `( | )`, `?`, `*`, `+`, `EOF`,
  `grammar` and `fragment` keywords, comments. Anything else is refused by name with its line.
- **Refusals** (each a planted grammar in `tools/planted-parser/`, all refused by `--check`): a semantic predicate, an
  action, a lexer mode or command (`-> skip`, `-> channel`), left recursion, an SLL conflict (two alternatives with the
  same continuation), a lookahead machine over 400 states, a tree annotation naming no rule or two annotations on one
  rule. Names: `predicate.g4`, `action.g4`, `lexer-mode.g4`, `left-recursion.g4`, `sll-conflict.g4`,
  `state-limit.g4`, `bad-annotation.g4`.
- **Tree annotations (F19):** a trailing comment `// cst: <node kind>` on the line where a parser rule starts, for
  exactly the five rules the `.ebnf` annotates (`document`, `directive`, `block`, `slicedWord` -> `slice`, `list`).
  The `.ebnf` keeps its annotations; `--check` compares the two sets (the `.ebnf`'s PascalCase rule names lowered at
  the first letter) and fails on any difference. ANTLR ignores comments, so the TypeScript and Python parsers are
  unchanged; Lane P proves it with the TypeScript and Python checks and `tools/check.sh` (the Bison and token checks
  read the same file). If any of them breaks, Lane P leaves the annotations in the `.ebnf`, reads them from there and
  says why in an erratum.
- `test_parser.py` (standard-library `unittest`, run by `--check`): the lexer's longest match and first-rule tie, one
  LL(1) and one LL(*) decision, each refusal's message.

### 3.2 Output: the generated header's interface (frozen C++)

```cpp
// cpp/include/knobly/detail/syntax/parser.gen.hpp
#ifndef KNOBLY_DETAIL_SYNTAX_PARSER_GEN_HPP            // this guard, exactly
#include <cstddef> <cstdint> <string_view>                  // and nothing heavier
#include <knobly/kinds.hpp>                             // ::knobly::token_kind, ::knobly::node_kind (Lane A)
#include <knobly/support/config.hpp>
KNOBLY_NAMESPACE_BEGIN
namespace syntax::detail {

enum class tk : std::uint8_t { /* the 21 token kinds in grammar order */, end_of_text };
inline constexpr std::size_t token_count = 21;
static_assert(static_cast<int>(tk::WORD) == static_cast<int>(::knobly::token_kind::WORD));   // one per token kind

struct lex_match { int kind; std::size_t end; };            // kind: an index into tk, or -1 (no token starts here)

// Longest match at byte `at`; ties go to the rule written first. decode(text, i, cp) returns the byte length of the
// code point at i (stored in cp), 0 when the bytes there do not decode (then the match stops).
template <class Decode>
constexpr lex_match lex_longest(std::string_view text, std::size_t at, Decode decode) noexcept;

template <class Derived>
class generated_parser {
protected:
    std::size_t err_ = 0;                                   // the token index where the last failed prediction died
    Derived& self() noexcept;
public:
    bool r_<rule>();                                        // one per parser rule, g4 spelling: r_document, r_slicedWord,
                                                            // r_statementsText, ... (entry rules included)
};
}  // namespace syntax::detail
KNOBLY_NAMESPACE_END
```

**Hooks `Derived` supplies** (Slice T, in `detail/syntax/parse.hpp`; the skeleton declares them):

| Hook | Contract |
|---|---|
| `tk la(std::size_t i) const noexcept` | the kind `i` tokens ahead of `pos()`; `tk::end_of_text` past the end |
| `std::size_t pos() const noexcept` | the current token index |
| `bool match(tk kind)` | consume a token of `kind` (`end_of_text` is matched, not consumed), or report at `pos()` and return false |
| `bool fail(std::size_t at)` | report a syntax error at token index `at`; returns false |
| `void open_node(::knobly::node_kind)` | an annotated rule starts (called before its body) |
| `void close_node()` | that rule's body (or its recovery) succeeded |
| `void fail_node()` | that rule failed |
| `bool recover_document()`, `recover_statements()`, `recover_block()` | spec 3.2 recovery, called when that rule's own body fails; its result is the rule's |

**Rule function shape** (as the probe): `r_<rule>()` of an annotated rule is
`open_node(k); if (b_<rule>() [|| recover_<rule>()]) { close_node(); return true; } fail_node(); return false;`;
an unannotated rule returns `b_<rule>() [|| recover_<rule>()]`. The recovery list is
`cpp.RECOVER = ("document", "statements", "block")`, the generator's one copy (a rule named there and missing from the
grammar is refused). A choice point that finds no alternative calls `fail(err_)` with the token where the last
alternative died.

**Not generated by Lane P:** token names as text (`to_string(token_kind)` is Lane A's, in `kinds.hpp`), the token loop,
error codes, recovery, the nesting guard. The generated code must compile with `-Wall -Wextra -Werror -fno-exceptions
-fno-rtti` (GCC 12+, Clang 16+, AppleClang 16+) and `/W4 /WX` (MSVC), under C++20 and C++23.

**Done when (Lane P):** `tools/parser/gen.py --check` passes with every planted grammar refused; `tools/check.sh`,
TypeScript and Python checks green; the skeleton's CMake build green against the real header (`parser_hooks.cpp`
instantiates every rule); the probe's numbers reproduced or explained in the result (lexer 45 states, 32 one-token
and 5 longer choice points, 57 lookahead states). Slice T, not Lane P, proves the 168 cases.

## 4. Lane A: the C++ API emitter

### 4.1 Loader hooks (each a `Language` field with a default that keeps TypeScript and Python unchanged)

| Hook | Why | C++ value |
|---|---|---|
| `type_case: Callable[[str], str] = pascal` | `Model.public` and `gen-api.py`'s `check_layers` spell type names with `pascal` (erratum C++ 2) | `snake` |
| `member_spelling: Callable[[str, str], str]` (class, member) | F2: a member may not share its class's name, own or inherited; the loader checks inherited members | `member + "_"` when `snake(member) == snake(cls)` (`index_()`, `list_()`) |
| `pattern_form: Callable[[str], str]` | the public name of a pattern's matcher | `is_<snake(constant)>` |
| `trait_names` (exists) | the support templates are public names | `sequence`, `ordered_map`, `walk_view` in `knobly` |

Then `cpp` joins `EMITTERS` (delete `TARGETS`: it equals `EMITTERS` again), `--check` renders it, `check_layers`
checks the planted record by the language's type spelling, and `python3 tools/gen-api.py docs` gives every
per-language docs table a C++ column (the tables have one column per `Language`: the stub proves it). Commit the
regenerated tables.

### 4.2 Generated files (exact names; `render`, `render_shapes`, `render_contract`)

| File | Holds | Defined by |
|---|---|---|
| `knobly.hpp` | includes `kinds codes limits errors`, `<knobly/support/{config,sequence,ordered_map,view,block,walk_view}.hpp`; declares the shared and io layers in `namespace knobly`; `is_program_code`; ends `#if KNOBLY_HEADER_ONLY` including `detail/shared/definitions.hpp` and `detail/io/definitions.hpp` | generator (records, kinds, matchers whole); hand (`to_string` of records, io functions, `diagnostics`) |
| `syntax.hpp`, `written.hpp`, `rendered.hpp` | includes `knobly.hpp` and the headers of the layers it may import; declares the layer in `namespace knobly::syntax` etc.; `written::is_variable_name` in `written.hpp`; ends including `detail/<layer>/definitions.hpp` | as above |
| `files.hpp`, `extensions.hpp` | the adapter modules (`files`, `include`), namespaces `knobly::files`, `knobly::extensions` | hand (slice 2) |
| `kinds.hpp` | every kind list the binding keeps as `enum class <snake name> : std::uint8_t`, values `snake` (token kinds verbatim, in grammar order), and `std::string_view to_string(<kind>) noexcept` per list, all inline; includes only `<cstdint> <string_view>` and `support/config.hpp` (the generated parser includes it) | generator, whole |
| `codes.hpp` | `enum class diagnostic_code : std::uint16_t { unterminated_string = 1001, ... }`, `to_string(diagnostic_code)` (`"E1001"`), the messages, `code_facts`, `describe` | generator, whole |
| `limits.hpp` | `inline constexpr std::int64_t max_nesting = 100;` and every limit; the reserved names | generator, whole |
| `errors.hpp` | the class tree of design 2.2 from `error groups` and `error_roots`: each class `[[gnu::visibility("default")]]` on GCC and Clang, with a constructor taking the message (when given) then its fields, `const` accessors for fields | generator, whole |
| `implementation.hpp` | compiled mode: `#error` in header-only mode; includes every public header, then every `detail/<x>/definitions.hpp` | generator, whole (it is the schema's layer list: one home) |
| `cpp/conformance/shapes.hpp` | `namespace adapter::shapes`: `inline constexpr int protocol = 1;`, `std::string_view spelling(std::string_view spec_name)` (a spec name in C++ casing), `std::optional<std::string_view> error_group_of(const std::exception&)` (most specific group first), all inline | generator, whole |
| `cpp/tests/generated/api_contract_<header>.cpp` | one `int main()` per public header that odr-uses every hand-defined public function and member of that header (takes each address, calls each free function through a volatile function pointer), so a declaration without a definition fails to link | generator |
| `cpp/tests/generated/layers_<header>.cpp` | defines the include guards of every header the header's layer may not import (from `may import`), then includes the header; a forbidden include leaves names undeclared and fails to compile | generator |

Header rules: guard `KNOBLY_<STEM>_HPP`; every type spelled fully qualified from `::knobly`; Doxygen `///`
comments from each concept's and member's `doc`, `@throws` from `errors`; layout from clang-format only.

### 4.3 The generated/hand split (frozen; design 1.3 and 1.4 give the type forms)

- **Records, named types (`config_text`, `program_code`), kinds, codes, limits, errors, matchers: generated whole**,
  inline in the header. A record is an immutable class: private fields `<name>_`, one public constructor taking the
  properties in Python's dataclass field order (inherited first, then own, in schema order; `match args` first when
  the schema gives them), a `const` accessor per property returning by value (`noexcept` for scalars), and
  `friend bool operator==(const T&, const T&) = default;`.
- **Free functions and hand-defined members: declared with `KNOBLY_API`** (inline in header-only mode, nothing in
  compiled mode); the hand code defines them with `KNOBLY_API` in `detail/`. A trailing optional parameter is an
  overload without it.
- **Handles and snapshots:** one private `::knobly::detail::view view_;`, a private
  `explicit T(::knobly::detail::view) noexcept;` and `friend struct ::knobly::detail::access;`. A union's
  view class has the shared members, `kind()`, `as<V>()` and `visit(f)`; each variant derives from it.
- **People form:** `std::string to_string(const T&)` declared in the concept's namespace (ADL); the hand code defines
  it.
- Every layer's header is rendered in milestone 1 and compiles on its own with `-Wall -Wextra -Werror`; definitions
  exist only for what Slice T implements (section 5).

### 4.4 Milestone 1 signatures the tracer rests on

```cpp
namespace knobly {
class source_position { public: source_position(std::int64_t offset, std::int64_t line, std::int64_t column);
    std::int64_t offset() const noexcept; std::int64_t line() const noexcept; std::int64_t column() const noexcept; };
class source_span { public: source_span(source_position start, source_position end);
    source_position start() const noexcept; source_position end() const noexcept; };
class diagnostic { public: diagnostic(diagnostic_code code, std::string message, source_span span);
    diagnostic_code code() const noexcept; std::string message() const; source_span span() const noexcept; };
KNOBLY_API std::string to_string(const diagnostic& d);         // hand: "4:5: E1001: unterminated string"
constexpr std::string_view to_string(token_kind) noexcept;        // generated: "WORD"
constexpr std::string_view to_string(node_kind) noexcept;         // generated: "directive"
std::string to_string(diagnostic_code);                           // generated, inline: "E1001"
class index_out_of_range : public std::out_of_range { public: explicit index_out_of_range(std::string message); };
}
namespace knobly::syntax {
class token_range { public: token_range(std::int64_t start, std::int64_t end);
    std::int64_t start() const noexcept; std::int64_t end() const noexcept; };
class token { public: token(token_kind kind, std::string text, source_span span);
    token_kind kind() const noexcept; std::string text() const; source_span span() const noexcept; };
class node : public token_range { public: node(std::int64_t start, std::int64_t end, node_kind kind,
    sequence<node> children); node_kind kind() const noexcept; sequence<node> children() const; };
class syntax { public: syntax(sequence<token> tokens, node root, sequence<diagnostic> diagnostics);
    sequence<token> tokens() const; node root() const; sequence<diagnostic> diagnostics() const; };
KNOBLY_API syntax parse(std::string_view text);                                   // total; never throws (but bad_alloc)
KNOBLY_API source_span span_of(const syntax& syntax, const token_range& range);  // index_out_of_range
KNOBLY_API std::string text_of(const syntax& syntax, const token_range& range);  // index_out_of_range
}
```

(`constexpr`/`inline` and `noexcept` details follow 4.3; Doxygen comments omitted here.) Positions are bytes of UTF-8;
`line` from 0; `column` in bytes from the line's start.

**Done when (Lane A):** `cpp` in `EMITTERS`; `tools/check.sh` green (the planted breakages still caught, the docs
tables current with a C++ column, the stub check unchanged); TypeScript and Python checks green with **no change to
their generated output** (render both before and after and compare, as the skeleton did for its schema edit); `bash
tools/gen.sh cpp` writes every file of 4.2 through clang-format; the skeleton's CMake build green with
`headers.cpp`, every `layers_<header>.cpp` and `api_contract_syntax.cpp` compiling (`api_contract_syntax` is linked
by Slice T); `spec/codegen.md` section 4 gains the C++ table and the formatter row, section 10 the loader hooks.

## 5. Slice T: the tracer

### 5.1 Hand-written C++

| File | Holds |
|---|---|
| `support/config.hpp` | as committed (`KNOBLY_HEADER_ONLY`, `KNOBLY_API`, `KNOBLY_EXCEPTIONS`, `KNOBLY_NAMESPACE_BEGIN/END` with `inline namespace v0`) |
| `support/sequence.hpp` | defined whole: shared immutable storage, incomplete `T` allowed at declaration, random-access iterator yielding `T` by value, `std::ranges::random_access_range`, `at/front/back` raising `index_out_of_range` through `detail::raise` |
| `support/ordered_map.hpp`, `view.hpp`, `block.hpp`, `walk_view.hpp` | stay declarations in M1 (slices 2 and 3 define them) |
| `detail/raise.hpp` | `template <class E> [[noreturn]] void raise(const E&)`: throws with `KNOBLY_EXCEPTIONS`, else writes `what()` to stderr and `std::abort()`; the only `throw` in the library |
| `detail/text_in.hpp` | `constexpr std::size_t decode_utf8(std::string_view, std::size_t at, char32_t& cp) noexcept`: the provisional rule of design 2.4 (WTF-8 surrogates decode; any other invalid byte does not) |
| `detail/syntax/parse.hpp` | the token loop (`lex_longest` + `decode_utf8`; an undecodable byte or no match is one `BAD_CHAR`), `classify` (spec 2.4 codes, first match wins), per-statement recovery (spec 3.2), the tree hooks, the nesting guard (E2010, `max_nesting` from `limits.hpp`), messages from `codes.hpp`; ported from the probe without its `KNOBLY_ANTLR_COMPAT` switch |
| `detail/syntax/definitions.hpp` | `parse`, `span_of`, `text_of` |
| `detail/shared/definitions.hpp` (+ `people.hpp`) | `to_string(const diagnostic&)` and what else `api_contract_syntax` names from the shared layer |
| `detail/io|written|rendered|files|extensions/definitions.hpp` | stay empty in M1 |

No `throw`, `try` or RTTI anywhere in `support/` or `detail/syntax/`; the syntax layer compiles with `-fno-exceptions
-fno-rtti`.

### 5.2 The adapter (`cpp/conformance/`)

- `hello` answers exactly `{"protocol": 1, "binding": "cpp", "unit": "byte", "level": 0}`.
- `parse` answers the **syntax** dump of spec/conformance.md 4.2: tokens `[kind, text, start, end]`, nodes `[kind,
  start, end, children]`, diagnostics `{"id", "code", "message", "start", "end"}`, positions `[line, column, offset]`
  in bytes, ids unique for the process.
- Any other op answers `{"id", "fault": "op not supported at level 0: <op>"}`; a `knobly_error` or program-bug class
  answers `thrown` through `shapes::error_group_of`.
- `json.hpp`: the codec as declared (insertion-ordered objects; `\uD800` to WTF-8 bytes and back; output ASCII only).
- Built with RTTI and exceptions (test code).

### 5.3 CMake (`cpp/CMakeLists.txt`)

- Keep: CMake 3.24, `knobly::knobly` INTERFACE (include dir + `cxx_std_20`), `KNOBLY_REGENERATE` (default ON
  when `include/knobly/knobly.hpp` is absent; configure-time `bash tools/gen.sh cpp`; inputs as configure
  dependencies), `KNOBLY_COMPILED`, `KNOBLY_BUILD_TESTS` (default `PROJECT_IS_TOP_LEVEL`).
- Add under tests: Catch2 v3 through `FetchContent` pinned by tag and URL hash (tests only), unit tests in
  `tests/unit/` registered with CTest (sequence, `decode_utf8`, `parse` on the F16 and F17 inputs giving spec 3.2's
  answer, `span_of`/`text_of` raising `index_out_of_range`); `knobly_contract_syntax` (links
  `api_contract_syntax.cpp`); a compile-only target over `layers_*.cpp`; a compile-only target including
  `<knobly/syntax.hpp>` with `-fno-exceptions -fno-rtti` (and `/EHs-c- /GR-` on MSVC); in compiled mode the
  implementation file linked into the adapter, the unit tests and the contract; the conformance test
  `add_test(NAME conformance_l0 COMMAND Python3::Interpreter <repo>/conformance/driver/run.py --level 0 --
  $<TARGET_FILE:knobly_adapter>)`; `-Wall -Wextra -Werror` (GCC, Clang) and `/W4 /WX` (MSVC) on every test target;
  an option `KNOBLY_SANITIZE` adding `-fsanitize=address,undefined`.

### 5.4 The CI leg (`.github/workflows/ci.yml`)

A job `cpp` with `fail-fast: false`, every tool pinned in `env` or the matrix, actions pinned by full sha as the file
already does, `setup-uv` (clang-format comes through uv) and Python 3 on the runner:

| Leg | Runner | Compiler | Mode |
|---|---|---|---|
| gcc | `ubuntu-24.04` | GCC 13 (apt, pinned version) | header-only, `KNOBLY_SANITIZE=ON` |
| clang | `ubuntu-24.04` | Clang 18 (apt, pinned version) | compiled mode, `-DCMAKE_CXX_STANDARD=23` |
| appleclang | `macos-15` | AppleClang (Xcode pinned), `CMAKE_OSX_DEPLOYMENT_TARGET=13.3` | header-only |
| msvc | `windows-2022` | MSVC 19.4x | header-only; only if it passes with no special casing in the build (Git Bash runs `tools/gen.sh`); otherwise left out and reported NOT RUN with the reason |

Each leg: configure with `-DKNOBLY_BUILD_TESTS=ON`, build, `ctest --output-on-failure` (unit tests, the contract,
the shared driver's L0). The `release` job's `needs` gains `cpp`. One extra step on the gcc leg: clang-format
`--dry-run --Werror` over the hand-written `cpp/` files, with the version from `tools/api/emit_cpp.py` (`CLANG_FORMAT`;
the step reads it from there, never a second pin).

### 5.5 Scripts and spec text

- `tools/gen.sh` and `tools/check.sh`: as committed (Slice T owns them from here; nothing more needed unless a lane's
  erratum asks).
- `spec/binding-guide.md` step 3 and `spec/README.md`'s "Generate" step (F18): two routes to a parser, ANTLR 4.13.2
  (TypeScript, Python) and knobly's own generator (`tools/parser/gen.py`, C++), and the checks a generated parser
  passes (the L0 corpus through the adapter; the generator accepts the grammar and refuses every planted grammar).
- Root `README.md`: the C++ binding's line (header-only, CMake target, level 0 in milestone 1).

**Done when (Slice T):** `ctest` green locally in header-only and compiled mode with ASan and UBSan; `python3
conformance/driver/run.py -- <adapter>` reports 168 of 168 at L0 and the claimed level holds; the CI leg green on the
pushed branch (CI is the full gate); `tools/check.sh`, TypeScript and Python checks green; the compile time of one file
including `<knobly/syntax.hpp>` (`-fsyntax-only -O2`) reported in the result, not gated.

## 6. Behaviour changes

TypeScript and Python: none. Their generated output must stay byte-identical (every lane checks it when it touches
`tools/api/` or `spec/schema/`). The only TypeScript/Python-visible changes are documentation: a C++ column in the
generated tables (Lane A) and the two parser routes (Slice T).

## 7. Risks and their answers

1. **clang-format through `uv tool run`** needs network on first use; CI has it, and a run with no network fails loudly
   in `tools/api/formatter.py`. The same holds for ruff today.
2. **Two token-kind lists** (Lane A's `token_kind`, Lane P's `tk`): both come from the grammar, and the generated
   `static_assert`s make a mismatch a compile error.
3. **Lane A's header rendering for written and rendered layers is large.** It is needed for `cpp` to join `EMITTERS`
   (the planted-layer check renders every layer). If a type form blocks it, Lane A reports the form; the orchestrator
   decides whether `cpp` joins `EMITTERS` in milestone 1 or slice 2.
4. **F16 and F17**: the C++ parser follows spec 3.2; TypeScript and Python do not. The `rec-*` cases are not added to
   the shared corpus in milestone 1; the C++ unit tests hold the spec's answers. The fix in TypeScript and Python is a
   separate item for the orchestrator.

## 8. NOT RUN by the skeleton

GCC and MSVC (none on this Mac); `-fno-exceptions -fno-rtti` builds (no definitions yet); the shared driver against the
adapter (the skeleton adapter answers nothing); CI (no leg yet).

## 9. Differences from design.md, and why

| design.md | This page | Why |
|---|---|---|
| 1.4: `implementation.hpp` hand-written | generated | it lists every layer's headers and definitions, which is the schema's layer list: one home; and it leaves `include/knobly/` all generated, so `gen-api.py` can own the folder |
| 1.4: `patterns.hpp` | none; each matcher in its layer's header | `is_variable_name` is the written layer's; a shared `patterns.hpp` would break the layer check |
| 1.4: `tests/api_contract.cpp`, `tests/layers.cpp` | one file per public header | the contract links only the layers implemented so far; a layer check needs one translation unit per header |
| 1.4: definitions in `detail/<layer>/` with no named entry | `detail/<x>/definitions.hpp` per layer and module | one include point per generated header, for both modes |
| 2.5 / slice 4: the versioned inline namespace | in milestone 1 (`KNOBLY_NAMESPACE_BEGIN`) | adding it later touches every header; the macro costs nothing now |
| 1.5: the generator is standard library only | plus the pinned clang-format on its output | the owner's Q3 A covers every generated file |
| 1.5: tree annotations from the `.ebnf` | from the `.g4` (F19), compared with the `.ebnf` | the `.g4` is the specification |
