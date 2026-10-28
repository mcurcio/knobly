# Round 12 brief: the real low-level layer (config as written, editable, saved back)

## The problem
PR 3 (merged 2026-10-28, merge cb08803) built `load()`: one tree with variables replaced, snippets used and
includes spliced in. The owner says that is the MIDDLE layer, wrongly named "low-level". The low-level layer, the
one below it, does not exist. Design it.

## Owner's words (binding; quote, never paraphrase as his)
- 2026-10-28: "you have incorrectly written the middle layer representation as if it were the low-level API. lets
  start there. consumers need to be able to see which files were included in a config load, what variables exist,
  and where they were overloaded. consumers should be able to manipulate/alter that data so that it can be written
  back to the source files"
- 2026-10-28, on a value that came from `$pixels`: "It depends if the integration program changes the `$pixels`
  variable itself, or if it instead changes `max_count` to no longer use the variable. both kinds of changes should
  be possible"
- 2026-10-28: "a rendered config tree is not something that we currently have. that seems like a medium layer
  between the low-level API (AST level?) and the high-level (idiomatic integrations)."
- 2026-10-24: "How will includes be round-tripped through modifications to an included subtree?"
- 2026-10-28: one `set` per name per block stays ("this seems alright").
- Earlier steers still standing (see requirements.md): lead with user code; idiomatic per language (TS and Python;
  Python takes inspiration from pydantic); include is an extension, not built in; nothing is locked until he likes
  the user APIs.

## Layer and scope
- Layer: system design of ONE layer, the low level (config as written). Show its domain model, its public
  interfaces as TypeScript and Python sketches, and the user code that calls them.
- Show how the middle layer (PR 3's rendered tree, to be renamed) sits on top of it: which concepts it reuses,
  and how a value in the rendered tree leads back to where it is written (the existing Origin steps).
- Out of scope: the high-level sugar; diff details (parked for the middle layer: his diff steers are in
  requirements.md); internals (caches, algorithms).

## What consumers must be able to do (from his words)
1. See which files a load read, and which include line pulled each one in.
2. See what variables exist: every `set`, where it is, which uses it reaches, and what wins over it (a nested block's
   `set`, an include line's block, a value the program hands in).
3. Change things and write them back to the source files, keeping comments and layout everywhere else:
   - change a variable itself (the `set` line, so every use changes);
   - change one use so it no longer uses the variable (`max_count $pixels;` becomes `max_count 2400;`);
   - change, add and remove directives and values in any file, including an included one.
4. Save: only changed files are written, through the program's writer (the core does no I/O).

## Read (code is evidence, not a template: the Architects rule)
- Merged code: /Volumes/Dock/Home/Code/villanelle/.claude/worktrees/consumer-api-build (same tree as main):
  ts/src/syntax/cst.ts (read-only token trees), ts/src/load/*, ts/src/graph/save.ts, py/src/villanelle/*,
  docs/language.md, docs/low-level-api.md, fixtures/rasl/ (real configs, including split/).
- Requirements and history: /Volumes/Dock/Home/Code/villanelle/.claude/worktrees/consumer-api/.claude/design/consumer-api/requirements.md
  (its last two sections are the newest).
- Prior art to name and weigh: tomlkit, ruamel.yaml (round-trip config editing), LibCST, recast (lossless editable
  trees), language-server symbol indexes (definitions and references).

## Caps
- At most 3 questions for the owner, each with a recommended option and the cost of each option.
- Briefing at frame level: 1-2 pages, user code first, TS sketches multiline and commented.
