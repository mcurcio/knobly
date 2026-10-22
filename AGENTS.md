# AGENTS.md

Instructions for AI coding agents in this repo. `CLAUDE.md` is a symlink to this file.

- `grammar/Villanelle.g4` is the language. Change the language only there, and run
  `tools/check.sh` after every grammar change. It must exit 0.
- The grammar may not use ANTLR actions, semantic predicates, lexer commands or modes. The check
  refuses them because they can hide a conflict.
- Whitespace, comments and newlines are ordinary tokens. Nothing goes on a hidden channel, so the
  parse tree keeps every character.
- Work lands through pull requests into `main`. The owner reviews and merges; never push to `main`.
- Commits follow Conventional Commits.
- Design history and current choices are in `design/RECORD.md`. Planned work is tracked in the
  `mcurcio/rasl` beads (epic `rasl-g7n`).
