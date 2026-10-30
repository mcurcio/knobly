# Round 12 slices: the low-level layer (config as written, editable, saved back)

Code architecture for round 12, inside the approved frame `design.md` (owner gate v12, 2026-10-28: names A, copies A,
values A). Decisions taken while cutting are one line each in `decisions.md` (ids `D…` below). Rules: the
`implementation-workflow` skill. One PR, branch `feat/low-level-layer`, base `main` (owner, 2026-10-28, via the run
brief: one PR for this layer).

## 0. Order and why

| Slice | Owns (and only these) | Runs | Why here |
|---|---|---|---|
| **S1 tracer** (TS) | `ts/`, `conformance/`, `fixtures/` | first, alone | the riskiest seam is the binding moving out of PR 3's expansion (design rule 3) while `render` keeps every load-conformance byte; the tracer proves it end to end, plus both L3 kinds and save |
| **S2** (TS) | `ts/` | after S1, beside S3 | the rest of the TS surface; one package, so it can be large |
| **S3** (Python) | `py/` | after S1, beside S2 | the same model in Python; reads S1's landed TS as its reference and runs S1's shared cases |
| **S4 docs** | `docs/`, `README.md`, `design/RECORD.md`, `ts/README.md`, `py/README.md` | after S2 and S3 | docs are their own slice (skill §3.6) |

S2 and S3 share the checkout: disjoint owned paths (`ts/` vs `py/`), and their checks write only inside them
(`ts/src/gen/`, `ts/dist/`, `py/src/knobly/_gen/`, `py/.venv/`). Everything both need (the shared conformance
cases and their format) is S1's (D9). Neither touches `conformance/`, `fixtures/` or `.claude/`; an error in a
shared case is an erratum (`.claude/errata.md`) and a STOP, never a local edit.

Land command per slice (paths named, skill §4):

```bash
git add -A -- <owned> && git commit -m '<conventional message>' -- <owned> && git push origin feat/low-level-layer
```

## 1. Shared primitives (frozen now; committed as compiling code in this round's interface commit)

| Primitive | Home | One responsibility | Consumers now / scheduled |
|---|---|---|---|
| low-level types | `ts/src/written/model.ts` | the public shape of documents, statements, values, copies, variables, resolutions, writer | S1 (graph, documents, statements, values), S2 (all other members), render (S1), S3 mirrors it as `py/src/knobly/written/model.py` |
| edit and save errors | `ts/src/written/errors.ts`, `py/src/knobly/written/errors.py` | the typed failures of edits, save and the root read | S1 (`BadTextError`, `DetachedError`, `NoSetLineError`, `SaveError`), S2 (`ReadError`), S3 |
| the binding contract | `ts/src/written/bind.ts` | the one home of the name-lookup rule and the copy walk; what `render` consumes | S1 implements, S1's render consumes; S3 ports it as `knobly/written/_bind.py` |
| save and quote | `ts/src/written/save.ts`, `py/src/knobly/written/save.py` | hand changed files to the writer in one batch; a plain string as knobly text | S1, S3 |
| fs writer | `ts/src/node.ts` `createFsWriter`, `py/src/knobly/files.py` `fs_writer` | the batch on disk | S1 (batch, simple), S2 (staging, lost update), S3 |
| `canonicalString` (exists) | `ts/src/load/values.ts`, `py/src/knobly/_values.py` | a decoded string's canonical text | `quote` delegates to it (one rule: it is the same text) |
| written-layer conformance | `conformance/written/` | the cases both languages must produce byte for byte | S1 writes all of them; S1/S2/S3 runners |

The committed files are the frozen signatures. A slice that needs a change to one appends an erratum and stops.

## 2. Internal rules every slice implements the same way (frozen)

These are the "parked for the code architects" items of design.md §13, decided (one line each in `decisions.md`).

