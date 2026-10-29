/**
 * Value readers (ExpandedValue) and canonical text (slices.md §1.3), through the public processor. Also carries the
 * value behaviour the deleted tier-1 value reader had: slices, indexes, negative bounds and string decoding.
 */

import { describe, expect, it } from "vitest";

import { DiagnosticCode } from "../diagnostics.js";
import { DiagnosticError } from "../errors.js";
import type { ExpandedValue } from "../written/index.js";
import { loadText, only, originText } from "./testing.js";

/** The values of the one directive `v ...;`. */
async function values(written: string, overrides?: Record<string, string>): Promise<readonly ExpandedValue[]> {
  const loaded = await loadText(`v ${written};\n`, overrides === undefined ? {} : { overrides });
  expect(loaded.diagnostics).toEqual([]);
  return only(loaded.block).values;
}

async function value(written: string): Promise<ExpandedValue> {
  return only(await values(written));
}

/** What `read` threw: its code and where it is placed. */
function thrown(read: () => unknown): [string, string] {
  try {
    read();
  } catch (error) {
    expect(error).toBeInstanceOf(DiagnosticError);
    const { diagnostic } = error as DiagnosticError;
    return [diagnostic.code, originText(diagnostic)];
  }
  throw new Error("expected a throw");
}

describe("readers", () => {
  it("word: a bare word; E4002 for any other kind, placed at the value", async () => {
    const [word, string, list] = await values('listen "x" [1]');
    expect(word?.word()).toBe("listen");
    expect(thrown(() => string?.word())).toEqual([DiagnosticCode.WrongValueKind, "main.conf:0:9"]);
    expect(thrown(() => list?.word())).toEqual([DiagnosticCode.WrongValueKind, "main.conf:0:13"]);
  });

  it("string: a word or a string, decoded; E4002 for a list, slice or index", async () => {
    const [word, string, list, slice, index] = await values('w "a\\tb" [1] c[1~2] c[1]');
    expect(word?.string()).toBe("w");
    expect(string?.string()).toBe("a\tb");
    for (const other of [list, slice, index]) expect(thrown(() => other?.string())[0]).toBe(DiagnosticCode.WrongValueKind);
  });

  it("number: a NumberText word (JSON number); E4004 for another word, E4002 for another kind", async () => {
    const read = await values('8080 0.5 -0.0176515 1e3 -2E-2 20hz 1. .5 01 "8080"');
    expect(read.slice(0, 5).map((a) => a.number())).toEqual([8080, 0.5, -0.0176515, 1000, -0.02]);
    for (const bad of read.slice(5, 9)) expect(thrown(() => bad.number())[0], bad.text).toBe(DiagnosticCode.NotANumber);
    expect(thrown(() => read[9]?.number())[0]).toBe(DiagnosticCode.WrongValueKind);
  });

  it("integer: an IntegerText word in the safe range; E4005 for another word (1.0 among them)", async () => {
    const read = await values("150 -3 0 1.0 007 9007199254740993 x");
    expect(read.slice(0, 3).map((a) => a.integer())).toEqual([150, -3, 0]);
    for (const bad of read.slice(3)) expect(thrown(() => bad.integer())[0], bad.text).toBe(DiagnosticCode.NotAnInteger);
    expect(thrown(() => read[3]?.integer())).toEqual([DiagnosticCode.NotAnInteger, "main.conf:0:11"]);
  });

  it("boolean: true or false; E4006 for any other word (on, yes), E4002 for another kind", async () => {
    const read = await values('true false on yes "true"');
    expect(read.slice(0, 2).map((a) => a.boolean())).toEqual([true, false]);
    expect(thrown(() => read[2]?.boolean())[0]).toBe(DiagnosticCode.NotABoolean);
    expect(thrown(() => read[3]?.boolean())[0]).toBe(DiagnosticCode.NotABoolean);
    expect(thrown(() => read[4]?.boolean())[0]).toBe(DiagnosticCode.WrongValueKind);
  });

  it("list: a list's items, each with its own origin, also its items property; E4002 for another kind", async () => {
    const list = await value('[0.04, "x", [1, 2], c[0~1]]');
    const items = list.list();
    expect(list.kind === "list" ? list.items : []).toEqual(items);
    expect(items.map((i) => [i.kind, i.text, originText(i.origin)])).toEqual([
      ["word", "0.04", "main.conf:0:3"],
      ["string", '"x"', "main.conf:0:9"],
      ["list", "[1, 2]", "main.conf:0:14"],
      ["slice", "c[0~1]", "main.conf:0:22"],
    ]);
    expect(items[2]?.list().map((i) => i.integer())).toEqual([1, 2]);
    expect(thrown(() => items[0]?.list())[0]).toBe(DiagnosticCode.WrongValueKind);
  });

  it("slice: a slice (either side may be absent) or an index, negative bounds allowed; E4002 otherwise", async () => {
    const read = await values("hyperhdr_color[144~152] c[144~] c[~152] foo[1] foo[-3~-1] w");
    expect(read[0]?.slice()).toEqual({ kind: "slice", name: "hyperhdr_color", start: 144, end: 152 });
    expect(read[1]?.slice()).toEqual({ kind: "slice", name: "c", start: 144 });
    expect(read[2]?.slice()).toEqual({ kind: "slice", name: "c", end: 152 });
    expect(read[3]?.slice()).toEqual({ kind: "index", name: "foo", index: 1 });
    expect(read[4]?.slice()).toEqual({ kind: "slice", name: "foo", start: -3, end: -1 });
    expect(read[1]?.slice()).not.toHaveProperty("end");
    expect(thrown(() => read[5]?.slice())[0]).toBe(DiagnosticCode.WrongValueKind);
  });

  it("places a reader's error on a value from a variable at its definition, via the variable", async () => {
    const loaded = await loadText("@set $n many;\nv $n;\n");
    expect(thrown(() => only(only(loaded.block).values).integer())).toEqual([DiagnosticCode.NotAnInteger, "main.conf:0:8 < variable n main.conf:1:2"]);
  });

  it("places a reader's error on an override at the $name that used it", async () => {
    const [arg] = await values("$n", { n: "many" });
    expect(thrown(() => arg?.integer())).toEqual([DiagnosticCode.NotAnInteger, "main.conf:0:2"]);
  });
});

