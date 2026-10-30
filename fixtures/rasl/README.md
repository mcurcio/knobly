# rasl's real configs, for the low-level API's tests

These are rasl's own configuration files, kept here so each language's tests load a real file through the file
source and the include extension (owner answer kno-m8w.5, 2026-10-23: "Neutral here, real ones to rasl
(Recommended)": the neutral cases live in `conformance/`, these do not). No conformance runner reads them.

| File | What it is |
|---|---|
| `family_room.conf` | rasl's `family_room.conf`, written with `@set $pixels` and `@snippet twinkle` where the file repeated itself |
| `hyperhdr.conf` | rasl's `hyperhdr.conf`, written with `@set $pixels` and `@snippet byte_console` (a snippet value that is a slice) |
| `split/main.conf`, `split/sink.conf` | a small rasl graph whose DDP sink is one file included at two places, each include block giving its own `$name` and `$host`; `$leds_host` has a default `@set` in `main.conf` and is meant to be handed in as well |
| `expected.json` | what a load of each must give (below) |

## Differences from the syntax rasl reads today

Since knobly's milestone 5 the files also use its spellings where rasl's differ: `@set`, `@snippet`, `@use` and
`@include` for the language and extension statements, and `~` between a slice's bounds (`hyperhdr_color[144~152]`,
where rasl writes `[144:152]`); commented-out lines were respelled the same way.

The two real files were copied from rasl's working tree (`family_room.conf`, `hyperhdr.conf`) and changed only
where the file repeated itself:

| Difference | Where | Effect on what rasl reads |
|---|---|---|
| `@set $pixels 2284;` at the top; `max_count`, `repeat_until` and `channel_count` say `$pixels` instead of `2284` | both files | none: each reaches rasl as `2284` |
| `@snippet twinkle $source { ... }` and `@use twinkle rgb_150;` / `@use twinkle white_150;` replace two copies of a six-line block | `family_room.conf` | none: the same directives, in the same order, reach each node |
| `@snippet byte_console $source { ... }` and `@use byte_console hyperhdr_color[144~152];` replace two copies of a three-line block | `hyperhdr.conf` | none; the variable's value is a slice |
| `20 hz` (two words) was joined into `20hz` by rasl's TypeScript reader | both files write `20hz` | none |
| rasl's Python reader read `on`, `yes`, `off`, `no` as booleans | only `true` is written | none; only `true` and `false` are booleans |
| `x[3]` was read as `x[3:4]` by rasl's Python reader | not written | an index is its own kind of value |
| rasl's TypeScript reader ignored includes | written only in `split/` | an include is spliced in where it is written |

## expected.json

For each fixture (the key is its path under `fixtures/rasl/`, loaded with the include extension and the `"rasl"` key
rule of `conformance/load/format.md`):

- `nodes`: the id (second value) of each `node` directive directly in `graph`, in walk order;
- `diagnostics`: the load's diagnostics as `[code, origin]` (none for these files);
- `changes`: `[kind, address]` for each change from a second load of the same processor in which
  `@set $pixels 2284;` is replaced by `@set $pixels 2400;`, addresses in the people form.

`split/main.conf` gives the same result with or without a handed-in `leds_host`.
