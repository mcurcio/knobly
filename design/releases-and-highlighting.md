# Releases a downstream editor can consume, and highlighting generated from the grammar

Bead `kno-wii`. Status: **proposal**. The parts marked *owner* are open questions (section 5); nothing here is
agreed until the owner answers them.

The consumer that started this is ear (mcurcio/ear), an audio router whose config, `ear.conf`, is written in knobly.
Its browser editor wants to syntax-highlight knobly text with knobly's TypeScript package, installed from a release
rather than built from a pinned commit. ear's own C++ reader stays the judge of validity: the editor uses the
highlighter for display only.

## 1. What exists today

- **Releases** are already wired up but have never run for real. A push to `main` that passes CI runs semantic-release
  (`.releaserc.json`): the commit analyzer picks the version, the release-notes generator writes the notes,
  `.github/release-build.sh` builds five assets, and `@semantic-release/github` tags the commit and attaches the assets to a
  GitHub Release. The job stays in dry-run until the repository variable `RELEASE_ENABLED` is `true` (owner,
  2026-10-23, kno-g7n.3). The dry run on `c1ef4ae` (CI run 41208935289) computed **1.0.0** and built
  `knobly-1.0.0.tgz`, `knobly-1.0.0-py3-none-any.whl`, `knobly-1.0.0.tar.gz`, `knobly-cpp-1.0.0.tar.gz` and
  `knobly.hpp`.
- **Highlighting** exists only as the docs site's Pygments lexer (`docs/site/lexer/`). It scans with the
  longest-match DFA that `tools/parser/lexer.py` builds from `Knobly.g4`, and adds one rule: a statement's first word
  is its name.
- **The TypeScript package** gets its tokens only through `parse` (`knobly/syntax`), which runs the ANTLR lexer and
  parser. Measured with esbuild 0.28.2 (minified, browser target): `parse` alone bundles to 163 KB (41.6 KB
  gzipped), nearly all of it the antlr4 runtime. `render` plus `load` bundles to 219 KB (58.6 KB gzipped).
  `knobly/browser`'s fetch adapters are 0.3 KB.

## 2. The highlight model: one table, generated outputs

All highlighting reads one model: the grammar's token rules plus a small table, `grammar/highlight.json`. That table
gives each token kind a **highlight class**, and says which kinds are a statement's name when they come first.

| Class | Tokens | TextMate scope | Pygments |
|---|---|---|---|
| `directive` | `WORD` as a statement's first token | `entity.name.function.knobly` | `Name.Function` |
| `keyword` | `AT_WORD` (`@set`, `@include`, ...) | `keyword.control.knobly` | `Keyword` |
| `word` | `WORD` elsewhere (a value) | `string.unquoted.knobly` | `Name` |
| `variable` | `VARIABLE` | `variable.other.knobly` | `Name.Variable` |
| `number` | `INTEGER`, `DIGIT_WORD` | `constant.numeric.knobly` | `Number` |
| `string` | `STRING` | `string.quoted.knobly` | `String` |
| `comment` | `COMMENT` | `comment.line.number-sign.knobly` | `Comment.Single` |
| `punctuation` | `{ } [ ] ; , ~` | `punctuation.*.knobly` (one per kind) | `Punctuation` |
| `space` | `BOM`, `SPACE`, `NEWLINE` | none | `Whitespace` |
| `error` | `UNTERMINATED_STRING`, `BAD_ESCAPE`, `LONE_DOLLAR`, `BAD_CHAR` | `invalid.illegal.knobly` | `Error` |

**The head rule** is the Pygments lexer's rule, unchanged. The first `WORD` after the start of the text, a `;`, a
`{` or a `}`, with only `BOM`, `SPACE`, `NEWLINE` or `COMMENT` tokens in between, is a `directive`. The rule works
on tokens only, not on the parse tree. So it holds for broken text too, and it never needs the parser.

`tools/check.sh` refuses a token kind with no class. So a token added to the grammar cannot go unhighlighted
anywhere. (The Pygments lexer already refuses one; it now reads its styles from this table.)

Three outputs are generated from the model. None of them is committed:

