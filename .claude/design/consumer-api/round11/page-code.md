# Knobly's low-level API, in rasl's own code

**Status:** round 11 draft for the gate (kno-9vn) · **Layer:** **[ System design ]** › Module › Feature · the low level only (tokens and the directive layer); the sugar is deferred (kno-xlo)

**What you are asked:** does rasl's code below read like an API worth integrating against? Three questions, in §2, §3 and §5.

You said on 2026-10-28: "it's not clear how practical these APIs are for a real integration." So four programs were written against the stubs: rasl's reader in TypeScript and in Python, a third party's proxy with zod or pydantic, and the round-10 sugar rebuilt on top. All pass the type checkers; none has run on knobly, which has no parser for the new grammar yet (§8). What they ran into changed six things (§4).

---

## 1. rasl reads its file: TypeScript

Excerpt of `integrate-rasl-ts/src/read.ts`, lines 7-39, checked by tsc 6.0.3 strict:

```ts
export function readConfig(loaded: Loaded, types: NodeTypes): RaslConfig {
  const errors: Diagnostic[] = [...loaded.diagnostics];
  let uiPort: number | undefined;
  let graph: Directive | undefined;
  for (const top of loaded.body) {
    // Other top-level names are ignored, as both current readers do.
    if (top.name === "ui") {
      for (const d of top.body ?? []) {
        if (d.name === "port") collect(errors, () => (uiPort = need(d, 0, "port <number>").integer()));
      }
    } else if (top.name === "graph") {
      if (graph === undefined) graph = top;
      else errors.push(top.error("write one graph block", "rasl/graph-twice").diagnostic);
    }
  }
  if (graph === undefined) errors.push(fileError(loaded, "no 'graph' block found in configuration", "rasl/no-graph"));

  const nodes = new Map<string, NodeSpec>();
  for (const d of graph?.body ?? []) {
    if (d.name !== "node") continue; // as both current readers
    collect(errors, () => {
      const node = readNode(d, types, errors);
      if (nodes.has(node.id)) throw (d.args[1] ?? d).error(`node ${node.id} is defined twice`, "rasl/duplicate-node");
      nodes.set(node.id, node);
    });
  }
  for (const node of nodes.values()) {
    for (const c of node.connects) {
      if (!nodes.has(c.sourceNode)) errors.push(c.source.error(`no node named ${c.sourceNode}`, "rasl/unknown-node").diagnostic);
    }
  }
  return { uiPort, nodes, errors };
}
```

`need`, `collect` and `fileError` are rasl's own (`errors.ts`). Now `collect` ships in knobly and `loaded.error(...)` replaces line 22's hand-built `fileError` (§4). rasl never sees `$pixels`, `use` or `include`: `max_count $pixels` arrives as `2284`.

## 2. rasl reads its file: Python

Excerpt of `integrate-rasl-py/rasl_vl/reader.py`, lines 58-74 and 131-145, checked by pyright 1.1.407 strict and mypy 1.18.2 --strict. The top-level read (lines 41-57) is the same as §1's.

```python
    for d in graph.body or ():
        if d.name != "node":
            continue
        node_id = d.address.steps[-1].key or ""  # the key rule's answer: the id, even when the line is bad
        before, spec = len(errors), None
        with _collecting(errors):
            if node_id in seen:
                raise _id_arg(d).error(
                    f"node '{node_id}' is already defined at {_where(seen[node_id])}", code="rasl/duplicate-node"
                )
            seen[node_id] = d
            spec = _read_node(d, errors)
        if spec is None or len(errors) > before:
            failed.add(node_id)
        else:
            nodes[spec.id] = spec
    return RaslConfig(ui, nodes, tuple(errors), frozenset(failed), loaded)
```

```python
    match args:
        case [_, _]:
            return first, node_id, {}, head
        case [_, _, *fields] if first == "cron":  # node cron <id> <field1> [... field5]
            if len(fields) > 5:
                raise fields[5].error(f"cron node supports 1-5 fields, got {len(fields)}", code="rasl/cron")
            return first, node_id, {"schedule": [a.as_str() for a in fields]}, {**head, "schedule": tuple(fields)}
        case [_, _, model] if first in _COLOR_TYPES:
            return first, node_id, {"model": model.as_word()}, {**head, "model": (model,)}
        case [_, _, third]:
            raise third.error(f"node type '{first}' does not accept a third value", code="rasl/node-head")
        case [_, _, _, extra, *_]:
            raise extra.error(f"node takes 1-3 values, got {len(args)}", code="rasl/node-head")
        case _:
            raise d.error("write node <Type> <id>", code="rasl/node-head")
```

