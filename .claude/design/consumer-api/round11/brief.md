# Round 11 brief: the low-level consumer API (R15 tiers 1-2)

D = /Volumes/Dock/Home/Code/villanelle/.claude/worktrees/consumer-api/.claude/design/consumer-api/
Repo = /Volumes/Dock/Home/Code/villanelle/.claude/worktrees/consumer-api/ (ts/, py/, grammar/, design/, reference/)

## Where we are (owner, 2026-10-28)
He approved the language features and design (page v10: D/briefing-v10.md, configs in D/briefing-v9.md §1)
and said yes to building the LOW-LEVEL API first, deferring the high-level sugar. His doubt, verbatim:
"it’s not clear how practical these APIs are for a real integration." This round answers it with real
integration code. Read D/requirements.md (newest sections win; the last section states the plan).

## Layer: system design, low level only
R15 tiers 1-2: (1) tokens / parse tree with spans; (2) the directive layer over it (what consumers walk:
directives, their values, their blocks, includes made transparent, variables and snippets expanded).
NOT tier 3 (registration sugar, typed records, decorators): that is deferred (vil-xlo); the round-10
prototypes D/round10/final-py and D/round10/final-ts are its record.

## What the low-level API must carry (the plan he said yes to)
- errors placed at the line/column that caused them (located diagnostics, vil-bzv);
- a stable identity for each place a directive is written (change reports rest on it);
- the change list between two loads (added, changed, replaced, removed);
- include as a graph of files, transparent to the directive walk (vil-bgz);
- variables and snippets expanded, each value traceable to where it was written (both the use site
  and the definition);
- typed values in core (vil-9ze) and DirectiveDelegator typing/defaults (vil-stq): read those beads
  (`bd show vil-9ze`, `bd show vil-stq`, run in /Volumes/Dock/Home/Code/villanelle).
Design rule: the round-10 sugar must be buildable purely on top of this API.

## Prior art first (CLAUDE.md): name it
Candidates to weigh: nginx crossplane (directive lists as data), PostCSS (node tree + walk + source
maps), Python `ast` + NodeVisitor / libcst, ESTree/Babel visitors, lezer/tree-sitter cursors, Caddyfile
dispenser, HCL's hcl.Body / gohcl (partial content, ranges on every value). Pick per language, one model
each, idiomatic (R36); each type stated once.

## The real integration (the test of practicality)
rasl's real configs: /Volumes/Dock/Home/Code/rasl/.claude/worktrees/friendly-saha-6a52d1/family_room.conf
and hyperhdr.conf (rasl uses its current syntax; write them in the v10 grammar where they differ, and
list each difference). rasl's current config readers, for what rasl must get out of the file:
/Volumes/Dock/Home/Code/rasl/.claude/worktrees/friendly-saha-6a52d1/ (js/packages/config, src/rasl).

## Rules for every agent
- The Architects rule: read existing villanelle code for constraints and cost of change; do not copy it.
- Interfaces only at this layer: TS and Python sketches, multiline, one member per line, commented.
- Disk: caches under /Volumes/Dock (npm_config_cache=/Volumes/Dock/Home/.cache/npm,
  UV_CACHE_DIR=/Volumes/Dock/Home/.cache/uv). Checkers as round 9/10 (run scripts in D/round10/final-*).
- Plain words; state costs, don't sell; NOT RUN for anything not run.
