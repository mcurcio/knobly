# Low-level consumer API: the slice pages (round 11 build)

**Status:** frozen pages for the build run on branch `feat/consumer-api-low-level` · **Layer:** Module › Feature
(R15 tiers 1-2 only; the sugar is deferred, kno-xlo) · **Beads:** S1 `kno-9ze.4`, S2 `kno-stq.3`, S3 `kno-stq.4`,
S4 `kno-9vn.1`.

**Sources, newest wins:** `requirements.md` (its last section is the plan the owner said yes to on 2026-10-28),
`round11/design.md` as corrected by `round11/decisions.md` (every review finding is weighed there), this page.
Where this page and `design.md` disagree, this page wins and `decisions.md` says why.

**Interfaces as code:** commit `3cf7460` holds every public signature below as compiling code with bodies that
throw "not implemented": `ts/src/load/{origin,graph,report,directive,source,processor}.ts`, `ts/src/include.ts`,
`createFileSource` in `ts/src/node.ts`, `createFetchSource` in `ts/src/browser.ts`;
`py/src/knobly/{origin,graph,report,directives,source,processor,include,files}.py`. Their docstrings are part of
the frozen page. An implementer who finds a signature or rule here wrong appends to `.claude/errata.md` and stops;
the change comes back through an erratum, never a local edit.

---

## 0. Slice order, and why

| Slice | What it delivers | Owns | Runs |
|---|---|---|---|
| **S1 tracer** | the grammar delta, its tier-1 co-changes in both languages, all conformance inputs and fixtures, and the thinnest TS path: `set`/`$var` expanded with both origins, a located diagnostic for an unknown variable | `grammar/`, `tools/planted/`, `conformance/`, `fixtures/`, the tier-1 token files of both languages, `ts/src/load/` (partial bodies) | first, alone |
| **S2 TS** | everything else of the TS low-level API, the TS barrel switch and deletions | `ts/` | after S1, concurrently with S3 |
| **S3 Python** | the same surface in Python, the Python load-conformance runner | `py/` | after S1, concurrently with S2 |
| **S4 docs** | README, RECORD, the low-level API reference for both languages, the language changes | `README.md`, `design/RECORD.md`, `ts/README.md`, `py/README.md`, `docs/` | after S2 and S3 |

Why this order: the grammar is the package every other part imports (package-depth first), and growing the token
vocabulary has consumers in both languages (the adapters refuse an unknown token name at load), so S1 carries every
tier-1 consumer (implementation-workflow §3.2) and both runners of the new syntax cases. Everything S2 and S3 both
read (grammar, syntax and load conformance cases with their expected outputs, rasl fixtures) is S1's, so S2 and S3
own disjoint trees (`ts/` and `py/`) and run at once. Docs are their own slice (§3.6).

**Siblings share one checkout.** S2 and S3 run in the same checkout at the same time. Each keeps to its owned tree
and lands with its paths named: `git add -A -- <owned> && git commit -m '<msg>' -- <owned>`, then
`git push origin feat/consumer-api-low-level`; an `index.lock` means wait 5 s and retry. Neither edits `conformance/`,
`fixtures/`, `grammar/` or the other's tree: a wrong expected output is an erratum, not an edit.

---

## 1. The model (normative for every slice)