**2.1 Handles (D20).** A document keeps one handle per statement and per written value, in a tree mirroring its
current parse. An edit computes the new text, checks it (2.3), re-parses the whole document, and reconciles: a
handle whose tokens lie wholly outside the replaced range is kept (matched by kind and start offset, shifted by the
splice's length change); one inside it detaches; the edit's new statements or values get new handles. The edited
statement itself keeps its handle for `setValues` and `rename` (only its values or name are replaced); a value's
`replaceWithText` and any `replaceWithText` on a statement detach the handle they were called on. A detached handle
throws `DetachedError` from every member except `kind`. `IDocument.replaceWithText` detaches every handle into the
document (the document handle stays). An `IVariable` of a `set` line is that line's `variable` (same object); a
parameter's is its snippet line's; a handed-in value has one `IVariable` per name for the graph's life (D28).

**2.2 Comment ownership and spans (D15, D31).** A statement owns (a) each comment line directly above its first
line, with no blank line between (a comment line holds only spaces/tabs and one COMMENT), and (b) a COMMENT after
its last token on the same line, with only spaces between. A trailing comment after `a; b;` is `b`'s. `text` and
`place` run from its first owned token to its last owned token: interior text verbatim, without the indentation
before the first token and the line break after the last. `remove()` deletes that span; when nothing else is on its
lines, it deletes the whole lines (indentation and line break included); otherwise it also deletes one space next
to it.

**2.3 Edit checks (rule 2; D16, D17, D30).** On any failure the document is unchanged and `BadTextError` carries
diagnostics located in the given text (0-based, as `parse` gives them):
- values text (`setValues`, value `replaceWithText`): parsed as the values of one directive (`x <text>;`; in a list,
  `x [<text>];`). Its syntax diagnostics, shifted to the given text; if it is more than values (a `;`, a block),
  one E2001 at the first such token. A slice bound takes exactly one WORD or `$name` (E2001 otherwise).
- statements text (`replaceWithText` on a statement, `insertStatements`, `addStatements`): parsed as a document;
  its syntax diagnostics. Empty text is zero statements.
- then the text-alone rules on the block that would result, reported on the new text: E5002 (a second `set` of a
  name in one block), E5005 (a second `snippet`), E5009 (`set` without `$name` or value, or with a block), E5010,
  E5011 (the shapes PR 3 checks). A `set` left with no value by `remove()` or `setValues("")` is E5009.
- `rename(name)`: one WORD; a name that is `set`, `snippet`, `use` or a registered extension's, or renaming such a
  line, is E2001 at 0:0. `IVariable.rename`: `[A-Za-z0-9_]+`, then E5002 in its block.
- An include line keeps kind "extension" through edits; `addStatements("include \"x.conf\";")` is a legal edit
  (its file is unread until read).

**2.4 Splicing whitespace (D14).** `setValues(text)` replaces first value to last (comments between included); with
no values it inserts one space then the text after the name (a `set` line: after its `$name`); an empty text deletes
the values and the space before them. `remove()` of a value deletes it and the space before it; in a list, the item
and its comma (the following one, or the preceding one for the last item). Inserted statements: each line of the
given text, after removing the text's common leading indentation, is prefixed with the siblings' indentation (the
indentation of `statements[0]`; in an empty block, the parent's line indentation plus the document's indentation
unit: the leading whitespace of its first indented line, else four spaces). Line breaks are the document's first
(`\r\n` or `\n`; `\n` when it has none). An empty block written `{}` becomes `{`, line break, the lines, line
break, the parent's indentation, `}`.

**2.5 The binding (design rule 3).** `bind()` (contract: `ts/src/written/bind.ts`) walks copies exactly as PR 3's
`Expander` walks: the root's statements, then each block; an include line splices each target's statements at that
place through `SpliceScope`'s rule; `use` splices its snippet's block with its parameters. The winner of a `$name`
at a copy is PR 3's rule unchanged (`Scope.lookup` and `Expander.variable` at cb08803: nearest `set` or parameter;
an include block's `set` wins over every `set` inside the spliced files but not a nearer parameter; a handed-in
value wins over every `set` and include-block `set`, never over a parameter). `overridden` lists every other
variable of that name visible there in the order the rule would pick them if the ones before were removed ("next
first"). The limits (E5006 cycle, E5007 depth, E5008 count), the include checks (E3001, E3004, E3005, E3006, E5012)
and the per-copy E5002/E5003/E5004/E5005/E5009-E5011 are found by the walk, at the same places and in the same
order PR 3 reports them, and recorded as `IBoundUnreadable` items. `argumentsAt` builds PR 3's `Argument` with PR
3's origins (a `set` stores its values without its own copy's steps; a reader adds the variable step then its own
copy's steps), plus `written` and `resolutions` (S1's page). Value problems (E4001, E4003, E5001) throw
`BindingProblem`.

