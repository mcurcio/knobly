import { describe, expect, it } from "vitest";

import { type EntryRule, parse, parseEntry } from "./parse.js";
import { MAX_NESTING } from "../gen/api/limits.js";
import { DiagnosticCode } from "../index.js";
import { type Node, textOf } from "./index.js";

/** A node as [kind, source text, children], for readable tree assertions. */
type Shape = [kind: string, text: string, children: Shape[]];

function shape(text: string): { tree: Shape; codes: [string, number, number][] } {
  const syntax = parse(text);
  const of = (node: Node): Shape => [node.kind, textOf(syntax, node), node.children.map(of)];
  return {
    tree: of(syntax.root),
    codes: syntax.diagnostics.map((d) => [d.code, d.span.start.line, d.span.start.column]),
  };
}

describe("statement ending (spec 3.2; owner, 2026-10-29: \"';' is required and a line break is plain whitespace\")", () => {
  it("reads a wrapped line as one directive with two values", () => {
    const { tree, codes } = shape("ranges 0.0627\n       0.922;\n");
    expect(codes).toEqual([]);
    expect(tree[2]).toEqual([["directive", "ranges 0.0627\n       0.922;", []]]);
  });

  it("refuses a directive name that starts with a digit or '-' with E2001", () => {
    expect(shape("0.922;\nx 1;\n")).toEqual({
      tree: ["document", "0.922;\nx 1;\n", [["error", "0.922;", []], ["directive", "x 1;", []]]],
      codes: [["E2001", 0, 0]],
    });
    expect(shape("-x 1;\n").codes).toEqual([["E2001", 0, 0]]);
  });

  it("gives a last statement without its ';' E2001 where the ';' was due", () => {
    expect(shape("x 1").codes).toEqual([["E2001", 0, 3]]);
    expect(shape("a { b 1 }\n").codes).toEqual([["E2001", 0, 8]]);
    expect(shape("a { b 1 }\n").tree[2][0]?.[2][0]?.[2]).toEqual([["error", "b 1 ", []]]);
  });

  it("accepts a '{' on a line of its own: a line break is whitespace (E2008 is retired)", () => {
    const { tree, codes } = shape("a\n  # c\n  {\n b 1;\n}\nc 2;\n");
    expect(codes).toEqual([]);
    expect(tree[2].map((n) => [n[0], n[1]])).toEqual([
      ["directive", "a\n  # c\n  {\n b 1;\n}"],
      ["directive", "c 2;"],
    ]);
  });
});