describe("canonical text", () => {
  it("is a word as written, a string double-quoted with its decoded text re-escaped", async () => {
    const cases: [string, string, string][] = [
      ['"plain"', "plain", '"plain"'],
      ["'single'", "single", '"single"'],
      ['"a\\\\b"', "a\\b", '"a\\\\b"'],
      ['"a\\nb"', "a\nb", '"a\\nb"'],
      ['"a\\tb"', "a\tb", '"a\\tb"'],
      ['"a\\rb"', "a\rb", '"a\\rb"'],
      ['"a\\"b"', 'a"b', '"a\\"b"'],
      // A single-quoted string is raw (TOML's literal string): a backslash is itself.
      ["'a\\b'", "a\\b", '"a\\\\b"'],
      ["'C:\\new'", "C:\\new", '"C:\\\\new"'],
      ['"a\\\'b"', "a'b", '"a\'b"'],
      ["'a\"b'", 'a"b', '"a\\"b"'],
      ['""', "", '""'],
      ['"x😀y"', "x😀y", '"x😀y"'],
    ];
    for (const [written, decoded, text] of cases) {
      const arg = await value(written);
      expect([arg.string(), arg.text], written).toEqual([decoded, text]);
    }
    expect((await value("/var/www")).text).toBe("/var/www");
  });

  it("writes slices and indexes in decimal, either side empty when absent", async () => {
    expect((await values("c[0~3] c[3~] c[~3] c[-1] c[0]")).map((a) => a.text)).toEqual(["c[0~3]", "c[3~]", "c[~3]", "c[-1]", "c[0]"]);
  });

  it("drops comments, line breaks and a trailing comma from a list", async () => {
    const arg = await value("[1, # warm\n  'two',\n  [3,4,],\n]");
    expect(arg.text).toBe('[1, "two", [3, 4]]');
  });

  it("gives a value from a variable the value's text, never $name", async () => {
    const loaded = await loadText('@set $c "x";\nv $c [$c];\n');
    expect(only(loaded.block).values.map((a) => a.text)).toEqual(['"x"', '["x"]']);
  });
});

describe("expanded value origins and kinds", () => {
  it("gives each value its kind and the place it was written", async () => {
    const read = await values('80 "a b" foo[1~2] bar[3] [1, 2]  # trailing\n');
    expect(read.map((a) => [a.kind, a.text, originText(a.origin)])).toEqual([
      ["word", "80", "main.conf:0:2"],
      ["string", '"a b"', "main.conf:0:5"],
      ["slice", "foo[1~2]", "main.conf:0:11"],
      ["index", "bar[3]", "main.conf:0:20"],
      ["list", "[1, 2]", "main.conf:0:27"],
    ]);
  });
});
