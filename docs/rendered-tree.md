# The rendered tree (TypeScript and Python)

This page is for a program that reads villanelle config. It covers the middle layer, the **rendered tree**: the
directives a program reads, with variables, snippets and included files already worked out, every value's origin
(where it was written), and the problems found, as located diagnostics. It also covers addresses (a directive's
identity across reloads) and the list of what changed between two renders.

> The language-neutral rules every binding follows are in [`spec/`](../spec/README.md), which wins
> where this page differs; the words are in [`spec/glossary.md`](../spec/glossary.md).

villanelle has three layers. Each one is built on the one below, and a program can work at any of them:

| Layer | What it is | Where it is described |
|---|---|---|
| the syntax tree | `parse(text)`: one text, every character in exactly one token | [`ts/README.md`](../ts/README.md), [`py/README.md`](../py/README.md) |
| the low level | `load(path)`: the files as written, with the variables and include lines in them, editable and saved back | [low-level-api.md](low-level-api.md) |
| the rendered tree | `render(graph)`: what the files say once variables, snippets and includes are worked out | this page |

The language itself is described in [language.md](language.md).

The two packages have the same parts under each language's own names. Each section shows TypeScript first, then
Python.

**About the examples.** Every example is copied from a test that passes, named under it. The tests import from the
package's source files (`./render.js`, `../include.js`); the examples write the imports a program would write
(`villanelle`, `villanelle/include`, `villanelle/node`). "Excerpt" means lines were left out; nothing else was
changed.

## Worked example: how rasl reads its config and reloads it

rasl is the program villanelle was built for. Its config has a `graph` block of `node` directives, each named by
its second value (`node DdpSink leds { ... }`). It wants: every node, the place of every problem, and, when a file
changes while it runs, the list of what changed, with each node keeping its identity when lines move.

TypeScript:

```ts
import { fileURLToPath } from "node:url";

import { type IDirective, type IProcessor, type IRendered, type KeyRule, render, villanelle } from "villanelle";
import { include } from "villanelle/include";
import { fileSource } from "villanelle/node";

/** The "rasl" key rule of conformance/load/format.md. */
const RASL_KEY: KeyRule = (d) => {
  if (d.name === "node" && d.parent?.name === "graph") return d.values[1]?.text;
  if (d.name === "connect") return d.values.map((a) => a.text).join(" ");
  if (d.name === "fill") return d.values[0]?.text;
  return undefined;
};

function nodeIds(loaded: IRendered): string[] {
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.values[1]?.text ?? "");
  });
  return ids;
}

const OVERRIDES = { leds_host: '"10.0.70.1"' };

export async function rendered(processor: IProcessor, path: string, options?: { readonly overrides?: Readonly<Record<string, string>> }): Promise<IRendered> {
  return render(await processor.load(path, options));
}

    const processor = villanelle({ source: files, extensions: [include()] });
    const path = fileURLToPath(new URL(name, FIXTURES));
    const options = { overrides: OVERRIDES };
    const first = await rendered(processor, path, options);
    expect(first.diagnostics).toEqual(expected.diagnostics);
    expect(nodeIds(first)).toEqual(expected.nodes);
    edit();
    const second = await rendered(processor, path, options);
    expect(first.diff(second, { key: RASL_KEY }).map((c) => [c.kind, c.address.toString()])).toEqual(expected.changes);
```

Excerpt of `ts/src/rendered/rasl.test.ts`, test "%s loads with the expected nodes and reload changes" (run once
per fixture), and of `rendered` in `ts/src/rendered/testing.ts`. `files` is the file source from `fileSource()`,
wrapped so that `edit()` makes the next read say `set $pixels 2400;` instead of `2284`.

Python:

```python
import villanelle as vl
from villanelle.files import file_source
from villanelle.include import include


def rasl_key(d: vl.Directive) -> str | None:
    """The "rasl" key rule of conformance/load/format.md."""
    if d.name == "node" and d.parent is not None and d.parent.name == "graph":
        return d.values[1].text if len(d.values) > 1 else None
    if d.name == "connect":
        return " ".join(a.text for a in d.values)
    if d.name == "fill":
        return d.values[0].text if d.values else None
    return None


def node_ids(loaded: vl.Rendered) -> list[str]:
    graph = next(d for d in loaded.block if d.name == "graph")
    return [d.values[1].text for d in graph.block or () if d.name == "node"]


    processor = vl.Processor(source=file_source(), extensions=[include()])
    overrides = {"leds_host": '"10.0.0.9"'} if override else None
    first = vl.render(processor.load(str(root), overrides=overrides))
    expected = EXPECTED[name]
    assert expected["diagnostics"] == []
    assert first.diagnostics == ()
    assert node_ids(first) == expected["nodes"]
    text = root.read_text(encoding="utf-8")
    assert text.count("set $pixels 2284;") == 1
    root.write_text(text.replace("set $pixels 2284;", "set $pixels 2400;"), encoding="utf-8")
    second = vl.render(processor.load(str(root), overrides=overrides))
    changes = first.diff(second, key=rasl_key)
    assert [[type(c).__name__.lower(), str(c.address)] for c in changes] == expected["changes"]
```