describe("recovery", () => {
  it("makes a bad statement inside a block one error node, up to its ';', and keeps the block and later siblings", () => {
    const text = "server {\n  listen 80 ];\n  root /x;\n}\nnext 1;\n";
    expect(shape(text)).toEqual({
      tree: [
        "document",
        text,
        [
          [
            "directive",
            "server {\n  listen 80 ];\n  root /x;\n}",
            [
              [
                "block",
                "{\n  listen 80 ];\n  root /x;\n}",
                [
                  ["error", "listen 80 ];", []],
                  ["directive", "root /x;", []],
                ],
              ],
            ],
          ],
          ["directive", "next 1;", []],
        ],
      ],
      codes: [["E2004", 1, 12]],
    });
  });

  it("reports the first error of each bad statement at its real position, and only that one", () => {
    expect(shape('a ];\nb 1;\nc "x ] ];\nd 2;\n')).toEqual({
      tree: [
        "document",
        'a ];\nb 1;\nc "x ] ];\nd 2;\n',
        [
          ["error", "a ];", []],
          ["directive", "b 1;", []],
          ["error", 'c "x ] ];\nd 2;', []],
        ],
      ],
      codes: [
        ["E2004", 0, 2],
        ["E1001", 2, 2],
      ],
    });
  });

  it("resumes after the bad statement's ';' or block, never at a line break", () => {
    expect(shape("a ]\nb 1;\nc 2;\n").tree[2].map((n) => [n[0], n[1]])).toEqual([
      ["error", "a ]\nb 1;"],
      ["directive", "c 2;"],
    ]);
    expect(shape("a ] { b; }\nc;\n").tree[2].map((n) => [n[0], n[1]])).toEqual([
      ["error", "a ] { b; }"],
      ["directive", "c;"],
    ]);
    expect(shape("a }\nb;\n").tree[2].map((n) => [n[0], n[1]])).toEqual([
      ["error", "a }"],
      ["directive", "b;"],
    ]);
  });

  it("reports where the statement breaks, never conjuring or deleting a token", () => {
    // ANTLR's default inline recovery would conjure the missing '}' and report it as a different error.
    expect(shape("a {\n b 1;\n").codes).toEqual([["E2003", 2, 0]]);
    expect(shape("x [a b];\ny 1;\n").codes).toEqual([["E2001", 0, 5]]);
    expect(shape("x a[1 2];\ny 1;\n").codes).toEqual([["E2007", 0, 5]]);
    expect(shape("x a[1:2 z];\ny 1;\n").tree[2].map((n) => n[0])).toEqual(["error", "directive"]);
  });

  it("gives a stray ']' and an unclosed '[' one located E2004 each", () => {
    expect(shape("x ];\ny 1;\n").codes).toEqual([["E2004", 0, 2]]);
    expect(shape("a {\n x [1\n}\n").codes).toEqual([["E2004", 2, 0]]);
    expect(shape("x [1, 2").codes).toEqual([["E2004", 0, 7]]);
  });

  it("gives touching values E2009, number-like words included", () => {
    expect(shape('x "a""b";').codes).toEqual([["E2009", 0, 5]]);
    expect(shape('x a"b";').codes).toEqual([["E2009", 0, 3]]);
    expect(shape("x [a][b];").codes).toEqual([["E2009", 0, 5]]);
    expect(shape("x a[0~1]b;").codes).toEqual([["E2009", 0, 8]]);
    expect(shape("x 1[0];").codes).toEqual([["E2009", 0, 3]]);
  });

  it("refuses a literal bound that is not an integer with E2007 at parse", () => {
    expect(shape("x a[i];").codes).toEqual([["E2007", 0, 4]]);
    expect(shape("x a[1.5];").codes).toEqual([["E2007", 0, 4]]);
  });

  it("resumes after a long run of bad statements in a loop, never overflowing the stack", () => {
    const run = 5000;
    const bad = "a ];\n".repeat(run);
    for (const text of [bad, "a ];".repeat(run), `a {\n${bad}}\n`, "a ];\nb 1;\n".repeat(run / 2)]) {
      const syntax = parse(text);
      expect(syntax.diagnostics.length).toBe(text.startsWith("a ];\nb") ? run / 2 : run);
      expect(textOf(syntax, syntax.root)).toBe(text);
    }
    const top = shape(bad);
    expect(top.tree[2]).toEqual(Array.from({ length: run }, () => ["error", "a ];", []]));
    expect(top.codes[run - 1]).toEqual(["E2004", run - 1, 2]);
    const inBlock = shape(`a {\n${bad}}\n`).tree[2][0]?.[2][0];
    expect(inBlock?.[2]).toEqual(Array.from({ length: run }, () => ["error", "a ];", []]));
    expect(shape("a ];\nb 1;\n".repeat(run / 2)).tree[2].slice(0, 4)).toEqual([
      ["error", "a ];", []],
      ["directive", "b 1;", []],
      ["error", "a ];", []],
      ["directive", "b 1;", []],
    ]);
  });

  it("parses wrong-format files and bad runs at full nesting depth without throwing", () => {
    const lines = (f: (i: number) => string): string => Array.from({ length: 600 }, (_, i) => f(i)).join("");
    for (const text of [
      lines((i) => `key${i}: [value, ${i}]]\n`),
      lines((i) => `"k${i}": "v",\n`),
      `${"a {".repeat(MAX_NESTING)}${"x ];\n".repeat(200)}${"}".repeat(MAX_NESTING)}`,
    ]) {
      const syntax = parse(text);
      expect(syntax.diagnostics.length).toBeGreaterThan(0);
      expect(textOf(syntax, syntax.root)).toBe(text);
    }
    const deep = parse(`${"a {".repeat(MAX_NESTING)}${"x ];\n".repeat(200)}${"}".repeat(MAX_NESTING)}`);
    expect(deep.diagnostics.map((d) => d.code)).toEqual(Array.from({ length: 200 }, () => "E2004"));
  });
});

