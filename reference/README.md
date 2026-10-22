# Reference snapshots from mcurcio/rasl

These are copies of the config code as it stood in mcurcio/rasl, `alpha` @ `6f4f819` (2026-10-22),
before the language moved here. They are source material for the villanelle packages. They are
not built or tested here. Port what the design keeps; leave the rest behind.

| Path | From rasl | What the design keeps |
|---|---|---|
| `rasl-config-ts/` | `js/packages/config/` (`@rasl/config`), plus `js/STYLE.md` | Layer 3: the AST facade, `DirectiveDelegator`, the include graph and the I/O edges. The lexer and parser are replaced by the ANTLR4 parser built from `grammar/Villanelle.g4` |
| `rasl-config-py/` | `src/rasl/config/` and its 3 test files | The Python port follows the TS packages. `directive.py` parses through crossplane, which is to be replaced. `loader.py`, `connection.py`, `channel_mapping.py` and `connect_parser.py` are RASL runtime meaning and stay in rasl |