**2.6 Declarations (by where written).** A reference's `declaration` is, in its own file only: the parameter of
the enclosing `snippet` line of that name if any, else the nearest `set` of that name above it in its block or an
enclosing block (an include line's block counts as a block; a `set` inside it is seen by later lines of that block,
as PR 3's `extensionBlock` binds). A second `set` of a name in one block is an `IUnreadableLine` and declares
nothing. A `use` line's `snippet` is the nearest `snippet` line of that name above it, by the same rule.

**2.7 Orders (D29).** `copies()`, `edges()`, `reaches()`, `overridden()`, `resolutions()`, `snippets()`: walk order
(the order render meets them). `variables()`: each document in `documents` order, and in it each `set` line's and
`snippet` line's `$name`s in text order; then handed-in values in `handed` order. `documents`: the root, then
first-read order. `handed`: the load option's insertion order, a new `setHanded` name at the end.

**2.8 What is stored (design rule 1; D12).** Only the texts (and each `source`), the handed-in texts and the read
ledger: per `(parentPath, spec)` the paths it resolved to or the rejection; per path the document read or the
rejection. A spec or path not in the ledger makes its edge unread. A rejection is kept: `read(graph)` does not retry
it. The binding is cached per graph version (bumped by every edit, `setHanded`, `replaceWithText` and read);
everything holds with the cache empty.

## 3. The shared conformance cases (S1 writes them all)

`conformance/written/format.md` (S1 writes it; this is its content in short), `conformance/written/cases.json`,
`conformance/written/expected/<name>.json`. Bytes as `conformance/format.md`. Expected files are derived by hand from
section 2 and design.md, never generated by a runner.

- **Case:** `{"name", "needs", "files"? | "fixture"?, "root", "variables"?, "extensions"?, "steps"}`. `fixture` is a
  directory under `fixtures/` whose `*.conf` files are served by path relative to it (D10); `extensions` is absent
  or `["include"]`. No key rule anywhere: rendered addresses are positional.
- **`needs`** (a runner skips a case needing a feature it lacks): `include`, `snippet`, `values` (ISetLine and
  IVariable `setValues`, value `replaceWithText`), `save`, `quote` (S1); `directive-values` (IWrittenDirective and
  IUseLine `setValues`, value `remove`), `statements` (statement `replaceWithText`, `remove`), `blocks`
  (`insertStatements`, `addStatements`), `rename`, `document` (`IDocument.replaceWithText`), `handed` (`setHanded`)
  (S2). S1's runner implements the S1 set; S2 and S3 run every case.
- **Steps**, each giving one output entry: `["list"]`; `["render"]`; `["texts"]` (each document whose text differs
  from its source, `[path, text]`, documents order); `["save"]` (what a recording writer got, `[path, text]` in
  batch order; `[]` when it was not called); `["edit", target, op, ...args]`; `["quote", text]`.
- **Targets:** `["document", path]`; `["statement", path, line, col]` (the statement whose name token starts there);
  `["block", path]` (a document's body) or `["block", path, line, col]` (that statement's block); `["value", path,
  line, col]` (the written value starting there; a reference at its `$`); `["variable", path, line, col]` (its
  `$name`), `["handed", name]`; `["graph"]`; `["rendered", address, arg, step, "winner" | "reference"]` (render
  now, the directive at that people address, `args[arg].resolutions[step]`, then its winner or reference).
- **Ops:** `["setValues", text]`, `["replaceWithText", text]`, `["remove"]`, `["rename", name]`,
  `["insertStatements", index, text]`, `["addStatements", text]`, `["setHanded", name, text | null]`. Output
  `["ok"]`, `["ok", [text, ...]]` (returned handles' texts), or `["error", "BadTextError" | "DetachedError" |
  "NoSetLineError", [[code, line, col], ...]]`.
- **`list` output:** `{"files": [[path, [edge, ...]], ...], "edges": [[copy, [spec, ...], [target, ...]], ...],
  "variables": [[name, kind, place | "handed", [copy, ...], [[copy, winner], ...]], ...], "diagnostics": [[code,
  origin], ...]}`: per document its `includedBy()` edges, each as its copy; a copy is the load-conformance origin text
  of `{written: statement.place, via}` (for a reach or an override, of `{written: reference.place, via:
  copy.via}`); a winner is its place or `handed <name>`.
- **`render` output:** the load-conformance object without `files` (`directives`, `unreadable`, `diagnostics`),
  each argument extended to `[text, origin, written, [[reference, winner], ...]]`: `written` its place or `null`,
  each resolution as the reference's copy text and the winner (place, `handed <name>`, or `null`).

Cases S1 must write (at least; each named for what it proves): `split-list` (the briefing's §3 (1) table, with
`leds_host` handed in), `split-kind2` (edit `["rendered", "graph > node #2 > max_count", 0, 0, "winner"]`
`setValues "2400"`, then save, render), `split-kind3` (from a fresh load, the same resolution's `reference`
`replaceWithText "2400"`, then save, list, render), `chain-step` (`target $host` at leds: step 0 is `$host`, step 1
`$leds_host`, D7), `ports-two-values` (`set $ports 8080 443; listen $ports;` and a replace of the reference),
`set-values-bad` (BadTextError E2001 for `"1; x"`, nothing changed), `detached` (the replaced reference used again),
`handed-no-set-line`, `overridden-next-first` (a handed value over an include-block `set` over a file's `set`),
`declaration-free-and-bound`, `snippet-copies` (one body line, two `use`s), `save-twice` (`[]` the second time),
`quote-escapes`, `comment-owned` (remove a statement with a comment above and after); and for S2's features one or
more cases per `needs` token: `directive-set-values`, `use-set-values`, `value-remove-list-item`,
`statement-replace`, `statement-remove-shared-line`, `insert-indent`, `insert-empty-block`, `add-include-unread`,
`rename-directive`, `rename-kind-refused`, `rename-variable-e5002`, `document-replace-detaches`, `set-handed`.

---

## S1: the tracer (TypeScript)

**Owns:** `ts/`, `conformance/`, `fixtures/`. Alone in the checkout. Checks: `corepack pnpm -C ts test`,
`typecheck`, `lint` (exit 0 each, foreground). Commit message: `feat(ts): the low-level layer tracer: documents,
binding, render on top, save`.

**What it delivers.** The low level of section 1's committed types for reading every statement kind, the binding
(section 2.5-2.8) with the lookup rule moved out of `load/expand.ts`, `render(graph)` on top of it keeping every
load-conformance byte, rendered values carrying `written` and `resolutions`, the edits L3 needs (2) and (3), save
with the batch writer, and the shared cases of section 3.

**Files.**

| Action | Path | What |
|---|---|---|
| fill | `ts/src/written/model.ts` | unchanged types; classes implementing them live in new files below |
| fill | `ts/src/written/bind.ts` | `bind()`; move `MAX_DEPTH`, `MAX_DIRECTIVES`, `RESERVED` definitions here |
| fill | `ts/src/written/save.ts` | `save`, `quote` (= `canonicalString`) |
| new | `ts/src/written/document.ts` | the document: text, source, syntax, handle tree, splice and reconcile (2.1-2.4) |
| new | `ts/src/written/statements.ts`, `ts/src/written/values.ts` | statement and value handle classes |
| new | `ts/src/written/graph.ts` | `DocumentGraph implements IDocumentGraph` (holds extensions, handed, ledger; binding cache) |
| new | `ts/src/written/read.ts` | `loadGraph(...)` and `readUnread(graph, source)` (the read loop; S2 exposes it) |
| new | `ts/src/load/render.ts` | `render(graph)`: walks `binding.items`, builds `Directive`, `Argument`s via `argumentsAt`, addresses with the processor's key (until S2) |
| delete | `ts/src/load/expand.ts`, `ts/src/load/graph.ts`, `ts/src/graph/save.ts`, `ts/src/graph/save.test.ts` | replaced |
| change | `ts/src/load/processor.ts`, `ts/src/load/directive.ts`, `ts/src/load/tree.ts`, `ts/src/load/report.ts`, `ts/src/node.ts`, `ts/src/browser.ts`, `ts/src/index.ts`, `ts/src/include.ts` (imports only) | the signatures below |
| change | every PR 3 caller in `ts/src/**/*.test.ts` and `ts/src/load/testing.ts` | mechanical: `render(await load(...))` (D8) |
| new | `ts/src/written/*.test.ts`, `ts/src/written-conformance.test.ts`, `ts/src/written/tracer.test.ts` | tests |
| new | `conformance/written/format.md`, `cases.json`, `expected/*.json` | section 3 |
| change | `conformance/load/format.md` | the call shape: `render(load(...))`; the key rule's wording neutral to where it is passed |

**Frozen signatures: changes to existing code** (new code: the committed files of section 1).

```ts
// ts/src/load/processor.ts
export interface IProcessor {
  /**
   * Read the root file at `path` (resolved through the source, as before) and every file its include lines name,
   * once each (R21), repeating until nothing new is named. Never rejects for anything in the text.
   * @throws (rejects) DiagnosticError E3004 at the root path when the source cannot resolve or read it (S2: ReadError);
   * TypeError for bad handed-in variables (unchanged rule)
   */
  load(path: string, options?: ILoadOptions): Promise<IDocumentGraph>;
  /**
   * The rendered tree of the graph's current texts and handed-in values. Pure: reads no file; an unread include
   * copy renders as nothing (its edge is in `graph.unread()`). @throws TypeError for a graph another processor made
   */
  render(graph: IDocumentGraph): IRendered;
  /** Unchanged in S1 (S2 moves the key to its options). */
  diff(before: IRendered, after: IRendered): readonly Change[];
}

