import { describe, expect, it } from "vitest";

import { DiagnosticCode, DiagnosticError } from "./diagnostics.js";
import type { INode, ISyntax } from "./syntax/cst.js";
import { NodeKind } from "./syntax/cst.js";
import { parse } from "./syntax/parse.js";
import { TokenKind } from "./syntax/tokens.js";
import { valueOf } from "./value.js";

/** The slice node of the first directive (`connect <value>;`). */
function sliceOf(syntax: ISyntax): INode {
  const node = syntax.root.children[0]?.children[0];
  expect(node?.kind).toBe(NodeKind.Slice);
  return node as INode;
}

function thrown(fn: () => unknown): unknown {
  try {
    fn();
  } catch (error) {
    return error;
  }
  throw new Error("expected a throw");
}

describe("valueOf", () => {
  it("gives the tracer slice", () => {
    const syntax = parse("connect hyperhdr_color[144:152];");
    expect(syntax.diagnostics).toEqual([]);
    const value = valueOf(syntax, sliceOf(syntax));
    expect(value).toMatchObject({ kind: "slice", name: "hyperhdr_color", start: 144, end: 152 });
    expect(value.span).toEqual({
      start: { offset: 8, line: 0, column: 8 },
      end: { offset: 31, line: 0, column: 31 },
    });
  });

  it("gives one-sided slices, the absent side undefined", () => {
    const openEnd = parse("connect hyperhdr_color[144:];");
    expect(openEnd.diagnostics).toEqual([]);
    const a = valueOf(openEnd, sliceOf(openEnd));
    expect(a).toMatchObject({ kind: "slice", name: "hyperhdr_color", start: 144 });
    expect(a).not.toHaveProperty("end");

    const openStart = parse("connect hyperhdr_color[:152];");
    expect(openStart.diagnostics).toEqual([]);
    const b = valueOf(openStart, sliceOf(openStart));
    expect(b).toMatchObject({ kind: "slice", name: "hyperhdr_color", end: 152 });
    expect(b).not.toHaveProperty("start");
  });

  it("gives an index for foo[1]", () => {
    const syntax = parse("connect foo[1];");
    expect(syntax.diagnostics).toEqual([]);
    expect(valueOf(syntax, sliceOf(syntax))).toMatchObject({ kind: "index", name: "foo", index: 1 });
  });

  it("accepts negative integer bounds", () => {
    const syntax = parse("connect foo[-3:-1];");
    expect(syntax.diagnostics).toEqual([]);
    expect(valueOf(syntax, sliceOf(syntax))).toMatchObject({ kind: "slice", start: -3, end: -1 });
  });

  it("throws E4001 at a non-integer bound: foo[a:b] parses clean", () => {
    const syntax = parse("connect foo[a:b];");
    expect(syntax.diagnostics).toEqual([]);
    const error = thrown(() => valueOf(syntax, sliceOf(syntax)));
    expect(error).toBeInstanceOf(DiagnosticError);
    const { diagnostic } = error as DiagnosticError;
    expect(diagnostic.code).toBe(DiagnosticCode.NonIntegerBound);
    expect(diagnostic.span.start).toEqual({ offset: 12, line: 0, column: 12 });
  });

  it("throws E4001 for bounds that are not safe integers", () => {
    for (const src of ["connect foo[1.5];", "connect foo[9007199254740993];", "connect foo[1:-];"]) {
      const syntax = parse(src);
      expect(syntax.diagnostics).toEqual([]);
      const error = thrown(() => valueOf(syntax, sliceOf(syntax)));
      expect((error as DiagnosticError).diagnostic?.code).toBe(DiagnosticCode.NonIntegerBound);
    }
  });

  it("gives a word for a WORD token index", () => {
    const syntax = parse("connect foo;");
    expect(valueOf(syntax, 2)).toEqual({ kind: "word", text: "foo", span: syntax.tokens[2]?.span });
  });

  it("throws 'unsupported value kind' for lists", () => {
    const list = parse("connect [1, 2];");
    const node = list.root.children[0]?.children[0] as INode;
    expect(node.kind).toBe(NodeKind.List);
    expect(() => valueOf(list, node)).toThrow(new Error("unsupported value kind: list"));
  });

  it("throws TypeError for a ref that is not a value", () => {
    const syntax = parse("connect foo;");
    expect(() => valueOf(syntax, 1)).toThrow(TypeError); // SPACE
    expect(() => valueOf(syntax, 99)).toThrow(TypeError);
    expect(() => valueOf(syntax, -1)).toThrow(TypeError);
    expect(() => valueOf(syntax, syntax.root.children[0] as INode)).toThrow(TypeError); // directive
  });

  it("gives a string, its quotes stripped and each v1 escape decoded", () => {
    const cases: [string, string][] = [
      ['"plain"', "plain"],
      ["'single'", "single"],
      ['"a\\\\b"', "a\\b"],
      ['"a\\nb"', "a\nb"],
      ['"a\\tb"', "a\tb"],
      ['"a\\rb"', "a\rb"],
      ['"a\\"b"', 'a"b'],
      ["'a\\'b'", "a'b"],
      ['"a\\\'b"', "a'b"],
      ['""', ""],
    ];
    for (const [literal, decoded] of cases) {
      const syntax = parse(`connect ${literal};`);
      expect(syntax.diagnostics).toEqual([]);
      expect(valueOf(syntax, 2)).toEqual({ kind: "string", value: decoded, span: syntax.tokens[2]?.span });
    }
  });

  it("decodes an unknown escape to the escaped character, astral ones whole", () => {
    for (const [literal, decoded] of [
      ['"\\q"', "q"],
      ['"\\\\n"', "\\n"],
      ['"x\\😀y"', "x😀y"],
    ] as const) {
      const syntax = parse(`connect ${literal};`);
      expect(syntax.diagnostics).toEqual([]);
      expect(valueOf(syntax, 2)).toMatchObject({ kind: "string", value: decoded });
    }
  });

  it("throws TypeError for an unterminated string token", () => {
    const syntax = parse('connect "abc');
    const index = syntax.tokens.findIndex((t) => t.kind === TokenKind.UnterminatedString);
    expect(index).toBeGreaterThan(0);
    expect(() => valueOf(syntax, index)).toThrow(TypeError);
  });
});
