# The villanelle language

This page describes what a villanelle file may say, and what a program reads after loading it. The grammar file
[`grammar/Villanelle.g4`](../grammar/Villanelle.g4) is the specification of the syntax; this page explains it in
plain words and adds the rules the load applies (variables, snippets and included files).

Every example below is taken from a file or a test that passes. The line under each example names it. "Excerpt"
means lines were left out; nothing was changed.

## A file is directives

A directive is a name, then values, then either `;`, the end of the line, or a block in `{ }`. A block holds more
directives. `#` starts a comment that runs to the end of the line.

```conf
graph {
    # Sawtooth wave for uniform hue cycling (rainbow effect)
    # Unlike sine, sawtooth gives equal time to each hue
    node Waveform hue_ramp {
        shape sine;
        frequency_hz 0.01;
        output_channels 150;
        fps 30;
    }
```

Excerpt of [`fixtures/rasl/family_room.conf`](../fixtures/rasl/family_room.conf), loaded by both languages' rasl
tests (`ts/src/load/rasl.test.ts`, `py/tests/test_rasl.py`).

## Values

A directive's values come in five kinds:

| Kind | Written as | Example |
|---|---|---|
| word | letters, digits and `_ . / @ * ? -`; after the first character also `# + :` (a word that starts with a digit or `-` cannot hold `:`) | `sine`, `0.01`, `/var/www`, `color:hsl` |
| string | `"..."` or `'...'`, with six escapes: `\\` `\"` `\'` `\n` `\t` `\r` | `"10.0.60.30"`, `"*/2 * * * *"` |
| list | `[` values separated by `,` `]`; may span lines, hold comments, and end with a `,` | `[0.04, 1, 0.5]` |
| slice | a word with `[start:end]`, either side may be left out (`[:]` is an error) | `hyperhdr_color[144:152]`, `c[144:]` |
| index | a word with `[n]` | `foo[1]` |

Values are separated by a space or a comment. Two values written touching (`fps$x`, `a"b"`) are an error (E2009),
never joined.

Slice and index bounds must be whole numbers written without leading zeros, within ±(2^53-1). Anything else is
E4001, found when the file is loaded. A string escape other than the six is E4003, also found at load.

A number or a boolean is a word that a program asks to read as one: `8080` and `true` are words until a reader
reads them. Quoting means text: `"8080"` is a string, never a number. The test "plain: one rule for every value;
quoting means text" (`ts/src/load/readers.test.ts`) and `test_plain_reads_by_the_one_rule_quoting_means_text`
(`py/tests/test_readers.py`) show this rule for every kind.

## Variables: `set` and `$name`

`set $name value...;` gives a name to one or more values. `$name` written as a value is replaced by all of them.

```conf
set $pixels 2284;
```

```conf
    node DdpSink leds {
        target "10.0.60.30";
        fps 20hz;
        input_port pixels;
        max_count $pixels;
```

Excerpts of [`fixtures/rasl/family_room.conf`](../fixtures/rasl/family_room.conf). rasl reads `max_count 2284`.
The rasl tests also change the `set` line to `2400` and check that the change list names exactly the two directives
that use `$pixels`.

The rules:

- **Where a `set` is seen.** From its line to the end of the block it is written in, including nested blocks and
  everything spliced in below it. A `$name` before its `set` is unknown.
- **One `set` per name per block** (E5002, placed on the second `$name`). A nested block may set the same name again;
  inside that block its own value is used.
- **A variable is always a whole value.** `port $ports dev;` with `set $ports 8080 443;` reaches the program as
  three values: `8080 443 dev`. In a list, `[$ports, 1]` becomes `[8080, 443, 1]`. (Test: "rule 4: $name as a
  value", "becomes all its values in a directive and in a list", `ts/src/load/rules.test.ts`.) A variable is never
  joined to other text: `fps$x` and `$x"y"` are two values touching (E2009; syntax conformance cases
  `var-touch-word` and `var-touch-string` in `conformance/variables.json`).
- **As a slice bound** a variable must hold one whole number: `a[0:$n]` with `set $n 3;` is `a[0:3]`. Anything else is
  E4001. A variable is never the word in front of `[`: `$x[0:3]` is a syntax error (case `var-slice-base`).
- **Values keep their kind.** `set $b $a;` copies `$a`'s values (strings stay strings, lists stay lists).
- **An unknown name** (no `set` above it, nothing handed in) is E5001 at the `$name`, and its directive is kept as
  unreadable (see below). It never quietly becomes nothing.
- **Values handed in by the program win.** A program can pass variables when it loads a file (rasl's
  `--set host=...`). A handed-in value wins over every `set` of that name, so a `set` acts as the default. It does
  not win over a snippet parameter: the value written on the `use` line is used (load case
  `load-snippet-param-beats-handed` in `conformance/load/`).
- `$` inside a string is plain text; a `$` on its own is E1004; `$x 1;` is a syntax error, because a directive's
  name is a word (cases `var-in-string`, `var-lone-dollar`, `var-as-name`).
- Any other form of `set` (no `$name`, no value, a block) is E5009 at `set`.

```conf
set $pixels 2284;
set $leds_host "10.0.60.30";
```

Excerpt of [`fixtures/rasl/split/main.conf`](../fixtures/rasl/split/main.conf). Loaded with `leds_host` handed in as
`"10.0.70.1"`, the `leds` sink's `target` reads `"10.0.70.1"`; loaded without it, `"10.0.60.30"` (test "splits one
sink file over two places, each with its own include-block values and the handed-in host",
`ts/src/load/rasl.test.ts`).