Excerpt of `py/tests/test_rasl.py`, `test_a_rasl_fixture_loads_and_reloads_as_expected`.

For [`family_room.conf`](../fixtures/rasl/family_room.conf), the change list after the `$pixels` edit is exactly the
two directives that use `$pixels` ([`fixtures/rasl/expected.json`](../fixtures/rasl/expected.json)):

```
changed  graph > node "leds" > max_count
changed  graph > node "leds" > connect "crossfade_rgb pixels" > repeat_until
```

The rest of this page goes through each part used above.

## Making a processor, loading and rendering

A **processor** is made once, with two things: the **document source** (where files come from) and the
**extensions** (such as include). Loading is its only operation, so two loads are always read the same way.
Everything after a load is a method on what it gave back, or the rendered layer's `render`:

| | TypeScript | Python |
|---|---|---|
| make | `villanelle({ source, extensions? })` | `Processor(source=..., extensions=())` |
| load the files as written | `await processor.load(path, { overrides? })` | `processor.load(path, overrides=None)` |
| read files an edit added | `await graph.read()` | `graph.read()` |
| render | `render(graph)` | `render(graph)` (`villanelle.render`, from `villanelle.rendered`) |
| compare | `before.diff(after, { key? })` | `before.diff(after, key=None)` |

`load` gives back the **document graph**: the files as written, described on the [low-level page](low-level-api.md).
The low level knows nothing of the rendered tree; `render(graph)`, in the rendered layer, builds the rendered tree
from the graph's current texts and overrides. It reads no file, so
it can be called again after an edit, and two calls never disagree about the same texts. A rendered tree is a
snapshot: an edit made after `render` does not change it; render again to see the edit.

`load` resolves `path` through the source as an include spec is resolved (with an empty parent path), reads that
file, then everything it splices in, so the root has one path however it is written (load case `load-root-spelling`).
Each file is read once per load, however many places include it. A load never fails because of what a file says:
every problem becomes a diagnostic and the rest is read. It fails only when:

- the source cannot resolve `path` to exactly one file, or cannot read it: a `ReadError` with `paths` (the root
  path) and the source's failure as its cause, and no diagnostic or code (test "rejects with ReadError, paths the root
  path and no diagnostic, when the source resolves no file (B10)", `ts/src/written/edits.test.ts`;
  `test_a_root_the_source_cannot_read_raises_read_error_from_the_sources_failure`, `py/tests/test_load.py`);