/** `ILoaded`, renamed (owner answer names A). Members unchanged; `graph` is the graph it was rendered from. */
export interface IRendered {
  readonly body: readonly IDirective[];
  readonly unreadable: readonly IUnreadable[];
  readonly origin: IDirectiveOrigin;
  /** PR 3's content and order (D11): every file's syntax diagnostics, then the walk's problems in walk order. */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  readonly graph: IDocumentGraph;
  walk(visit: (directive: IDirective) => WalkControl | void): void;
  error(message: string, code: ProgramCode): DiagnosticError;
}
// IExtension, IExtensionUse, ILoadOptions, IProcessorOptions, Change types: unchanged in S1.

// ts/src/load/directive.ts: IArgument gains (a snapshot of the render's derivation; the handles are live)
  /** The written value at the end of its chain (for `$pixels`, the `2284` of its `set`); undefined when handed in. */
  readonly written: WrittenValue | undefined;
  /**
   * One per variable step of `origin.via`, from this value's own line toward where it is written (D7): `[0]` is the
   * `$name` written on the directive's line. Empty for a value written where it is read.
   */
  readonly resolutions: readonly IReferenceResolution[];

// ts/src/load/report.ts
/** As before; the source line comes from `graph.documents.get(path)?.text` (the current text). */
export function formatDiagnostic(diagnostic: ILocatedDiagnostic, graph?: IDocumentGraph): string;