rasl's own `_collecting` (a class, so the checkers know the block can end early) now ships as `vl.collecting`. `validate.py` runs each node through rasl's existing pydantic models and puts each error on the line or value that caused it.

> **Question: is Python's `load` synchronous?**
>
> | | **A. Synchronous (recommended, shown)** | B. Async only, as in TypeScript | C. Both, `load` and `aload` |
> |---|---|---|---|
> | Evidence | All three Python programs call it from plain functions | | |
> | Cost | An asyncio program reading includes over a network blocks its loop, or uses a thread | Every script and test needs an event loop | Two entry points and two loader types for one question |

---

## 3. A reload

rasl names each node by its id, so it keeps its identity when lines move. Excerpt of `integrate-rasl-ts/src/source.ts`, lines 20-25 and 42-56:

```ts
export const raslKey: KeyRule = (name, args, parent) => {
  if (name === "node" && parent?.name === "graph") return args[1]?.text;
  if (name === "connect") return args.map((a) => a.text).join(" ");
  if (name === "fill") return args[0]?.text;
  return undefined;
};
```

```ts
  async load(): Promise<LoadOutcome> {
    const source = await this.readText(this.path);
    if (source === undefined) return { kind: "rejected", report: `${this.path}: config file not found` };
    const loaded = await this.vl.load({ resolvedPath: this.path, source }, { variables: this.variables });
    const config = readConfig(loaded, this.types);
    if (config.errors.length > 0) {
      return { kind: "rejected", report: config.errors.map((d) => formatDiagnostic(d, loaded.graph)).join("\n\n") };
    }
    const before = this.accepted;
    const plan = before
      ? planReload(this.vl.diff(before.loaded, loaded), before.config, config)
      : planStart(config);
    this.accepted = { loaded, config };
    return { kind: "accepted", config, plan };
  }
```

Excerpt of `integrate-rasl-ts/src/reload.ts`, lines 14-32: rasl decides what each change means.

```ts
  for (const change of changes) {
    const [top, node, inner] = change.address.steps;
    if (top?.name === "ui") uiChanged = true;
    if (top?.name !== "graph") continue;
    if (node === undefined) {
      // The whole graph block came or went.
      if (change.kind === "added") for (const id of after.nodes.keys()) start.add(id);
      if (change.kind === "removed") for (const id of before.nodes.keys()) stop.add(id);
      continue;
    }
    if (node.name !== "node" || node.key === undefined) continue;
    const id = node.key;
    if (inner === undefined) {
      if (change.kind === "added") start.add(id);
      else if (change.kind === "removed") stop.add(id);
      else restart.add(id); // its own values changed: type, model or literal data
    } else if (inner.name === "connect") rewire.add(id);
    else retune.set(id, (retune.get(id) ?? new Set()).add(inner.name));
  }
```

Editing `set $pixels 2284;` to `2400` (worked by hand):

| Change listed | Kind | rasl's plan |
|---|---|---|
| `graph › node leds › max_count` | changed | retune `leds` (`max_count`) |
| `graph › node leds › connect crossfade_rgb pixels › repeat_until` | changed | rewire `leds` |
| the `set` line | never listed | |

