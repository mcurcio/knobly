# The villanelle language

This page describes what a villanelle file may say, and what a program reads after loading it. It teaches; it is
not where the rules live. The grammar file [`grammar/Villanelle.g4`](../grammar/Villanelle.g4) is the specification
of the syntax, and [`spec/expansion.md`](../spec/expansion.md) is the specification of what a `$name`, a `@use` and
an included file reach and which definition wins. Where this page and those two differ, they win.

Every example below is taken from a file or a test that passes. The line under each example names it. "Excerpt"
means lines were left out; nothing was changed.

## A file is directives

A directive is a name, then values, then either `;` or a block in `{ }`. A block holds more directives. A line
break is a space like any other (as in nginx), so a long directive may wrap over several lines, and `;` is required
even on the last line of a file or block. `#` starts a comment that runs to the end of the line.

```conf
rescale r {
  range 0.0627
        0.922;
  clamp true;
}
```

Load case `load-wrapped-line`: `range` has two values. A forgotten `;` joins the next line's statement onto this one
(`b 2` then `c 3;` is one directive `b` with values `2 c 3`, case `load-missing-semicolon`); only a missing `;` before
the end of a block or file is an error (E2001).

A directive's name is a word that starts with a letter or one of `_ . / * ?`: never a digit, `-` or `@`, so a
wrapped number can never become a directive of its own (`0.922;` alone is E2001, syntax case `digit-name`). A
statement that starts with `@` is one of the language's own statements (`@set`, `@snippet`, `@use`) or an
extension's (`@include`); every other name is yours, `set`, `use` and `include` included (below).

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
tests (`ts/src/rendered/rasl.test.ts`, `py/tests/test_rasl.py`).

## Values

A directive's values come in five kinds:

| Kind | Written as | Example |
|---|---|---|
| word | letters, digits and `_ . / * ? - @`; after the first character also `# + :` | `sine`, `0.01`, `/var/www`, `color:hsl`, `07:30`, `00:1a:2b:3c:4d:5e` |
| string | `"..."` with six escapes, `\\` `\"` `\'` `\n` `\t` `\r` (any other escape is E1005); or `'...'`, raw: exactly the text typed, no escapes | `"10.0.60.30"`, `"*/2 * * * *"`, `'C:\new\x'` |
| list | `[` values separated by `,` `]`; may span lines, hold comments, and end with a `,` | `[0.04, 1, 0.5]` |
| slice | a word or a `$name` with `[start~end]`, either side may be left out (`[~]` is an error) | `hyperhdr_color[144~152]`, `c[144~]`, `$src[0~3]` |
| index | a word or a `$name` with `[n]` | `foo[1]`, `$src[1]` |

Values are separated by spaces, line breaks or comments. Two values written touching (`fps$x`, `a"b"`) are an error
(E2009), never joined.

A single-quoted string is raw, like a TOML literal string: a backslash is an ordinary character, so `'C:\new'` is
the text `C:\new` (a double-quoted `"C:\new"` would hold a line break). It cannot hold `'` or a line break; write a
double-quoted string for those.

`:` is an ordinary word character after a word's first character, so times, ports and MAC addresses are words
(`07:30`, `127.0.0.1:3000`). A slice's two bounds are separated by `~`, which is not a word character: `a[1~3]`.
(`a[1:3]` is a bad slice, E2007, because `1:3` is one word.)

Slice and index bounds must be whole numbers written without leading zeros (`0`, `12`, `-3`) or a `$name`. Any other
literal bound (`a[i]`, `a[1.5]`) is a syntax error, E2007, and a string escape other than the six is E1005: both are
found by the parser. A whole number beyond ±(2^53-1), or a variable whose value is not one whole number, is E4001,
found when the file is loaded.

