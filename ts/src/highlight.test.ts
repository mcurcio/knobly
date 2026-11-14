// The highlighter (design/releases-and-highlighting.md sections 2 and 3): its spans are parse()'s tokens, classed by
// grammar/highlight.json; the generated TextMate grammar tokenizes the same texts the same way under VS Code's own
// engine; and the entry stays small, with no antlr4.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "esbuild";
import * as oniguruma from "vscode-oniguruma";
import * as textmate from "vscode-textmate";
import { beforeAll, describe, expect, it } from "vitest";

import { HighlightClass, highlight, type HighlightSpan } from "./highlight.js";
import { parse, TokenKind } from "./syntax/index.js";

const repo = fileURLToPath(new URL("../../", import.meta.url));

interface Model {
  readonly classes: Readonly<Record<string, { readonly textmate: string | null }>>;
  readonly tokens: Readonly<Record<string, { readonly class: string; readonly textmate?: string }>>;
}
const model = JSON.parse(readFileSync(join(repo, "grammar/highlight.json"), "utf8")) as Model;

/** Every text the tests run: the real configs in fixtures/, every syntax conformance case, and texts made to probe. */
function corpus(): [string, string][] {
  const texts: [string, string][] = [];
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (name.endsWith(".conf")) texts.push([path.slice(repo.length), readFileSync(path, "utf8")]);
    }
  };
  walk(join(repo, "fixtures"));
  const corpora = JSON.parse(readFileSync(join(repo, "conformance/corpora.json"), "utf8")) as {
    corpora: { name: string; cases: string[] }[];
  };
  for (const file of corpora.corpora.find((c) => c.name === "syntax")?.cases ?? []) {
    for (const c of JSON.parse(readFileSync(join(repo, file), "utf8")) as { name: string; src: string }[]) {
      texts.push([`${file}#${c.name}`, c.src]);
    }
  }
  const probes = [
    "",
    "a",
    "@set $x 1;\nserver { port $x; host \"10.0.0.1\"; }\n",
    "x -; y -5; z -abc; w 0x1f; v 12ab; u 007; t -0; s 1-2;",
    'a "ok" "bad \\q" "open\nb \'raw \\q\' \'open\n',
    "a $ $b $$c;\r\nb\r c\t\t;  # comment\r\n",
    "\uFEFF# bom\nx [1, 2~3] name[1~3] k[0];",
    "}}{{;; a { b } c",
    "x 😀 é ü;\u0000\u0007\u007f",
    "# a\n# b\nfirst second; @include \"x.conf\" { @set $n 1; }",
  ];
  probes.forEach((text, i) => texts.push([`probe ${String(i)}`, text]));
  // Seeded random texts over characters that start, end or break tokens.
  const alphabet = [..." \t\n\r\r\n#$@\"'\\{}[];,~-0123a_.:*?+é😀\uFEFF\u0001nqt"];
  let seed = 0x2545f491;
  const next = (): number => ((seed = (Math.imul(seed, 1103515245) + 12345) >>> 0) >>> 8) % alphabet.length;
  for (let i = 0; i < 300; i++) {
    let text = "";
    for (let n = 1 + (next() % 30); n > 0; n--) text += alphabet[next()] as string;
    texts.push([`random ${String(i)}`, text]);
  }
  return texts;
}

const texts = corpus();

describe("highlight()", () => {
  it.each(texts)("its spans are parse()'s tokens: %s", (_name, text) => {
    const spans = highlight(text);
    const tokens = parse(text).tokens;
    expect(spans.map((s) => [s.kind, s.start, s.end])).toEqual(tokens.map((t) => [t.kind, t.span.start.offset, t.span.end.offset]));
    // Lossless: contiguous from 0 to the end, never empty.
    let at = 0;
    for (const s of spans) {
      expect(s.start).toBe(at);
      expect(s.end).toBeGreaterThan(s.start);
      at = s.end;
    }
    expect(at).toBe(text.length);
  });

  it("classes each token by grammar/highlight.json, a statement's first word as its name", () => {
    const text = '@set $port 8080;\nserver {  # main\n    listen $port; name "a" \'b\' -x;\n    tags [a, b];\n}\nx "open';
    const got = highlight(text)
      .filter((s) => s.class !== HighlightClass.Space)
      .map((s) => `${text.slice(s.start, s.end)}:${s.class}`);
    expect(got).toEqual([
      "@set:keyword", "$port:variable", "8080:number", ";:punctuation",
      "server:directive", "{:punctuation", "# main:comment",
      "listen:directive", "$port:variable", ";:punctuation",
      "name:directive", '"a":string', "'b':string", "-x:number", ";:punctuation",
      "tags:directive", "[:punctuation", "a:word", ",:punctuation", "b:word", "]:punctuation", ";:punctuation",
      "}:punctuation", "x:directive", '"open:error',
    ]);
  });

  it("gives every kind its model class, and only a WORD that comes first a head class", () => {
    for (const [, text] of texts) {
      for (const s of highlight(text)) {
        const own = model.tokens[s.kind]?.class;
        if (s.class === HighlightClass.Directive) expect(s.kind).toBe(TokenKind.WORD);
        else expect(s.class).toBe(own);
      }
    }
  });
});

