# The syntax tree

The bottom layer reads one text, with no files, variables or includes: an editor's highlighting, a formatter, or
a tool that needs every character. `parse(text)` returns the tokens, a tree over them, and the syntax problems. It
never throws: a broken text gives a tree with an `error` node and a diagnostic.

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/syntax_tree.ts:main"
    ```

=== "Python"

    ```python
    --8<-- "py/examples/syntax_tree.py:main"
    ```

=== "C++"

    ```cpp
    --8<-- "cpp/examples/syntax_tree.cpp:main"
    ```

It prints:

```text
--8<-- "examples/expected/syntax_tree.txt"
```

- **Lossless.** Every character of the text is in exactly one token, comments, spaces and line breaks included, so
  joining the tokens' texts gives the text back, for valid and broken input alike.
- **Nodes** cover a range of tokens (`start` to `end`, an index into `tokens`), and have a `kind`: `document`,
  `directive`, `block`, `list`, `slice` and `error`. A slice's parts stay separate tokens.
- **Problems** are diagnostics with a code and a span (line and column from 0). The parser reads a broken statement
  as one unreadable statement up to its `;` (or to the end of a block it opens), so the statements after its `;` are
  still read. An unterminated string runs to the end of its line, and the statement it is in then runs to the next
  `;`, which may be on a later line: in the sample, `b "open;` swallows `c 3;`.
- `span_of(syntax, node)` and `text_of(syntax, node)` (TypeScript `spanOf`, `textOf`) give a node's span and text.

The grammar file [`grammar/Villanelle.g4`](https://github.com/mcurcio/villanelle/blob/main/grammar/Villanelle.g4) is
the specification of the syntax, and every binding's parser is generated from it, so every parser accepts exactly the
grammar's language. Blocks and lists may nest 100 deep in one text; deeper is E2010.
