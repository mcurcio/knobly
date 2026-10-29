# Round 13: API shape review and the language-binding spec

Six reviewers looked at the API from different seats: a TypeScript newcomer, a Python newcomer, a
TypeScript idiom expert, a Python idiom expert, a reviewer comparing the layers, and a reviewer
comparing the two languages. Each wrote real code against the code on `feat/low-level-layer` (PR 4)
and ran it. This page is the lead reviewer's merge of their work: what holds up, what causes it, the
rules that would stop it happening again, and three questions for you.

## Where we are

Both newcomers finished the rasl task without reading the library's source:
- list the files, and the include line that pulled each one in;
- list every variable, with where it is used and overridden;
- change `$pixels`;
- make `max_count` stop using it;
- add a line in `sink.conf`;
- save, then render.

TypeScript took about 40 lines and Python about 50, and both ran first time. Everything the API can
do works. The problems are in its words and in where things live:

- **The same word means different things.** `written` means four things. A value's `written` points
  at the `set` line at the end of the chain, so the edit that looks obvious changes the wrong line.
  A reviewer ran it: `max_count` and `other` both changed.
- **The same thing has different names in each layer.** A directive's values are `values` in the
  low level and `args` in the rendered tree. Its braces are `block` in one and `body` in the other.
- **Operations live in three homes.** Some are processor methods, some are free functions and some
  are graph methods. A graph handed to the wrong processor is caught only when the program runs,
  although the API could make that mistake impossible to write.
- **Python copies the TypeScript model member by member and fixes each spot on its own.** It
  separates kinds in four different ways. It reports positions in TypeScript's units, so cutting a
  Python string at a reported position cuts in the wrong place.
- **Nothing describes the API without picking a language.** The rules sit in round-numbered design
  notes and in TypeScript's spellings. You ruled on 2026-10-27 that the spec wins over a reference
  language, but `spec/` does not exist yet. Every fixed list (error codes, kinds, limits) is copied
  by hand in each language.

None of this needs a redesign. Most fixes are renames and moves, and they are cheap now because
nothing is locked.

## Checking the findings

The reviewers rated 18 findings high. I checked each one against the code myself (file and line):

| Finding | Claim | Result |
|---|---|---|
| NT-1, C1, TS-1 | `written` has four meanings; a value's `written` is the end of the chain | **Confirmed.** `ts/src/load/directive.ts:35` (a value's `written` is "the written value at the end of its chain"), `:122` (Statement), `:144` (written directive); `ts/src/load/origin.ts:52` (`IOrigin.written: IPlace \| IHanded`). |
| NT-2, py-newcomer-2, TS-3, PY-6, C3 | Operations in three homes; checking that a graph belongs to its processor only at run time | **Confirmed.** `ts/src/load/processor.ts:170-194` (a WeakSet guard throws TypeError); `ts/src/written/save.ts:18` (`save` is a free function that reaches a private method by duck typing, `:39-43`); `py/src/villanelle/processor.py:223` (`graph._owner is not self`). This was a design choice (D27), not something you asked for. |
| NT-3, py-newcomer-1, PY-2, C4 | values/args, block/body, `.statements` in TS but a sequence in Python | **Confirmed.** `directive.ts:134,136`; `ts/src/written/model.ts:56,112,114,161`; `py/.../written/model.py` (the block is a `Sequence`). |
| py-newcomer-1 | `resolutions` is a property in one layer and a method in the other, and counts different things | **Confirmed.** `directive.ts:41` (one per step along the chain) against `model.ts:232` (`resolutions()`, one per copy). |
| py-newcomer-3 | Values passed from Python crash or split in two | **Partly kept.** The crash is real: `set_values(2400)` fails inside the library because `py/.../written/model.py:328` never checks its input type. Turning program values into text automatically goes against your pick of 2026-10-28 ("values: A, new values written as villanelle text, with quote()"). That part is question 3 below, not a defect. |
| TS-2 | `kind` fields do not narrow the type, so methods that cannot work for a kind exist anyway and throw | **Confirmed.** `model.ts:236-251` (`IVariable` has `setValues` for every kind; `NoSetLineError` exists only because of this). |
| PY-1 | Python positions count UTF-16 units, so slicing a `str` gives the wrong text | **Confirmed.** `py/src/villanelle/span.py:5-7` says so. |
| PY-3 | Python separates kinds four ways | **Confirmed.** Literal strings in `written/model.py:303…`, StrEnums in `value.py:11`, `directives.py:236` and `origin.py:31`, and classes with no `kind` at `processor.py:125`. |
| C2 | `source` means both the reader and the last-saved text | **Confirmed.** `model.ts:51` against `processor.ts:44`. |
| P1 | No language-neutral spec; the rules live in agent notes | **Confirmed.** `conformance/written/format.md:4-6` points to `.claude/design/.../round12/slices.md`; there is no `spec/` folder. |
| P2 | Every fixed list is copied by hand | **Confirmed.** `py/src/villanelle/diagnostics.py:3` says "This mirrors the TypeScript package's registry value for value". |
| P3 | The two languages disagree on `-0` and on a lone carriage return, and no shared test catches it | **Confirmed at the code level** (Python reads it with `int(word)` at `_values.py:23`). The reviewer's run showed both differences. I did not run it again. |

