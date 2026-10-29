# Generating a binding's basics from one schema

**Status: a proposal, not built. It waits for the owner's decision.** Nothing on this page exists in
the repo yet. It follows the round 13 review
([review.md, root cause 5](../../.claude/design/consumer-api/round13/review.md#root-cause-5-no-neutral-spec-and-nothing-generated-from-one-source)).

## The problem

Every fixed list in villanelle is typed out by hand in each binding and again in the docs:

- 32 diagnostic codes with names and messages (`ts/src/diagnostics.ts`, messages in
  `ts/src/syntax/recovery.ts`; Python's
  `py/src/villanelle/diagnostics.py` says it "mirrors the TypeScript package's registry value for
  value");
- about 9 kind lists (token, node, statement, value, variable, step, unreadable, change, place);
- 4 limits and the reserved names;
- each binding's conformance runner, about 300 lines each.

A third binding would copy all of it a third time, and nothing checks that the copies agree except
the shared cases, which do not cover every list. The parser already avoids this: `tools/gen.sh`
generates both parsers from `grammar/Villanelle.g4`, and the token kind names come from the grammar.
This proposal does the same for the API's fixed lists.

## What could be generated

| Piece | From | Gives each binding |
|---|---|---|
| Kind lists | the schema's closed sets | TypeScript: a string-literal type per list. Python: a `StrEnum` per list. Go: a typed string and a `const` block. The values are the spec's lowercase words |
| Per-kind type skeletons | statement, value, change and `plain` kinds, each mapped to the type it gives | TypeScript: the union members. Python: one class per kind with `__match_args__` in a fixed field order. Go: a sealed interface and one struct per kind. Bodies stay hand-written |
| Member signatures | each type's members (below) | the public-name check, and for a language with error values, which members return `(T, error)` and which take a context |
| Diagnostic code registry | `diagnostics.json`: code, spec name, message, owning layer, found by, unreadable kind, placement rule, retired codes | the code constants, the message table, and the code table in [spec.md 2.4](spec.md#24-the-diagnostic-code-registry) |
| Conformance tokens | the token-to-spec-name table of `conformance/written/format.md` | each runner's op and error mapping |
| Limits and reserved names | the schema | constants |
| Plain data records | place, span, position, step, origin, address step, file write | read-only records (TypeScript interfaces, Python frozen slotted dataclasses) |
| Conformance driver | the three case formats under `conformance/` | one shared driver, plus a small adapter interface each binding fills in: load files, find a target, apply one operation, dump the result |
| Public-name check | the schema's concepts and members, and each binding's casing rule | a test that lists the binding's exports and fails on a name the schema does not have, or a missing one |

Generated files are not committed, as with the parser (owner, 2026-10-23: "Don't commit the
generated code, just the source"). Build and test regenerate them.

## What stays hand-written

- The algorithms: binding variables and snippets, edits and where text goes, render, diff. The
  shared cases check them; generating them would cost more than writing them.
- Everything that makes a binding feel native: async or sync, iteration, error classes, options,
  module layout, docs and examples. The owner wants each binding idiomatic. On JSON Schema as a way
  to declare configuration, he said "it can't be the only one because it is not conducive to
  building natural APIs that are idiomatic in each target language" (2026-10-26). The same holds
  for generating an API: generating only fixed lists and data records keeps that line.

## Schema format options

The schema has to describe closed lists of words, records with a few field types, and a table of
codes. It is read by small generators at build time and never shipped.

| Option | What it is | Fit for villanelle | Cost |
|---|---|---|---|
| **JSON data checked by a JSON Schema** | Hand-written `api.json` and `diagnostics.json`, with a JSON Schema that checks their shape | Good. Every language reads JSON with its standard library, so a generator needs no extra tools. The owner: "JSON scheme is a nice foundation, where it works." (2026-10-25) | The generators are small scripts written by hand, one template per language |
| tree-sitter `node-types.json` | A file tree-sitter writes from a grammar, listing node types and their fields | Good prior art for the shape of a kinds list, and the model for deriving node kinds from the grammar | Made by tree-sitter from its own grammar, so not directly usable with the ANTLR grammar |
| TypeSpec | Microsoft's language for describing APIs, emitting OpenAPI and others | Overkill: aimed at HTTP services, needs Node and its compiler | A new tool and language for 3 small lists |
| Smithy | Amazon's interface language for services and SDKs | Powerful code generators, but built around services and operations over a network | Java toolchain, service-shaped model |
| Protocol Buffers | Google's schema for messages on the wire | Generates records and enums in many languages | Its records are wire messages, not the read-only handles villanelle needs; it brings a runtime library, against the no-third-party-dependency rule (2026-10-25) |
| WebIDL | The browser's interface language | Describes objects and methods precisely | Browser and JavaScript centred; no mainstream Python generator |

### Recommendation

Use **JSON data files checked by a JSON Schema**, with one small generator per language:

```text
docs/bindings/schema/          # or spec/schema/ if the owner prefers the review's layout
  api.schema.json              # the JSON Schema that checks the two files below
  api.json                     # kind lists, records and their fields, limits, reserved names,
                               # each concept's spec name and its members (property or method)
  diagnostics.json             # code, spec name, message, owning layer, retired codes
tools/gen-api.sh               # runs each language's generator; output git-ignored, like gen.sh
```

What `api.json` carries, so that a binding unlike TypeScript and Python (the Go review's list) can be
planned from it:

- per type: `layer` (shared, syntax, written, rendered), and `nature`: `handle` (one object per
  thing, identity holds, may detach), `snapshot` (plain data from one working-out) or `record`
  (plain data); the layer direction then follows (a type may name only its own layer or a lower one);
- per member: `kind` (`property`, `method` or `factory`), parameters with whether each is optional,
  the result type with whether it may be absent and whether empty text counts as present, `errors`
  (the error groups of spec 2.8 it can raise), `io` (true when it goes through a port, so it may be
  asynchronous or take a context), `detachable`, and `order` (the stated order of a returned list,
  as text, or the spec section that states it);
- per number: its range (`integer`: ±(2^53-1)).

A sketch of `diagnostics.json`:

```json
{
  "retired": ["E2006", "E3002", "E3003"],
  "codes": [
    {
      "code": "E1001",
      "name": "unterminated string",
      "layer": "syntax",
      "foundBy": ["parse"],
      "unreadableKind": "syntax",
      "message": "unterminated string"
    }
  ]
}
```

A binding's generator turns `"unterminated string"` into its casing (`UnterminatedString`,
`UNTERMINATED_STRING`) by the same rule as every other spec name
([design-guide.md, rule 1](design-guide.md#2-naming-and-structure-rules-proposed-pending-owner)).

Why this one: it needs no new toolchain, it is plain data any language can read, and it matches the
size of the problem. The other formats are built to describe network services or whole APIs, which
is more than villanelle needs and pulls the bindings toward one generated shape. tree-sitter's
`node-types.json` is the model for the kinds part.

What it gives up: no ready-made generators, so each language's template is written by hand once
(roughly a page each). The schema does not describe the handles' behaviour, so the spec and the
shared cases still carry that.

## Questions for the owner

1. Build this, or keep copying the lists by hand with a test that compares them?
2. Where does the schema live: `docs/bindings/schema/` beside this spec, or the review's `spec/`
   folder?
3. Should the public-name check fail the build (the review's proposal), or only report?
