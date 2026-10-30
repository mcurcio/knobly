# Conformance: the shared driver and the adapter protocol

Status: canonical, like the rest of `spec/` (owner, 2026-10-27: "Within villanelle I want the spec to win over a
reference language"). Written in milestone 3 (bead vil-j80) from the round 13 review's root cause 5
([review.md](../.claude/design/consumer-api/round13/review.md#root-cause-5-no-neutral-spec-and-nothing-generated-from-one-source):
"a binding writes one small adapter (load files, find a target, apply a neutral op, dump); one shared driver runs
every case; the "rasl" key rule becomes data"). Everything on this page beyond that sentence is a design choice of the
milestone, revisable, not the owner's words. The exact per-binding work is on the milestone's frozen page,
`.claude/design/consumer-api/round14/frozen-m3.md`.

A binding proves it meets the spec by running **one shared driver** (`conformance/driver/run.py`) against **one small
adapter** of its own. The adapter is a program in the binding's language that answers requests about the binding's
public API on its standard input and output. The driver holds everything else: which corpora exist, every case, how a
case's target is found, how positions convert to the corpus's units, how each expected file is printed, and the one
comparison with `conformance/**/expected`. No binding has a conformance runner of its own.

## 1. Prior art, and what is bespoke

| Piece | Follows | Why |
|---|---|---|
| One harness, a thin adapter per implementation | test262's harness with its host adapters (`eshost`): one test suite runs against every JavaScript engine through a small per-host shim | the suite and its rules live once; an implementation adds only the shim |
| A process that answers requests on stdin and stdout | the Language Server Protocol's base protocol (stdio transport, request ids, one response per request) | every language can read and write its standard streams; the driver needs nothing installed in the binding's toolchain |
| The binding dumps a neutral tree; the harness compares | tree-sitter's corpus runner, which compares a parser's S-expression with the expected one | the comparison and its byte rules have one home |
| Results as TAP | the Test Anything Protocol, version 14 (`ok` / `not ok` lines, `# SKIP`, YAML diagnostics) | any CI log or TAP consumer reads it |

Bespoke, with the reason:

- **Newline-delimited JSON, not LSP's `Content-Length` headers.** One message is one line: JSON escapes every line
  break inside a string, so a line is always a whole message, and every language's standard library reads lines.
- **Three response shapes (`ok`, `thrown`, `fault`), not JSON-RPC's `result` and `error`.** An error the binding
  raises on purpose (a `bad text error`, a reader's `diagnostic error`) is a result a case checks; an adapter that
  failed is not. JSON-RPC's one error object would mix the two.
- **The adapter finds no target.** The review's sentence gave the adapter "find a target"; this page moves it into
  the driver. The adapter dumps what the binding holds, with an id on each object, and the driver finds the target
  in the dump and names it by id. So the target rules (a statement by its name token, a value by its start) and the
  position conversion they need are written once, and an adapter is a mechanical dump.

## 2. Conformance levels

A binding claims one level in its `hello`. It holds the level when every case at that level and below passes.

| Level | What | Cases |
|---|---|---|
| L0 | syntax (spec 3) | the syntax corpus |
| L1 | the low level: load, edit, save (spec 4, 6) | the written corpus, but its cases that render or use the include extension |
| L2 | the rendered tree: render, readers, addresses, diff (spec 7, 2.9, [contract.md](contract.md)) | the load, rendered and contract corpora, and written cases whose steps render (`["render"]`, a `rendered` target) |
| L3 | extensions: include (spec 5) | every case that uses the include extension (`extensions` or `needs` holds `include`) |
| L4 | adapters: the memory writer and the file and fetch adapters (spec 4.3, contract 5) | none yet: each binding tests its adapters itself (section 7) |

The levels are cumulative: L2 means L0, L1 and L2. The high level (spec 8) is outside the levels.

## 3. Transport

- The driver starts the adapter as a child process (its command is the driver's argument) and keeps it for the whole
  run. It restarts it after a fault (below).
- Each request is one line of JSON on the adapter's standard input: an object with `id` (an integer, rising), `op`
  (the message name) and the message's parameters as further members. The driver writes ASCII only: every
  character above U+007F, and a lone surrogate, as a `\u` escape.
- Each response is one line of JSON on the adapter's standard output, UTF-8, answering the request with the same
  `id`, before the next request is sent. A lone surrogate in a string MUST be written as a `\u` escape (JavaScript's
  `JSON.stringify` does; Python's `json.dumps` does by default), so a response stays valid UTF-8 even from a binding
  that holds the surrogate as WTF-8 bytes. The adapter writes nothing else to standard output; its standard error
  passes through to the driver's.
- **The lone-surrogate trap** (three syntax cases, `surrogate-*` in `extra.json`). Many standard JSON libraries
  replace a lone surrogate with U+FFFD in both directions: Go's `encoding/json` decodes the escape `\ud800` to
  U+FFFD, and encodes the WTF-8 bytes `ED A0 80` as three U+FFFD characters. The adapter must decode `\ud800` into
  the binding's own form of it (for Go, its WTF-8 bytes; spec 2.1) and encode that form back as `\ud800`: a string
  codec of its own for these escapes (about 100 lines of Go), or a library that keeps them.
- A response is one of:
  - `{"id", "ok": value}`: the request's result;
  - `{"id", "thrown": error}`: the binding raised the class of one of spec 2.8's error groups, of either sort
    (milestone 4: a program bug too, such as a `misuse error`, since each group has its own class). `error` is
    `{"group": spec name, "code"?: text, "diagnostics"?: [syntax diagnostic, ...], "paths"?: [text, ...]}`: the error
    group's spec name (`bad text error`, `detached error`, `misuse error`, `lost update error`, ...: `error groups`
    in [schema/api.json](schema/api.json)), the most specific group the class belongs to; `code` for a `diagnostic
    error` (its diagnostic's code); `diagnostics` for a `bad text error`, positions in the text the edit was given;
    `paths` for a `read error`, `save error` and `lost update error`;
  - `{"id", "fault": text}`: anything else failed (a native error, an unknown op). The case fails.
- The adapter exits when its standard input closes. If it exits early, or writes a line that is not a response to
  the request, the case fails with a fault and the driver starts a new adapter for the next case.

## 4. Messages

Every object the adapter dumps that the binding holds (a statement, value, variable, place, step, diagnostic,
directive, expanded value, block, document, graph, render) carries an `id`: text the adapter chooses, unique for the life
of the process. A later request names an object by its id. The adapter keeps every dumped object alive until it
exits; the same binding object may get several ids.

A **position** is `[line, column, offset]`, in the binding's own unit (the `unit` of its `hello`; contract 1). The
driver converts every position to UTF-16 units with the text it counts in: the document's current text, or the text
an edit was given. The adapter never converts.

Sections 4.1 and 4.2 are generated from [schema/protocol.json](schema/protocol.json), the one home of the messages
(`python3 tools/gen-api.py docs`; `tools/check.sh` fails when they are stale). Each adapter's message types are
generated from the same file.

### 4.1 Requests

<!-- generated: adapter requests (tools/gen-api.py docs) -->
| `op` | Parameters | `ok` result | Level |
|---|---|---|---|
| `hello` | `protocol`: 1 | `{"protocol": 1, "binding": name, "unit": "utf-16" \| "code point" \| "byte", "level": 0 to 4}` | all |
| `parse` | `text` | a **syntax** dump of `parse (text)` | L0 |
| `load` | `files` (path to text), `root`, `extensions` (`[]` or `["include"]`), `overrides`? (name to text) | `{"graph": id}`: a processor with a `memory source` over `files` and the extensions named, then `load (root, overrides)` | L1 |
| `graph` | `graph` | a **graph** dump | L1 |
| `edit` | `target` (an id), `member` (a spec member name: `set` (on a statement, a variable or, milestone 5, a written value), `replace with text`, `remove`, `rename`, `insert statements`, `add statements`, `insert before`, `insert after`, `set override`), `args` (in the member's parameter order; `null` means the argument is absent) | `{"handles": [{"id", "text"}, ...]}` when the member returns handles, else `{}` | L1 |
| `save` | `graph`, `disk`? (path to text) | without `disk`: `{"batches": [[[path, text], ...], ...]}`, what a recording writer got, each `write` call one batch, during this one `save (writer)`. With `disk`: `save (writer)` with a `memory writer` over a new map holding `disk` (so a file whose text there differs from its saved text is a lost update), then `{"files": [[path, text], ...]}`, the map after, sorted by path | L1 |
| `quote` | `text` | `quote (text)` | L1 |
| `render` | `graph` (any dumped object's id), `key`? (key rules, section 4.3) | a **render** dump of `render (graph)`, its addresses under the key rule; for an id that is not a graph, the binding's `render` is called with that object and raises the `argument type error` (milestone 5, spec 7.0) | L2 |
| `diff` | `before`, `after` (render ids), `key`? | `[{"kind", "address": address}, ...]`: `before`'s `diff (after, key?)`, in its order | L2 |
| `read` | `value` (an expanded value's id), `reader` (`word`, `string`, `number`, `integer`, `boolean`, `list`, `slice`; milestone 5 deleted `plain`) | the reader's **result** (section 4.4) | L2 |
| `print` | `target` (an id) | the object's `people form` (contract 2): the language's own to-text conversion | L2 |
| `format` | `diagnostic` (a located diagnostic's id), `graph`? | `format diagnostic (diagnostic, graph?)` | L2 |
| `cut` | `text`, `start`, `end` (native offsets) | `text` cut at `start` and `end` with the language's own string slicing (the check that the binding's unit is its language's, contract 1) | L2 |
<!-- end generated -->

Every text the driver sends as an edit's `text`, an override's text or a `load` override is JSON text; the adapter
passes it on as `config text` through its binding's own `text (raw)` (spec 6.9, milestone 5), never through a cast, so
the adapter type-checks against the public API like any program.

A member, reader or op name is a spec name (lowercase words); the adapter spells it in its binding's casing
(binding guide rule 1: `replaceWithText`, `replace_with_text`). An error group is sent back the same way, as its
spec name.

### 4.2 Dumps

The shapes below are exact: members in any order, no other members. `null` stands for absent. The driver checks
the **syntax** dump and its **syntax diagnostic**s exactly: their members, and every position's line and column
against its offset in the input (`conformance/driver/syntax.py`). The other shapes it checks only as far as it reads
them (section 7), so an extra or wrong member there is not yet caught: build to the shape, not to the driver.

<!-- generated: adapter dumps (tools/gen-api.py docs) -->
| Shape | Members |
|---|---|
| position | `[integer, integer, integer]` ([line, column, offset], in the binding's own unit) |
| place | `{"id", "path": text, "start": position, "end": position}` (a place (spec 2.2)) |
| override | `{"id", "override": text}` (an origin's place for a value from an override) |
| step | `{"id", "kind": text, "name": text, "place": place}` |
| origin | `{"place": place \| override, "via": [step, ...]}` |
| syntax diagnostic | `{"id", "code": text, "message": text, "start": position, "end": position}` |
| located diagnostic | `{"id", "code": text, "message": text, "place": place \| override, "via": [step, ...]}` |
| token | `[text, text, position, position]` ([kind, text, start, end]) |
| node | `[text, integer, integer, [node, ...]]` ([kind, start, end, children]: token indices, half-open) |
| syntax | `{"tokens": [token, ...], "root": node, "diagnostics": [syntax diagnostic, ...]}` |
| variable reference | `{"id", "name": text, "kind": text, "place": place \| null}` (place null for an override variable) |
| reference place | `{"id", "place": place}` |
| resolution | `{"reference": reference place, "via": [step, ...], "winner": variable reference \| null, "shadowed": [variable reference, ...]}` (a reference resolution; via is its copy's) |
| written value | `{"id", "kind": text, "place": place, "text": text}`; by `kind`: `list` `{"items": [written value, ...]}`; `slice` `{"name": written value, "start": written value \| null, "end": written value \| null}`; `index` `{"name": written value, "index": written value}`; `reference` `{"declaration": variable reference \| null, "resolutions": [resolution, ...]}` (a slice's or index's name is a word or a reference (milestone 5)) |
| statement | `{"id", "kind": text, "place": place, "text": text}`; by `kind`: `directive` `{"values": [written value, ...], "block": block \| null}`; `extension` `{"values": [written value, ...], "block": block \| null}`; `set` `{"values": [written value, ...]}`; `use` `{"values": [written value, ...]}`; `snippet` `{"block": block \| null}` |
| block | `{"id", "statements": [statement, ...]}` |
| copy | `{"place": place, "via": [step, ...]}` (place is the copy's statement's place) |
| document | `{"id", "path": text, "text": text, "savedText": text, "syntax": syntax, "block": block, "includedBy": [copy, ...]}` (includedBy: the copies of included by ()) |
| edge | `{"copy": copy, "specs": [text, ...], "targets": [text, ...]}` |
| graph variable | `{"id", "name": text, "kind": text, "place": place \| null, "wins": [resolution, ...], "shadowedAt": [resolution, ...]}` (a variable reference with its wins and shadowed at) |
| graph | `{"id", "documents": [document, ...], "edges": [edge, ...], "variables": [graph variable, ...], "diagnostics": [located diagnostic, ...]}` (each list in the graph's own order) |
| address | `{"text": text, "people": text}` (an address's text and its people form (spec 7.4)) |
| unreadable | `{"reason": text, "origin": origin}` (an unreadable expansion) |
| expanded value | `{"id", "kind": text, "text": text, "origin": origin, "definition": place \| null, "chain": [resolution, ...]}` (definition: the place of the value's definition) |
| directive | `{"id", "name": text, "address": address, "origin": origin, "values": [expanded value, ...], "block": [directive, ...] \| null, "unreadable": [unreadable, ...]}` |
| render | `{"id", "block": [directive, ...], "unreadable": [unreadable, ...], "diagnostics": [located diagnostic, ...]}` |
| change | `{"kind": text, "address": address}` |
| handle | `{"id", "text": text}` |
| key rule | `{"directive": text, "parent"?: text \| null, "key": ["value", integer] \| ["join", text]}` (one rule of a key rule as data (spec/conformance.md 4.3)) |
| reader result | exactly one of `{"text": text}`, `{"boolean": boolean}`, `{"number": number \| "-0"}`, `{"slice": [text, integer \| null, integer \| null]}`, `{"index": [text, integer]}`, `{"value": text}`, `{"list": [reader result, ...]}` (exactly one member: a reader's value (spec/conformance.md 4.4); negative zero is the string "-0") |
| hello result | `{"protocol": integer, "binding": text, "unit": "utf-16" \| "code point" \| "byte", "level": integer}` |
| loaded | `{"graph"}` |
| edited | `{"handles"?: [handle, ...]}` (handles only when the member returns handles) |
| saved | `{"batches"?: [[[text, text], ...], ...], "files"?: [[text, text], ...]}` (batches without disk; files with disk) |
<!-- end generated -->

A token's kind is its token name as written in [grammar/Villanelle.g4](../grammar/Villanelle.g4), in capitals
(`WORD`, `SPACE`, `BAD_CHAR`; all 21 are listed in spec 3.1). Every other kind (a node's,
a statement's, a value's, a step's), and reasons, are the generated lists' lowercase values (spec 2.10); codes are
their text (`E2001`).

### 4.3 Key rules as data

A key rule (spec 7.4) is a program's function, so a case cannot hold one. It holds the name of a rule in
`conformance/keys.json` (`"key": "rasl"`), and the driver sends that rule's data in `render` and `diff`:

```json
[{"directive": "node", "parent": "graph", "key": ["value", 1]},
 {"directive": "connect", "key": ["join", " "]},
 {"directive": "fill", "key": ["value", 0]}]
```

The adapter builds its binding's key rule from it. For a directive, the first rule whose `directive` is its name,
and whose `parent` (when given) is its parent's name, gives the key: `["value", i]` is its `i`-th value's text (0-based;
absent when it has fewer values); `["join", sep]` is every value's text joined by `sep` (empty text when it has
none). When no rule matches, the key is absent. This is the `"rasl"` rule of `conformance/load/format.md`, now one
data file every adapter reads the same way.

### 4.4 Reader results

The `read` result is the reader's value, neutral: `{"text": t}`, `{"boolean": b}`, `{"number": n}` (a JSON number;
negative zero MUST be sent as the string `"-0"`, which JSON numbers cannot always carry, so the driver can fail the
case), `{"slice": [name, start \| null, end \| null]}` (a `slice value`), `{"index": [name, index]}` (an `index
value`), `{"value": text}` (an expanded value, by its canonical text), `{"list": [result, ...]}` (the `list`
reader's items, each `{"value": text}`). The driver prints numbers by the number rule of `conformance/contract/format.md`.

## 5. The driver

```
python3 conformance/driver/run.py [--level N] [--corpus NAME]... [--case NAME]... [--cwd DIR] -- ADAPTER...
```

- `ADAPTER...` is the command that starts the adapter. `--level` runs the cases up to that level (default: the level
  the adapter claims); a case above it is reported `# SKIP`. `--corpus` and `--case` narrow the run. `--cwd` is the
  adapter's working directory.
- Python 3.9 or later, standard library only (as `tools/gen-api.py`): every CI job and the owner's Mac have it.
- Output: TAP version 14 on standard output: one `ok` or `not ok` line per case (and one per corpus for its
  integrity: unique names, one expected file per case and no stray ones), with the case's level; a failure's first
  difference in a YAML block; then a count per level, and whether the claimed level holds.
- Exit status: 0 when every case run passed; 1 when one failed; 2 when the adapter could not start or its `hello` is
  wrong.
- It is the only place that compares an output with an expected one, and the only place positions convert
  (`conformance/driver/units.py`, contract 1) and the byte rule is applied (`conformance/driver/encode.py`,
  `conformance/format.md`).

### 5.1 Corpus layout

`conformance/corpora.json` lists every corpus: its case files, its expected directory (or `null` when results are
inline), its level and its format page. The driver reads nothing else to find cases.

| Corpus | Cases | Expected | Format |
|---|---|---|---|
| `syntax` | `conformance/{cases,extra,depth,edge,tracer,variables}.json` | `conformance/expected/` | [format.md](../conformance/format.md) |
| `written` | `conformance/written/cases.json` | `conformance/written/expected/` | [written/format.md](../conformance/written/format.md) |
| `load` | `conformance/load/cases.json` | `conformance/load/expected/` | [load/format.md](../conformance/load/format.md) |
| `rendered` | `conformance/rendered/cases.json` | `conformance/rendered/expected/` | [rendered/format.md](../conformance/rendered/format.md) |
| `contract` | `conformance/contract/cases.json` | inline (`expect`) | [contract/format.md](../conformance/contract/format.md) |

`conformance/keys.json` holds the key rules (section 4.3). `fixtures/` holds the files a `fixture` case reads; the
driver reads them and sends their text in `load`.

A new corpus is a manifest entry, its case files, its format page and its projection in the driver
(`conformance/driver/`, one module per format). A new case is a line in a case file and, where the corpus has
expected files, its file, derived by hand from the spec: never generated by a binding.

## 6. What a binding writes

One adapter, in its own language, through its public API only (`spec/binding-guide.md` section 5):

1. Read requests line by line; answer each with one line (section 3).
2. Keep a list of the objects it has dumped; an id is an index into it.
3. Dump each shape of section 4.2 from the binding's objects, positions as the binding reports them, typed by the
   generated message shapes (milestone 6: `ts/conformance/shapes.ts`, `py/conformance/shapes.py`, from
   [schema/protocol.json](schema/protocol.json); codegen.md section 5), so the adapter's compiler checks each dump.
4. Build a key rule from its data (section 4.3).
5. Call a member by its spec name in the binding's casing, looked up in the generated `SPELLING` table (never a
   casing function of its own); turn `null` arguments into the language's absent.
6. Report every error of a spec 2.8 group as `thrown` with the group's spec name (the most specific: a `lost update
   error`, not a `save error`), looked up by the error's class name in the generated `ERROR_GROUP_OF_CLASS` table
   (never a regular expression over the name); everything else as `fault`.

TypeScript's adapter is under 200 lines and Python's under 300 (about 220 lines of code). A binding keeps its unit tests; it has no conformance
runner of its own, and CI runs the driver with its adapter after its tests.

## 7. Not covered, and costs

- L4 has no shared cases: a corpus that writes files needs a scratch directory the driver owns; until it exists, each
  binding tests its memory writer and file adapters itself (spec 9 lists what else no case covers).
- The `cut` check trusts the adapter to cut with the language's own slicing; a cut written by hand defeats it.
- A dump holds the whole graph each time a step asks for one, so a written case asks the adapter for several large
  objects. The corpora are small; the full run takes about a second per binding.
- The driver checks the protocol's shapes only as far as it reads them, except the syntax dump (4.2); a member it
  never reads is not checked. Since milestone 6 each adapter's own compiler checks its dumps against the generated shapes
  (codegen.md section 5), which catches a wrong or missing member at build time; an extra member a dynamic language
  adds at run time is still not caught.