describe("entry rules (spec 2.8)", () => {
  const first = (text: string, rule: EntryRule): [string, number, number] | undefined => {
    const [d] = parseEntry(text, rule).diagnostics;
    return d === undefined ? undefined : [d.code, d.span.start.line, d.span.start.column];
  };

  it("take a values text with line breaks anywhere, and refuse more than values at its first error", () => {
    expect(first("1\n2", "valuesText")).toBeUndefined();
    expect(first("1 # c\n", "valuesText")).toBeUndefined();
    expect(first("1;", "valuesText")).toEqual(["E2001", 0, 1]);
    expect(first("1; # c", "valuesText")).toEqual(["E2001", 0, 1]);
    expect(first("1 # c", "valuesText")).toEqual(["E2001", 0, 5]);
    expect(first("[1 # c", "valuesText")).toEqual(["E2004", 0, 6]);
    expect(first('"\\q"', "valuesText")).toEqual(["E1005", 0, 0]);
    expect(parseEntry("1;;", "valuesText").diagnostics).toHaveLength(1);
  });

  it("take list items without a trailing ',', a bound that is one integer or $name, a name that is one word", () => {
    expect(first("3,\n4", "itemsText")).toBeUndefined();
    expect(first("3,", "itemsText")).toEqual(["E2001", 0, 2]);
    expect(first("0", "boundText")).toBeUndefined();
    expect(first("$n", "boundText")).toBeUndefined();
    expect(first("1.5", "boundText")).toEqual(["E2001", 0, 0]);
    expect(first("i", "boundText")).toEqual(["E2001", 0, 0]);
    expect(first("rate", "nameText")).toBeUndefined();
    expect(first("0x", "nameText")).toEqual(["E2001", 0, 0]);
    expect(first("a b", "nameText")).toEqual(["E2001", 0, 1]);
  });
});

describe("nesting depth guard", () => {
  const blocks = (n: number): string => "a {".repeat(n) + "}".repeat(n);
  const lists = (n: number): string => `x ${"[".repeat(n)}${"]".repeat(n)}`;
  /** `n` blocks nested through recovery: each holds a stray `]` and then the next block. */
  const recovered = (n: number): string => "a { ] ; ".repeat(n);

  it(`parses ${MAX_NESTING} levels of blocks and lists clean`, () => {
    expect(MAX_NESTING).toBe(100);
    for (const text of [blocks(MAX_NESTING), `${lists(MAX_NESTING)};`, `a {x ${"[".repeat(MAX_NESTING - 1)}`, recovered(MAX_NESTING)]) {
      const syntax = parse(text);
      expect(syntax.diagnostics.filter((d) => d.code === DiagnosticCode.NestingTooDeep)).toEqual([]);
    }
    expect(parse(blocks(MAX_NESTING)).diagnostics).toEqual([]);
    expect(parse(`${lists(MAX_NESTING)};`).diagnostics).toEqual([]);
  });

  it("rejects one level more with one E2010 at the opener of that level and one error node over everything", () => {
    for (const [text, column] of [
      [blocks(MAX_NESTING + 1), 3 * MAX_NESTING + 2],
      [lists(MAX_NESTING + 1), 2 + MAX_NESTING],
      [`a {x ${"[".repeat(MAX_NESTING)}`, 5 + MAX_NESTING - 1],
      [recovered(MAX_NESTING + 1), 8 * MAX_NESTING + 2],
      [recovered(100_000), 8 * MAX_NESTING + 2],
    ] as const) {
      const syntax = parse(text);
      expect(syntax.diagnostics.map((d) => [d.code, d.span.start.column])).toEqual([["E2010", column]]);
      expect(syntax.root).toEqual({
        kind: "document",
        start: 0,
        end: syntax.tokens.length,
        children: [{ kind: "error", start: 0, end: syntax.tokens.length, children: [] }],
      });
      expect(textOf(syntax, syntax.root)).toBe(text);
    }
  });

  it("rejects nesting past the limit in an entry rule with its one diagnostic", () => {
    expect(parseEntry(`${"[".repeat(MAX_NESTING)}${"]".repeat(MAX_NESTING)}`, "valuesText").diagnostics).toEqual([]);
    const deep = parseEntry("[".repeat(MAX_NESTING + 1), "valuesText");
    expect(deep.diagnostics.map((d) => [d.code, d.span.start.column])).toEqual([["E2010", MAX_NESTING]]);
    expect(deep.root).toEqual({ kind: "document", start: 0, end: deep.tokens.length, children: [] });
  });

  it("counts only the blocks and lists the parser opens, and never throws", () => {
    expect(parse(`${blocks(MAX_NESTING)}\n${blocks(MAX_NESTING)}`).diagnostics).toEqual([]);
    expect(() => parse("}".repeat(500) + blocks(MAX_NESTING))).not.toThrow();
    // Brackets and braces a bad statement's recovery skips open nothing: the statement's first error is its diagnostic.
    expect(parse("]".repeat(500) + "[".repeat(MAX_NESTING + 1)).diagnostics.map((d) => d.code)).toEqual(["E2004"]);
    expect(parse(`a {${"x [".repeat(MAX_NESTING)}`).diagnostics.map((d) => d.code)).toEqual(["E2001"]);
    expect(parse("{".repeat(100_000)).diagnostics.map((d) => d.code)).toEqual(["E2001"]);
  });
});