**None of the high findings was dropped.** I changed two of them:
- py-newcomer-3 is split as the table shows.
- In TS-3, C3 and NT-2, I reject the reviewers' shared proposal of `graph.render()`. It would make
  the low level depend on the rendered tree above it. Root cause 2 explains why, and question 1
  asks you to decide.

Where reviewers proposed opposite fixes, I chose one and give the reason inline. The cases were:
`body` or `block`; `kind` on every Python class or on none; constant objects or plain strings for
kinds; and which error class a detached handle raises. Every verdict, including the medium and low
findings, is in `findings.json`.

---

## Root cause 1: no shared glossary, so each layer named things on its own

The reviewers found these clashes:
- `written` has 4 meanings;
- `source` has 2;
- `body` has 3;
- `overridden` is a method on a variable but a list of other variables on a resolution;
- `resolutions` counts copies in one layer and chain steps in the other;
- handed-in values are called `variables` going in and `handed` coming out;
- a location is called `place`, `origin.written`, `at` or `span`;
- `diagnostics` is a method on the graph and a property on the rendered tree;
- `kind` is the type everywhere except `Unreadable`, where it holds the reason.

**Rule that makes the class impossible:** `spec/glossary.md` gives each concept one word and each
word one meaning, the same in every layer and language. A test checks every public name in both
bindings against that list (see root cause 5), so a second meaning fails the build instead of
waiting for a reviewer to notice.

**Rule for properties and methods:** a fact the object holds, or can work out cheaply on its own,
is a property. Anything worked out across the whole graph, or that can fail, or that takes
arguments, is a method. This holds in every layer. So `diagnostics` becomes the same kind of member
on the graph and on the render, and readers that can fail (`integer()`) stay methods.

The glossary I propose (only the words that change or clash):

