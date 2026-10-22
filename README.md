# villanelle

A small configuration language: directives, `{ }` blocks, lists and slices, with `#` comments.

```conf
# comments start with '#'
server {
  listen 8080;
  include /etc/app/*.conf
}
connect sensor[0:3] output
```

## The language is defined by one file

[`grammar/Villanelle.g4`](grammar/Villanelle.g4) (ANTLR4) is the specification. ANTLR4
generates the TypeScript and Python parsers from it, so both parsers accept exactly the
grammar's language. [`grammar/villanelle.ebnf`](grammar/villanelle.ebnf) is the same grammar
in W3C EBNF, kept as a readable view.

The grammar is checked to be unambiguous, so every valid file has exactly one parse:

```bash
tools/check.sh
```

The script runs three checks:
- it translates the parser rules to Bison and requires 0 conflicts;
- it checks that no two token kinds can match the same text;
- it confirms that both checks still catch the planted bad grammars in `tools/planted/`.

It needs `python3`, `bison` and `uv`.

## Layout

| Path | What it is |
|---|---|
| `grammar/` | The grammar (`Villanelle.g4`) and its EBNF view |
| `tools/` | The soundness checks and the planted bad grammars they must catch |
| `conformance/` | Test cases every parser must pass. The expected-output format is still to be fixed |
| `design/` | The design record ([`design/RECORD.md`](design/RECORD.md)), drafts, reviews and experiments |

## Status

Design. No packages are published yet. The design was done in
[mcurcio/rasl#2](https://github.com/mcurcio/rasl/pull/2), where this language began as `@rasl/config`.
