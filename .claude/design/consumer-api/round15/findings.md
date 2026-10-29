## Appendix: every reviewer finding

All five reviewers returned FAIL. Re-checked by me against /Volumes/Dock/Home/Code/villanelle/.claude/worktrees/binding-spec (commit f7bf793):
- Python concept probes 1-14 (/Volumes/Dock/tmp/vil-review/lang/probe.py).
- TS probes unread.ts, unread2.ts, task2.ts and lost.ts, under Node 24.14.1.
- Python probes probe_seqstr, probe_detach, probe_errtext and probe_runtime.
- The StrEnum mypy probe; grammar lines; RENDER_CODES; fetchWriter; spec.md:382; generated line counts.

One correction: api.json has 31 `spell` entries, not 21.

NOT RUN: ext.ts, names.ts, syn.ts, kinds.ts, the snippet-check script, and the jscpd duplication scan. Findings not listed as re-checked rest on the reviewers' own evidence, which they marked as confirmed.

### Language concepts
- HIGH. Two statement endings plus number-named directives split a statement silently. Villanelle.g4:9,14,29; docs/language.md:12. Re-checked.
- HIGH. An included file's top-level set lines join the includer's block, so a file cannot set its own default or be included twice in one block. docs/language.md:197-203; spec.md:551-552. Re-checked.
- HIGH. Overrides are undeclared and global by name; they beat per-place include bindings and nested locals. docs/language.md:89-92; spec.md:625-628. Re-checked.
- HIGH. The rules about names (scope, precedence, splicing) have no normative home in spec/. spec.md:19-21; docs/language.md:3-5.
- MEDIUM. The values-text check is a hand-written probe-and-scan per binding and has drifted. ts written/document.ts:817-859; py _document.py:858-920; errata 2026-10-29.
- MEDIUM. set, snippet and use are reserved in every block; whether `include` is a splice depends on the processor's extensions; the "extension" port is really only include. docs/language.md:212-216; extension.py:24-40. `use epoll` re-checked.
- MEDIUM. Both quote styles process escapes; Windows paths corrupt silently; there is no raw or multi-line string. Villanelle.g4:30-31. Re-checked.
- MEDIUM. The `plain` reader guesses types YAML-style (1.10 becomes 1.1; 01234 text against 12345 number). spec.md:344,371-374.
- MEDIUM. Slice and index work only on a WORD; ':' is banned in words that start with a digit (07:30, MAC addresses). Villanelle.g4:17,29; RECORD.md:23. Re-checked.
- MEDIUM. A bad escape or a literal non-integer bound is invisible to parse and to the graph. villanelle.ebnf:52-55; spec.md:450,654. Re-checked.
- LOW. "One set per name per block" still lets a name change meaning partway through a block. docs/language.md:75-78. Re-checked (probe 13).
- LOW. 'set' names five things across the language and the API. spec.md:727-739.
- Extra, seen in my re-run, not ranked by any reviewer: `%`, `~`, `+` and `=` are refused characters inside unquoted words (`100%`, `~/x`, `+1`, `a=b` all give E1003).

### Domain model across layers
- HIGH. Two trees of the same shape and three value families (22 types); render re-copies the expansion. spec.md:908-951; render.ts:22-46.
- HIGH. api.json is a hand-kept name list: free-text types, undefined type names, prose `spell` notes, incomplete error lists, a one-way name check. api.json; gen-api.py:83-95.
- HIGH. Three diagnostics lists, one filtered by hard-coded render codes; the registry's owning layer is wrong. graph.ts:25-30; _graph.py:23; diagnostics.json. Re-checked.
- MEDIUM. The error class tree contradicts its own rule (DetachedError under VillanelleError; EditError never raised; TS misuse equals TypeError). contract.md:122-152; errors.ts; errors.py. Re-checked.
- MEDIUM. The glossary's "one word, one meaning" is broken by override, place, written and definition, and by text fields with concept names. glossary.md:24-63; origin.ts:27,48.
- MEDIUM. Layers are cut by imports, not by domain ("io" holds a pure port; "shared" holds the readers); each layer has two names. api.json:20-60; README:9-14.
- MEDIUM. Schema facts repeated by hand per throw site and in docs; the docs have drifted (E3004 read error, a TypeError claim). bind.ts:512-807; docs/low-level-api.md:235; rendered-tree.md:165,580,677.
- MEDIUM. Spec 2.10 forbids TS runtime enumerations, against the owner's 2026-10-29 ask. spec.md:378-384. Re-checked.
- LOW. The reader and writer ports for one storage medium are wired by hand (the memory pair shares a map by convention). contract.md:171-195.
- LOW. The key rule is passed per call, so addresses and diff can disagree. spec.md:992-993.
- LOW. The canonical schema and spec carry history and stale internal names. api.json:3250-3429.
- SUSPECTED. render is called "pure" but writes the graph's cache and returns live handles. spec.md:475-478 against 914, 965.