## Snippets: `snippet` and `use`

A snippet is a named block of directives with parameters. `use` puts a copy of its body where the `use` line is.

```conf
snippet twinkle $source {
    seed 11337;
    mode brightness;
    frequency_hz 0.3;
    attack_ratio 0.33;
    min_speed 1.0;
    max_speed 3.0;

    connect $source;
}
```

```conf
    node TwinkleEffect twinkle { use twinkle rgb_150; }
```

```conf
    node TwinkleEffect white_twinkle { use twinkle white_150; }
```

Excerpts of [`fixtures/rasl/family_room.conf`](../fixtures/rasl/family_room.conf). Each node reads the seven
directives of the body, with `connect rgb_150;` and `connect white_150;`.

The rules:

- **Values bind parameters by position**, and the count must match exactly (E5004 at `use`). A variable holding two
  values counts as two.
- **A snippet is seen** from its line to the end of its block, like a `set`. One definition per name per block
  (E5005, at the second name).
- **Snippet names are their own namespace.** `use universe;` looks only for a snippet called `universe`, never at a
  directive of that name.
- **The body sees the variables where the snippet is written**, plus its parameters; never the variables of the
  block where it is used. It sees a `set` written after the snippet but before the `use`.
- **A body exports nothing.** A `set` or `snippet` inside a body is seen only inside it.
- A parameter is the body's own variable: `set` of a parameter's name in the body is E5002. A value handed in by the
  program or set in an include line's block never replaces a parameter (load cases `load-snippet-param-beats-handed`
  and `load-include-block-param`).
- An unknown snippet name is E5003, at the name. Any other form of `snippet` (no name, no block, a parameter written
  twice) is E5010 at `snippet`; a `use` with a block or a name that is not a word is E5011 at `use`.
- A problem inside a body is reported at each `use` of it, and its place says which `use` brought it there.

Tests: "rules 5 and 6: snippet and use" in `ts/src/load/rules.test.ts`; the snippet tests in `py/tests/test_load.py`.

## Including files: an extension

Including is not built into the language. It is an **extension** that a program turns on when it makes its
processor (`include()` from `villanelle/include` in TypeScript, `villanelle.include` in Python). Without it,
`include "x.conf";` is an ordinary directive named `include`.

With it, `include "path";` puts the top-level directives of the named file where the line is. The path is relative to
the including file. A `*` or `?` in the last part of the path matches several files, which are spliced in code-point
order of their paths.

```conf
    include "sink.conf" {
        set $name leds;
        set $host $leds_host;
    }

    include "sink.conf" {
        set $name porch;
        set $host "10.0.60.31";
    }
```

Excerpt of [`fixtures/rasl/split/main.conf`](../fixtures/rasl/split/main.conf). It includes one file at two places.

```conf
node DdpSink $name {
    target $host;
    fps 20hz;
    input_port pixels;
    max_count $pixels;

    connect crossfade_rgb pixels;
}
```

Excerpt of [`fixtures/rasl/split/sink.conf`](../fixtures/rasl/split/sink.conf). The program reads two nodes,
`leds` and `porch`, each with its own `target`.

The rules:

- **A file is read once per load**, however many places include it, and its syntax errors are reported once. Each
  place gets its own copy of the directives, with its own variables.
- **The include line's block may hold only `set` lines** (E5012 at the first other line). They set variables for the
  included file and win over every `set` of the same name in it, also inside its blocks (load case
  `load-include-block-wins-inner`), but not over a snippet parameter. After the include line, the including block
  sees the file's own `set` values, not the block's. E5012 is placed on the other line's name, and the include line
  is kept unreadable with kind `extension` (case `load-include-block-not-set`).
- **An included file's top-level `set` and `snippet`** are seen after the include line in the including block, and
  count for that block's one-per-name checks.
- `include` takes exactly one quoted path (E3005, on the first value when it is not quoted, else on the second value,
  or on `include` when there is none; case `load-include-extra-path`). A path that
  matches no file is E3001, and a source that fails to read is E3004, both at `include`.
- A program can write its own extensions. One that fails with anything but a located error gives E3006.

Tests: "rules 7 and 8: extension directives and their blocks" in `ts/src/load/rules.test.ts`; the include tests in
`py/tests/test_load.py`.

## Reserved names

At the start of a statement, in every block, `set`, `snippet` and `use` are always reserved, and so is the name of
every extension the program has turned on (`include` with the include extension). They never reach the program as
directives; what they produce does. (Test: "rule 1: reserved names", `ts/src/load/rules.test.ts`.)

## Limits

Shared by `use` and included files:

- A snippet or file that reaches itself again is E5006, placed on the `use` or `include` that closes the loop.
- Up to 16 snippets or included files may be open inside each other; the 17th is E5007. The root file is not counted.
- More than 100,000 directives after expansion is E5008, and the load stops expanding there.
- Blocks and lists may nest 100 deep in one file; deeper is E2010.

## When a line cannot be read

A broken line never hides its neighbours. A statement that fails a rule above, or that the parser could not read,
stays in its place as an **unreadable** statement, so a program can tell "this block is incomplete" from "this
directive was removed". Its block is not expanded, so problems inside it are not reported.

A file with problems still loads: every problem is a diagnostic with a code and a place, and the rest of the file is
read. Diagnostics come in this order: each file's syntax problems (files in the order they were first read), then
the load's problems in the order the load met them.

## Error codes

Every code, with where it is placed, is listed in the [low-level API reference](low-level-api.md#error-codes).