| Concept | Owns | Not its job |
|---|---|---|
| Syntax (tier 1) | one file's tokens, lossless tree, syntax diagnostics (`parse`, `ISyntax`, `IDiagnostic`) | includes, variables, meaning |
| Processor | made once: document source, extensions, key rule; `load` and `diff` | what the program does with a load |
| load | reading through the source (each file once), expansion (`set`, `$x`, `snippet`/`use`, extension directives), value rules checked at load, limits, addresses, origins | meaning; I/O itself (the source does it) |
| Loaded | the expanded top level (owned by the root file), unreadable top-level statements, the file graph, every load diagnostic | |
| Directive, Argument | what was written, after expansion; value readers by the grammar's value rules | which directives are allowed where (the sugar's) |
| Unreadable | a statement kept in its place that could not be read (syntax, expansion, value, extension) | guessing what it would have been |
| Origin | where text was written and the steps that brought it here | identity |
| Address | identity of a directive across loads of one processor | where the text is |
| diff | what differs between two loads, including "unknown" where a block is incomplete | what to do about it (retune, restart: the program's) |
| Diagnostics (sink) | the one place problems collect: load's, readers', the program's | formatting (`formatDiagnostic`) |
| Document source | where files come from: resolve a spec, read a path | parsing, caching across loads |
| Extension | turning one directive's values into specs of files to splice | reading, depth, cycles, variables |

### 1.1 Grammar delta (S1)

```antlr
value         : WORD | STRING | VARIABLE | slicedWord | list ;
slicedWord    : WORD '[' bounds ']' ;
bounds        : bound ':' bound? | ':' bound | bound ;
bound         : WORD | VARIABLE ;

VARIABLE      : '$' [A-Za-z0-9_]+ ;                 // L1: nginx's name rule
// error tokens: never used by the syntax
LONE_DOLLAR   : '$' ;                               // E1004
BAD_CHAR      : ~[\t\n "#$',./0-9:;@A-Z_a-z{}*?[\]\-﻿] ;   // '$' added to the excluded set
```

`knobly.ebnf` gets the same: `Value ::= Word | String | Variable | SlicedWord | List`,
`Bounds ::= Bound ':' Bound? | ':' Bound | Bound` (this also adds the index form the EBNF lacked, round 8 finding),
`Bound ::= Word | Variable`, `Variable ::= '$' VariableChar+`, `LoneDollar ::= '$'` (error token),
`VariableChar ::= [A-Za-z0-9_]`, `'$'` added to `TokenStart`, the tokens comment line updated.

Consequences, each a located error, never a silent join: `fps$x` and `$x"y"` are two values touching (E2009);
`$x[0:3]` is a variable touching a list that cannot parse (a syntax error: a variable is never a slice base);
`$x 1;` is a syntax error (E2001: a directive name is a WORD); a `$` inside a string is plain text; a lone `$` is
E1004. `set`, `snippet` and `use` need no grammar change: they are ordinary directives the load reserves.

### 1.2 Expansion rules

Order of work for every load: (1) read and parse each file once (R21); (2) expand per place, top to bottom; (3) the
program reads the expanded tree. Rules, by L-number where the run's decisions fixed them:

1. **Reserved names (L6).** At a statement's start, in every block (also blocks a program later reads raw), `set`,
   `snippet` and `use` are always reserved, and each registered extension's name is reserved while registered. They
   never appear in `body`; their results do.
2. **`set $name value...;`** binds `$name` from that line to the end of the enclosing block (nested blocks and
   everything spliced in below included). One `set` per name per block (E5002, at the second `$name`). An inner
   block may shadow an outer binding. Values keep their kinds (word, string, list, slice, index). `set $a $b;` copies
   `$b`'s values as visible there. Any other form (no `$name`, no value, a block) is E5009 at `set`.
3. **Passed-in values win (L3).** A variable handed in by the program wins over every `set` of its name, which is
   then the default; the same holds for a `set` in an extension directive's block over the spliced files' own `set`
   of that name (rule 8). Handed-in variables are visible everywhere.
4. **`$name` as a value (L1, L7).** Only as a whole value: a directive value, a list item, or a whole slice bound.
   It is replaced by all its values in place: `port $ports dev` with `set $ports 8080 443;` reaches the program as
   three values; `[$ports, 1]` becomes three items. As a slice bound the variable must hold exactly one word that
   spells an IntegerText (E4001 otherwise, at the value's place via the variable step). No `set` visible and nothing
   handed in: E5001 at the `$name`.
5. **`snippet name $param... { body }`** defines a snippet visible from that line to the end of its block. Snippet
   names are their own namespace (L7): `use universe` looks only at snippets, never at directives. One definition per
   name per block (E5005); any other form, or a parameter named twice, is E5010 at `snippet`.
6. **`use name value...;`** splices the body in place. The values bind the parameters by position; the count must
   match exactly (E5004 at `use`; there is no `$args`). The body sees what is visible where it is written (lexical,
   round 8 S1-A) plus its parameters, never the use site's variables. A body exports nothing (L2): its `set` and
   `snippet` lines are visible only inside it. Unknown name: E5003 at the name value. A block on `use` or any other
   form: E5011.
7. **Extension directives** (include is the first-party one): the extension gives specs; the load resolves each
   through the document source (empty: E3001; the source throws: E3004), sorts each spec's paths in code-point order,
   reads each path once per load, and splices each file's top-level statements in place. An included file's
   top-level `set` and `snippet` are visible after the extension line in the including block (L2), and count for
   rule 2's and rule 5's one-per-block checks there.
8. **An extension directive's block** may hold only `set` lines (E5012 at the first other line); they bind for the
   spliced files and win over those files' own `set` of the same name (R22: "each instance of the file would have
   its own bindings").
9. **Limits and cycles**, shared by `use` and extensions: a `use` or extension directive that reaches itself again
   is E5006 at the directive that closes the cycle; nesting deeper than 16 places is E5007; more than 100,000
   directives after expansion is E5008, and expansion stops there.
10. **Value rules checked at load:** a slice or index bound that is not an IntegerText (E4001) and a string escape
    other than the six of EscapeText (E4003) make their directive unreadable (kind `value`), so readers never meet
    them.
11. **Unreadable statements.** A statement that fails any rule above (or is an error node of the parser) is not in
    `body`; it is an `IUnreadable` in its container's `unreadable`, with kind `syntax`, `expansion`, `value` or
    `extension`, its origin and its tier-1 node. Its block is not expanded (problems inside it are not reported).
    A syntax error in a snippet body or an included file is reported once per file (R21), and every place that
    splices it gets its own unreadable entry.
12. **Diagnostics order:** every file's syntax diagnostics, files in first-read order; then load diagnostics in the
    order expansion meets them (depth-first, written order). The load never throws for anything in a text.

### 1.3 Canonical text (`IArgument.text`, `Argument.text`)

The same in both languages: a word as written; a string as `"` + its decoded text with `\` `"` newline tab carriage
return escaped as `\\` `\"` `\n` `\t` `\r` + `"`; a slice `name[start:end]` with either side empty when absent; an
index `name[i]`; bounds in decimal; a list `[` + its items' texts joined by `, ` + `]`. Comments, line breaks and a
trailing comma are never part of it. A value from a variable has the value's text, never `$name`.

### 1.4 Address

Steps from the top level down; each step is the directive's name, the key rule's answer (or none), and its
occurrence among earlier siblings with the same name and key (0-based). `text` is
`JSON.stringify(steps.map((s) => [s.name, s.key ?? null, s.occurrence]))` in TypeScript and
`json.dumps([[s.name, s.key, s.occurrence] for s in steps], ensure_ascii=False, separators=(",", ":"))` in Python
(the same bytes: names are ASCII words). `toString()` / `str()` is for people: each step as its name, then a space
and the JSON-quoted key when there is one, then ` #n` when the occurrence is not 0, joined by ` > `:
`graph > node "leds" > max_count`. The key rule receives `IKeyInput`/`KeyInput` (name, expanded args, whether it has
a block, the parent's key input); it runs once per readable directive, parents first, in expansion order; what it
throws ends the load. Without a rule every key is none.

### 1.5 diff

Only loads of one processor (TypeError / ValueError otherwise; Python ties the key rule to the `Processor` for this).
By address: **added** (only in `after`); **removed** (only in `before`, and its container in `after` exists with no
unreadable statement); **unknown** (only in `before`, and its container in `after`, or the top level, holds an
unreadable statement: it may be the line that is broken now); **changed** (in both, and its own args' canonical
texts or whether it has a block differ). An added, removed or unknown directive is listed alone (its subtree is not);
a changed or unchanged one's block is compared at its own addresses. Order: removed and unknown in `before`'s walk
order, then added and changed in `after`'s. `diff` accepts loads with diagnostics. A program groups changes by its
own unit with `directive.closest(...)` or `address.parent`.

### 1.6 Diagnostic codes (both registries already hold them, commit `3cf7460`)

| Code | Name (TS / Python) | At |
|---|---|---|
| E1004 | LoneDollar / LONE_DOLLAR | the `$` (tier 1) |
| E3001 | IncludeNotFound / INCLUDE_NOT_FOUND | the extension directive's name: a spec matched no file |
| E3004 | IncludeResolverFailed / INCLUDE_RESOLVER_FAILED | the extension directive's name: the source threw (the root: rule in §2) |
| E3005 | IncludeBadPath / INCLUDE_BAD_PATH | the bad value, or the directive name when there is none: include takes exactly one quoted path |
| E3006 | ExtensionFailed / EXTENSION_FAILED | the extension directive's name: `specs` threw something else |
| E4001 | NonIntegerBound | the bound (a variable bound: the value's place, via the variable) |
| E4002-E4006 | WrongValueKind, BadEscape, NotANumber, NotAnInteger, NotABoolean | the value (E4003 at load, the rest by readers) |
| E5001-E5012 | UnknownVariable, VariableSetTwice, UnknownSnippet, SnippetArity, SnippetDefinedTwice, ExpansionCycle, ExpansionTooDeep, TooManyDirectives, BadSet, BadSnippet, BadUse, ExtensionBlockNotSet | per §1.2 |

Retired with the code that emits them (never reused): **E2006** (S2 deletes `parseGraph`; replaced by E3005),
**E3002** and **E3003** (replaced by E5006 and E5007). S2 removes them from the TS registry and message table, S3
from Python's. E6xxx is reserved for the deferred sugar; none is defined. A program's code is
`<namespace>/<name>`; both languages check it when the error or report is made (TypeError / ValueError).

---

## 2. Shared primitives

| Primitive | One responsibility | Consumers today | Scheduled |
|---|---|---|---|
| `IPlace`, `IHanded`, `IStep`, `IOrigin`, `IDirectiveOrigin` (`load/origin.ts`, `origin.py`) | where text was written and how it got here | directives, arguments, unreadable, edges, diagnostics | the sugar's `ConfigError(at=...)`, editing (kno-uji) |
| `ILocatedDiagnostic` + `Diagnostics` sink + `formatDiagnostic` (`load/report.ts`, `report.py`) | collecting and printing load-level problems | load, readers, programs | the sugar's E6xxx, rasl-ynq's printer |
| value rules module (private: `ts/src/load/values.ts`, `py/src/knobly/_values.py`) | NumberText, IntegerText, BooleanText, the six escapes, canonical text: the one home of each rule | load (bounds, escapes), readers, canonical text | — |
| `IDocumentSource` + `memorySource` (`load/source.ts`, `source.py`) | where files come from | the processor (root and extensions), tests | rasl's file watcher |
| directive anatomy (`ts/src/ast/anatomy.ts` today; Python's port inside `ast.py`) | which tokens of a directive node are its name, values and block | load | S2/S3 move it beside the load (internal) when the facade goes |
| `compareCodePoints` (`ts/src/graph/order.ts`) | include ordering both languages share | load (splice order), file source | — |

Root file rule: `load(path)` reads the root through the source's `read(path)`; when that throws, `load` rejects
(TS) or raises (Python) a `DiagnosticError` whose diagnostic is E3004 placed at `path` 0:0 with empty `via`. There
is no load without a root. `formatDiagnostic` without the file in the graph prints the first line only.

---

## 3. Frozen public surface, TypeScript (final state after S2)

`knobly` (barrel, `ts/src/index.ts`) exports exactly:

- tier 1, unchanged: `ISourcePosition`, `ISourceSpan`, `DiagnosticCode`, `IDiagnostic`, `IToken`, `TokenKind`
  (gains `Variable: "VARIABLE"` and `LoneDollar: "LONE_DOLLAR"` in S1), `INode`, `ISyntax`, `ITokenRange`,
  `NodeKind`, `spanOf`, `textOf`, `ValueRef`, `parse`, `ValueKind` (gains `List`), `ISliceValue`, `IIndexValue`
  (both lose `span`: an argument's origin says where it is).
- `DiagnosticError`: `class DiagnosticError extends Error { readonly diagnostic: ILocatedDiagnostic; constructor(diagnostic: ILocatedDiagnostic) }`.
- load layer: `IPlace`, `IHanded`, `StepKind`, `IStep`, `IOrigin`, `IDirectiveOrigin`, `ProgramCode`,
  `ILocatedDiagnostic`, `ILocatable`, `Diagnostics`, `formatDiagnostic`, `PlainValue`, `IArgument`, `IAddressStep`,
  `IAddress`, `UnreadableKind`, `IUnreadable`, `WalkControl`, `IDirective`, `IKeyInput`, `KeyRule`, `ILoadContext`,
  `IDocumentSource`, `memorySource`, `IDocumentNode`, `IDocumentEdge`, `IDocumentGraph`, `IExtensionUse`,
  `IExtension`, `IProcessorOptions`, `ILoadOptions`, `ILoaded`, `ChangeKind`, `IAdded`, `IRemoved`, `IChanged`,
  `IUnknown`, `Change`, `IProcessor`, `knobly`; and `IDocumentWriter`, `save(graph: IDocumentGraph, writer: IDocumentWriter): Promise<void>` (kept, reading `node.syntax`).
- `knobly/include`: `include(): IExtension`. `knobly/node`: `createFileSource(): IDocumentSource`,
  `createFsWriter(): IDocumentWriter`. `knobly/browser`: `createFetchSource(fetchImpl: typeof fetch): IDocumentSource`,
  `createFetchWriter(...)` (unchanged), `IFetchWriterOptions`.

Deleted (no dual paths): `createAst`, `parseDocument`, `walkDirectives`, `findDirectives`, `IAst*`, `valueOf`,
`IWordValue`, `IStringValue`, `Value`, `parseGraph`, `IParseGraphOptions`, `iterateDirectives`, `composeLoaders`,
`DocumentLoader`, `ILoadContext` (old shape with `depth`), `ILoadedDocument`, `IGraphDiagnostic`, the old
`IDocumentGraph`/`IDocumentNode`/`IDocumentEdge`, `createFsLoader`, `createFetchLoader`, and `load/todo.ts`.

## 4. Frozen public surface, Python (final state after S3)

`knobly` (`py/src/knobly/__init__.py`) exports exactly: tier 1 unchanged (`SourcePosition`, `SourceSpan`,
`Diagnostic`, `DiagnosticCode`, `Token`, `TokenKind` (+`VARIABLE`, `LONE_DOLLAR` in S1), `Node`, `NodeKind`, `Syntax`,
`TokenRange`, `ValueRef`, `span_of`, `text_of`, `parse`, `ValueKind` (+`LIST`), `SliceValue`, `IndexValue` (both lose
`span`)); `DiagnosticError` (carries a `LocatedDiagnostic`); and `Place`, `Handed`, `StepKind`, `Step`, `Origin`,
`DirectiveOrigin`, `LocatedDiagnostic`, `Locatable`, `Collecting`, `Diagnostics`, `format_diagnostic`, `PlainValue`,
`Argument`, `AddressStep`, `Address`, `UnreadableKind`, `Unreadable`, `Directive`, `KeyInput`, `KeyRule`, `walk`,
`LoadContext`, `DocumentSource`, `memory_source`, `DocumentNode`, `DocumentEdge`, `DocumentGraph`, `ExtensionUse`,
`Extension`, `Loaded`, `Added`, `Removed`, `Changed`, `Unknown`, `Change`, `Processor`. Modules: `knobly.include`
(`include()`), `knobly.files` (`file_source()`).

Deleted: `knobly.ast` and its names (`AstArgument`, `AstDirective`, `AstDirectiveList`, `AstDocument`,
`create_ast`, `find_directives`, `parse_document`, `walk_directives`), `value_of`, `WordValue`, `StringValue`,
`Value`. Read-only attributes may be properties or frozen-dataclass fields (implementer's choice); names, types and
`__match_args__` are frozen.

## 5. The load conformance format (S1 writes `conformance/load/format.md` from this)

Inputs: `conformance/load/cases.json`, an array of
`{"name", "needs", "files", "root", "variables"?, "key"?, "extensions"?, "after"?}`: `needs` is a subset of
`["snippet", "include", "diff", "key"]`; `files` maps path to text; `variables` are handed in; `key` is absent (no
rule) or `"rasl"` (the rule below); `extensions` is absent or `["include"]`; `after` maps paths to replacement texts
for a second load of the same processor (other files unchanged). Every runner uses `memorySource(files)`.

The `"rasl"` key rule (both runners implement exactly this): a `node` directive whose parent is `graph` is keyed by
its second argument's text; `connect` by its arguments' texts joined by one space; `fill` by its first argument's
text; everything else has no key.

Expected: `conformance/load/expected/<name>.json`, one object with exactly these keys in this order:

```
{"files":[path,...],
 "directives":[[address, block, origin, [[text, origin],...]],...],
 "unreadable":[[containerAddress, kind, origin],...],
 "diagnostics":[[code, origin],...],
 "changes":[[kind, address],...]}
```

- `files`: `graph.nodes` keys in first-read order. `directives`: the walk order; `address` is the people form
  (§1.4); `block` is whether it was written with a block. `unreadable`: in walk order; `containerAddress` is `""` at
  the top level. `diagnostics`: `loaded.diagnostics` in order, the origin built from `at` and `via`. `changes`:
  present only when the case has `after`, from `diff(first, second)`.
- An origin is one string: the written place as `path:line:col` (0-based line, UTF-16 column, the span's start), or
  `handed <name>`; then for each via step, innermost first, ` < <kind> <name> <path>:<line>:<col>`. Example:
  `main.conf:5:10 < variable source main.conf:9:12 < use twinkle main.conf:14:4`.
- Bytes as `conformance/format.md` (no insignificant whitespace, non-ASCII escaped, one trailing newline).

Expected outputs are derived by hand from §1 by S1 (its TS tracer cross-checks the `needs: []` ones). S2 and S3 may
not edit them: a disagreement with §1 is an erratum.

---

## S1: tracer (`kno-9ze.4`)

**Owns:** `grammar/Knobly.g4`, `grammar/knobly.ebnf`, `tools/planted/var-twice.g4` (new), `conformance/**`
(new `conformance/variables.json` and its `expected/var-*.json`; `conformance/load/{format.md,cases.json,expected/}`),
`fixtures/rasl/**` (new), `ts/src/syntax/tokens.ts`, `ts/src/syntax/recovery.ts`, `ts/src/ast/anatomy.ts`,
`ts/src/conformance.test.ts`, `ts/src/load/**`, `ts/src/load-conformance.test.ts` (new), `ts/src/load/tracer.test.ts`
(new), `py/src/knobly/syntax/tokens.py`, `py/src/knobly/syntax/_recovery.py`, `py/tests/test_conformance.py`,
`py/tests/test_tokens.py`. Nothing else.

**Signatures introduced or changed:**
- `TokenKind.Variable = "VARIABLE"`, `TokenKind.LoneDollar = "LONE_DOLLAR"` (TS); `TokenKind.VARIABLE`,
  `TokenKind.LONE_DOLLAR` (Python).
- Recovery, both languages: `LONE_DOLLAR` classifies as E1004 (as `BAD_CHAR` does as E1003); `VARIABLE` counts as a
  value token for E2009 on both sides of the touch.
- `anatomyOf`: `VARIABLE` tokens are values (`ValueRef` token indexes), as `WORD` and `STRING` are.
- `tools/planted/var-twice.g4`: the grammar with a variable usable both as a value and as a slice base piece, so the
  Bison check must report conflicts (round 8's planted case).
- TS bodies, in `ts/src/load/`: `memorySource`; `knobly({ source })` with `load` doing rules 1-4, 10-12 of §1.2
  for files without `snippet`, `use` or extensions (those are S2's; S1 may leave them as ordinary directives) and
  `diff` still throwing; `ILoaded` (`body`, `unreadable`, `origin`, `diagnostics`, `graph`); `IDirective` (`name`,
  `args`, `body`, `unreadable`, `parent`, `address` with no key rule, `origin`, `node`); `IArgument` (`kind`, `text`,
  `origin`). Readers, `walk`, `closest`, `error`, the key rule, `Diagnostics` and `formatDiagnostic` may still throw.

**Acceptance criteria, each with its mutation probe:**
1. `bash tools/check.sh` exits 0, including `var-twice.g4` caught. *Probe:* make `bounds` also accept `VARIABLE '['`
   (a variable as slice base) in the real grammar: the Bison check must report a conflict or the planted case must
   stop biting; restore.
2. `conformance/variables.json` holds at least these inputs, with expected outputs that TS writes
   (`KNOBLY_WRITE_EXPECTED=1`) and Python reproduces byte for byte: `set $pixels 2284;`, `max_count $pixels;`,
   `port $ports dev;`, `[$a, 1, $b]`, `c[0:$n];`, `c[$i];`, `c[$a:];`, `fps$x;` (E2009), `$x 1;`, `$x[0:3];`, `$1`,
   `cost $;` (E1004), `"a $b"`, `use twinkle rgb_150;`, `snippet twinkle $source { connect $source; }`. *Probe:*
   drop `VARIABLE` from the TS E2009 touch rule: `fps$x;` must fail its expected file; restore.
3. Python's `test_conformance.py` runs `variables.json` and passes. *Probe:* remove `LONE_DOLLAR` from Python's
   E1004 classification: the `cost $;` case must fail; restore.
4. TS tracer test (`ts/src/load/tracer.test.ts`): loading `set $pixels 2284;\ngraph {\n  node DdpSink leds { max_count $pixels; }\n}\n`
   through `knobly({ source: memorySource({ "main.conf": ... }) })` gives `max_count`'s argument with text
   `2284`, `origin.written` at `main.conf` 0:12 and `origin.via` = one `variable pixels` step at 2:32.
   *Probe:* set `via` to `[]` for variable values: the test fails; restore.
5. Same file with `$pixel` misspelt: `loaded.diagnostics` = one E5001 at the `$pixel` token; `leds.unreadable` holds
   one entry of kind `expansion` at `max_count`; `leds.body` is empty. *Probe:* make an unknown variable expand to no
   values instead: the test fails (a `max_count` with no values would be read as `true` by rasl); restore.
6. Handed-in value wins (L3): `{ variables: { host: '"10.0.0.2"' } }` over `set $host "10.0.0.1";\ntarget $host;`
   gives `target`'s argument text `"10.0.0.2"` with `origin.written` `{ kind: "handed", variable: "host" }`.
   *Probe:* let the file's `set` win: the test fails; restore.
7. `conformance/load/cases.json` holds at least the cases listed below with hand-derived expected outputs, and the TS
   runner (`ts/src/load-conformance.test.ts`) passes every case whose `needs` is empty. *Probe:* change one expected
   origin column by one: the runner fails; restore.
8. `fixtures/rasl/` holds `family_room.conf` and `hyperhdr.conf` (v10, copied from round 11's
   `integrate-rasl-ts/configs/`), `split/main.conf` + `split/sink.conf` (one file included at two places with
   different include-block `set` lines, and `$leds_host` both `set` in the file and meant to be handed in), a
   `README.md` listing each difference from rasl's current syntax (design.md §1 table), and `expected.json`:
   per fixture the node ids in walk order, the diagnostics (none), and the changes after replacing `set $pixels 2284;`
   with `set $pixels 2400;`. No test of S1 reads them (S2 and S3 do). *Probe:* none (data only; S2/S3 probe it).
9. TS `test`, `typecheck`, `lint` and Python `pytest`, `ruff check`, `ruff format --check`, `mypy` all pass.

**Load cases S1 writes (name: needs):** `load-var-basic: []`, `load-var-multi-list: []`, `load-var-unknown: []`,
`load-var-handed-wins: []`, `load-var-slice-bound: []`, `load-var-bad-bound: []` (E4001 via the variable),
`load-var-set-twice: []`, `load-var-shadow: []`, `load-syntax-unreadable: []` (a bad line in a block, siblings kept),
`load-bad-escape: []` (E4003, kind value), `load-snippet-basic: [snippet]`, `load-snippet-arity: [snippet]`,
`load-snippet-cycle: [snippet]`, `load-snippet-lexical: [snippet]`, `load-snippet-exports-nothing: [snippet]`,
`load-include-twice: [include]` (`files` lists the included file once; two edges' worth of directives),
`load-include-exports: [include]`, `load-include-not-found: [include]`, `load-include-block-wins: [include]`,
`load-include-cycle: [include]`, `load-diff-var-edit: [diff]` (changed at two addresses, never the `set`),
`load-diff-broken-line-unknown: [diff]` (unknown, not removed), `load-diff-moved-node: [diff, key]` (no change),
`load-diff-list-comment: [diff]` (editing a comment inside a list: no change).

**Land:** `git add -A -- <owned> && git commit -m 'feat(grammar): variables, snippets and the load tracer' -- <owned>`; push.

---

## S2: the TypeScript low-level API (`kno-stq.3`)

**Owns:** `ts/**` (S1's files included, now S2's). Nothing outside `ts/`.

**Signatures:** §3 is the final TS surface; every body in `ts/src/load/`, `ts/src/include.ts`, `createFileSource`,
`createFetchSource` filled; the barrel switched to §3's list; the deletions in §3 done with their tests rewritten
against the load layer (no behaviour of a deleted function survives except through the load layer); `DiagnosticError`
retyped; `ISliceValue`/`IIndexValue` lose `span`; E2006, E3002, E3003 removed from the registry and messages;
`package.json` `exports` gains `"./include": { "types": "./dist/include.d.ts", "import": "./dist/include.js" }`.
Private modules are the implementer's (`load/values.ts` is the one home of the value rules, §2).

**Acceptance criteria, each with its mutation probe:**
1. The TS load-conformance runner passes every case in `conformance/load/cases.json` (the `needs` filter removed).
   *Probe:* make snippet bodies see use-site variables: `load-snippet-lexical` fails; restore.
2. Each rule of §1.2 has a unit test through `knobly(...)`: reserved names, set (incl. E5009), handed-in wins,
   `$name` in values/lists/bounds, snippet/use (E5003, E5004, E5005, E5010, E5011), extension block (E5012), limits
   (E5006, E5007, E5008 with a small fan-out snippet), value rules at load. *Probe:* lower the depth limit check from
   `> 16` to `> 17`: the E5007 test fails; restore.
3. Read once (R21): a counting source shows `read` called once per path when one file is included at two places, and
   `graph.nodes` holds it once while `graph.edges` has two entries. *Probe:* drop the per-load read cache: the
   count test fails; restore.
4. Readers: each of `word`, `string`, `number`, `integer`, `boolean`, `items`, `slice`, `plain` returns the right
   value for a valid input and throws `DiagnosticError` with the §1.6 code placed at the value for an invalid one;
   `plain()` on `"8080"` is the string `8080` and on `8080` the number. *Probe:* make `plain()` read quoted text as a
   number: the test fails; restore.
5. Canonical text (§1.3) for every kind, incl. a list with a comment and a trailing comma, and a string written with
   single quotes. *Probe:* keep comments in list text: `load-diff-list-comment` and the unit test fail; restore.
6. `diff` (§1.5): added, removed, changed (values and has-block), unknown for a broken line, subtree listed once,
   order, TypeError across processors. *Probe:* report a missing directive as removed even when its container in
   `after` has an unreadable statement: the unknown test fails; restore.
7. Address and key rule: `text` bytes, `toString()`, `parent`; the key rule sees expanded args, `hasBlock` and its
   parent's key input, parents first; a throw from it rejects the load. *Probe:* compute occurrence across all
   siblings instead of same name and key: the address test fails; restore.
8. Diagnostics sink: `report`, `add`, `collect` (records a DiagnosticError and returns undefined; rethrows anything
   else); program codes without "/" throw TypeError in `error()` and `report()`; a handed-in value's error is placed
   on the `$name`. `formatDiagnostic` prints `path:line:col: code: message` 1-based, the source line, the caret and
   one via line per step. *Probe:* make `collect` swallow every exception: the rethrow test fails; restore.
9. rasl acceptance (`ts/src/load/rasl.test.ts`): with `createFileSource()` and `include()`, `family_room.conf`,
   `hyperhdr.conf` and `split/main.conf` (handed `leds_host`) load with no diagnostics and the node ids of
   `fixtures/rasl/expected.json`; the `$pixels` edit's `diff` equals the expected changes (under the `"rasl"` key
   rule). *Probe:* ignore handed-in variables: the split fixture's `target` value differs from expected; restore.
10. `corepack pnpm -C ts test`, `typecheck`, `lint` pass; `git grep -n "parseGraph\|createAst\|valueOf" ts/src` is
    empty.

**Land:** `git add -A -- ts && git commit -m 'feat(ts): low-level consumer API: load, directives, diff, include' -- ts`; push.

---

## S3: the Python low-level API (`kno-stq.4`)

**Owns:** `py/**` (S1's files included, now S3's). Nothing outside `py/`.

**Signatures:** §4 is the final Python surface; every body in the new modules filled; `__init__.py` switched to
§4's list; the deletions in §4 done with tests rewritten (`test_ast.py`, `test_value.py`); `DiagnosticError` carries
a `LocatedDiagnostic`; `SliceValue`/`IndexValue` lose `span`; E2006, E3002, E3003 removed. `Processor.load` is
synchronous (decision Q-pyload). Private modules are the implementer's (`_values.py` is the one home of the value
rules).

**Acceptance criteria, each with its mutation probe:** the same nine behaviours as S2's criteria 1-9, through the
Python API, with these Python spellings: the conformance runner is `py/tests/test_load_conformance.py` and runs
every case; readers are `as_word`, `as_str`, `as_number` (int or float), `as_int`, `as_bool`, `as_list`,
`as_slice`, `plain`; the sink's keep-going form is `with problems.collecting():`; `walk(node, descend=...)` passes
over a block when `descend` returns False; `Directive` matches `case vl.Directive("node", [kind, node_id, *rest], body)`;
a program code without "/" raises ValueError, also when a `LocatedDiagnostic` is made directly; diff across
processors raises ValueError; the rasl test uses `file_source()` and `include()`. Each criterion's probe is S2's
probe applied to the Python code. Plus:
10. `uv run pytest`, `ruff check`, `ruff format --check`, `mypy` pass; `git grep -n "create_ast\|value_of" py/src` is
    empty.

**Land:** `git add -A -- py && git commit -m 'feat(py): low-level consumer API: load, directives, diff, include' -- py`; push.

---

## S4: docs (`kno-9vn.1`)

**Owns:** `README.md`, `design/RECORD.md`, `ts/README.md`, `py/README.md`, `docs/language.md` (new),
`docs/low-level-api.md` (new). Runs after S2 and S3.

**Content:** the language changes (variables, snippets, include as an extension, reserved names, the rules of §1.2
in plain words with examples from rasl's fixtures); the low-level API reference for both languages side by side
(load, walk, readers, origins, addresses, diff, the sink, the source port, extensions) with rasl's reading and
reload code as the worked example; RECORD: new owner answers since 2026-10-24 that this build rests on (quoted, with
dates, from `requirements.md`), the codes table, the retired codes, and the bead outline status; README: the new
entry points. **Acceptance:** every code in §1.6 appears in the reference; every example in `docs/` is copied from a
test that passes (name the test); no claim about behaviour that no test shows. *Probe:* none (docs are checked by
review, never fail a code slice).

---

## Test architecture

- **Tier 1** stays tested through the syntax conformance corpus (byte-identical in both languages) plus recovery
  tests. New syntax rides the same corpus (`variables.json`).
- **Load layer, each language in isolation:** every test goes through the public `knobly(...)` / `Processor`
  with `memorySource`; no test reaches into private modules except the value-rules module's own table tests. The
  document source is the seam: a counting or failing fake source tests read-once, E3001 and E3004 without a disk.
- **Cross-language conformance boundary:** `conformance/load/` is the contract for R17 (identical codes, places,
  trees, addresses and change lists). Both runners are thin: build the expected object from the public API and
  compare bytes.
- **The real artifact:** each language's rasl test loads the real v10 fixtures through the file source and the
  include extension, with a handed-in variable, and diffs a reload.
- **What is not tested:** speed on large trees, non-UTF-8 files, the fetch source against a real server.

## Maintenance risks

1. **Two implementations of one expansion.** R17 rests on the load conformance corpus; a rule added in one language
   without a case drifts silently. Rule: every new expansion rule lands with a load case.
2. **Hand-derived expected outputs.** Wrong ones stop S2/S3 through errata, which costs a round trip; S1 keeps the
   cases small to limit this.
3. **`text` is canonical, not as written.** A program that wants the written text must go through `origin` and the
   tier-1 node. Changing the canonical form later changes every address that uses `text` in a key rule.
4. **Key rules live in programs.** A key rule that reads values from variables makes identity follow config edits;
   documented, not prevented.
5. **The sugar must keep its own records** of inherited reads, applied changes and pending failures (review finding
   5): this layer does not track them, and the sugar's design must not assume it does.

## Integration with existing code, and departures (with cost)

| Today | This build | Cost |
|---|---|---|
| `IAstDocument`/`IAstDirective` facade, `parseDocument` (TS and Python) | `ILoaded`/`IDirective` through `knobly(...).load` | the facade and its tests are rewritten; synchronous single-text reading now needs a processor and `memorySource` (async in TS) |
| `parseGraph` with a `DocumentLoader`, include hard-coded, E2006 a syntax code | the document source port (`resolve`/`read`) owned by the processor, include an extension, E3005 | `node.ts`/`browser.ts` loaders become sources; glob rules move into the file source and `memorySource` |
| `valueOf` (lists throw, any escape decodes) | `IArgument` readers; lists read; only six escapes (owner v6 values: A) | a string with `\q` that decoded to `q` is now E4003 |
| `IGraphDiagnostic` (path only), no chain | `ILocatedDiagnostic` with `at` and `via` | every load-level diagnostic maker changes |
| includes ignored by rasl | spliced where written | rasl's `graph.root`-only read changes meaning once it adopts this (rasl-8st) |

## New terms

| Term | Meaning | Why needed | Could be an existing term |
|---|---|---|---|
| processor | made once with a document source, extensions and key rule; loads and compares | ties key rule and extensions to every load, so `diff` compares like with like | PostCSS's processor; jinja2's environment |
| loaded | what one load produced | the one result a program reads | round 8's "expanded tree" |
| origin | where text was written, and the steps that brought it here | traceability to use site and definition | R14's "include chain", widened |
| step | one expansion: a variable, a use, an extension directive | the parts of an origin | round 10's `via` |
| handed | a variable the program passed in, written in no file | `rasl --set host=...` | round 10's "handed in" |
| address | where a directive lands: name, key, occurrence per level | identity in change lists | v15's "identity" |
| key rule | the program's rule naming a directive among its siblings | addresses that survive moved lines | the sugar's `key=True` |
| unreadable | a statement kept in place that could not be read | tells "broken" from "removed" (review finding 1) | R6's "error node", widened past syntax |
| document source | where files come from: resolve a spec, read a path | one port for the root and every include; read once | the old "loader" |
| extension | owns one directive name and gives specs of files to splice | include as a first-party plugin (R20) | round 10's "plugin" |
| sink (`Diagnostics`) | the one place problems collect | R14's report helper (review finding 2) | HCL's `Diagnostics` |
| canonical text | a value's text with layout and comments removed and strings normalized | "changed" means the value changed (review finding 4) | the value's "text" |
