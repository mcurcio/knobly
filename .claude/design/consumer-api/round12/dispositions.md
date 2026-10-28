# Round 12 dispositions (review + three integrators)

Working state, not for the owner page. design.md went from 24,945 to 24,943 bytes.

## Root causes (the domain-model fixes; most findings are proof of one of these)

| # | Root cause | Model change in design.md | Findings it closes |
|---|---|---|---|
| A | "Place" meant both a span (`IPlace`) and the context a line is read in; the second had no concept, so binding per context had nothing to hang on | new concept **copy** (`ICopy`: statement + `via`), the language doc's own word ("each place gets its own copy"); `statement.copies()`; edges are copies of include lines; resolutions are per copy; rendered `IArgument.resolutions` gives each value's own per-copy resolution | R1, R6, R8, rasl 4/7/9, editor 1/4/5, tool F7 |
| B | Binding had only the per-context half; the language binds snippet bodies by where they are written | design rule 3 now has two halves: `IReference.declaration` (by where written, reached or not) and `resolutions()` (per copy); `IVariable.references()`; `IUseLine.snippet` and `snippets()` | R7, editor 4, tool F2 |
| C | Edges and include structure were stored "as of the load" while text claimed to be the truth | edges, copies, `includedBy()` derived from current texts on ask; the only stored state is which files were read; `unread()` defines the incomplete state; `read(graph)` fetches missing files keeping all texts | R2, R15 (partly), rasl 13, editor 3 |
| D | The document had no whole-text member, so undo, formatting and refresh all fell back to reload, which lost unsaved status | `IDocument.replaceWithText(text)` (ts-morph's SourceFile has the same), leaves `source` untouched, detaches handles | R3, rasl 1, editor 2, tool F1 |
| E | `set`/`snippet`/`use`/include lines were one shape with a `role` tag, so what `values` held and which rules an edit could break were undefined | `Statement` is a discriminated union (`ISetLine`, `ISnippetLine`, `IUseLine`, `IWrittenDirective` with kind extension); values per kind stated; rule 2 forbids leaving text-alone rules broken (E5002, E5005, E5009-E5011) | R5, R13, rasl 8, editor 7/13, tool F4/F5/F17 |
| F | The save contract gave the writer too little (one file, no as-read text) | writer takes one batch of `IFileWrite { resolvedPath, text, source }`; `source` becomes the text handed over, only on resolve | R10, rasl 2/3/6, editor 8, tool F3/F15 |

## Review findings

| # | Disposition | Reason / where |
|---|---|---|
| 1 | Accept | Kind (2) now goes through `IArgument.resolutions[i].winner` at the value's own copy (root cause A), so chains (`set $b $a`, `$host` → `$leds_host`) pick the step; `written` is described as the end of the chain. Label for (3) changed to "the line no longer uses the variable"; "Where L3 holds" paragraph states kind (3) is met per written line, next to the code. |
| 2 | Accept | Root cause C. Edges are derived; `IDocumentEdge` loses the stored `origin` (one place per edge: `copy`). The stale state is named (`unread()`), and costs list it. Refresh keeping texts is `read(graph)`; its mechanism is parked. |
| 3 | Accept | Root cause D. §8 rewritten: B is now Roslyn/LibCST immutable trees with the same named methods (not an edit list), with tracking as its cost; A's undo is per document via `replaceWithText`. |
| 4 | Accept | Handle identity is a public contract in §5's lead line and §6 (`===` / `is`, one object per written thing for the graph's life, follows its tokens). Variable identity: the `$name`'s place, or the handed name. Mechanism stays parked. |
| 5 | Accept | Root cause E. Rule 2 covers E5002, E5005, E5009-E5011; values per statement kind are in the sketch. A second `set` of a name (loaded text) is unreadable and declares nothing, so `winner` is defined. E3005 and E5012 are not text-alone (include args are expanded per copy; E5012 is the extension's) so they are reported in `graph.diagnostics()`, not prevented. |
| 6 | Accept | Root cause A: `copy` is its own term (new-terms table); Question 1 A's premise now uses `statement.copies()`, which counts nested includes, snippet uses and the root (1). |
| 7 | Accept | Root cause B. |
| 8 | Accept | `IReferenceResolution` doc states one reference renders to all of `values`, and a replace replaces them together; `IValueBase.replaceWithText` states the separator (spaces on a line, commas in a list). |
| 9 | Accept | Rule 2: a statement owns the comment lines directly above it and its trailing comment (LibCST leading lines, Roslyn trivia); `setValues` replaces first value to last, comments between included; inserted lines keep their own relative indent. A comment-only line is not addressable: refuted as a need at this layer, because a whole-document replace now covers formatters. |
| 10 | Accept | Root cause F. `source` becomes "the text handed over", after the writer resolves; the writer's field is `source` with the same meaning as `IDocument.source` (no collision now); lost-update detection is the writer's comparison with `source`; partial disk state is listed in §10 as the writer's. |
| 11 | Refute in part | Kept in the graph: L1 "where they were overloaded" and brief item 2 name a handed-in value as a winner, so the low layer's resolutions need them. Accepted the cost half: `setHanded` changes one without a reload (no data loss). That a resolution depends on what is handed in is the language's semantics, not a defect. |
| 12 | Accept | One model: TypeScript's live tree with named methods, read-only properties, a read-only `Sequence` block, kinds as classes for `match`. Dropped `__delitem__`, tuple-returning `append` (now `add_statements`), "tomlkit and ruamel.yaml" model claim; `name` is a read-only property. |
| 13 | Accept | `WrittenValue` and `Statement` are discriminated unions by `kind`. |
| 14 | Accept | `load` throws only `ReadError` (root unreadable); `graph.diagnostics()` holds syntax, text-alone rules and reading (E3001, E3004-E3006, E5006, E5007, E5012); `BadTextError { diagnostics }` located in the given text; `SaveError { files; cause }` typed; `DetachedError` covers a replaced document. A handle from a graph a new `load` replaced is not detached: it still edits its own graph, which the program holds (not on the page: no new surface needed). |
| 15 | Accept in part | Globs: an edge's `targets` lists every match; each target's `includedBy()` lists the edge (sketch, concept table). What to watch is parked to the file source (one home for path rules), since path rules are the source's I/O, not this layer's. |
| 16 | Accept | `quote(text)` exported in both languages; Question 2 A's cost now "a program calls `quote`"; the word-versus-string choice is in the text given. |

## rasl integrator (TS)

| # | Disposition | Reason |
|---|---|---|
| 1 undo/hot reload | Accept | Root cause D; plus `read(graph)` for new files without reload. A file changed on disk while edits are unsaved: the program reads it and decides; merge is deferred (writer sees `source` for conflict detection). |
| 2 edit during save | Accept | `source` becomes the text handed over. |
| 3 hand-edited file overwritten | Accept | Writer gets `source` to compare with disk; the race between compare and write is the writer's (parked: fs writer staging). |
| 4 kind (3) for one node | Accept | Stated next to L3; Question 1 holds the choice. |
| 5 several values | Accept | Review 8. |
| 6 half-saved files | Accept in part | One batch per save lets a writer stage and commit; on-disk atomicity remains the writer's, listed as a cost. |
| 7 count of places | Accept | `statement.copies()`. |
| 8 `$pixels` in set values | Accept | `ISetLine.values` excludes the name. |
| 9 resolutions without matching | Accept | `IArgument.resolutions`. |
| 10 handle identity | Accept | Review 4. |
| 11 UI text adds include lines; no quote helper | Accept quote; refute the first | Adding an include line through `addStatements` is a legitimate edit; a program that forbids it checks the returned statements' kinds. |
| 12 word vs string | Accept | Question 2 A: decided by the text given. |
| 13 render after include edit | Accept | Root cause C. |
| 14 watch set | Park | File source names what to watch. |
| 15 old handles after reload | Refute | They belong to the old graph; with `replaceWithText` and `read` there is no need to reload. |
| 16 source fixed per processor (overlay) | Park | Code architects; not a domain question. |
| 17 handed value has no route to its default | Accept | `variable.overridden()` gives the `set` the handed value wins over; `resolutions[i].overridden` too. |
| 18 written value back to its variable | Accept | `IReference.declaration`, `IVariable.references()`. |
| 19 invented fields; no transaction | Accept in part | Fields now in the sketch; a multi-edit transaction is a kept text per document plus `replaceWithText`. |

## Editor integrator (Python)

| # | Disposition | Reason |
|---|---|---|
| 1 wrong set line | Accept | `Argument.resolutions` per copy. |
| 2 no rollback | Accept | Root cause D. |
| 3 include edit forces save | Accept | `read(graph)`. |
| 4 snippets unbound | Accept | Root cause B; `copies()` counts each `use`. |
| 5 case 3 copying text that rebinds | Refute | Which text a program writes is its choice; an "inline keeping meaning" is a refactor (high level). The edit returns the new values now, so it can check. |
| 6 list item with several values; no parent | Accept | Separator rule; `IValueBase.list`. |
| 7 `values` on set/use/include | Accept | Root cause E. |
| 8 lost update | Accept | Root cause F. |
| 9 identity | Accept | Review 4. |
| 10 ids across requests, versions | Park | In-process identity is the contract; an id a program keeps across requests is parked; `text !== source` is the unsaved signal. |
| 11 comment ownership, indentation | Accept | Review 9. |
| 12 BadTextError location | Accept | `BadTextError { diagnostics }`. |
| 13 variable `$name` place, rename | Accept | `IVariable.place`, `IVariable.rename`. |
| 14 quote helper | Accept | `quote`. |
| 15 innermost-first misread | Refute | Existing `IStep` convention, unchanged; documentation. |
| 16 append tuple; threads; `Rendered.diagnostics` | Accept / park / out of layer | `add_statements`; "one thread edits" parked; rendered diagnostics are the middle layer's (unchanged). |

## Tool integrator (TS)

| # | Disposition | Reason |
|---|---|---|
| F2 rename misses unused snippet refs | Accept | Root cause B. A `$name` inside an unreadable line is not a reference: accepted as stated (an unreadable line has no values). |
| F1 whole-document edit | Accept | Root cause D. A failed edit changes nothing (rule 2); a multi-edit refactor keeps texts to restore. |
| F3 two graphs over one file | Accept in part | Writer's `source` comparison catches it; several roots in one graph deferred (§10). |
| F9 depends on what was handed in | Refute | Language semantics; `setHanded` lets a tool state what the program hands in. |
| F4 variable's `$name` handle | Accept | `IVariable.place`, `rename`; `ISetLine.values` excludes it; it is not an `IReference`. |
| F5 setValues on set line | Accept | Root cause E. |
| F6 identity, return values | Accept | Review 4; `replaceWithText` on a value returns the new values and detaches the old handle. |
| F15 half-written rename | Accept in part | Batch writer; atomicity the writer's (cost). |
| F10 load errors | Accept | `graph.diagnostics()`. |
| F7 parameter value per use | Accept | `IReferenceResolution.values`. |
| F8 value position, separator, slice bounds | Accept; slice bounds parked | `list`, separator rule; slice-bound references parked as before. |
| F13 diff ignores diagnostics | Out of layer | Middle layer's diff. |
| F17 not a discriminated union | Accept | Review 13. |
| F11 lookup by typed path | Park | Path normalisation is the source's. |
| F14 comment ownership | Accept | Review 9. |
| F12 general tool guesses extensions | Refute | Extensions are the program's by design (R20). |
| F16 variable-name check | Accept | `BadTextError` from `rename`; no separate validator. |
