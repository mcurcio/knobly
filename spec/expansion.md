# Expansion semantics

Status: normative, the one home of which definition a `$name` or a `use` reaches and which one wins (bead
vil-umh.2). The owner, 2026-10-29, round 15 question 2 ("Which variables may a program override, and what does an
included file see?"), picked: "Keep today's model and write it down in the spec". So this page describes the
behaviour both bindings had at milestone 3, exactly; it changes none of it. Where it reads as a rule nobody would
choose (section 8), that is today's model, written down, and changing it is a new question for the owner.

Milestone 5 (bead vil-umh.14) respells the statements this page speaks of: `@set`, `@snippet`, `@use` and an
extension's `@include` (spec 6.5); "a `set` line" here is the statement spelled `@set`. It adds one rule, a variable
as a slice's name (section 8). The scoping and precedence model is unchanged.

Pattern: CUE's "Declarations and scopes" (a block is a scope, a declaration is visible from where it is to the end
of its block, lookups go outward), plus nginx's order of walking. [spec.md](spec.md) 5, 6.6, 6.7 and 6.10 use this
page; [docs/language.md](../docs/language.md) teaches it with examples and links here.

## 1. Words

| Word | Meaning |
|---|---|
| definition | what a `$name` can reach: a `set` line's variable, a snippet's parameter, an include block's `set` line (an extension line's block, spec 5), or an override (spec 6.2) |
| environment | the definitions and snippets one walked block holds, and the environment it looks outward to (its parent) |
| walk | expansion's one pass over the files (section 2) |
| candidate | a definition of the name a lookup finds (section 5) |

These are the words of this page; the glossary lists them.

## 2. The walk

Expansion walks the root document's top-level statements in written order, depth first: a directive, then its
block, then the next statement. A `use` line is replaced, where it stands, by its snippet's body, walked there. An
extension line is replaced, where it stands, by the top-level statements of its files, walked there in splice order
(spec 4.1). A definition is made when its line is walked, so a `$name` reaches only definitions walked before it
(or in an enclosing environment, or an override).

Every lookup happens when its line is walked, against the environments as they are at that moment ("live"). Two
consequences, each pinned by a load case:

- A snippet's body, walked at a `use`, sees the `set` lines its defining block has walked by then, including ones
  written after the `snippet` line but before the `use` (`load-snippet-sees-later-set`).
- An included file sees the `set` lines of the including block walked before the include line, never one written
  after it (`load-include-sees-includer`: `u $b` with `@set $b` after the include line is E5001).

## 3. Environments