> **Question: who names a directive among its siblings, so it keeps its identity when lines move?**
>
> | | **A. The program gives a key rule (recommended, shown)** | B. A fixed knobly rule: a directive with a block is named by its values | C. Position only |
> |---|---|---|---|
> | Evidence | rasl and both sugars wrote one: rasl in TypeScript names nodes, connects and fills; the sugars build theirs from `@Key` / `key=True` | Would not name rasl's connects or fills | |
> | Cost | Every program writes a rule (React's list `key` is the same idea) | Changing a node's type is "removed + added", never "changed" | Inserting one node marks every later node as changed |

---

## 4. An error report, and what the programs changed

The third party's probe, run with the real zod 4.1.12 against a hand-built stand-in for knobly. Excerpt of `integrate-third-party/ts/evidence/probe.txt`, lines 2-11:

```text
== whole load, Proxy: value=undefined, 7 diagnostics
  proxy-bad.conf:1:1: vlschema/invalid_type: listen: Invalid input: expected tuple, received undefined
  proxy-bad.conf:10:23: vlschema/invalid_type: upstream.0.server.0.1: Invalid input: expected number, received string
  proxy-bad.conf:2:14: vlschema/invalid_type: upstream.0.timeout: Invalid input: expected number, received string
      via variable timeout at 11:13
  proxy-bad.conf:12:16: vlschema/invalid_type: upstream.0.rate: Invalid input: expected number, received string
      via variable rps at 5:10
      via use limits at 12:5
  proxy-bad.conf:13:5: vlschema/unrecognized_keys: retries: not allowed here
  proxy-bad.conf:16:1: vlschema/invalid_type: upstream.1.server: Invalid input: expected array, received undefined
```

The bad `rate` points at `fast` in `use limits fast;`, then lists the variable and the snippet use that carried it. The `1:1` line is a missing top-level `listen`, which had no line to point at (first row below).

| Found by | What got in the way | This revision |
|---|---|---|
| rasl TS, rasl Py, third party | A problem with no line (a missing top-level block) had nowhere to go; all three built a place at 1:1 by hand | **Changed:** the root file owns the top level, as a directive owns its block: `loaded.origin`, `loaded.error()` |
| rasl and the sugar, both languages | Nobody used `whole` or `replaced`. rasl needs retune vs restart vs rewire; the sugar works out its own "replaced" | **Changed:** both deleted. A change says what differs, never what to do |
| rasl TS, rasl Py, sugar | A line left out for a syntax error compares as "removed", so each of them refused to compare a broken load | **Changed:** `diff` refuses a load with problems |
| rasl TS, rasl Py | Each wrote the same "record it and keep going" helper | **Changed:** `collect` (TS), `vl.collecting` (Python) |
| rasl Py, third party | What `plain()` makes of a quoted `"8080"` was unstated; both special-cased quotes | **Changed:** quoting means text; only a bare word becomes a number or true/false (both of rasl's readers do this today) |
| sugar, third party | The sugar had no code range of its own; Python never checked a hand-made code | **Changed:** E6xxx is the sugar's; Python checks a code when a diagnostic is made |
| sugar; third party | The key rule sees the parent directive, not the sugar's scope; changes are listed where they happened, not at the record around them; a block's own values have no names (`$args[0]`) | **Kept:** scopes, records and named values are the sugar's or the schema's ideas. `parent` and `walk` carry them, at 20 to 35 lines in each sugar |

---

## 5. The interfaces

TypeScript shown; Python has the same names in Python spelling (`as_word()`, `vl.load(document, *, extensions, variables, key)`). Full stubs: `api-ts/index.d.ts`, `api-py/knobly/__init__.pyi`.

```ts
interface Loaded {
  readonly body: readonly Directive[];        // the top level, expanded
  readonly origin: Origin;                    // new: the root file; a problem with no line goes here
  readonly diagnostics: readonly Diagnostic[];
  readonly graph: DocumentGraph;              // every file read, each once
  walk(callback: (d: Directive) => false | void): void;
  error(message: string, code: ProgramCode): DiagnosticError; // new
}

interface Directive {
  readonly name: string;
  readonly args: readonly Arg[];
  readonly body: readonly Directive[] | undefined;  // undefined: written without a block
  readonly parent: Directive | undefined;
  readonly address: Address;                        // identity across loads
  readonly origin: Origin;                          // where written, plus each variable, use, include
  walk(callback: (d: Directive) => false | void): void;
  error(message: string, code: ProgramCode): DiagnosticError;
}

interface Arg {
  readonly kind: "word" | "string" | "list" | "slice" | "index";
  readonly text: string;                            // as written
  readonly origin: Origin;
  word(): string;                                   // each reader throws a located error
  string(): string;
  number(): number;
  integer(): number;
  boolean(): boolean;
  items(): readonly Arg[];
  slice(): SliceValue | IndexValue;
  plain(): PlainValue;                              // quoted: text; a word: number, boolean or text
  error(message: string, code: ProgramCode): DiagnosticError;
}

type Change =
  | { kind: "added"; address: Address; after: Directive }
  | { kind: "removed"; address: Address; before: Directive }
  | { kind: "changed"; address: Address; before: Directive; after: Directive }; // its own values

interface Processor {
  load(document: Document, options?: { variables?: Record<string, string> }): Promise<Loaded>;
  diff(before: Loaded, after: Loaded): readonly Change[]; // throws if either load has problems
}

declare function knobly(options?: { extensions?: Extension[]; key?: KeyRule }): Processor;
declare function collect(into: Diagnostic[], read: () => void): void; // new
```

> **Question: does the DirectiveDelegator (kno-stq) still ship?**
>
> | | **A. No: its job is split (recommended)** | B. Ship a walker that calls a handler per directive name |
> |---|---|---|
> | Evidence | rasl and the third party read with `if` or `match`; the sugar does its own per-directive calls on top of the walk | |
> | Cost | kno-stq's acceptance text (hooks, typed `children`/`skip` results) is not met as written; it closes into the sugar (kno-xlo) | A third way to read a config; in Python it is subclass-based, the style you called "too class-inheritance driven" |

## 6. Design rules (design choices, not requirements)

1. **Expanded for the reader, never lost.** A program sees only expanded directives; each directive and value carries its origin, and the text is kept as written.
2. **Identity is where a directive lands; origin is where it was written.** A change list compares the addresses in two loads that have no problems. It says what differs and never what to do.
3. **Located, or not a problem.** Every diagnostic has an origin, including a whole-file problem. `load` never throws because of the text, and a reader throws only a located error.

## 7. New terms

| Term | Meaning | Why needed | Could be an existing term |
|---|---|---|---|
| loaded | what one load produced: expanded top level, problems, file graph | the one result a program reads | round 8's "expanded tree" |
| origin | where text was written, and the steps that brought it here | tracing a value to both its use and its definition | R14's "include chain", widened |
| step | one expansion: a variable, a `use`, or an extension directive | the parts of an origin | round 10's `via` |
| handed | a variable value the program passed in, written in no file | `rasl --set host=...` | round 10's "handed in" |
| address | where a directive lands: a name, key and occurrence per level | identity in change lists | v15's "identity" |
| key rule | the program's rule naming a directive among its siblings | addresses that survive moved lines | the sugar's `key=True` |
| extension | owns one directive name and gives files to splice in its place | include as a first-party plugin (R20) | round 10's "plugin" |
| plain value | a value read by knobly's one rule | rasl's open property sets | R7's "one rule" |

## 8. Line counts and NOT RUN

Non-blank, non-comment lines (Python docstrings counted, TypeScript doc comments not).

| Program | Lines | Checks (all seen this round) |
|---|---|---|
| rasl, TypeScript: reader, reload plan, file source, helpers, types | 359 (read 145, reload 71, model 62, source 50, errors 31) | tsc exit 0 |
| rasl, Python: reader, pydantic placement, reload plan, files, CLI demo | 527 (reader 255, reload 85, validate 51, model 49, cli_demo 37, files 27, init 23) | pyright 0 errors (2 expected stub-only warnings), mypy exit 0 |
| third party, zod | 145 (vlschema 102, proxy 27, schemas 16) | tsc exit 0; probe exit 0 |
| third party, pydantic | 162 (vlschema 110, proxy 52) | pyright and mypy exit 0; probe exit 0 |
| round-10 sugar, TypeScript | 835 (runtime 774, index 44, include 17); its decorators (303) are round 10's | tsc exit 0; 5 planted exit 2 |
| round-10 sugar, Python | 610 (build 286, changes 161, init 92, key 71); its declarations (368) are round 10's | pyright, mypy exit 0; one run exit 0 |
| the stubs, with their own rasl examples | | tsc, pyright, mypy exit 0; 6 of 6 planted mistakes fail in each language |

**NOT RUN**
- No knobly implementation exists, so no config was ever loaded. rasl's readers, reloads and the planted `family_room.bad.conf` never ran, and the reload table in §3 was worked out by hand.
- The third-party probes and the Python sugar's run used hand-built stand-ins for knobly. The TypeScript sugar never ran.
- "Valid v10 text" for rasl's two files was judged by reading them against the grammar, not by parsing them.
- The integrations were changed only to keep compiling: `collect`, `vl.collecting` and `loaded.error` are used only by the stubs' own rasl examples.
- No review of this revision; ruff, eslint, and other Python or TypeScript versions.

*History: v10 approved the language · round 11: the low-level API, tried by four programs.*