- an override has a bad name (MisuseError in TypeScript, ValueError in Python), is not a string (TypeError), or has
  text the check of an override refuses (`BadTextError`, located in the text: see
  [low-level-api.md](low-level-api.md#overrides)).

`render` takes any graph a processor loaded (TypeError for anything else, in both languages), and a render's
`diff` takes any other render.

**Overrides** are texts read as values: `{ ports: '8080 443 "x" [1, 2]' }` gives `$ports` four values. They win
over every `set` of the same name ([spec/expansion.md](../spec/expansion.md) 6 has the whole precedence table). The low level can change them later without a reload (`graph.setOverride`,
[low-level-api.md](low-level-api.md#overrides)).

What a render gives back (`IRendered` / `Rendered`):

| Field | What it is |
|---|---|
| `block` | the top-level directives, expanded (a read-only sequence) |
| `unreadable` | top-level statements that could not be read, in place (`IUnreadableExpansion` / `UnreadableExpansion`, the low level's own objects) |
| `diagnostics` | every problem: each file's syntax problems, then the low level's, in order; the same list as `graph.diagnostics` |
| `graph` | the document graph it was rendered from |
| `origin` | the root file at 0:0, where a problem of the whole file is placed |
| `walk(...)`, `error(...)` | see "Walking" and "Problems" |
| `addresses({ key })` | every directive's address under a key rule (see "Addresses and the key rule") |
| `diff(after, { key })` | what changed between this render and a later one (see "What changed: diff") |

## Walking the directives

A directive (`IDirective` / `Directive`) has `name`, `values`, `block` (the directives of its block, a read-only
sequence, or undefined/None when written without a block), `unreadable`, `parent`, `origin` and `written`. `set`, `snippet`,
`use` and include lines never appear: what they produce does, in their place.

`written` is the directive as written, on the low level: the line to edit. A line read at two places (a file
included twice, a snippet used twice) renders as two directives with the same `written` object, so an edit to it
shows in both:

```ts
    const files = { "main.conf": 'g {\n  include "s.conf";\n}\nh {\n  include "s.conf";\n}\n', "s.conf": "x 1;\ny $nope;\n" };
    const processor = villanelle({ source: memorySource(files), extensions: [include()] });
    const graph = await processor.load("main.conf");
    const rendered = render(graph);
    const [g, h] = rendered.block;
    const x = graph.documents.get("s.conf")?.block.statements[0];
    const y = graph.documents.get("s.conf")?.block.statements[1];
    expect(g?.block?.[0]?.written).toBe(x);
    expect(h?.block?.[0]?.written).toBe(x);
    expect(g?.unreadable[0]?.written).toBe(y);
    expect(h?.unreadable[0]?.written).toBe(y);
    expect(g?.written).toBe(graph.root.block.statements[0]);
```

`ts/src/written/edits.test.ts`, test "gives both copies of a line read twice the same statement, and an unreadable
copy its statement".

```python
    files = {"main.conf": 'a { include "p.conf"; }\nb { include "p.conf"; }\n', "p.conf": "x 1;\n"}
    graph = vl.Processor(source=vl.memory_source(files), extensions=[include()]).load("main.conf")
    rendered = vl.render(graph)
    x1, x2 = (d for d in rendered.walk() if d.name == "x")
    assert x1.written is x2.written is graph.documents["p.conf"].block[0]
    assert len(x1.written.copies()) == 2
```

`py/tests/test_written.py`, `test_a_rendered_directive_is_a_copy_of_one_written_directive_handle`.

TypeScript walks with a callback. Return `"skip"` to pass over a directive's block, `"stop"` to end the walk:

```ts
  const ids: string[] = [];
  loaded.walk((d: IDirective) => {
    if (d.name === "node" && d.parent?.name === "graph") ids.push(d.values[1]?.text ?? "");
  });
  return ids;
```

Excerpt of `nodeIds` in `ts/src/rendered/rasl.test.ts`.

Python walks with a generator, a method on the render and on each directive. `descend` returning False passes
over a block; `break` ends the walk:

```python
    skipped = [d.name for d in loaded.walk(descend=lambda d: d.name != "server")]
    assert skipped == ["http", "server", "server", "events"]
```

Excerpt of `test_walk_is_depth_first_in_written_order_and_descend_false_passes_over_a_block`,
`py/tests/test_load.py`.

Both walk depth-first in written order, from the render or from one directive. `closest(predicate)` gives this
directive or the nearest enclosing one that matches. Python directives and values also take part in `match`
(`Directive` matches as `name`, `values`, `block`):

```python
    match graph.block[0]:
        case vl.Directive("node", [kind, node_id, *rest], block):
            assert (kind.text, node_id.text, [r.text for r in rest]) == ("DdpSink", "leds", ["1"])
```

Excerpt of `test_directive_matches_by_name_values_and_block`, `py/tests/test_load.py`.

A rendered `block` is a plain sequence of directives, not the low level's `written block`: it has no
`directives(name)` lookup; filter it by `name` or `walk` it.

### Unreadable statements

A statement that could not be read stays in its block's `unreadable` list as an unreadable expansion (the same
object `graph.expand()` gives), with its `reason`, its `origin` and `written` (the statement as written). It has no
name and no address: what it would have been is unknown.

| Reason | Why |
|---|---|
| `syntax` | the parser could not read it |
| `expansion` | a variable, `set`, `snippet` or `use` failed (unknown name, wrong count, loop, limits) |
| `value` | a value broke a rule checked when expanding (E4001) |
| `extension` | an include line (or another extension's line) failed |
| `unread` | an include line's files are not read yet: an edit added or changed it, and `graph.read()` has not run (E3007) |

```ts
    const loaded = await loadText("a {\n  b 1;\n  : x;\n  c $nope { d $nope2; }\n  e;\n}\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E2001", "main.conf:2:2"],
      ["E5001", "main.conf:3:4"],
    ]);
    const a = only(loaded.block);
    expect(a.unreadable.map((u) => [u.reason, originText(u.origin)])).toEqual([
      ["syntax", "main.conf:2:2"],
      ["expansion", "main.conf:3:2"],
    ]);
    expect(addresses(loaded)).toEqual(["a", "a > b", "a > e"]);
```

`ts/src/rendered/rules.test.ts`, test "keeps a bad line in its place without its block expanded, siblings kept"
(`loadText` loads one text and renders it). The `$nope2` inside the broken line's block is not reported.

## Reading values

Each value is an **expanded value** (`ExpandedValue`, a union over `kind` in both languages: `IExpandedWord`,
`IExpandedString`, `IExpandedList`, `IExpandedSlice`, `IExpandedIndex`; Python `ExpandedWord`, `ExpandedString`,
...), the low level's own object, the one an extension use holds too: a `kind` (word, string, list, slice, index;
never reference), a canonical `text`, an `origin`, readers, and three links to the low level, `written`,
`definition` and `chain` (below). (Before milestone 4 the rendered tree had its own `Argument` family that copied
it.) In Python two expanded values are `==` when their texts are equal. A reader that meets the wrong value throws a
`DiagnosticError` placed on that value.

| Reads | TypeScript | Python | Error |
|---|---|---|---|
| a bare word | `word()` | `word()` | E4002 |
| a word or a string, decoded | `string()` | `string()` | E4002 |
| a number (JSON's number syntax: `8080`, `0.5`, `-2E-2`; not `20hz`, `01`, `.5`) | `number()` | `number()` | E4004, E4002 |
| a whole number within ±(2^53-1) (`1.0` is not one) | `integer()` | `integer()` | E4005, E4002 |
| `true` or `false` only (`on`, `yes` are not) | `boolean()` | `boolean()` | E4006, E4002 |
| a list's items, each with its own origin | `list()` | `list()` | E4002 |
| a slice or an index | `slice()` | `slice()` | E4002 |
| anything, by one rule | `plain()` | `plain()` | never |

`plain()` reads a string as its text, a word as a number when it spells one, `true`/`false` as booleans, any other
word as its text, a list item by item, a slice or index as itself:

```ts
    const read = await values('"8080" 8080 true "true" on [1, "a", [false]] c[1:2] c[3] 20hz');
    expect(read.map((a) => a.plain())).toEqual([
      "8080",
      8080,
      true,
      "true",
      "on",
      [1, "a", [false]],
      { kind: "slice", name: "c", start: 1, end: 2 },
      { kind: "index", name: "c", index: 3 },
      "20hz",
    ]);
```

`ts/src/rendered/readers.test.ts`, test "plain: one rule for every value; quoting means text".

```python
    assert arg("hyperhdr_color[144:152]").slice() == vl.SliceValue("hyperhdr_color", 144, 152)
    assert arg("c[144:]").slice() == vl.SliceValue("c", 144, None)
    assert arg("c[:-2]").slice() == vl.SliceValue("c", None, -2)
    assert arg("foo[1]").slice() == vl.IndexValue("foo", 1)
```

Excerpt of `test_slice_gives_slices_with_an_absent_side_none_and_indexes`, `py/tests/test_readers.py`. In
TypeScript an absent side is left out of the object (`{ kind: "slice", name: "c", start: 144 }`).

### Canonical text

`text` is the same in both languages, and two values are the same exactly when their texts are equal:

- a word as written;
- a string in double quotes, with `\` `"` newline tab and carriage return escaped (`'single'` becomes `"single"`);
- a slice `name[start:end]` with either side empty when absent, an index `name[i]`, in decimal;
- a list `[` + its items' texts joined by `, ` + `]`, with comments, line breaks and a trailing comma dropped;
- a value from a variable has the value's text, never `$name`.

```ts
    const arg = await value("[1, # warm\n  'two',\n  [3,4,],\n]");
    expect(arg.text).toBe('[1, "two", [3, 4]]');
```

`ts/src/rendered/readers.test.ts`, test "drops comments, line breaks and a trailing comma from a list".

### From a rendered value to what is written

Three members lead from a rendered value back to the low level, where it can be edited:

- `written`: the written value on the same line, the line of the statement the value is read in: for
  `max_count $pixels;`, the `$pixels` there; for a value written where it is read, the value itself. Never absent.
  Editing it edits that one line, which every copy of the line shares: in a file included twice, the edit shows in
  both copies. So a loop that edits every directive's `written` value meets the same handle twice, and the first
  edit (`replaceWithText` or `remove()`) detaches it: keep the handles already edited (a `Set` in TypeScript, a
  `set` in Python; handles are one object per written value) and skip them. Test "edits a line an included file
  shares between two copies once, keeping the written values already edited", `ts/src/rendered/rasl.test.ts`;
  `test_an_edit_loop_edits_a_line_an_included_file_shares_between_two_copies_once`, `py/tests/test_rasl.py`.
- `definition`: the written value at the end of its chain (for `max_count $pixels;`, the `2284` of
  `set $pixels 2284;`); undefined (None) for an override. Editing it changes every use.
- `chain`: one reference resolution per `$name` the value came through, starting with the `$name` written on the
  directive's own line. Each says which variable won at this place, and which it shadowed. Empty for a value
  written where it is read.

So `chain[0].winner` is the variable to change for every place that reads it, and `chain[0].reference` (the same
handle as `written`) is the `$name` on this line, to replace with a value of its own. To change one copy of an
included file only, edit what that copy is given (its include block's `set` line, at the include step of
`chain`). The
[low-level page](low-level-api.md#user-code-first) shows both edits.

## Origins: where each value was written

Every directive, value, unreadable statement and diagnostic carries an **origin**: `place`, where the text was
written (a file and a span, or an override), and `via`, the steps that brought it to where it is read,
innermost first. A step is a `variable`, a `use` or an `extension` (an include line), with its name and the place of
the reference.

So a value from a variable says both where it was set and where the `$name` was used:

```python
    value = next(d for d in loaded.walk() if d.name == "max_count").values[0]
    assert value.text == "2284"
    assert isinstance(value.origin.place, vl.Place)
    assert value.origin.place.span.start == vl.SourcePosition(12, 0, 12)
    [step] = value.origin.via
    start = step.place.span.start
    assert (step.kind, step.name, start.line, start.column) == ("variable", "pixels", 2, 32)
```

Excerpt of `test_a_variable_value_has_its_set_place_and_the_variable_step`, `py/tests/test_load.py`
(`set $pixels 2284;` on line 0, `max_count $pixels;` on line 2).

A value from an override has `origin.place` = the override, and its steps say how it got there. In the split rasl
fixture, the `leds` sink's `target` comes from `--set leds_host`, through `$host` in the include block, through the
include line:

```python
    leds_target = next(d for d in overridden_host.walk() if d.name == "target")
    assert leds_target.values[0].origin.place == vl.Override("leds_host")
    assert [(s.kind, s.name) for s in leds_target.values[0].origin.via] == [
        ("variable", "leds_host"),
        ("variable", "host"),
        ("extension", "include"),
    ]
```

Excerpt of `test_the_split_fixtures_sinks_take_their_include_blocks_values_and_the_override_host_wins`,
`py/tests/test_rasl.py`.

Lines and columns are 0-based and columns count UTF-16 code units, in both languages. `formatDiagnostic` prints them
1-based for people.

## Addresses and the key rule

An **address** is a directive's identity across renders: from the top level down, each step is the
directive's name, its key (what the key rule returned, or none), and its occurrence among earlier siblings with the
same name and key (counting from 0). It is unique within one render. A file included at two places, or a snippet
used twice, lands at two addresses.

| | TypeScript | Python |
|---|---|---|
| every directive's address | `rendered.addresses({ key })`, a map from directive to address | `rendered.addresses(key=...)` |
| for people | `address.toString()`: `graph > node "leds" > max_count` | `str(address)` |
| as a map key | `address.text` (JSON, the same bytes in both languages) | `address.text`, or the `Address` itself (hashable) |
| enclosing | `address.parent` | `address.parent` |

The **key rule** is the program's, and it is given where addresses are asked for: to `addresses({ key })` and to
`before.diff(after, { key })`. It is called once per readable directive, parents first, with the rendered
directive, and returns a key or nothing. What it throws comes out of `addresses` or `diff` unchanged (a bug in the
program, not in the config):

```ts
    const named = loaded.addresses({ key: RASL_KEY });
    loaded.walk((d) => {
      if (d.name === "target") targets.push([named.get(d)?.toString() ?? "", d.values[0]?.text ?? ""]);
    });
    expect(targets).toEqual([
      ['graph > node "leds" > target', '"10.0.70.1"'],
      ['graph > node "porch" > target', '"10.0.60.31"'],
    ]);
```

Excerpt of `ts/src/rendered/rasl.test.ts`, test "splits one sink file over two places, each with its own
include-block values and the override host".

Without a key rule, a directive is named by its position among same-name siblings, so moving a line changes
addresses:

```python
def test_without_a_key_rule_a_directive_is_named_by_its_position_among_same_name_siblings() -> None:
    loaded = load("a 1;\nb;\na 2;\n")
    assert [str(a) for a in loaded.addresses().values()] == ["a", "b", "a #1"]
```

`py/tests/test_load.py`. With rasl's rule, a node keeps its address when it moves:

```ts
    const text = (first: string, second: string): string => `graph {\n  ${first}\n  ${second}\n}\n`;
    const one = "node A one { x 1; }";
    const two = "node B two { x 2; }";
    expect(await changes(text(one, two), text(two, one), RASL_KEY)).toEqual([]);
    expect(await changes(text(one, two), text(two, one))).toEqual([
      ["changed", "graph > node"],
      ["changed", "graph > node > x"],
      ["changed", "graph > node #1"],
      ["changed", "graph > node #1 > x"],
    ]);
```

`ts/src/rendered/diff.test.ts`, test "follows a keyed node that moved: no change". `RASL_KEY` there is
`(d) => (d.name === "node" && d.parent?.name === "graph" ? d.values[1]?.text : undefined)`.

A key rule that reads values from variables makes identity follow config edits; that is the program's choice.

## What changed: diff

`before.diff(after, { key })` (Python: `before.diff(after, key=...)`) compares two renders by address, under the
key rule given. Each change carries its address and its directives (`before`, `after`, or both):

| Change | When |
|---|---|
| added | only in `after` |
| removed | only in `before`, and its block in `after` has no unreadable statement |
| unknown | only in `before`, but its block in `after` (or the top level) holds an unreadable statement: the broken line may be it |
| changed | in both, and its own values (by canonical text) or whether it has a block differ |

An added, removed or unknown directive is listed alone, never with the directives inside it. A changed or unchanged
directive's block is compared at its own addresses. Order: removed and unknown in `before`'s walk order, then added
and changed in `after`'s. Renders with diagnostics can be compared.

In TypeScript a change has `kind` (`"added"`, `"removed"`, `"changed"`, `"unknown"`). In Python each kind is its own
class (`Added`, `Removed`, `Changed`, `Unknown`); test with `isinstance` or `match` (Python's `kind` field comes
with a later milestone).

```python
def test_a_directive_missing_beside_an_unreadable_statement_is_unknown_not_removed() -> None:
    assert changes("g {\n  a 1;\n  b 2;\n}\nz;\n", 'g {\n  a 1;\n  b x"y";\n}\n') == [
        ("unknown", "g > b"),
        ("removed", "z"),
    ]
    assert changes("a;\nb;\n", 'a;\nb x"y";\n') == [("unknown", "b")]
```

`py/tests/test_load.py`. `changes` renders the first text, then the second, through one processor.

A comment or a quote style is no change; a number's spelling is (`0.5` to `0.50`), because values compare by text
(test "compares canonical texts: a comment or a quote style is no change, a number's spelling is",
`ts/src/rendered/diff.test.ts`). To group changes by its own unit (a rasl node), a program uses `directive.closest(...)` or
`address.parent`.

## Problems: diagnostics, program errors and the sink

A **located diagnostic** (`ILocatedDiagnostic` / `LocatedDiagnostic`) has a `code`, a `message` (for people; not
part of the contract between the languages), `place` (a place in a file) and `via` (the steps). A problem with an
override's value is placed on the `$name` that used it.

A program places its own problems on what it read. Every directive, value and the render itself has
`error(message, code)` (Python: `error(message, code=...)`), which returns a `DiagnosticError` to throw or record. A
program's code is `<namespace>/<name>`, such as `rasl/unknown-node`; both parts must be there (TypeError /
ValueError otherwise), so a program's code never looks like villanelle's.

**The sink** (`Diagnostics`) is the one place problems collect. Start it with the render's problems, report into it,
and run reads through it so a reader's error is recorded instead of ending the program:

```ts
    const loaded = await loadText("port eighty;\n");
    const sink = new Diagnostics();
    const port = only(only(loaded.block).values);
    expect(sink.collect(() => port.integer())).toBeUndefined();
    expect(sink.collect(() => port.word())).toBe("eighty");
    expect(problems(sink)).toEqual([["E4005", "main.conf:0:5"]]);
```

Excerpt of `ts/src/rendered/report.test.ts`, test "collect records a DiagnosticError and returns undefined; passes
anything else through". Any other exception passes through.

```python
    load = loaded("a $x;\nb 1;\n")
    problems = vl.Diagnostics(load.diagnostics)
    b = load.block[0]
    problems.report(b, "b is not wanted", code="rasl/unwanted")
    problems.add(load.error("no graph", code="rasl/no-graph").diagnostic)
    assert len(problems) == 3
    assert [str(d.code) for d in problems] == ["E5001", "rasl/unwanted", "rasl/no-graph"]
```

Excerpt of `test_report_and_add_record_in_order_after_the_initial_ones`, `py/tests/test_report.py`. Python's
`with problems.collecting():` records a `DiagnosticError` raised inside it and ends the block.

**Printing** (`formatDiagnostic(d, graph?)` / `format_diagnostic(d, graph=None)`): the place 1-based, the code and
message, the source line (from the document's current text), a caret line under the span, and one line per step.
Without the graph, only the first line. It reads a graph, so it belongs to the low level (`villanelle.written` in
Python; both packages also export it from `villanelle`).

```ts
    const files = { "main.conf": 'include "x.conf";\n', "x.conf": "a 1;\nport c[0:$n];\n" };
    const loaded = await loadFiles(files, { extensions: [include()] });
    expect(formatDiagnostic(only(loaded.diagnostics), loaded.graph)).toBe(
      ["x.conf:2:10: E5001: unknown variable: $n", "port c[0:$n];", "         ^^", "  via extension include at main.conf:1:1"].join("\n"),
    );
```

`ts/src/rendered/report.test.ts`, test "prints path:line:col: code: message 1-based, the source line, a caret and one via
line per step".

## Document sources: where files come from

The core does no input or output. A **document source** does it, with two methods: `resolve(spec, context)` gives the
paths a spec names (a path, or a glob with `*` and `?` in its last part; none means not found, E3001), and
`read(path)` gives a file's text. If either throws, the render reports E3004 at the include line (or, for the root
file, `load` fails as above). In TypeScript both return promises; in Python both are plain calls.

| Source | TypeScript | Python |
|---|---|---|
| texts held in memory (tests, editors) | `memorySource({ path: text })` | `memory_source({path: text})` |
| the filesystem | `fileSource()` from `villanelle/node` | `file_source()` from `villanelle.files` |
| `fetch` (paths are URLs) | `fetchSource(fetch)` from `villanelle/browser` | none |

A program can write its own, for example to count reads:

```python
class _Counting:
    def __init__(self, files: Mapping[str, str], *, resolve_fails: str = "", read_fails: str = "") -> None:
        self.inner = vl.memory_source(files)
        self.reads: list[str] = []
        self.resolve_fails = resolve_fails
        self.read_fails = read_fails

    def resolve(self, spec: str, context: vl.LoadContext, /) -> Sequence[str]:
        if spec == self.resolve_fails:
            raise OSError("resolve failed")
        return self.inner.resolve(spec, context)

    def read(self, resolved_path: str, /) -> str:
        self.reads.append(resolved_path)
        if resolved_path == self.read_fails:
            raise OSError("read failed")
        return self.inner.read(resolved_path)
```

`py/tests/test_load.py`, used by `test_a_file_included_at_two_places_is_read_once_held_once_and_has_two_edges`,
which shows `p.conf` read once though two places include it.

The fetch source never fetches in `resolve`, so a missing remote file is E3004 (the read fails), not E3001, and a
glob resolves to nothing (test "resolves without fetching, resolves a glob to nothing, and rejects a non-2xx read",
`ts/src/browser.test.ts`).

## Extensions

An **extension** owns one directive name and turns each use of it into specs of files to splice in its place.
`include()` is the one villanelle ships. The extension only names files: villanelle resolves and reads them through
the source, reads each file once, applies the line's block of `set` lines, and checks loops and limits.

An extension has `directive` (its name) and `specs(use)`, where `use` has the line's `values` (expanded values, the
low level's own type, the same a rendered directive's values are; the low level never hands an extension a rendered
type) and its `origin`. `specs` returns a list of texts (Python: a `tuple[str, ...]`; a bare `str` is refused at
run time as E3006, since Python would read it as a list of letters).
To refuse a use at a place, throw a `DiagnosticError` from a value's or the use's `error(...)`; anything else thrown
becomes E3006 at the line:

```ts
    const throwing: IExtension = {
      directive: "pull",
      specs: (use) => {
        if (use.values.length === 0) throw new Error("boom");
        throw use.values[0]?.error("bad pull", "test/bad-pull") ?? new Error("no value");
      },
    };
    const loaded = await loadText("pull;\npull x;\n", { extensions: [throwing] });
    expect(problems(loaded.diagnostics)).toEqual([
      ["E3006", "main.conf:0:0"],
      ["test/bad-pull", "main.conf:1:5"],
    ]);
```

Excerpt of `ts/src/rendered/rules.test.ts`, test "gives E3006 when an extension throws anything but a DiagnosticError,
and records a DiagnosticError as thrown". In Python an extension is any object with a `directive` attribute and a
`specs(use)` method (`test_an_extension_that_raises_something_else_is_e3006`, `py/tests/test_load.py`).

While an extension is registered, its name is reserved at the start of a statement, as `set`, `snippet` and `use` are.

### The files behind a render

`rendered.graph` is the document graph the render was built from: `root`, `documents` (each file read, by path,
root first, then in first-read order, with its text and syntax tree), `edges()` (one per place an extension line is
read: the line, the specs it gave and the paths it spliced, empty when resolving or reading failed), variables, and
the edits and save of the low level. All of it is on the [low-level page](low-level-api.md).

## Error codes

Lines and columns are 0-based in the API. "At" says where the diagnostic is placed. The 1xxx and 2xxx codes come from
the syntax tier, which places them as the cases in [`conformance/`](../conformance/) show; they are listed here so
the table is complete. An edit on the low level that is refused reports the same codes, placed in the text the edit
was given ([low-level-api.md](low-level-api.md#edits-and-their-errors)).

| Code | TypeScript name | Python name | Meaning | At |
|---|---|---|---|---|
| E1001 | `UnterminatedString` | `UNTERMINATED_STRING` | a string with no closing quote | per `conformance/` |
| E1003 | `UnexpectedCharacter` | `UNEXPECTED_CHARACTER` | a character the language does not use | per `conformance/` |
| E1004 | `LoneDollar` | `LONE_DOLLAR` | `$` not followed by a name | the `$` (case `var-lone-dollar`) |
| E1005 | `BadEscape` | `BAD_ESCAPE` | a string escape other than the six (found by the parser) | the string |
| E2001 | `UnexpectedToken` | `UNEXPECTED_TOKEN` | a token where it cannot go, a missing `;` at the end of a block or file among them | per `conformance/` |
| E2003 | `ExpectedClosingBrace` | `EXPECTED_CLOSING_BRACE` | a block with no `}` | per `conformance/` |
| E2004 | `ExpectedClosingBracket` | `EXPECTED_CLOSING_BRACKET` | an unmatched bracket | per `conformance/` |
| E2007 | `BadSlice` | `BAD_SLICE` | a malformed slice (`[:]` among them), or a literal bound that is not a whole number | per `conformance/` |
| E2009 | `ValuesTouch` | `VALUES_TOUCH` | two values with no space or comment between | per `conformance/` |
| E2010 | `NestingTooDeep` | `NESTING_TOO_DEEP` | blocks and lists nested deeper than 100 | per `conformance/` |
| E3001 | `IncludeNotFound` | `INCLUDE_NOT_FOUND` | a spec matched no file | the extension line's name |
| E3004 | `IncludeResolverFailed` | `INCLUDE_RESOLVER_FAILED` | the source threw (for the root file `load` fails) | the extension line's name; the root file at 0:0 |
| E3005 | `IncludeBadPath` | `INCLUDE_BAD_PATH` | include needs exactly one quoted path | the bad value, or the name when there is none |
| E3006 | `ExtensionFailed` | `EXTENSION_FAILED` | an extension threw something other than a located error, or returned something other than a list of texts | the extension line's name |
| E3007 | `UnreadCopy` | `UNREAD_COPY` | an include copy whose files are not read yet (`graph.read()` reads them) | the extension line's name |
| E4001 | `NonIntegerBound` | `NON_INTEGER_BOUND` | a bound from a variable that is not one whole number, or a literal whole number beyond the range | the bound (a bound from a variable: the value, via the variable) |
| E4002 | `WrongValueKind` | `WRONG_VALUE_KIND` | a reader met the wrong kind of value | the value |
| E4004 | `NotANumber` | `NOT_A_NUMBER` | `number()` met a word that is not a number | the value |
| E4005 | `NotAnInteger` | `NOT_AN_INTEGER` | `integer()` met a word that is not a whole number | the value |
| E4006 | `NotABoolean` | `NOT_A_BOOLEAN` | `boolean()` met a word other than `true`, `false` | the value |
| E5001 | `UnknownVariable` | `UNKNOWN_VARIABLE` | `$name` with no `set`, parameter or override | the `$name` |
| E5002 | `VariableSetTwice` | `VARIABLE_SET_TWICE` | two `set` of one name in one block | the second `$name` |
| E5003 | `UnknownSnippet` | `UNKNOWN_SNIPPET` | `use` of a snippet not seen there | the name |
| E5004 | `SnippetArity` | `SNIPPET_ARITY` | wrong number of values for the snippet | `use` |
| E5005 | `SnippetDefinedTwice` | `SNIPPET_DEFINED_TWICE` | two snippets of one name in one block | the second name |
| E5006 | `ExpansionCycle` | `EXPANSION_CYCLE` | a snippet or file reaches itself | the `use` or extension line that closes the loop |
| E5007 | `ExpansionTooDeep` | `EXPANSION_TOO_DEEP` | more than 16 snippets or files open inside each other | the `use` or extension line |
| E5008 | `TooManyDirectives` | `TOO_MANY_DIRECTIVES` | more than 100,000 directives after expansion; expansion stops | the statement that is one too many |
| E5009 | `BadSet` | `BAD_SET` | any other form of `set` | `set` |
| E5010 | `BadSnippet` | `BAD_SNIPPET` | any other form of `snippet` | `snippet` |
| E5011 | `BadUse` | `BAD_USE` | any other form of `use` | `use` |
| E5012 | `ExtensionBlockNotSet` | `EXTENSION_BLOCK_NOT_SET` | an extension line's block holds a line other than `set` | that line's name |

Codes that are no longer used, and never will be again: **E2006** (the old include path error, replaced by E3005),
**E3002** and **E3003** (the old include loop and depth errors, replaced by E5006 and E5007), **E2008** (a `{` on its
own line, allowed since a line break is whitespace) and **E4003** (a bad escape found when rendering, now E1005 found
by the parser). Every code but the readers' is in one list, `graph.diagnostics`, which the render shows unchanged. E6xxx is kept for the
high-level API, which is not built yet; none is defined.

## How the two languages differ

By design (each language's own way):

- TypeScript's `load`, `graph.read()`, `graph.save(writer)` and document sources are async (promises); Python's are
  plain calls. `render` and `diff` are plain calls in both.
- Readers have the same names in both (`word()`, `string()`, `number()`, `integer()`, `boolean()`, `list()`,
  `slice()`, `plain()`); `walk` is a method in both, taking a callback in TypeScript and returning a generator
  in Python; change kinds are a `kind` field in TypeScript and classes in Python.
- The key rule is an options object in TypeScript (`{ key }`) and a keyword argument in Python (`key=`).
- Misuse by a program is MisuseError in TypeScript and ValueError in Python.
- Python has no fetch source or fetch writer.

Both languages refuse an extension named `set`, `snippet` or `use`, or two extensions with one name, when the
processor is made (MisuseError in TypeScript, ValueError in Python).

## What is not tested

Speed on large trees, files that are not UTF-8, and the fetch source against a real server.