### TypeScript
- HIGH. A render over an unread include drops directives silently; diff reports them as removed. render.ts:19; spec.md:957. Re-checked.
- HIGH. Config text and program strings share one type. model.ts edit signatures; processor.ts:26. Re-checked.
- HIGH. The extension port is not usable from the public API; include.ts uses internals; a hand-built diagnostic loses its place. include.ts:7-11,25,28; extension.ts.
- HIGH. A lost update is a plain Error with per-writer wording; SaveError.paths lists every file; fetchWriter never checks. node.ts:69; source.ts:88; browser.ts:47. Re-checked.
- MEDIUM. Validation rules (VARIABLE_NAME, RESERVED, limits) are not exported; a bad name raises TypeError or BadTextError depending on the method. override.ts:23-26; gen/api/limits.ts. Re-checked.
- MEDIUM. A flat namespace of 114 names, 76 with an I prefix, against adopted binding-guide rule 1; ValueRef leaks. index.ts:11-46; binding-guide.md:62-77.
- MEDIUM. Public types are hand-written; a 450-line runtime probe checks names. api-names.test.ts; codegen.md:123-131.
- MEDIUM. The low level casts through unknown 15 times; the no-cast lint covers only rendered/. bind.ts; statements.ts; value.ts:183,287.
- MEDIUM. Containers, walks and copies differ per layer; syntax nodes have no typed accessors. written/model.ts:232-245; rendered/model.ts:126-180; cst.ts:27-30.
- LOW. The generated keyword set is untyped; dispatch on keywords is hard-coded. limits.ts:17; bind.ts:492-494,692.
- LOW. An uncaught DiagnosticError prints without its place or code. errors.ts:25.
- LOW. "Every example is copied from a test" is unchecked; no complete first-hour program exists. docs pages; ts/README.md:36-49.

### Python
- HIGH. Port results typed `Sequence[str]` let a bare str split into letters; the error names include. extension.py:33; source.py:29; codes.py:39-40. Re-checked.
- HIGH. The edit loop over a render raises DetachedError on the second copy. README.md:66-77; model.py:696-703. Re-checked.
- HIGH. str(BadTextError) is a bare code; its diagnostics leak the probe text. errors.py:59-69; _document.py:858-868. Re-checked.
- MEDIUM. A lost update arrives as RuntimeError or OSError inside SaveError. source.py:110-112; files.py:63-65. Re-checked.
- MEDIUM. Value `==` compares identity despite spec 2.9. value.py:46-75.
- MEDIUM. Names that shadow builtins or mean two things (list, slice, set, List, String). model.py:690-694; value.py:47-50.
- MEDIUM. Shapes are chosen by hand per method (list against tuple results; five copied Argument constructors; prose parsed with regexes). model.py:121,128; _render.py:105; _tree.py:68-188; test_api_names.py.
- MEDIUM. Keywords and precedence tiers are hand-typed strings in two dispatchers; program codes are an untyped str. _shape.py:53-99; _bind.py:271,548-555; report.py:25.
- MEDIUM. Two container shapes across layers; a flat 98-name root. model.py:576-634; _tree.py:314; __init__.py:99-198.
- LOW. The internal layout copies TS's free functions; public constructors build half-made objects. model.py:80-92; _graph.py:26-46.
- LOW. Public docstrings cite internal design IDs and TS. 93 occurrences.
- LOW. The same bad name raises ValueError or BadTextError depending on the method. _graph.py:43-46; model.py:950-957. Re-checked.

### DRY and codegen
- HIGH. The public API shape is declared three times, tied together by a test-time check. api.json; 93 TS interfaces; Python classes; codegen.md:115.
- HIGH. Diagnostic facts are re-typed at every raise site; the three code tables disagree (8 of 32 meanings, 14 of 32 found-by); E3005 has a layer that does not exist. bind.ts:470-813; _bind.py:531-899; spec.md:142-175.
- HIGH. Python StrEnum comparisons and string-keyed tables pass mypy --strict with typos. _shape.py:92,99; _document.py:376-394. Re-checked.
- HIGH. The adapter protocol and its 20 data shapes are prose, hand-implemented per adapter, with TS spellings in the neutral format. conformance.md 4.1-4.2; adapters; driver/written.py:15-28.
- MEDIUM. The casing rule is written 7 times and the copies differ; derivable spellings are stored. gen-api.py:60-72; adapters; name tests.
- MEDIUM. `spell` mixes four kinds of fact and is regex-parsed by three tools. api.json (31 entries).
- MEDIUM. gen-api.py and api.json are not yet an interface definition; the stated reasons for rejecting TypeSpec are partly wrong (its core is protocol-neutral). gen-api.py; codegen.md:126,140.
- MEDIUM. The value text rules live in an unchecked second grammar file and are hand-translated per binding. villanelle.ebnf:55-63; values.ts; _values.py.
- MEDIUM. The rule-to-node-kind table and the statement keywords are hand-mapped per binding. walk.ts:32-39; _walk.py:16-23; shape modules.
- MEDIUM. The error class trees are hand-written twice; adapters recover the group from the class name by regex (minifier risk). errors.ts; errors.py; adapters.
- MEDIUM. The algorithms are kept in step by line-for-line porting from TS and have drifted; 15 files call themselves ports. _bind.py:7 and others; errata 2026-10-29.
- LOW. Reader names, adapter units and levels, operation names and found-by are not schema lists; reader names collide with value kinds. conformance.md 4.1; units.py:12.