| Walked block | Its environment | Parent | Its top-level `set` and `snippet` lines define in |
|---|---|---|---|
| the root document's top level | a new one | none | itself |
| a directive's block | a new one | the enclosing environment | itself |
| a snippet's body, at one `use` | a new one, holding the parameters bound to the `use` line's values | the environment the `snippet` line was written in (lexical, not the `use`'s) | itself: a body exports nothing (`load-snippet-exports-nothing`) |
| an include line's block (only `set` lines, E5012) | a new one | the including environment | itself; the spliced files see these as include-block `set` lines |
| an included file's top level | the including environment, seen through a **splice view** that puts the include block's `set` lines in front | (the including environment's) | the including environment: visible after the include line (`load-include-exports`) |
| a block inside an included file | a new one | the splice view | itself |

## 4. One definition per name per environment

In one environment a name is set once (E5002, placed on the second `$name`) and a snippet is defined once (E5005, on
the second name). A nested environment may define the name again. The checks count:

- a parameter as its body's own `set` of the name: `set` of a parameter's name in the body itself is E5002;
- an included file's top-level `set` and `snippet` lines as the including environment's: one file included twice in
  one block defines its names twice (E5002 on the second copy's `$name`, `load-include-twice-same-block`);
- an include line's block on its own: its `set` lines never collide with the including block's.

When a name is set twice in one environment, the first `set` is the definition and the second defines nothing:
`@set $a 1; @set $a 2; x $a;` gives `x 1` (E5002 on the second, `load-var-set-twice`).

## 5. Lookup

A `$name` written in environment E finds its **candidates** by going outward from E, nearest first:

1. at each environment: its parameter of that name, then its `set` of that name;
2. at a splice view: its include-block `set` of that name, then on to the including environment;
3. last, an override of that name, which belongs to no environment and is a candidate everywhere.

A `@use name` finds the nearest snippet of that name the same way (snippets only: snippet names are their own
namespace, and directives of that name are never candidates). None is E5003 at the name.

## 6. Precedence: the one table

Among a `$name`'s candidates, the first row that applies wins:

| Rank | Candidate | Wins when | Pinned by |
|---|---|---|---|
| 1 | a parameter | it is the nearest candidate: no `set` and no include-block `set` is nearer | `load-snippet-param-beats-override`, `load-include-block-param` |
| 2 | an override | rank 1 does not apply | `load-var-override-wins`, `load-override-beats-include-block`, `load-scope-set-nearer-than-param`, `load-override-free` |
| 3 | an include-block `set` | there is no override: the nearest include-block `set`, over every `set` nearer or farther | `load-include-block-wins`, `load-include-block-wins-inner` |
| 4 | a `set` | none of the above: the nearest `set` | `load-var-basic`, `load-var-shadow`, `load-snippet-lexical` |

No candidate is E5001 at the `$name`, found by the low level. A resolution's `shadowed` (spec 6.7) lists the other
candidates in the order this table would pick them, each as if the ones before it were gone.

Rank 1 is decided by nearness alone: a parameter farther than a `set` does not win, and then an override does
(`load-scope-set-nearer-than-param`: in a snippet `s $p`, `t $p` reads the `use` line's value, while `u $p` inside a
block of the body that sets `$p` reads the override).

## 7. What an included file sees, and what an override reaches

An included file sees, at every depth inside it: the include block's `set` lines (rank 3), the including
environment as it is at the include line (section 2), and its own lines. Its top-level `set` and `snippet` lines
become the including block's, so the lines after the include line see them and the one-per-name checks count them.
It never sees a parameter of the including block unless the include line is in that snippet's body.

An override reaches every `$name` of its name, in every file and every copy, at any depth, unless a parameter is the
nearest candidate there (rank 1). An override needs no `set` line: a free `$name` resolves to it. An override is
never a declaration (spec 6.7), and it has no line to edit (spec 6.3 `set override`).

## 8. Values

- A `set` line's values are expanded at its line, in its environment: `@set $b $a;` holds `$a`'s values there.
- A `set` line's values are looked up before its own definition exists, so `@set $a $a;` reads an outer `$a`
  (`@set $a 1; b { @set $a $a; x $a; }` gives `x 1`, `load-var-set-reads-outer`) and, with none, is E5001
  (`load-var-set-reads-itself-top`).
- A `set` line whose values fail (E5001) defines nothing: a later `$name` of that name finds the next
  candidate outward. `@set $a 1; b { @set $a $nope; x $a; }` gives `x 1`, with one E5001 at `$nope`
  (`load-var-failed-set-shows-outer`); at the top level with nothing outward, `@set $a $nope; x $a;` is E5001 twice,
  at `$nope` and at `x`'s `$a` (`load-var-failed-set-top`).
- An include block's `set` values are expanded in the including environment (`@set $host $leds_host;`).
- A `use` line's values are expanded at the `use`, in its environment, and bound to the parameters by position; a
  variable holding two values counts as two (E5004 when the count differs).
- A `$name` is always every value its winner holds, never part of a word (spec 6.7, `reference resolution`). As a
  slice or index bound it must hold one integer word within the integer range (E4001). As a slice's or index's name
  (`$src[0~3]`, milestone 5: a variable may be subscripted wherever a name can stand, a snippet's parameter
  included) it must hold exactly one word (E4007); the slice is then that word's slice (`@set $src leds; a
  $src[0~3];` gives `a leds[0~3]`, `load-var-subscript`; `load-snippet-param-subscript`,
  `load-var-subscript-not-word`). The slice is read where it is written: its `origin` is the slice's own place, and
  the name's resolution is its reference's (spec 6.6), as for a bound.
- Only a statement written `@set`, `@snippet` or `@use` is a language statement (milestone 5, spec 6.5); a line
  `use epoll;` is a directive and takes part in none of these rules (`load-plain-keyword-directives`).

## 9. Stated costs (today's model, kept by the owner's pick)

- Included files leak their top-level `set` lines into the including block, and a file cannot be included twice in
  one block when it sets a name (round 15 review, "Language concepts"; `load-include-twice-same-block` pins it).
- An override is global by name: it beats every `set` and include-block `set` of its name at any depth, so two
  include copies cannot keep their own values for an overridden name.
- A snippet's body looks names up where the snippet is written, an included file where it is included: two scoping
  rules for two ways of reusing text.
- A `set` whose values fail defines nothing (section 8), so an outer `set` of the same name shows through silently:
  the only problem reported is the failing value, and the lines below read the outer value as if the inner `set`
  were not there.

Changing any of these is a language change, for the owner.