A number or a boolean is a word that a program asks to read as one: `8080` and `true` are words until a reader
reads them, and nothing reads them on its own (there is no reader that guesses a word's kind). Quoting means text:
`"8080"` is a string, never a number (contract cases `number-quoted`, `boolean-quoted` in
`conformance/contract/cases.json`).

## Variables: `@set` and `$name`

`@set $name value...;` gives a name to one or more values. `$name` written as a value is replaced by all of them.

```conf
@set $pixels 2284;
```

```conf
    node DdpSink leds {
        target "10.0.60.30";
        fps 20hz;
        input_port pixels;
        max_count $pixels;
```

Excerpts of [`fixtures/rasl/family_room.conf`](../fixtures/rasl/family_room.conf). rasl reads `max_count 2284`.
The rasl tests also change the `@set` line to `2400` and check that the change list names exactly the two directives
that use `$pixels`.

The rules (the exact ones, with the one precedence table, are [`spec/expansion.md`](../spec/expansion.md)):

- **Where a `@set` is seen.** From its line to the end of the block it is written in, including nested blocks and
  everything spliced in below it. A `$name` before its `@set` is unknown.
- **One `@set` per name per block** (E5002, placed on the second `$name`). A nested block may set the same name again;
  inside that block its own value is used.
- **A variable is always a whole value.** `port $ports dev;` with `@set $ports 8080 443;` reaches the program as
  three values: `8080 443 dev`. In a list, `[$ports, 1]` becomes `[8080, 443, 1]`. (Test: "rule 4: $name as a
  value", "becomes all its values in a directive and in a list", `ts/src/rendered/rules.test.ts`.) A variable is never
  joined to other text: `fps$x` and `$x"y"` are two values touching (E2009; syntax conformance cases
  `var-touch-word` and `var-touch-string` in `conformance/variables.json`).
- **As a slice bound** a variable must hold one whole number: `a[0~$n]` with `@set $n 3;` is `a[0~3]`. Anything else
  is E4001.
- **As a slice's name** a variable must hold one word: `$src[0~3]` with `@set $src leds;` is `leds[0~3]`, and a
  snippet's parameter works the same way (load cases `load-var-subscript`, `load-snippet-param-subscript`). A string,
  a list or two values there is E4007 (`load-var-subscript-not-word`).
- **Values keep their kind.** `@set $b $a;` copies `$a`'s values (strings stay strings, lists stay lists).
- **An unknown name** (no `@set` above it, no override) is E5001 at the `$name`, and its directive is kept as
  unreadable (see below). It never quietly becomes nothing.
- **Overrides from the program win.** A program can give variables values when it loads a file (its `overrides`;
  rasl's `--set host=...`). An override wins over every `@set` of that name, at any depth and in every included
  file, so a `@set` acts as the default. It does not win over a snippet parameter that is the nearest definition: the
  value written on the `@use` line is used (load case `load-snippet-param-beats-override` in `conformance/load/`;
  [`spec/expansion.md`](../spec/expansion.md) 6 has the whole table).
- `$` inside a string is plain text; a `$` on its own is E1004; `$x 1;` is a syntax error, because a directive's
  name is a word (cases `var-in-string`, `var-lone-dollar`, `var-as-name`).
- Any other form of `@set` (no `$name`, no value, a block) is E5009 at `@set`.

```conf
@set $pixels 2284;
@set $leds_host "10.0.60.30";
```

Excerpt of [`fixtures/rasl/split/main.conf`](../fixtures/rasl/split/main.conf). Loaded with the override `leds_host` =
`"10.0.70.1"`, the `leds` sink's `target` reads `"10.0.70.1"`; loaded without it, `"10.0.60.30"` (test "splits one
sink file over two places, each with its own include-block values and the override host",
`ts/src/rendered/rasl.test.ts`).

## Snippets: `@snippet` and `@use`

A snippet is a named block of directives with parameters. `@use` puts a copy of its body where the `use` line is.

```conf
@snippet twinkle $source {
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
    node TwinkleEffect twinkle { @use twinkle rgb_150; }
```

```conf
    node TwinkleEffect white_twinkle { @use twinkle white_150; }
```

Excerpts of [`fixtures/rasl/family_room.conf`](../fixtures/rasl/family_room.conf). Each node reads the seven
directives of the body, with `connect rgb_150;` and `connect white_150;`.

The rules ([`spec/expansion.md`](../spec/expansion.md) has the exact ones):

- **Values bind parameters by position**, and the count must match exactly (E5004 at `@use`). A variable holding two
  values counts as two.
- **A snippet is seen** from its line to the end of its block, like a `@set`. One definition per name per block
  (E5005, at the second name).
- **Snippet names are their own namespace.** `@use universe;` looks only for a snippet called `universe`, never at a
  directive of that name.
- **The body sees the variables where the snippet is written**, plus its parameters; never the variables of the
  block where it is used. It sees a `@set` written after the snippet but before the `use`.
- **A body exports nothing.** A `set` or `snippet` inside a body is seen only inside it.
- A parameter is the body's own variable: `@set` of a parameter's name in the body is E5002. An override from the
  program or a `@set` in an include line's block never replaces a parameter (load cases `load-snippet-param-beats-override`
  and `load-include-block-param`).
- An unknown snippet name is E5003, at the name. Any other form of `snippet` (no name, no block, a parameter written
  twice) is E5010 at `@snippet`; a `@use` with a block or a name that is not a word is E5011 at `@use`.
- A problem inside a body is reported at each `use` of it, and its place says which `use` brought it there.

Tests: "rules 5 and 6: snippet and use" in `ts/src/rendered/rules.test.ts`; the snippet tests in `py/tests/test_load.py`.

## Including files: an extension

Including is not built into the language. It is an **extension** that a program turns on when it makes its
processor (`include()` from `villanelle/include` in TypeScript, `villanelle.include` in Python). An extension's
statement is written with `@`: with the include extension, `@include "path";` puts the top-level directives of the named file where the line is. The path is relative to
the including file. A `*` or `?` in the last part of the path matches several files, which are spliced in code-point
order of their paths. Without the extension, `@include` is E3008 (no extension for this `@name`, load case
`load-unknown-extension`), and `include "x.conf";` without `@` is always an ordinary directive named `include`
(`load-include-is-a-directive`).

```conf
    @include "sink.conf" {
        @set $name leds;
        @set $host $leds_host;
    }

    @include "sink.conf" {
        @set $name porch;
        @set $host "10.0.60.31";
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

The rules ([`spec/expansion.md`](../spec/expansion.md) 3, 4 and 7 say exactly what an included file sees):

- **A file is read once per load**, however many places include it, and its syntax errors are reported once. Each
  place gets its own copy of the directives, with its own variables.
- **The include line's block may hold only `@set` lines** (E5012 at the first other line). They set variables for the
  included file and win over every `set` of the same name in it, also inside its blocks (load case
  `load-include-block-wins-inner`), but not over a snippet parameter. After the include line, the including block
  sees the file's own `set` values, not the block's. E5012 is placed on the other line's name, and the include line
  is kept unreadable with kind `extension` (case `load-include-block-not-set`).
- **An included file's top-level `@set` and `@snippet`** are seen after the include line in the including block, and
  count for that block's one-per-name checks: a file that sets a name cannot be included twice in one block (E5002,
  load case `load-include-twice-same-block`). The file sees the including block's `set` lines written before the
  include line, not after (`load-include-sees-includer`).
- **A file added by an edit is not read until the program asks** (`read()`): until then the include line renders as
  an unreadable statement with reason `unread` and E3007, so a change list calls what it held `unknown`, not
  removed.
- `@include` takes exactly one quoted path (E3005, on the first value when it is not quoted, else on the second
  value, or on `@include` when there is none; case `load-include-extra-path`). A path that matches no file is E3001,
  and a source that fails to read is E3004, both at `@include`.
- A program can write its own extensions. One that fails with anything but a located error gives E3006.

Tests: "rules 7 and 8: extension directives and their blocks" in `ts/src/rendered/rules.test.ts`; the include tests in
`py/tests/test_load.py`.

## No reserved names

Only a statement that starts with `@` is the language's or an extension's: `@set`, `@snippet`, `@use`, and
`@include` with the include extension. Every other statement is a directive, whatever its name, so a config may use
the words for its own directives (`events { use epoll; }` is a directive `use` with the value `epoll`; load case
`load-plain-keyword-directives`). An `@name` that is none of these is E3008 at the `@name`, and the statement is
kept unreadable. A word that starts with `@` anywhere but at a statement's start is an ordinary word value
(`cron @daily;`).

## Limits

Shared by `@use` and included files:

- A snippet or file that reaches itself again is E5006, placed on the `@use` or `@include` that closes the loop.
- Up to 16 snippets or included files may be open inside each other; the 17th is E5007. The root file is not counted.
- More than 100,000 directives after expansion is E5008, and the load stops expanding there.
- Blocks and lists may nest 100 deep in one file; deeper is E2010.

## When a statement is broken

The parser reads a broken statement as one unreadable statement up to its `;` (or to the end of a block it opens),
so the statements after its `;` are still read. An unterminated string runs to the end of its line, and the
statement it is in then runs to the next `;`, which may be on a later line (syntax case `unterminated`).

## When a line cannot be read

A broken line never hides its neighbours. A statement that fails a rule above, or that the parser could not read,
stays in its place as an **unreadable** statement, so a program can tell "this block is incomplete" from "this
directive was removed". Its block is not expanded, so problems inside it are not reported.

A file with problems still loads: every problem is a diagnostic with a code and a place, and the rest of the file is
read. Diagnostics come in this order: each file's syntax problems (files in the order they were first read), then
the load's problems in the order the load met them.

## Error codes

Every code, with where it is placed, is listed in the [rendered-tree reference](rendered-tree.md#error-codes).
