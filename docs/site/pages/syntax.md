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

The grammar file [`grammar/Knobly.g4`](https://github.com/mcurcio/knobly/blob/main/grammar/Knobly.g4) is
the specification of the syntax, and every binding's parser is generated from it, so every parser accepts exactly the
grammar's language. Blocks and lists may nest 100 deep in one text; deeper is E2010, and the whole text is then one
error node with that one diagnostic. Only the blocks and lists the parser opens count, not brackets it skips while
recovering from an error.

## Highlighting an editor's text

An editor that only shows knobly text needs the tokens, not the tree. `highlight(text)` from `knobly/highlight`
(TypeScript only) gives one span per token, each with a highlight class to style. It never throws, and its spans
cover the text exactly, broken text included:

=== "TypeScript"

    ```ts
    --8<-- "ts/examples/highlight.ts:main"
    ```

It prints:

```text
--8<-- "examples/expected/highlight.txt"
```

- **The spans are the tokens.** Each span is exactly one of `parse(text).tokens`: same kind (`span.kind`), same
  start and end (UTF-16 offsets).
- **The classes** are `directive` (a statement's name), `keyword` (`@set`, `@include`, ...), `word` (a bare value),
  `variable`, `number`, `string`, `comment`, `punctuation`, `space` and `error` (an unterminated string, a bad
  escape, a lone `$`, a stray character). A word is a `directive` when it is a statement's first token: the first
  word of the text, or after a `;`, `{` or `}`, with only spaces, line breaks and comments in between. The rule reads
  tokens only, so it holds in broken text too.
- **Small.** `knobly/highlight` does not load the ANTLR runtime: it scans with tables generated from the grammar.
  It bundles to about 3 KB minified (1 KB gzipped), where `parse` bundles to about 160 KB (42 KB gzipped). It is
  fast enough to highlight the whole text again on every keystroke.
- **Display only.** Highlighting says nothing about whether a file is valid. Use `parse`, `load` and `render` for
  that.

**Other editors.** Every release also carries `knobly.tmLanguage.json`, a TextMate grammar generated from the same
grammar and the same classes. VS Code, Sublime Text, JetBrains IDEs, Shiki and GitHub can use it. It tokenizes
exactly as the lexer does, with two exceptions that come from TextMate itself: a lone surrogate, and a `\r` that is
the text's very last character, which TextMate reads as a line break.