// ------------------------------------------------------------------------------------------------- TextMate

/** One TextMate token as a class span; the deepest knobly scope names the class (no knobly scope: space). */
type Span = [number, number, string];

describe("the generated TextMate grammar (knobly.tmLanguage.json)", () => {
  let registry: textmate.Registry;
  const scopes = new Map<string, string>();

  beforeAll(async () => {
    const dir = mkdtempSync(join(tmpdir(), "knobly-tm-"));
    const path = join(dir, "knobly.tmLanguage.json");
    execFileSync("python3", [join(repo, "tools/highlight/gen.py"), "textmate", path]);
    for (const [name, c] of Object.entries(model.classes)) if (c.textmate !== null) scopes.set(c.textmate, name);
    for (const t of Object.values(model.tokens)) if (t.textmate !== undefined) scopes.set(t.textmate, t.class);
    const require = createRequire(import.meta.url);
    const wasm = readFileSync(join(require.resolve("vscode-oniguruma"), "../onig.wasm"));
    await oniguruma.loadWASM(wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength));
    const grammar = readFileSync(path, "utf8");
    registry = new textmate.Registry({
      onigLib: Promise.resolve({
        createOnigScanner: (patterns: string[]) => new oniguruma.OnigScanner(patterns),
        createOnigString: (s: string) => new oniguruma.OnigString(s),
      }),
      loadGrammar: (scope: string) =>
        Promise.resolve(scope === "source.knobly" ? textmate.parseRawGrammar(grammar, "knobly.tmLanguage.json") : null),
    });
  });

  /** The text tokenized line by line, as an editor does, the line ends included in the last span of each line. */
  async function tokenize(text: string): Promise<Span[]> {
    const grammar = await registry.loadGrammar("source.knobly");
    if (grammar === null) throw new Error("no grammar");
    const out: Span[] = [];
    let state = textmate.INITIAL;
    let offset = 0;
    const lines = text.split("\n");
    lines.forEach((line, i) => {
      const result = grammar.tokenizeLine(line, state);
      for (const token of result.tokens) {
        const end = Math.min(token.endIndex, line.length);
        if (end <= token.startIndex) continue;
        const scope = [...token.scopes].reverse().find((s) => scopes.has(s));
        out.push([offset + token.startIndex, offset + end, scope === undefined ? HighlightClass.Space : (scopes.get(scope) as string)]);
      }
      offset += line.length;
      if (i < lines.length - 1) {
        out.push([offset, offset + 1, HighlightClass.Space]);
        offset += 1;
      }
      state = result.ruleStack;
    });
    return merge(out);
  }

  /** Adjacent spans of one class joined: TextMate need not split two tokens with the same scopes. */
  function merge(spans: readonly Span[]): Span[] {
    const out: Span[] = [];
    for (const s of spans) {
      const last = out.at(-1);
      if (last !== undefined && last[2] === s[2] && last[1] === s[0]) last[1] = s[1];
      else out.push([...s]);
    }
    return out;
  }

  const expected = (spans: readonly HighlightSpan[]): Span[] => merge(spans.map((s) => [s.start, s.end, s.class]));

  // Two texts TextMate cannot see as the lexer does, left out (the guide says so): a lone surrogate (vscode-oniguruma
  // matches over UTF-8, where one cannot be written), and a "\r" that is the text's last character (TextMate gives
  // every line a "\n", so it reads "\r\n", a line break, where the lexer reads a lone "\r", an error).
  const lexable = texts.filter(
    ([, text]) => !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(text) && !text.endsWith("\r"),
  );

  it.each(lexable)("tokenizes like the lexer: %s", async (_name, text) => {
    expect(await tokenize(text)).toEqual(expected(highlight(text)));
  });

  it("splits tokens where the lexer does, not only where classes change", async () => {
    // Each pair is two tokens of one class with nothing between: TextMate must still find both ends.
    for (const text of ["x 12ab-3", "x 0;1", "x ;;", "x []"]) {
      const grammar = await registry.loadGrammar("source.knobly");
      const tokens = grammar?.tokenizeLine(text, textmate.INITIAL).tokens ?? [];
      const ends = tokens.map((t) => Math.min(t.endIndex, text.length)).filter((e, i, all) => all.indexOf(e) === i && e > 0);
      expect(ends).toEqual(highlight(text).map((s) => s.end));
    }
  });
});

// ---------------------------------------------------------------------------------------------- bundle size

describe("knobly/highlight's size", () => {
  it("bundles without antlr4, in under 8 KB minified", async () => {
    const result = await build({
      entryPoints: [fileURLToPath(new URL("highlight.ts", import.meta.url))],
      bundle: true,
      minify: true,
      format: "esm",
      platform: "browser",
      write: false,
      metafile: true,
      logLevel: "silent",
    });
    const inputs = Object.keys(result.metafile.inputs);
    expect(inputs.filter((i) => i.includes("antlr4"))).toEqual([]);
    const bytes = result.outputFiles[0]?.contents.length ?? 0;
    expect(bytes).toBeGreaterThan(0);
    expect(bytes).toBeLessThan(8 * 1024);
  });
});