1. **The TypeScript highlighter** (section 3). `tools/gen.sh ts` writes the minimized lexer DFA and the class table
   as a TypeScript module.
2. **The TextMate grammar**, `knobly.tmLanguage.json` (kno-w4b), built by `tools/highlight/gen.py textmate`.
3. **The docs site's Pygments lexer**, which already scans with the same DFA.

### Why the TextMate grammar is exact

TextMate tries its patterns in order and takes the first one that matches, not the longest. knobly's lexer takes
the longest match. The generator bridges the two with a property of the minimized DFA: it has 29 states, and every
state but the start state accepts. So the longest match is exactly "run until no transition applies". For each
accepting state *s*, the generator emits a regex for the strings that reach *s* (by state elimination), followed by
a negative lookahead for the characters that leave *s*. At any position exactly one state's pattern can match, the
one where the DFA stops, so pattern order does not matter. The generator refuses a grammar whose DFA lacks the
property.

The head rule becomes TextMate scopes. At the top level, and inside a block, the grammar matches filler, `;`, `{`,
`}`, and a statement begin. A statement begins at its first token, scoped `directive` when it is a `WORD`, and ends
before the next `;`, `{` or `}`. No token but those three punctuation tokens starts with those characters, so the
end can never cut a token.

**Check.** A vitest test loads the generated grammar with vscode-textmate and vscode-oniguruma (VS Code's own
engine) and tokenizes every file in `fixtures/` and every conformance syntax text. It requires the same boundaries
and classes as `highlight()`. A second test requires `highlight()`'s spans to equal `parse()`'s tokens.

## 3. The TypeScript highlighting API (*owner*: shape and placement)

```ts
import { highlight, HighlightClass } from "knobly/highlight";

const spans = highlight('server { port $port; }  # main');
// [ { start: 0,  end: 6,  class: "directive",   kind: "WORD" },
//   { start: 6,  end: 7,  class: "space",       kind: "SPACE" },
//   { start: 7,  end: 8,  class: "punctuation", kind: "LBRACE" },
//   { start: 9,  end: 13, class: "directive",   kind: "WORD" },
//   { start: 14, end: 19, class: "variable",    kind: "VARIABLE" }, ... ]
for (const s of spans) mark(s.start, s.end, `kn-${s.class}`);
```

```ts
export const HighlightClass: { readonly Directive: "directive"; readonly Keyword: "keyword"; ... };  // as const
export type HighlightClass = (typeof HighlightClass)[keyof typeof HighlightClass];
export interface HighlightSpan {
  readonly start: number;          // UTF-16 offset, as every TypeScript position (contract 1)
  readonly end: number;
  readonly class: HighlightClass;
  readonly kind: TokenKind;        // the token kind, for finer styling
}
export function highlight(text: string): HighlightSpan[];
```

- **Lossless.** The spans are contiguous, start at 0, end at `text.length`, and are never empty. `highlight` never
  throws, for broken text too: what does not lex is an `error` span.
- **One span per token.** The spans are exactly `parse(text).tokens` (same kinds, same offsets), with a class added.
- **No antlr4.** The module imports only the generated DFA table and the token kind list. It uses no Node API, so a
  browser bundle can take it. Measured cost, minified: about 4 KB with the tables (section 6 has the exact
  number, which the size test pins).
- **Performance.** One linear pass with no allocation beyond the spans. An editor can re-highlight the whole text on
  every change.

## 4. Release pipeline and artifacts

```
PR merged to main ──▶ CI (grammar, ts, py, cpp, docs, release-build, reproducible)
                        │ all green
                        ▼
                release job: semantic-release
                  analyze commits ─▶ version (none: stop)
                  notes            ─▶ release notes
                  prepare          ─▶ .github/release-build.sh <version>   (assets + SHA256SUMS)
                  publish          ─▶ git tag v<version>, GitHub Release with the assets
                                   ─▶ npm publish of the tarball to GitHub Packages   (owner: name)
                (RELEASE_ENABLED != true: dry run; builds the assets and uploads them as a workflow artifact)
```

