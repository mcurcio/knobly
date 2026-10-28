# final-py: a directive is a dataclass (round 10 winner, polished)

**Model:** stdlib `dataclasses`, applied the way attrs `@frozen` applies it: a decorator (no base
class) makes a frozen dataclass; `typing.dataclass_transform` tells the checkers. Refs:
[dataclasses](https://docs.python.org/3/library/dataclasses.html) (`KW_ONLY`, `field`,
`metadata`, `__post_init__`), [PEP 681](https://peps.python.org/pep-0681/) (field specifiers),
[attrs](https://www.attrs.org/en/stable/api.html).

**The one idea:** a record's fields are what is written. Before `_: KW_ONLY`: the values, in
written order. After it, written by name: a `bool` is a flag word, a field typed with a directive
is a line of the block, a tuple of plain records makes the block plain lines. A value's rules sit
on its field (`vl.field`). The instance is what the line builds.

## Changes from py-dataclass

1. **The one allowed graft:** `vl.field(doc=, min=, max=, key=True)`, the dataclass
   field-specifier idiom, replaces the `Annotated` markers `vl.Range` and `vl.Key`.
2. **Same reason:** `vl.Lines[L]` (an `Annotated` marker too) is gone: after `KW_ONLY`,
   `tuple[MimeLine, ...]` (a plain dataclass) or `tuple[str, ...]` is a block of plain lines.
   Three names fewer; user code imports no `Annotated`.
3. **Fix, the default lives once:** a holder writes `fps: Fps` with no default; giving one is a
   startup error (`planted/startup.py` s13, the judge's break). Filled from: written here, else
   the nearest enclosing block, else `Fps()` (None for `Timeout | None`). `evidence/runtime.txt`:
   no `fps` written anywhere, and graph, group and node all read 30hz.
4. **Fix, key uniqueness:** a second sibling with the same key in one holder field is
   `vl/duplicate-key` at its line; the same id in another block is allowed (`runtime.txt`).

## Concepts a dataclass user learns: 13

1 `@vl.directive` · 2 values before `KW_ONLY` · 3 after it: flag / child (tuple: repeats) /
plain lines · 4 `vl.field(doc=, min=, max=, key=)` · 5 value types: `int float str Literal
vl.Word`, or your own `@vl.value` with `parse` · 6 `inside=` · 7 `select=Protocol` + a
Protocol-typed field · 8 `inherit=` (holder writes no default), `restart=` · 9 `__post_init__` +
`vl.ConfigError(at=, code=)` · 10 `vl.Package` · 11 `@vl.file` · 12 `vl.Config(File, packages=)`,
`load` -> `Accepted | Rejected` · 13 `changes.of(D)`, `applied(handles=, failures=)`.
Same count as py-dataclass; names dropped: `Range`, `Key`, `Lines`.

## Where dataclasses had no idiom

- What a field means to the language: read from `KW_ONLY` plus the type, lazily at `Config(...)`.
- Placing into another package's block: `inside=[webby.Server, webby.Location]`; no field
  holds it, so its own module reads `changes.of(Gzip)`.
- Select: a `Protocol`-typed field takes a word naming a directive declared `select=` it.
- `inherit`, `restart`, `Package`, `@vl.file`, `@vl.value`'s `parse`: no dataclass precedent.

## Checkers (pyright 1.1.407 strict, mypy 1.18.2 --strict, Python 3.11; `run.sh`)

Good code, probe_types, not_caught, startup.py: **pyright 0, mypy 0**.

| Planted | pyright | mypy |
|---|---|---|
| p01 bad default, int for `Rate`, int for a port tuple | 3/3, exit 1 | 3/3, exit 1 |
| p02 misspelled flag read, child read via Protocol, Literal word | 3/3, exit 1 | 3/3, exit 1 |
| p03 optional child read unchecked; assigning to a built record | 2/2, exit 1 | 2/2, exit 1 |
| p04 a required value after an optional one | 1/1, exit 1 | 1/1, exit 1 |
| p05 rejected load read; `.value` on a removal; Node change as Group | 3/3, exit 1 | 3/3, exit 1 |

All 14 mistakes in `startup.py` are caught when `Config(...)` runs (`evidence/startup-run.txt`);
new: s13 holder overrides an inheriting default, s14 `key=True` after `KW_ONLY`.

**Nothing catches before load** (`not_caught.py`): a flag written before `KW_ONLY`; a misspelled
`ConfigError(at="xx")`; webby's `root` held in a rasl graph block (accepted).

## Costs

- A node type is held to its Protocol only at startup, not by the checkers
  (`evidence/probe-select-static.txt`, from py-dataclass's `probe/`, kept unchanged).
- The record is also the domain type; a program wanting its own types maps them itself.
- One-value directives are records: reads unwrap (`graph.fps.rate`, `leds.target.host`).
- An inheriting field has no default, so the constructor requires it: hand-built records
  (tests) pass `Graph(fps=Fps())`. `timeout: Timeout | None` without `= None` looks odd.
- `tuple[str, ...]` after `KW_ONLY` means plain lines; a newcomer may read it as a value list
  (a non-`str`, non-record tuple there is still rejected at startup).
- `vl.Word` subclasses `str`; `_: KW_ONLY` is imported from `dataclasses`; a field's name is not
  what is written (`inputs` holds `connect` lines).
- A select member or `inside=` directive left out of its `Package` is unknown at load.

## Open for the owner (not adopted silently)

1. A holder's field is the permission to write a directive there: a directive's author can no
   longer stop another package from holding it.
2. Repetition belongs to the holder's field (`tuple[D, ...]`), not `many=` on the directive.
3. No scope objects: "a group holds what a graph holds" is two field lists, plus
   `rasl.GRAPH_BLOCKS = (Graph, Group)` for third parties.
4. New here: a holder can no longer give an inheriting directive its own default.

**NOT RUN:** a parser load; variables, snippets, include; diffing (`Changed`/`Replaced`/`Removed`);
value-column spans; Python other than 3.11; ruff; editor hovers; rasl's 15 real node types.
