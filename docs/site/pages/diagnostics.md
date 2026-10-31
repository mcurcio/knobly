# Diagnostics and your own checks

A program that checks its own rules (a schema, a set of known node types) reports its problems the way knobly
reports its own: as located diagnostics, placed on what the program read, in one list with the config's problems.

## The sink

**The sink** (the `Diagnostics` class; C++ `diagnostics`) is the one place problems collect. Start it with the
render's problems, report into it, and run reads through it, so a reader's error is recorded instead of ending the
program:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/sink.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/sink.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/sink.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/sink.txt"
```

- `collect` runs a read; a diagnostic error it throws is recorded and the read gives back nothing (`undefined`,
  `std::nullopt`; Python's `with problems.collecting():` records it and ends the block). Any other exception passes
  through.
- `report(what, message, code)` records a problem placed on a directive, a value or the render. Every one of those
  also has `error(message, code)`, which returns a diagnostic error to throw or to add.
- A program's code is `<namespace>/<name>`, such as `app/unknown-node`; both parts must be there (a misuse error
  otherwise; a compile error in C++ for a literal without `/`), so a program's code never looks like knobly's.

The sink keeps the order problems were added: the render's first, then the reader's error, then the program's.

A custom schema is checked this way: walk the rendered tree ([Walking, addresses and reloads](walking.md)), read
each value with the reader its directive expects through `collect`, and `report` what the schema refuses.

## Printing

`format_diagnostic(d, graph)` (TypeScript `formatDiagnostic`) prints a diagnostic for people: the place counted
from 1, the code and message, the source line (from the document's current text), a caret line under the span, and
one line per step. Without the graph, only the first line, which is also the diagnostic's people form
(`String(d)`, `str(d)`, `vl::to_string(d)`). It reads a graph, so it belongs to the low level (`knobly/written`,
`knobly.written`, `knobly::written`); [Getting started](getting-started.md#problems-are-diagnostics) prints
a broken file's problems with it.

In C++, `<knobly/format.hpp>` is opt-in: it gives every type with a people form (`place`,
`located_diagnostic`, `rendered::address`, each kind list, `diagnostic_code`) an `operator<<` and a
`std::formatter`, both writing exactly its `to_string`, so `std::format("{}", place)` works with width, fill and
alignment.

A diagnostic's `code`, `severity` and `place` are the contract between the bindings; its `message` is for people
and may differ. A problem with an override's value is placed on the `$name` that used it.

## Errors and warnings

Every diagnostic has a `severity` (`severity()` in C++): `error` or `warning`, read from its code's letter. Errors
and warnings sit in the same list, in the order they were found. A warning does nothing: no load, render, read, edit
or save throws one or acts differently because one is there, and `collect` never records one, since only a reader's
error is thrown. The only way to see a warning is to read the list. Today there is one warning, W3005: an `@include`
glob that matches no file, so the include splices nothing (a path that matches no file stays the error E3001).

A program's own codes (`report`, `error`) are errors. A sink's count includes warnings, so a program that stops when
a config has problems counts the diagnostics whose severity is `error`.

## Error codes

Lines and columns are counted from 0 in the API. "At" says where the diagnostic is placed. A code starting with `W`
is a warning; every other code is an error. The 1xxx and 2xxx codes
come from the syntax layer, which places them as the cases in
[`conformance/`](https://github.com/mcurcio/knobly/tree/main/conformance) show. An edit that is refused reports the
same codes, placed in the text the edit was given ([Editing and saving](editing.md#named-edits-and-a-refused-edit)).

<!-- generated: error codes (tools/gen-api.py docs) -->
| Code | TypeScript name | Python name | C++ name | Meaning | At |
|---|---|---|---|---|---|
| E1001 | `UnterminatedString` | `UNTERMINATED_STRING` | `unterminated_string` | a string with no closing quote | per `conformance/` |
| E1003 | `UnexpectedCharacter` | `UNEXPECTED_CHARACTER` | `unexpected_character` | a character the language does not use | per `conformance/` |
| E1004 | `LoneDollar` | `LONE_DOLLAR` | `lone_dollar` | `$` not followed by a name | the `$` (case `var-lone-dollar`) |
| E1005 | `BadEscape` | `BAD_ESCAPE` | `bad_escape` | a double-quoted string escape other than the six (found by the parser; a single-quoted string is raw) | the string |
| E2001 | `UnexpectedToken` | `UNEXPECTED_TOKEN` | `unexpected_token` | a token where it cannot go, a missing `;` at the end of a block or file among them | per `conformance/` |
| E2003 | `ExpectedClosingBrace` | `EXPECTED_CLOSING_BRACE` | `expected_closing_brace` | a block with no `}` | per `conformance/` |
| E2004 | `ExpectedClosingBracket` | `EXPECTED_CLOSING_BRACKET` | `expected_closing_bracket` | an unmatched bracket | per `conformance/` |
| E2007 | `BadSlice` | `BAD_SLICE` | `bad_slice` | a malformed slice (`[~]` among them, and `[1:3]`, whose `1:3` is one word), or a literal bound that is not a whole number | per `conformance/` |
| E2009 | `ValuesTouch` | `VALUES_TOUCH` | `values_touch` | two values with no space or comment between | per `conformance/` |
| E2010 | `NestingTooDeep` | `NESTING_TOO_DEEP` | `nesting_too_deep` | blocks and lists nested deeper than 100 | the `{` or `[` that opens the level past the limit; at an edit, 0:0 when that bracket is not in the given text |
| E3001 | `IncludeNotFound` | `INCLUDE_NOT_FOUND` | `include_not_found` | a path (no glob) matched no file | the extension line's name |
| E3004 | `IncludeResolverFailed` | `INCLUDE_RESOLVER_FAILED` | `include_resolver_failed` | the source threw (for the root file `load` fails) | the extension line's name |
| E3005 | `IncludeBadPath` | `INCLUDE_BAD_PATH` | `include_bad_path` | include needs exactly one quoted path | the bad value, or the name when there is none |
| W3005 | `IncludeMatchedNothing` | `INCLUDE_MATCHED_NOTHING` | `include_matched_nothing` | a glob matched no file: a warning, so the include splices nothing and the load goes on | the extension line's name, as E3001 |
| E3006 | `ExtensionFailed` | `EXTENSION_FAILED` | `extension_failed` | an extension threw something other than a located error, or returned something other than a list of texts | the extension line's name |
| E3007 | `UnreadCopy` | `UNREAD_COPY` | `unread_copy` | an include copy whose files are not read yet (`graph.read()` reads them) | the extension line's name |
| E3008 | `UnknownExtension` | `UNKNOWN_EXTENSION` | `unknown_extension` | an `@name` that is no language statement and no registered extension | the `@name` |
| E4001 | `NonIntegerBound` | `NON_INTEGER_BOUND` | `non_integer_bound` | a bound from a variable that is not one whole number, or a literal whole number beyond the range | the bound (a bound from a variable: the value, via the variable) |
| E4002 | `WrongValueKind` | `WRONG_VALUE_KIND` | `wrong_value_kind` | a reader met the wrong kind of value | the value |
| E4004 | `NotANumber` | `NOT_A_NUMBER` | `not_a_number` | `number()` met a word that is not a number | the value |
| E4005 | `NotAnInteger` | `NOT_AN_INTEGER` | `not_an_integer` | `integer()` met a word that is not a whole number | the value |
| E4006 | `NotABoolean` | `NOT_A_BOOLEAN` | `not_a_boolean` | `boolean()` met a word other than `true`, `false` | the value |
| E4007 | `BadSliceName` | `BAD_SLICE_NAME` | `bad_slice_name` | a slice's `$name` that does not hold one word | as E4001 |
| E5001 | `UnknownVariable` | `UNKNOWN_VARIABLE` | `unknown_variable` | `$name` with no `set`, parameter or override | the `$name` |
| E5002 | `VariableSetTwice` | `VARIABLE_SET_TWICE` | `variable_set_twice` | two `set` of one name in one block | the second `$name` |
| E5003 | `UnknownSnippet` | `UNKNOWN_SNIPPET` | `unknown_snippet` | `use` of a snippet not seen there | the name |
| E5004 | `SnippetArity` | `SNIPPET_ARITY` | `snippet_arity` | wrong number of values for the snippet | `@use` |
| E5005 | `SnippetDefinedTwice` | `SNIPPET_DEFINED_TWICE` | `snippet_defined_twice` | two snippets of one name in one block | the second name |
| E5006 | `ExpansionCycle` | `EXPANSION_CYCLE` | `expansion_cycle` | a snippet or file reaches itself | the `@use` or extension line that closes the loop |
| E5007 | `ExpansionTooDeep` | `EXPANSION_TOO_DEEP` | `expansion_too_deep` | more than 16 snippets or files open inside each other | the `use` or extension line |
| E5008 | `TooManyDirectives` | `TOO_MANY_DIRECTIVES` | `too_many_directives` | more than 100,000 directives after expansion; expansion stops | the statement that is one too many |
| E5009 | `BadSet` | `BAD_SET` | `bad_set` | any other form of `@set` | `@set` |
| E5010 | `BadSnippet` | `BAD_SNIPPET` | `bad_snippet` | any other form of `@snippet` | `@snippet` |
| E5011 | `BadUse` | `BAD_USE` | `bad_use` | any other form of `@use` | `@use` |
| E5012 | `ExtensionBlockNotSet` | `EXTENSION_BLOCK_NOT_SET` | `extension_block_not_set` | an extension line's block holds a line other than `@set` | that line's name |
| E5013 | `ExpandedNestingTooDeep` | `EXPANDED_NESTING_TOO_DEEP` | `expanded_nesting_too_deep` | blocks and lists nested deeper than 256 after expansion | the name of the statement whose block or values sit too deep |
<!-- end generated -->

Codes that are no longer used, and never will be again: **E2006** (the old include path error, replaced by E3005),
**E3002** and **E3003** (the old include loop and depth errors, replaced by E5006 and E5007), **E2008** (a `{` on its
own line, allowed since a line break is whitespace) and **E4003** (a bad escape found when rendering, now E1005 found
by the parser). Every code but the readers' is in one list, `graph.diagnostics`, which the render shows unchanged.
E6xxx is kept for the high-level API, which is not built yet; none is defined.