// ts/src/node.ts and ts/src/browser.ts: IDocumentWriter is now the batch writer of written/model.ts
export function createFsWriter(): IDocumentWriter;          // S1: writes each file in batch order (S2: staging)
export function createFetchWriter(fetchImpl: typeof fetch, options?: IFetchWriterOptions): IDocumentWriter;
//   one request per file, in batch order; rejects on the first failure (not all-or-nothing, documented)

// ts/src/index.ts exports, added: everything public in written/model.ts and written/errors.ts, save, quote,
// IRendered; removed: ILoaded, IDocumentNode, the old IDocumentGraph/IDocumentEdge/IDocumentWriter/save.
```

**Internal contracts S1 freezes for S2 and S3:** `bind.ts` as committed; `loadGraph(source: IDocumentSource,
extensions: ReadonlyMap<string, IExtension>, path: string, handed: ReadonlyMap<string, string>):
Promise<DocumentGraph>`; `readUnread(graph: DocumentGraph, source: IDocumentSource): Promise<readonly string[]>`
(the paths read, in read order); `render(graph: DocumentGraph, key: KeyRule | undefined): Rendered`.

**Errors S1 raises:** `BadTextError` (2.3, codes E1xxx, E2001-E2010, E5002, E5009), `DetachedError`,
`NoSetLineError`, `SaveError`; load as before (DiagnosticError E3004, TypeError).

**Acceptance criteria** (each with the mutation probe that must turn it red):

| # | Criterion | Probe |
|---|---|---|
| A1 | `conformance/load/`: all 30 cases byte for byte through `render(await load(...))` | make the binding pick the outermost `set` instead of the nearest: `load-var-*` cases fail |
| A2 | `split-list` matches: two files, sink.conf included by main.conf:18 and :23 (0-based), the five variable rows of the briefing's §3 (1) table (`$leds_host` written: reaches nothing, overridden at main.conf:20 by `handed leds_host`) | drop the handed value from the candidates: the override row disappears |
| A3 | kind (2): `split-kind2`; save hands over only `main.conf`, its line 3 `set $pixels 2400;`, every other byte equal; render shows both `max_count` at `2400` with `written` main.conf:3:12 | make `IVariable.setValues` edit the reference instead of the set line: sink.conf is handed over |
| A4 | kind (3): `split-kind3`; save hands over only `sink.conf` with `max_count 2400;`; `$pixels` `reaches()` is empty; both sinks render `2400` with `written` at sink.conf:5:14 and no resolutions | keep the old reference handle attached in the reconcile: `detached` case fails, and `reaches()` keeps a row |
| A5 | the rendered value's `resolutions` follow D7 (`chain-step`) and `values` carry both of `$ports` (`ports-two-values`) | reverse the order: `chain-step` fails |
| A6 | a failed edit changes nothing and throws the typed error (`set-values-bad`, `handed-no-set-line`, `detached`) | splice before checking: `texts` after the failed edit is non-empty |
| A7 | save: changed files only, one writer call, `source` updated on resolve only, `[]` and no call when nothing changed (`save-twice`; a unit test with a rejecting writer: `SaveError`, `text !== source` still) | update `source` before awaiting the writer: the rejecting-writer test fails |
| A8 | the lookup rule has one home: no `lookup` or scope class outside `ts/src/written/bind.ts` (a unit test greps `ts/src/load/` for `class Scope`/`lookup(`) | copy `Scope` back into render.ts: the test fails |
| A9 | comment ownership (`comment-owned`) and handle identity (`===` across an edit elsewhere in the file, unit test) | make `remove()` leave the comment line: `comment-owned` fails |
| A10 | `tracer.test.ts`: fixtures/rasl/split through `memorySource` of the fixture files and a recording writer runs design.md §14's flow in one test | — (it is A2-A4 through the public API, not the runner; a probe of A3 breaks it too) |
| A11 | every PR 3 test still passes after the mechanical move; `rasl.test.ts` uses `graph.edges()` (2 edges) | — (green suite) |

Not in S1: section 3's S2 cases run (skipped by `needs`), `read(graph)` on the processor, the key move, `written`
on rendered directives.

---

## S2: the rest of the TypeScript surface

**Owns:** `ts/` only. Runs beside S3 in the same checkout; keep to `ts/`. Checks: `corepack pnpm -C ts test`,
`typecheck`, `lint`. Commit message: `feat(ts): every statement edit, read, setHanded, and the key at diff`.

**What it delivers.** Every member of `written/model.ts` S1 left (2.3-2.4 edits for every statement kind; blocks;
`rename`s; `IDocument.replaceWithText`; `setHanded`; `IUseLine.snippet`/`snippets()`; `unread()` after an include
edit); `IProcessor.read`; `ReadError`; the fs writer's staging; `written` on rendered directives and unreadables;
the key moved from the processor to `diff`'s call (D1, D4-D6); every caller and test on the new shapes; the TS runner
running every shared case (no skips).

**Frozen signatures: changes to existing code.**

```ts
// ts/src/load/processor.ts
export interface IProcessorOptions {
  readonly source: IDocumentSource;
  readonly extensions?: readonly IExtension[];
  // `key` removed (D4)
}
/** How directives are named among same-name siblings; without a key rule, by position. */
export interface IKeyOptions {
  readonly key?: KeyRule;
}
export interface IProcessor {
  /** @throws (rejects) ReadError (E3004 at the root path) when the source cannot resolve or read the root; TypeError */
  load(path: string, options?: ILoadOptions): Promise<IDocumentGraph>;
  /**
   * Resolve and read what `graph.unread()` names, repeating until nothing new is named; keeps every text and every
   * kept rejection (D12). Returns the resolvedPaths read, in read order. @throws TypeError for another processor's graph
   */
  read(graph: IDocumentGraph): Promise<readonly string[]>;
  render(graph: IDocumentGraph): IRendered;
  /**
   * What differs between two renders of this processor's graphs, by address under `options.key` (D4): removed and
   * unknown in `before`'s walk order, then added and changed in `after`'s (unchanged rules).
   * @throws TypeError when either render came from another processor; whatever the key rule throws
   */
  diff(before: IRendered, after: IRendered, options?: IKeyOptions): readonly Change[];
}
export interface IRendered {
  // ...S1's members, plus:
  /**
   * Every directive's address under `options.key`, in walk order (the map's order). The key rule is called once per
   * directive, parents before children; what it throws propagates. The one home of the address rule; `diff` uses it.
   */
  addresses(options?: IKeyOptions): ReadonlyMap<IDirective, IAddress>;
}

// ts/src/load/directive.ts
export interface IDirective {
  // `address` removed (D4: rendered.addresses(), and each Change's address); `node` removed
  /** The written directive this is a copy of (closes kno-uji). */
  readonly written: IWrittenDirective;
  // name, args, body, unreadable, parent, origin, walk, closest, error: unchanged
}
export interface IUnreadable {
  readonly kind: UnreadableKind;
  readonly origin: IDirectiveOrigin;
  /** The statement that could not be read here (replaces `node`). */
  readonly written: Statement;
}
/** Called by `addresses()` and `diff` with the rendered directive (D5). `IKeyInput` is removed. */
export type KeyRule = (directive: IDirective) => string | undefined;

// ts/src/node.ts
/**
 * One batch on disk (D18): reads each target first and rejects, writing nothing, when one no longer holds its
 * `source` (a lost update; the Error names the paths); else writes each text to a temporary file beside its target
 * (`<name>.<random>.tmp`), then renames each over its target. A failure while staging removes the temporaries and
 * rejects with nothing replaced; a failure while renaming can leave earlier files replaced (stated cost).
 */
export function createFsWriter(): IDocumentWriter;
```

**Errors:** every code of 2.3; `ReadError` from `load`; `RangeError` for `insertStatements` out of range;
`TypeError` from `read`/`render`/`diff` across processors; `NoSetLineError` from `IVariable.rename` on a handed value.

**Acceptance criteria.**

| # | Criterion | Probe |
|---|---|---|
| B1 | every `conformance/written/` case passes in TS, none skipped (the runner's feature set is complete) | leave `blocks` out of the runner's set: the test that asserts no skip fails |
| B2 | `conformance/load/` still byte for byte with the key passed to `addresses()`/`diff` | count occurrences across the whole tree instead of per container: `load-diff-moved-node` fails |
| B3 | an include line added by `addStatements` leaves `unread()` non-empty and `render` without its file; `read(graph)` reads it once, keeps every other unsaved text, and `render` then splices it (unit test with a counting source) | make `read` re-read every file: the count assertion fails |
| B4 | `IDocument.replaceWithText` keeps `source`, detaches old handles, and `save` writes the restored text only when it differs (`document-replace-detaches`) | update `source` too: `texts` is empty where the case expects the file |
| B5 | `setHanded` changes resolutions and render without a reload (`set-handed`); a bad text throws BadTextError | reload instead of re-binding: the case's `list` shows the read count rise (counting source unit test) |
| B6 | `rename` refuses a kind change (`rename-kind-refused`) and `IVariable.rename` reports E5002 (`rename-variable-e5002`) | allow `rename("set")`: the case fails |
| B7 | insert indentation and empty blocks follow 2.4 (`insert-indent`, `insert-empty-block`) | use a fixed two-space indent: `insert-indent` fails |
| B8 | the fs writer refuses a lost update writing nothing, and stages then renames (node.test.ts on a temp directory under the test's own tmp dir) | write before comparing: the lost-update test finds the file changed |
| B9 | `IDirective.written === ` the statement for both copies of a line read twice; `node` and `address` are gone (typecheck) and every caller uses `addresses()` | return a new statement object per copy: the `===` assertion fails |
| B10 | `load` of an unreadable root rejects with `ReadError` (instanceof `DiagnosticError` too, E3004) | throw a plain DiagnosticError: the instanceof test fails |

---

## S3: Python, the same model

**Owns:** `py/` only. Runs beside S2 in the same checkout; keep to `py/`. Reads S1's landed TS (`ts/src/written/`,
`ts/src/load/render.ts`) as its reference implementation, and section 2 as the rules. Checks: `cd py && uv run
pytest && uv run ruff check && uv run ruff format --check && uv run mypy`. Commit message: `feat(py): the low-level
layer: config as written, editable, saved back`.

**What it delivers.** The whole layer in Python at its final shape (S1 + S2 together): `knobly/written/`
filled, the binding ported, `render` on top, the key at `diff`, save and `fs_writer`, every caller and test moved,
and the runners for `conformance/written/` (every case) and `conformance/load/`.

**Idioms (design.md §6):** snake_case, synchronous, read-only properties, `WrittenBlock` a `Sequence`, kinds as
classes (`match` narrows), handles identical by `is`, errors `EditError(ValueError)`.

**Files.**

| Action | Path | What |
|---|---|---|
| fill | `py/src/knobly/written/model.py`, `errors.py`, `save.py`, `__init__.py` | as committed |
| new | `py/src/knobly/written/_bind.py`, `_document.py`, `_graph.py`, `_read.py` | ports of S1's TS modules |
| new | `py/src/knobly/_render.py` | replaces `_expand.py` (deleted) |
| delete | `py/src/knobly/graph.py`, `py/src/knobly/_expand.py` | replaced |
| change | `py/src/knobly/processor.py`, `directives.py`, `report.py`, `files.py`, `include.py`, `__init__.py` | signatures below |
| change/new | `py/tests/*` | callers moved; `test_written.py`, `test_written_conformance.py`, `test_tracer.py` |

**Frozen signatures: changes to existing code** (new code: the committed `knobly/written/`).

```python
# knobly/processor.py
@final
class Processor:
    def __init__(self, *, source: DocumentSource, extensions: Sequence[Extension] = ()) -> None: ...  # `key` removed
    def load(self, path: str, *, variables: Mapping[str, str] | None = None) -> DocumentGraph: ...    # ReadError, ValueError
    def read(self, graph: DocumentGraph, /) -> list[str]: ...        # ValueError: another processor's graph
    def render(self, graph: DocumentGraph, /) -> Rendered: ...       # ValueError: another processor's graph
    def diff(self, before: Rendered, after: Rendered, /, *, key: KeyRule | None = None) -> list[Change]: ...

@final
class Rendered:                       # `Loaded`, renamed; body, unreadable, origin, diagnostics, graph, error: unchanged
    def addresses(self, *, key: KeyRule | None = None) -> Mapping[Directive, Address]: ...

# knobly/directives.py
KeyRule: TypeAlias = Callable[["Directive"], str | None]   # KeyInput removed
class Directive:                      # `address` and `node` removed
    @property
    def written(self) -> WrittenDirective: ...
class Unreadable:                     # `node` replaced
    written: Statement
class Argument:
    @property
    def written(self) -> WrittenValue | None: ...
    @property
    def resolutions(self) -> tuple[ReferenceResolution, ...]: ...    # D7 order
def walk(node: Rendered | Directive, *, descend: Callable[[Directive], bool] | None = None) -> Iterator[Directive]: ...

# knobly/report.py
def format_diagnostic(diagnostic: LocatedDiagnostic, graph: DocumentGraph | None = None) -> str: ...  # current text

# knobly/files.py
def fs_writer() -> DocumentWriter: ...   # as committed: lost-update refusal, stage then rename (S2's TS rule)

# knobly/__init__.py exports: add everything in knobly.written's __all__; Rendered; remove Loaded,
# KeyInput, DocumentNode and graph.py's DocumentGraph/DocumentEdge.
```

`Processor.diff` keeps PR 3's check that both renders came from this processor (ValueError, as today).

**Acceptance criteria.**

| # | Criterion | Probe |
|---|---|---|
| C1 | every `conformance/written/` case passes in Python, none skipped | skip `handed`: the no-skip assertion fails |
| C2 | every `conformance/load/` case byte for byte, key passed to `addresses()`/`diff` | let a file's `set` win over its include block's: `load-include-block-wins` fails |
| C3 | `test_tracer.py`: design.md §14's flow on fixtures/rasl/split with `memory_source` and a recording writer, written as design.md §1's Python (`read.winner.set_values("2400")`, `read.reference.replace_with_text("2400")`) | make `save` hand over every document: the "only main.conf" assertion fails |
| C4 | Python idioms hold: `match` narrows every `Statement` and `WrittenValue` kind (a test with `assert_never`), `block[0] is block[0]`, `len(block)`, `in` | return new handle objects per access: the `is` test fails |
| C5 | `fs_writer` refuses a lost update writing nothing, then stages and renames (test on `tmp_path`) | write before comparing: the test finds the file changed |
| C6 | mypy strict and ruff pass with no new ignores | — (gate) |
| C7 | the lookup rule has one home: no scope lookup outside `knobly/written/_bind.py` (grep test, as A8) | copy `Scope` into `_render.py`: the test fails |

---

## S4: docs

**Owns:** `docs/`, `README.md`, `design/RECORD.md`, `ts/README.md`, `py/README.md`. After S2 and S3 land. No
checks beyond reading; links checked by hand. Commit message: `docs: the low-level layer reference and the rendered
tree page`.

| Page | What |
|---|---|
| `docs/low-level-api.md` | **new content** (D22): the low level, user code first (design.md §1 in both languages, from the landed tests), documents, statements, values, copies, variables and resolutions, edits and their errors (2.3, 2.4), handles (2.1), comment ownership (2.2), save and writers, `quote`, what is derived and what is stored (2.8), how the two languages differ |
| `docs/rendered-tree.md` | `git mv` of the old `docs/low-level-api.md`, then updated: `render(await load(...))`, `IRendered`, `written` and `resolutions`, the key at `diff`/`addresses()`, `IDirective.written` |
| `README.md`, `ts/README.md`, `py/README.md` | the three layers in two sentences each; entry points; links to both pages |
| `design/RECORD.md` | round 12's owner answers (quoted with dates from requirements.md), the current choices (`decisions.md` by id), the bead outline unchanged |

Acceptance: every code sample in both pages is copied from a test that runs (name the test beside it); no sample
uses a removed name (`ILoaded`, `Loaded`, `node`, `address` on a directive, `IKeyInput`, `KeyInput`, the processor's
`key`). Probe: grep the docs for each removed name: zero hits.

---

## Test architecture

| Module | Tested through | Isolation |
|---|---|---|
| document (`written/document.ts`) | `parse`-only fixtures; edits on one document | no graph, no source: a document is a text plus its handles |
| binding (`written/bind.ts`) | a graph built over `memorySource`; `list` outputs | pure; no I/O; one derivation per input |
| render (`load/render.ts`) | `conformance/load/` (the contract it must keep) and the rendered values' new members | over a binding; no source calls (a counting source proves render reads nothing) |
| save, writers | a recording writer; the fs writer on a temp directory | the core never touches the disk |
| processor | the tracer and both conformance runners | end to end over `memorySource` |

Conformance boundaries: `conformance/load/` (render, both languages, unchanged bytes) and `conformance/written/`
(the low level, both languages). A runner that disagrees with an expected file has found a bug in itself or in the
rules (section 2), never a reason to rewrite the file; a rule wrong in section 2 is an erratum.

## Maintenance risks

- **Handle reconcile** (2.1) is the subtle part: an off-by-one in offset shifting keeps a handle pointing at the
  wrong tokens. Guarded by the `detached` and identity tests and by re-reading every handle's `text` after each edit
  in the document tests.
- **Two walks become one.** The binding and render both used to be the expander; the binding now owns the walk and
  render only builds. A new language rule must go into `bind.ts` (A8/C7 grep tests keep the lookup there).
- **Python mirrors TS by hand.** The shared cases are the only guard; S1 writes them broad so S3 cannot drift.
- **Re-binding cost.** Every edit invalidates the whole derivation; fine for config sizes (100k directive cap), a
  risk only for an editor re-rendering on each keystroke over huge graphs (deferred: incremental binding).
- **The written layer imports `load/tree.ts`'s `Argument`** (D23): the dependency points up a layer for the one
  class extension values need. If a third consumer appears, move `Argument` to a shared values module.

## Departures from the existing code (cost)

| Today (cb08803) | After | Cost |
|---|---|---|
| `Expander` does lookup and building in one walk | `bind()` walks and decides; `render` builds | large, both languages (S1, S3) |
| `load` returns `ILoaded` | `load` → graph; `render` → `IRendered` | every caller (S1 mechanical, S3) |
| the key on the processor, addresses on every directive | the key at `diff`/`addresses()`; no `address` on a directive | medium; rasl's key rule keeps its body (D5) |
| `IDirective.node`, `IUnreadable.node` | `written` | small |
| `save` one write per file, TS only | one batch, `source` updated, both languages; the fs writer stages | small |
| graph edges stored at load | derived; the read ledger stored | medium |