| Concept | One word | Replaces |
|---|---|---|
| a line's values | `values` | `args` (rendered directive, `ExtensionUse`) |
| the statements inside `{ }`, and a file's top level | `block` | `body` (rendered, `Document`, `Rendered`) |
| the low-level handle behind a rendered thing, on **the same line** | `written` | (a value's `written` used to be the end of the chain) |
| the value at the end of a variable chain | `definition` | the old value `written` |
| a file and position | `place` | `origin.written`, `Step.at`, `LocatedDiagnostic.at` |
| how text got here | `via` | (unchanged) |
| the reader port | `source` | (kept) |
| the text as last read or saved | `savedText` / `saved_text` | `Document.source`, `FileWrite.source` |
| in a resolution: the one that wins / the others visible | `winner` / `shadowed` | `overridden` (on a resolution) |
| a variable's resolutions where it wins / loses | `wins()` / `shadowedAt()` | `reaches()` / `overridden()` |
| the rendered list of steps along a chain | `chain` | the rendered `resolutions` (so `resolutions()` only ever means one per copy) |
| why a statement could not be read | `reason` | `Unreadable.kind` |
| values the program passes in | **your choice, question 2** | `variables` (load option), `handed` (graph, kind, origin) |

Before and after, in the integration the newcomers wrote:

```ts
// BEFORE: the obvious edit lands on the wrong line
const maxCount = sink.block?.find((d) => d.name === "max_count");   // was: sink.body
const arg = maxCount.args[0];                // "args" here, "values" one layer down
arg.written.replaceWithText("150");          // rewrites `set $pixels 2284;` in main.conf,
                                             // so `other $pixels` changes too
if (graph.diagnostics.length > 0) { ... }    // compiles, and is never true (it is a method)

// AFTER: one word per concept, and `written` always means "this same line"
const arg = maxCount.values[0];
arg.written.replaceWithText("150");          // the `$pixels` on max_count's line: unbinds it
arg.definition?.replaceWithText("150");      // the `set` line, on purpose: changes every use
if (graph.diagnostics.length > 0) { ... }    // the same kind of member as rendered.diagnostics
```

```python
# BEFORE
arg = max_count.args[0]
arg.written.replace_with_text("150")    # edits the set line in main.conf
ref.resolutions[0]                      # a bound method on a written reference: a newcomer's trap

# AFTER
arg = max_count.values[0]
arg.written.replace_with_text("150")    # this line's `$pixels`
arg.definition.replace_with_text("150") # the set line
ref.resolutions()[0]                    # one per copy, in both layers
arg.chain[0]                            # the steps along the chain have their own word
```

Cost: almost every doc example changes, along with both bindings and the conformance dumps (which
use some of these names). There are no compatibility aliases, by your rule.

## Root cause 2: no rule for where an operation lives

Today, for one graph:
- `load`, `read`, `render` and `diff` are processor methods;
- `save` and `quote` are free functions;
- `setHanded`, `variables` and `diagnostics` are graph methods.

`render`, `read` and `diff` sit on the processor only so that it can refuse a graph or render made
by another processor (D27). That error exists only because of where the API put the operations.

**Rule that makes the class impossible:**
1. The processor is the factory. It holds the reader and the extensions, and `load` is its only job.
2. After that, every operation is a method on the object you hold, within that object's layer. The
   graph carries its reader and extensions, so it can do `read()` and `save(writer)` itself.
3. Going **up** a layer is a free function in the upper layer that takes the lower object:
   `render(graph)`. The low level never imports the rendered tree. This keeps your 2026-10-28
   point: "it allows consumers to build on top of any of the APIs".
4. Free functions are otherwise only pure text helpers: `quote`, `formatDiagnostic`, `parse`.
5. Nothing checks at run time which processor made something, because no operation takes the
   object back to one.

```ts
// BEFORE: three homes, and a run-time TypeError for a graph from another processor
const config = villanelle({ source: fileSource(), extensions: [include()] });
const graph = await config.load("main.conf");
await config.read(graph);
const r1 = config.render(graph);
await save(graph, fsWriter());
const changes = config.diff(r1, config.render(graph), { key });

// AFTER (recommended, question 1 option A)
import { render } from "villanelle/rendered";
const config = villanelle({ source: fileSource(), extensions: [include()] });
const graph = await config.load("main.conf");   // the processor makes graphs; that is all it does
await graph.read();                             // reads includes not yet read, using the graph's own reader
const r1 = render(graph);                       // going up a layer: the rendered tree's function
await graph.save(fileWriter());
const changes = r1.diff(render(graph), { key }); // diff compares two renders, so it lives on a render
```

```python
# BEFORE
config = vl.Processor(source=vl.file_source(), extensions=[vl.include()])
graph = config.load("main.conf")
r1 = config.render(graph)
vl.save(graph, vl.fs_writer())
changes = config.diff(r1, config.render(graph), key=key)

# AFTER
from villanelle import rendered
config = vl.Processor(source=vl.FileSource(), extensions=[vl.Include()])
graph = config.load("main.conf")
graph.read()
r1 = rendered.render(graph)
graph.save(vl.FileWriter())
changes = r1.diff(rendered.render(graph), key=key)
```

The same rule gives **one home for each check**. Today the load option `variables` and
`setHanded` check handed-in text with two separate functions (`ts/src/written/bind.ts:155`
`readHanded` and `ts/src/written/graph.ts:29` `handedValues`), and they disagree. `load` accepts
`"1;"` and `setHanded` refuses it. `load` throws a TypeError with no position, while `setHanded`
throws a `BadTextError` with located diagnostics. After the fix there is one check, both entry
points use it, it has one error type, and a conformance case covers `"1;"`.

Cost: the graph keeps a reference to its reader. The core still does no I/O of its own, because the
reader is injected. D27 is retired.

## Root cause 3: the types do not carry the kinds

TypeScript:
- `IVariable` is one interface for three kinds (a `set` line's variable, a snippet's parameter, a
  handed-in value). `setValues` and `rename` can be called on all three and throw
  `NoSetLineError` for two of them.
- A rendered value's `kind` does not narrow its type, so `items()` and `slice()` can be called on
  any value and throw.
- Include lines share the directive type.
- The docs show users writing `as ISetLine` seven times.

Python:
- Kinds are told apart in four ways (literal strings, StrEnums, classes with no kind, a kind on
  only one class).
- `match` works on the rendered tree (`__match_args__`) but raises TypeError on the low level. That
  is the "grafting several references into one API" you rejected on 2026-10-28.

**Rule that makes the class impossible:**
- Every closed set (statement kinds, value kinds, variable kinds, change kinds, place kinds) is one
  named list in the spec, with lowercase values.
- Every variant is its own type: a discriminated union in TypeScript, and in Python a class with
  `__match_args__` in the same field order in every layer.
- Every variant also carries `kind`, typed by that list. This is my call between two reviewers who
  disagreed. `kind` costs nothing, and it lets generic code (the conformance dumper, loggers)
  handle every variant with one `switch` or `match`.
- An operation exists only on the variants where it can succeed.
- Errors at run time are kept for problems in the user's text (the E4002 readers), never for
  misusing a type the checker could have caught.

```ts
// BEFORE: compiles, then throws NoSetLineError
for (const v of graph.variables("pixels")) v.setValues("2400");
const set = graph.root.body.statements[0] as ISetLine;      // an unchecked cast, taught by the docs

// AFTER: the compiler refuses the wrong call
for (const v of graph.variables("pixels")) {
  if (v.kind === "set") v.setValues("2400");   // only SetVariable has setValues
}                                              // Parameter: rename only; HandedVariable: neither
const [set] = graph.root.block.statementsOf("set", "pixels"); // typed SetLine[], no cast

// rendered values narrow too
if (a.kind === "list") for (const item of a.items) { ... }   // a property after narrowing
```

```python
# BEFORE
match stmt:
    case vl.WrittenDirective("port", [v]): ...   # TypeError: accepts 0 positional sub-patterns
if arg.kind is vl.ValueKind.WORD: ...            # an enum here, a bare string elsewhere
isinstance(change, vl.Added)                     # and no kind at all here

# AFTER: one Python model, the standard ast style, in every layer
match stmt:
    case written.Directive("port", [written.Word(text=t)]): ...
    case written.ExtensionLine(): ...            # include lines get their own class
match arg:
    case rendered.List(items=items): ...
match change:
    case rendered.Added(address=a): ...
match v:
    case written.SetVariable(): v.set_values("2400")  # Parameter and HandedVariable have no set_values
```

How kinds are spelled: TypeScript exports a named string-literal type for each list
(`StatementKind`) and drops the six constant objects (`ValueKind.List` becomes `"list"`), because a
literal narrows without an import. Python exports a `StrEnum` for each list. Both are generated
from one schema (root cause 5).

Cost: `NoSetLineError` is deleted. The variable and rendered-value types split, and the docs drop
their casts.

## Root cause 4: the contract at the edges is not written down neutrally

These are the places where a value or an error crosses from the library into a program. Each was
settled as "whatever TypeScript does", or not settled at all:

- **Positions.** Python reports UTF-16 units. `text[span.start.offset:span.end.offset]` returns
  `'080;'` for `8080` after an emoji. Lines count from 0 in places but from 1 in
  `formatDiagnostic`. There is no readable form, so every program, and the docs, writes its own
  `lineOf`.
- **Numbers.** `plain("-0")` gives `-0` in TypeScript and `0` in Python. Integers are capped at
  2^53-1 because JavaScript is. `1e400` has no rule.
- **Errors.**
  - Python has no base exception for the package.
  - `DetachedError` (raised by reading a property on a removed handle) is an `EditError`, and in
    Python a `ValueError`, so `except ValueError` around unrelated code swallows it.
  - `ReadError` is a diagnostic error but `SaveError` is not.
  - A root file that is missing is reported as an "include resolver" failure.
- **Writers.** Python has `memory_source` but no memory writer. A plain function passed as the
  writer gives "the writer raised" for a writer that never ran.

**Rule that makes the class impossible:** `spec/contract.md` states each edge in neutral terms, and
each binding maps it once:

- **Positions.** The conformance corpus uses one unit (UTF-16, as decided in D-S3-1). Each binding
  reports its own language's string unit, so cutting a string at a position works: code points in
  Python, UTF-16 in TypeScript. Each runner converts. Every located thing (place, address,
  diagnostic) prints as `path:line:col`, counting from 1, the same text `formatDiagnostic` prints.
- **Numbers.** Each rule is stated with a conformance case: `-0`, out of range, beyond 2^53.
- **Error groups.** Each binding maps these onto its own error classes:
  - problems in the config text are diagnostics and are never thrown;
  - text the caller passes in that breaks the language raises `BadTextError` with located
    diagnostics, from every entry point;
  - misuse raises the language's own errors (TypeError/ValueError, RangeError/IndexError);
  - a removed handle raises `DetachedError`, which is not an edit error (Python: under
    `ReferenceError`, the error a dead `weakref` proxy raises);
  - I/O raises `ReadError` and `SaveError` with the same fields;
  - each binding has one package base class.
- **Adapters.** Each is named after its medium and the port it fills: memory, file, fetch, then
  source or writer. Every binding ships memory and file adapters for both directions.

```ts
// BEFORE
const where = `${p.resolvedPath}:${p.span.start.line + 1}`;  // every program writes this
block.insertStatements(block.statements.indexOf(fps) + 1, "brightness 0.8;");

// AFTER
const where = String(p);                    // "sink.conf:4:5", the same as formatDiagnostic
fps.insertAfter("brightness 0.8;");         // insertBefore/insertAfter, as PostCSS has
```

```python
# BEFORE
f"{p.resolved_path}:{p.span.start.line + 1}"
text[s.start.offset:s.end.offset]           # wrong after an emoji
class Recorder:                             # every doc example uses this and never shows it
    def write(self, files): ...
try: ...
except (vl.DiagnosticError, vl.EditError, vl.SaveError, ValueError): ...

# AFTER
str(p)                                      # 'sink.conf:4:5'
text[s.start.offset:s.end.offset]           # right: Python positions count code points
graph.save(vl.MemoryWriter(files))          # updates the same dict MemorySource reads
try: ...
except vl.VillanelleError: ...
```

Cost: TypeScript and Python report different offsets for the same place when the text has
characters outside the basic plane, so a Python program talking to an editor over LSP converts.
That is how pygls (the Python LSP library) already works.

## Root cause 5: no neutral spec, and nothing generated from one source

This root cause is your request itself, and it is also why each problem above would be copied into
a third language:
- The rules live in agent notes from rounds 11 and 12.
- The conformance format docs cite those notes and use TypeScript's operation names.
- 33 error codes with their messages, about 9 kind lists, 4 limits and the reserved names are each
  typed out twice, plus a third time in the docs.
- Each binding's conformance runner is a 300-line harness of its own.
- The shared tests skip the value readers, addresses and formatting, which is where the two
  differences in P3 slipped through.

**Rule that makes the class impossible:** `spec/` is canonical (your words, 2026-10-27: "Within
villanelle I want the spec to win over a reference language"). Every fixed list is generated from
`spec/schema/`. Every binding passes the same corpora through one shared driver. Proposed contents:

```
spec/
  README.md            what a binding is, the conformance levels, how to read the rest
  glossary.md          one word per concept (root cause 1), with each concept's type in each layer
  layers/
    syntax.md          numbered rules, cited by conformance cases
    written.md         visibility, comment ownership, where edits put text, save batching, ...
    rendered.md        render, readers, addresses, diff order, "unknown"
    io.md              the source and writer ports, adapters, extensions
  contract.md          positions, numbers, error groups, printing (root cause 4)
  binding-guide.md     how to design a binding: the naming rules below, the one-model rule,
                       the required first-hour example, the deviations table
  schema/
    api.json           concepts, members (property or method, may be absent), kind lists,
                       error groups, reserved names, limits
    diagnostics.json   codes, names, messages, which layer owns each, retired numbers
tools/gen-api.sh       schema -> TS literal types and Python StrEnums, the code registry,
                       the docs' tables; generated files are not committed (as with gen.sh)
conformance/
  readers/ addresses/ format/   new corpora (-0, 1e400, 2^53+1, a lone CR, Address.text bytes)
  driver + adapter protocol     a binding writes one small adapter
                                (load files, find a target, apply a neutral op, dump);
                                one shared driver runs every case; the "rasl" key rule becomes data
```

Conformance levels a binding claims:
- **L0** syntax;
- **L1** the low level: load, edit, save;
- **L2** the rendered tree: render, readers, addresses, diff;
- **L3** extensions (include);
- **L4** adapters.

The high level (vil-xlo) stays per language and outside the levels. The spec governs only its
names and error groups.

**Codegen primitives** (what a new binding gets without hand work):
1. the kind lists and the class-per-kind or union skeletons for statements and values;
2. the diagnostic code registry and its messages;
3. plain data records (Place, Span, Step, Origin, Address, FileWrite);
4. a public-name check, which compares a binding's exports with `api.json` through that language's
   naming rule, so a name that drifts fails a test.

The algorithms (binding, edits, render) stay hand-written and are checked by the corpora.
Generating those is not worth it.

**Skill:** `.claude/skills/villanelle-binding/SKILL.md` in the villanelle repo. It covers starting
a binding (generate, write the adapter, climb the levels), the idiom checks below as a list, and
the traps found this round (UTF-16 against native units, `-0`, a lone CR, `match` on every layer).
It points to `spec/binding-guide.md` instead of repeating it, so the rules have one home.

Module layout (both bindings): one module per layer, the same short names in each, and a small top
level.

```ts
import { villanelle, quote, BadTextError } from "villanelle";
import type { Directive, Block } from "villanelle/written";    // written.Directive
import { render, type Directive as Rendered } from "villanelle/rendered";
import { fileSource, fileWriter } from "villanelle/file";
```

```python
import villanelle as vl                      # Processor, quote, errors, MemorySource, ...
from villanelle import written, rendered     # written.Directive, rendered.Directive
from villanelle.file import FileSource, FileWriter
```

This replaces Python's 81-name flat namespace. That namespace forced prefixes such as
`WrittenDirective` and `Slice` against `SliceValue`, and `from villanelle import *` replaced
`typing.List`.

---

## Naming and structure rules across languages

These go in `spec/binding-guide.md`, and the public-name check enforces them.

1. **The spec names each concept once,** as plain lowercase words (`set values`, `replace with
   text`, `document graph`). A binding changes only the casing:

   | Spec | TypeScript | Python | Go (example) |
   |---|---|---|---|
   | type `document graph` | `DocumentGraph` | `DocumentGraph` | `DocumentGraph` |
   | member `set values` | `setValues` | `set_values` | `SetValues` |
   | kind value | `"set"` | `StatementKind.SET` (value `"set"`) | `StatementKindSet` |

2. **No language-specific prefixes on type names.** TypeScript drops the `I` prefix. It came from
   rasl's style guide (`reference/rasl-config-ts/STYLE.md` 3.6), and you never asked for it in
   villanelle. Without it, the same types have the same names in both languages. Where a short name
   would collide with a built-in, the module provides the context (`written.String`), not a prefix.
3. **Factories.** Every binding uses one convention. TypeScript uses lowercase nouns with no
   `create` (`fileSource()`, `fetchSource()`, `memorySource()`, `include()`). Python uses public
   classes (`FileSource()`, `Include()`), as jinja2 does with `FileSystemLoader`. Fetch adapters
   default to the platform's `fetch`.
4. **One model per language, used in every layer** (your steer, 2026-10-28). A binding names its
   model in the guide:
   - TypeScript: discriminated unions, read-only objects, iteration through generators, options
     objects.
   - Python: the standard `ast` style, meaning a class per kind with `__match_args__`, frozen
     slotted records, generators, keyword-only options, tuples for results, and a `MutableMapping`
     where the user edits a map (handed-in values).
5. **Containers have one shape.** A block can be iterated and indexed in both layers. TypeScript:
   `for (const s of block)`, `block.at(i)`, `block.length`. Python: a `Sequence`. Both layers offer
   the same `walk({ descend })`, which is a generator in both languages; in TypeScript it returns
   an iterator that has `.find` and `.filter`, and an early exit is `break`. Both also offer
   `closest`, `directives(name?)` and `statementsOf(kind, name?)`. This replaces TypeScript's
   callback with `"skip"`/`"stop"`.
6. **Allowed differences, each listed with its reason in a deviations table:**
   - async I/O in TypeScript and sync in Python (the language's I/O habit; render and diff are
     always sync and pure);
   - an absent value is `undefined` in TypeScript and `None` in Python;
   - misuse errors map onto native classes;
   - Python readers carry an `as_` prefix only where the bare name would shadow a built-in (`as_int`,
     `as_str`, `as_bool`, `as_list`); otherwise they use the spec word (`word()`, `number()`,
     `plain()`, `slice()`);
   - positions use each language's string unit.

   Any other difference is a defect.
7. **A required first-hour example.** Each binding's docs open with the rasl task as one complete
   program that runs, with its imports, kept as a test. A binding is not done until that program
   reads naturally in its language. Today's Python examples are fragments that call `line_of`,
   `Recorder` and `node_named` without ever defining them.

---

## Questions for you

### 1. Where does `render` live?

- **A (recommended): `render(graph)`, a function in the rendered layer.** `read` and `save` become
  graph methods, and the processor only loads. The low level never depends on the layer above it,
  which keeps your point that "consumers can build on top of any of the APIs". Cost: one free
  function remains, but it is the only one and a rule explains it.
- **B: `graph.render()`.** Four reviewers proposed this, and every operation would be a method.
  Cost: the low level has to import the rendered tree, so the layers stop being separable, and a
  third-party rendering of a graph is not possible.
- **C: keep the processor methods and drop the ownership check.** Fewest changes. Cost: operations
  stay in three homes with no rule, which is the main complaint from both newcomers.

### 2. One word for the values a program passes in

Today they are `load(…, { variables })` going in and `graph.handed`, `setHanded` and kind `"handed"`
coming out, while `graph.variables()` means every variable.

- **A (recommended): `overrides`.** `load(path, { overrides })`, `graph.overrides` (an editable map
  in Python), kind `"override"`. It is plain English and matches how Helm and Terraform describe
  `--set` and `-var`. Cost: one more term to define. An override also wins over a `set` line, which
  this word says out loud.
- **B: `handed` everywhere** (`load(path, { handed })`). Fewest renames. Cost: newcomers in both
  languages needed the docs to explain the word.
- **C: `inputs`.** Neutral. Cost: it does not say that these values win over `set` lines.

### 3. Values going in: text only, or program values too?

On 2026-10-28 you picked "new values written as villanelle text, with quote()". Both newcomer
reviewers and the TypeScript idiom reviewer tripped on it. `set_values(2400)` crashed inside the
library. Passing `"my host"` became two values with no warning.

- **A (recommended): keep text only and make it impossible to misuse.** A clear TypeError for
  anything that is not a string. The parameter is named `text` in the docs. A docs callout shows
  `quote()`. Cost: callers still quote program strings themselves.
- **B: also accept program values.** `setValues([host, port])` in TypeScript,
  `set_values(host, port)` in Python: strings are always quoted, and numbers and booleans are
  written as words. Raw text stays available through `replaceWithText`. Cost: a second way to edit,
  and a conversion rule that the spec and every binding must carry. It also reverses your pick.
- **C: program values only.** Cost: text such as `name[1:3]` or a bare word could no longer be
  written in one step.

---

## What happens next if you agree

Nothing has been edited in `ts/`, `py/`, `docs/` or `conformance/`. With your answers:
1. Write `spec/`: the glossary, layer rules, contract, binding guide and schema, moving the round
   11 and 12 rules out of agent notes.
2. Write the generator and the public-name check.
3. Apply root causes 1 to 4 to both bindings in PR 4 or a follow-up.
4. Add the readers, addresses and format corpora and the shared driver.
5. Write the skill.

I would track each step as a bead under vil-e4x.

## Deferred or out of scope

- **The high level (vil-xlo).** Only its names and error groups follow the spec.
- **Async Python** (an asyncio source and load). It is still an open question in the requirements.
  I have not decided it here.
- **Fetch adapters for Python.** They are a documented gap. The spec lists them under L4 as
  optional.
- **The include extension's codes** (P9: E3001, E3004, E3005 named after include in the core list).
  The schema marks which layer owns each code. Renaming them waits for the code schema.
- **Helpers you mentioned as possible** ("disconnect" a variable, "inline" an include). They are not
  part of this review.
- **Generating the algorithms** (binding, edits, render). Rejected: the corpora check them, and
  generating them would cost more than writing them by hand.
- **Small items, as beads:**
  - a `Variable` repr that shows its name;
  - "cannot read root file" wording;
  - `isModified` on a document;
  - looking up a document by its include spec;
  - a note that a statement's text includes its block;
  - tuples instead of lists from `save`, `read` and `diff`;
  - library-only classes that users cannot construct;
  - stop exporting `ValueRef`, and rename the syntax tree's `ValueRef` so "reference" means only
    `$name`;
  - `IDirective.copy`, so a rendered directive knows which copy it is.

NOT RUN by me: the packages' test suites, lint and typecheck, and the reviewers' probes (I checked
their claims against the code; the run outputs quoted above are theirs).