| Asset | What | Where |
|---|---|---|
| `knobly-<v>.tgz` | `npm pack` of `ts/` | Release; and GitHub Packages (*owner*: package name) |
| `knobly-<v>-py3-none-any.whl`, `knobly-<v>.tar.gz` | wheel and sdist of `py/` | Release (not PyPI) |
| `knobly-cpp-<v>.tar.gz` | C++ source archive, generated headers included | Release |
| `knobly.hpp` | C++ single header | Release |
| `knobly.tmLanguage.json` | the TextMate grammar | Release (new) |
| `SHA256SUMS` | sha256 of every asset above, `sha256sum -c` format | Release (new) |

**Reproducible from the tag.** Every asset is a function of the tagged commit and the pinned tools:

- `SOURCE_DATE_EPOCH` is the tagged commit's committer time, for every build step.
- The C++ archive uses `tar --sort=name --mtime=@$SOURCE_DATE_EPOCH --owner=0 --group=0 --numeric-owner` and
  `gzip -n`.
- `npm pack` already fixes mtimes. hatchling honours `SOURCE_DATE_EPOCH`, and is pinned in the build (kno-h61).
- A new CI job, `reproducible`, builds the assets twice, in two checkouts at different times, and fails unless the
  two `SHA256SUMS` are identical.

**Changelog** (*owner*). Proposed: the release notes on each GitHub Release are the changelog, and no
`CHANGELOG.md` is committed. A committed changelog would need a bot commit to `main` on every release, and it is
generated text, which the owner's rule keeps out of the repository.

**Where commits land.** Releases cut on every push to `main`, which is either a PR merge or a direct push. So the
release flow does not conflict with either landing rule. This change lands as a PR, as the owner asked for
kno-bzv; kno-9ws tracks the general rule.

### How a consumer like ear installs it

| Route | `package.json` | Auth |
|---|---|---|
| Release tarball | `"knobly": "https://github.com/mcurcio/knobly/releases/download/v<v>/knobly-<v>.tgz"` | none (public repo); the lockfile records the integrity hash |
| GitHub Packages | `"knobly": "npm:@mcurcio/knobly@<v>"`, plus `.npmrc`: `@mcurcio:registry=https://npm.pkg.github.com` | a token with `read:packages`, even for a public package |
| C++ | `FetchContent_Declare(knobly URL .../knobly-cpp-<v>.tar.gz URL_HASH SHA256=<from SHA256SUMS>)` | none |

## 5. Questions for the owner

1. **The npm name on GitHub Packages.** GitHub's npm registry only takes a package scoped to its owner. Either
   (a) keep the package `knobly` and publish the same build as `@mcurcio/knobly`. Consumers alias it
   (`"knobly": "npm:@mcurcio/knobly@1.0.0"`), so `import ... from "knobly/syntax"` keeps working. The registry copy is
   the Release tarball with only its name changed. Or (b) rename the package to `@mcurcio/knobly` everywhere, so every
   import becomes `@mcurcio/knobly/syntax`.
2. **The first version.** semantic-release starts at 1.0.0 when there are no tags. The README says the API may
   still change. A `v0.1.0` tag made by hand before enabling releases would start at 0.1.0 instead. Then `feat:`
   gives 0.2.0, and a breaking change jumps to 1.0.0.
3. **Changelog.** Release notes only (proposed), or a committed `CHANGELOG.md`?
4. **The highlighter's place in the spec.** Every public declaration is generated from `spec/schema/api.json`.
   Options: (a) schema-declared, TypeScript at `knobly/highlight` now, with Python and C++ following under a bead;
   (b) TypeScript-only, like the fetch adapters (`MAY` in the spec); (c) all three bindings now, with a
   conformance corpus.

## 6. Other gaps a downstream consumer would hit (filed, not built)

- A line-at-a-time tokenizer with state, for CodeMirror's `StreamLanguage` (the head flag is the whole state).
- Python and C++ `highlight`, if question 4 says so.
- tree-sitter grammar (kno-w4b's second step).
- `knobly/browser` re-exporting nothing of the syntax layer. A browser program that wants `parse` imports
  `knobly/syntax` and pays for antlr4. That is fine, but the guide should say so.
