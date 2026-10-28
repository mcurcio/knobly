/**
 * The expansion rules of slices.md §1.2, one block per rule, each through the public processor.
 */

import { describe, expect, it } from "vitest";

import { DiagnosticCode, DiagnosticError } from "../diagnostics.js";
import { include } from "../include.js";
import type { IExtension } from "./processor.js";
import { villanelle } from "./processor.js";
import { memorySource } from "./source.js";
import { addresses, countingSource, loadFiles, loadText, only, originText, problems, rendered, texts } from "./testing.js";

const INCLUDE = { extensions: [include()] };

describe("rule 1: reserved names", () => {
  it("never puts set, snippet or use in a body, at the top level or in a block", async () => {
    const loaded = await loadText("set $a 1;\nsnippet s { x; }\nuse s;\nb {\n  set $c 2;\n  snippet t { y; }\n  use t;\n}\n");
    expect(loaded.diagnostics).toEqual([]);
    expect(addresses(loaded)).toEqual(["x", "b", "b > y"]);
  });

  it("reserves an extension's name only while it is registered", async () => {
    const files = { "main.conf": 'include "a.conf";\n', "a.conf": "a;\n" };
    expect(addresses(await loadFiles(files))).toEqual(["include"]);
    expect(addresses(await loadFiles(files, INCLUDE))).toEqual(["a"]);
  });

  it("refuses an extension named like a reserved word or like another extension", () => {
    const source = memorySource({});
    const named = (directive: string): IExtension => ({ directive, specs: () => [] });
    expect(() => villanelle({ source, extensions: [named("set")] })).toThrow(TypeError);
    expect(() => villanelle({ source, extensions: [named("use")] })).toThrow(TypeError);
    expect(() => villanelle({ source, extensions: [named("x"), named("x")] })).toThrow(TypeError);
  });
});

describe("rule 2: set", () => {
  it("binds from its line to the end of the block, nested blocks included", async () => {
    const loaded = await loadText("a $v;\nset $v 1;\nb $v;\nc { d { e $v; } }\n");
    expect(problems(loaded.diagnostics)).toEqual([["E5001", "main.conf:0:2"]]);
    expect(addresses(loaded)).toEqual(["b", "c", "c > d", "c > d > e"]);
  });

  it("refuses any other form with E5009 at set", async () => {
    for (const line of ["set;", "set x 1;", "set $a;", "set $a 1 { b; }", "set [$a] 1;"]) {
      const loaded = await loadText(`${line}\nok;\n`);
      expect(problems(loaded.diagnostics), line).toEqual([["E5009", "main.conf:0:0"]]);
      expect(loaded.unreadable.map((u) => u.kind), line).toEqual(["expansion"]);
      expect(addresses(loaded), line).toEqual(["ok"]);
    }
  });

  it("allows one set per name per block (E5002 at the second $name) and shadowing in an inner block", async () => {
    const loaded = await loadText("set $a 1;\nset $a 2;\nb { set $a 3; c $a; }\nd $a;\n");
    expect(problems(loaded.diagnostics)).toEqual([["E5002", "main.conf:1:4"]]);
    const [b, d] = loaded.body;
    expect(texts(only(b?.body))).toEqual(["3"]);
    expect(texts(d)).toEqual(["1"]);
  });

  it("copies another variable's values as visible there, kinds kept", async () => {
    const loaded = await loadText("set $a x \"y\" [1, 2] c[1:2] c[3];\nset $b $a;\nv $b;\n");
    expect(loaded.diagnostics).toEqual([]);
    const v = only(loaded.body);
    expect(v.args.map((a) => [a.kind, a.text])).toEqual([
      ["word", "x"],
      ["string", '"y"'],
      ["list", "[1, 2]"],
      ["slice", "c[1:2]"],
      ["index", "c[3]"],
    ]);
  });
});

describe("rule 3: handed-in values", () => {
  it("win over every set of the name and are visible everywhere", async () => {
    const files = {
      "main.conf": 'set $h "file";\na $h;\nb { set $h "inner"; c $h; }\nsnippet s { d $h; }\nuse s;\ninc { include "x.conf" { set $h "block"; } }\n',
      "x.conf": 'set $h "x";\ne $h;\n',
    };
    const loaded = await loadFiles(files, { ...INCLUDE, variables: { h: "given" } });
    expect(loaded.diagnostics).toEqual([]);
    const values: string[] = [];
    loaded.walk((d) => {
      values.push(...texts(d));
    });
    expect(values).toEqual(["given", "given", "given", "given"]);
  });

  it("are read as a run of values, with no variable, block or bad value", async () => {
    const loaded = await loadText("p $ports;\n", { variables: { ports: '8080 443 "x" [1, 2]' } });
    expect(texts(only(loaded.body))).toEqual(["8080", "443", '"x"', "[1, 2]"]);
    expect(only(loaded.body).args.map((a) => originText(a.origin))).toEqual([
      "handed ports < variable ports main.conf:0:2",
      "handed ports < variable ports main.conf:0:2",
      "handed ports < variable ports main.conf:0:2",
      "handed ports < variable ports main.conf:0:2",
    ]);
    for (const bad of ["", "   ", '"open', "$x", "a { b; }", '"\\q"', "c[x]", "a; b", "{"]) {
      await expect(loadText("p;\n", { variables: { v: bad } }), bad).rejects.toThrow(TypeError);
    }
    for (const name of ["", "a-b", "$a", "a b"]) {
      await expect(loadText("p;\n", { variables: { [name]: "1" } }), name).rejects.toThrow(TypeError);
    }
  });
});

describe("rule 4: $name as a value", () => {
  it("becomes all its values in a directive and in a list", async () => {
    const loaded = await loadText("set $ports 8080 443;\nport $ports dev;\nallow [$ports, 1];\n");
    const [port, allow] = loaded.body;
    expect(texts(port)).toEqual(["8080", "443", "dev"]);
    expect(texts(allow)).toEqual(["[8080, 443, 1]"]);
    expect(allow?.args[0]?.items()).toHaveLength(3);
  });

  it("can be a whole slice bound holding one IntegerText word", async () => {
    const loaded = await loadText("set $n 3;\nc a[0:$n] a[$n] a[$n:] a[:$n];\n");
    expect(texts(only(loaded.body))).toEqual(["a[0:3]", "a[3]", "a[3:]", "a[:3]"]);
  });

  it("gives E4001 for a bound variable that is not exactly one IntegerText word, at its value via the variable", async () => {
    for (const [value, place] of [
      ["x1", "main.conf:0:7"],
      ["1.5", "main.conf:0:7"],
      ['"3"', "main.conf:0:7"],
    ] as const) {
      const loaded = await loadText(`set $n ${value};\nc a[$n];\nok;\n`);
      expect(problems(loaded.diagnostics), value).toEqual([["E4001", `${place} < variable n main.conf:1:4`]]);
      expect(loaded.unreadable.map((u) => u.kind)).toEqual(["value"]);
      expect(addresses(loaded)).toEqual(["ok"]);
    }
    const two = await loadText("set $n 1 2;\nc a[$n];\n");
    expect(problems(two.diagnostics)).toEqual([["E4001", "main.conf:0:7 < variable n main.conf:1:4"]]);
  });

  it("places a bad handed-in bound on the $name", async () => {
    const loaded = await loadText("c a[$n];\n", { variables: { n: "x" } });
    expect(problems(loaded.diagnostics)).toEqual([["E4001", "main.conf:0:4"]]);
  });

  it("gives E5001 at the $name when nothing is set or handed in, and never expands to nothing", async () => {
    const loaded = await loadText("a { max_count $pixel; }\n");
    expect(problems(loaded.diagnostics)).toEqual([["E5001", "main.conf:0:14"]]);
    const a = only(loaded.body);
    expect(a.body).toEqual([]);
    expect(a.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([["expansion", "main.conf:0:4"]]);
  });
});

describe("rules 5 and 6: snippet and use", () => {
  it("splices the body in place with its parameters bound by position", async () => {
    const loaded = await loadText("snippet s $a $b {\n  x $b $a;\n  y;\n}\nbefore;\nuse s 1 [2, 3];\nafter;\n");
    expect(loaded.diagnostics).toEqual([]);
    expect(addresses(loaded)).toEqual(["before", "x", "y", "after"]);
    expect(texts(loaded.body[1])).toEqual(["[2, 3]", "1"]);
  });

  it("takes a snippet with no parameters", async () => {
    const loaded = await loadText("snippet s { x; }\nuse s;\n");
    expect(addresses(loaded)).toEqual(["x"]);
  });

  it("counts a multi-value variable as several values", async () => {
    const loaded = await loadText("set $two 1 2;\nsnippet s $a $b { x $a $b; }\nuse s $two;\n");
    expect(loaded.diagnostics).toEqual([]);
    expect(texts(only(loaded.body))).toEqual(["1", "2"]);
  });

  it("looks only at snippets for use (its own namespace)", async () => {
    const loaded = await loadText("universe 1;\nsnippet universe { u 2; }\nuse universe;\n");
    expect(addresses(loaded)).toEqual(["universe", "u"]);
  });

  it("gives a snippet a block-scoped visibility from its line on", async () => {
    const loaded = await loadText("use s;\nb { snippet s { x; } use s; }\nuse s;\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E5003", "main.conf:0:4"],
      ["E5003", "main.conf:2:4"],
    ]);
    expect(addresses(loaded)).toEqual(["b", "b > x"]);
  });

  it("exports nothing from a body: neither set nor snippet", async () => {
    const loaded = await loadText("snippet s { set $v 1; snippet t { y; } x $v; use t; }\nuse s;\nz $v;\nuse t;\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E5001", "main.conf:2:2"],
      ["E5003", "main.conf:3:4"],
    ]);
    expect(addresses(loaded)).toEqual(["x", "y"]);
  });

  it("treats parameters as the body block's own: a set of one there is E5002", async () => {
    const loaded = await loadText("snippet s $a { set $a 2; x $a; }\nuse s 1;\n");
    expect(problems(loaded.diagnostics)).toEqual([["E5002", "main.conf:0:19 < use s main.conf:1:0"]]);
    expect(texts(only(loaded.body))).toEqual(["1"]);
  });

  it("sees its defining block as it stands at the use, never the use site's own block", async () => {
    const loaded = await loadText("snippet s { x $late; }\nset $late 1;\nuse s;\nb { set $mine 2; snippet t { y $mine; } use t; }\nc { set $z 3; use s; }\n");
    expect(loaded.diagnostics).toEqual([]);
    expect(loaded.body.map((d) => [d.address.toString(), ...texts(d)])).toEqual([
      ["x", "1"],
      ["b"],
      ["c"],
    ]);
  });

  it("gives E5003 at the name, E5004 at use, E5005 at the second name", async () => {
    const loaded = await loadText("use nope;\nsnippet s $a { x $a; }\nuse s;\nuse s 1 2;\nsnippet s { y; }\nok;\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E5003", "main.conf:0:4"],
      ["E5004", "main.conf:2:0"],
      ["E5004", "main.conf:3:0"],
      ["E5005", "main.conf:4:8"],
    ]);
    expect(loaded.unreadable.map((u) => u.kind)).toEqual(["expansion", "expansion", "expansion", "expansion"]);
    expect(addresses(loaded)).toEqual(["ok"]);
  });

  it("refuses other snippet forms with E5010 at snippet", async () => {
    for (const line of ["snippet;", "snippet s $a;", "snippet s x { y; }", "snippet s $a $a { y; }", 'snippet "s" { y; }', "snippet { y; }"]) {
      const loaded = await loadText(`${line}\n`);
      expect(problems(loaded.diagnostics), line).toEqual([["E5010", "main.conf:0:0"]]);
    }
  });

  it("refuses other use forms with E5011 at use", async () => {
    for (const line of ["use;", "use s { x; }", 'use "s";', "use [s];"]) {
      const loaded = await loadText(`snippet s { y; }\n${line}\n`);
      expect(problems(loaded.diagnostics), line).toEqual([["E5011", "main.conf:1:0"]]);
    }
  });

  it("reports a problem inside a body at each use, with the use step", async () => {
    const loaded = await loadText("snippet s { x $nope; ok; }\nuse s;\nuse s;\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E5001", "main.conf:0:14 < use s main.conf:1:0"],
      ["E5001", "main.conf:0:14 < use s main.conf:2:0"],
    ]);
    expect(addresses(loaded)).toEqual(["ok", "ok #1"]);
  });
});

describe("rules 7 and 8: extension directives and their blocks", () => {
  it("splices an included file's statements in place, its set and snippet visible after the line", async () => {
    const files = { "main.conf": 'a;\ninclude "lib.conf";\nb $v;\nuse s;\n', "lib.conf": "set $v 1;\nsnippet s { c; }\nl;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(loaded.diagnostics).toEqual([]);
    expect(addresses(loaded)).toEqual(["a", "l", "b", "c"]);
  });

  it("counts an included file's set for the including block's one-set check", async () => {
    const files = { "main.conf": 'set $v 0;\ninclude "lib.conf";\n', "lib.conf": "set $v 1;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(problems(loaded.diagnostics)).toEqual([["E5002", "lib.conf:0:4 < extension include main.conf:1:0"]]);
  });

  it("lets the block's set lines win over the file's own set inside the file; after the line the file's own is seen", async () => {
    const files = { "main.conf": 'include "lib.conf" { set $v 2; }\nafter $v;\n', "lib.conf": "set $v 1;\nin $v;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(loaded.diagnostics).toEqual([]);
    expect(loaded.body.map((d) => [d.name, ...texts(d)])).toEqual([
      ["in", "2"],
      ["after", "1"],
    ]);
  });

  it("allows only set lines in an extension's block (E5012 at the first other line)", async () => {
    const files = { "main.conf": 'include "lib.conf" {\n  set $v 2;\n  other;\n}\nz;\n', "lib.conf": "l;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(problems(loaded.diagnostics)).toEqual([["E5012", "main.conf:2:2"]]);
    expect(loaded.unreadable.map((u) => u.kind)).toEqual(["extension"]);
    expect(loaded.diagnostics[0]?.at.span.end.column).toBe(7);
    expect(addresses(loaded)).toEqual(["z"]);
  });

  it("keeps an include whose block holds a syntax error unreadable, reported once by the parser", async () => {
    const files = { "main.conf": 'include "lib.conf" {\n  set $v x"y";\n}\nz;\n', "lib.conf": "l;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(loaded.diagnostics.map((d) => d.code)).toEqual(["E2009"]);
    expect(loaded.unreadable.map((u) => u.kind)).toEqual(["syntax"]);
    expect(addresses(loaded)).toEqual(["z"]);
  });

  it("reads a file included at two places once: one graph node, two edges (R21)", async () => {
    const { source, reads } = countingSource({ "main.conf": 'a { include "p.conf"; }\nb { include "p.conf"; }\n', "p.conf": "x 1;\n" });
    const loaded = await rendered(villanelle({ source, extensions: [include()] }), "main.conf");
    expect(loaded.diagnostics).toEqual([]);
    expect([...reads]).toEqual([
      ["main.conf", 1],
      ["p.conf", 1],
    ]);
    expect([...loaded.graph.documents.keys()]).toEqual(["main.conf", "p.conf"]);
    expect(loaded.graph.edges().map((e) => [e.copy.statement.kind, originText({ written: e.copy.statement.place, via: e.copy.via }), e.specs, e.targets])).toEqual([
      ["extension", "main.conf:0:4", ["p.conf"], ["p.conf"]],
      ["extension", "main.conf:1:4", ["p.conf"], ["p.conf"]],
    ]);
    expect(addresses(loaded)).toEqual(["a", "a > x", "b", "b > x"]);
  });

  it("splices a glob's files in code-point order", async () => {
    const files = { "main.conf": 'include "d/*.conf";\n', "d/b.conf": "b;\n", "d/B.conf": "B;\n", "d/a.conf": "a;\n", "d/é.conf": "e;\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(addresses(loaded)).toEqual(["B", "a", "b", "e"]);
    expect(loaded.graph.edges()[0]?.targets).toEqual(["d/B.conf", "d/a.conf", "d/b.conf", "d/é.conf"]);
  });

  it("gives E3001 when a spec matches nothing and E3004 when the source rejects, at the directive's name", async () => {
    const missing = await loadFiles({ "main.conf": 'x {\n  include "nope.conf";\n}\n' }, INCLUDE);
    expect(problems(missing.diagnostics)).toEqual([["E3001", "main.conf:1:2"]]);
    expect(missing.body[0]?.unreadable.map((u) => u.kind)).toEqual(["extension"]);
    expect(missing.graph.edges()[0]?.targets).toEqual([]);

    const failing = (resolve: boolean): ReturnType<typeof memorySource> => ({
      resolve: (spec) =>
        spec === "main.conf" ? Promise.resolve([spec]) : resolve ? Promise.resolve(["other"]) : Promise.reject(new Error("network down")),
      read: (path) => (path === "main.conf" ? Promise.resolve('include "other";\n') : Promise.reject(new Error("gone"))),
    });
    for (const resolve of [false, true]) {
      const loaded = await rendered(villanelle({ source: failing(resolve), extensions: [include()] }), "main.conf");
      expect(problems(loaded.diagnostics)).toEqual([["E3004", "main.conf:0:0"]]);
      expect(loaded.diagnostics[0]?.message).toContain(resolve ? "gone" : "network down");
      expect(loaded.unreadable.map((u) => u.kind)).toEqual(["extension"]);
    }
  });

  it("rejects the load with a DiagnosticError E3004 at the root file when the source cannot read it", async () => {
    const error: unknown = await loadFiles({}, {}, "missing.conf").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DiagnosticError);
    const { diagnostic } = error as DiagnosticError;
    expect(diagnostic.code).toBe(DiagnosticCode.IncludeResolverFailed);
    expect(diagnostic.at).toEqual({ kind: "file", resolvedPath: "missing.conf", span: { start: { offset: 0, line: 0, column: 0 }, end: { offset: 0, line: 0, column: 0 } } });
    expect(diagnostic.via).toEqual([]);
  });

  it("gives E3005 when include does not have exactly one quoted path, on the bad value or the name", async () => {
    const cases = [
      ["include bare;", "main.conf:0:8"],
      ["include;", "main.conf:0:0"],
      ['include "a" "b";', "main.conf:0:12"],
      ["include [a];", "main.conf:0:8"],
      ["include a[1:2];", "main.conf:0:8"],
    ] as const;
    for (const [line, at] of cases) {
      const loaded = await loadFiles({ "main.conf": `${line}\n`, a: "x;" }, INCLUDE);
      expect(problems(loaded.diagnostics), line).toEqual([["E3005", at]]);
      expect(loaded.unreadable.map((u) => u.kind), line).toEqual(["extension"]);
    }
  });

  it("gives E3006 when an extension throws anything but a DiagnosticError, and records a DiagnosticError as thrown", async () => {
    const throwing: IExtension = {
      directive: "pull",
      specs: (use) => {
        if (use.args.length === 0) throw new Error("boom");
        throw use.args[0]?.error("bad pull", "test/bad-pull") ?? new Error("no value");
      },
    };
    const loaded = await loadText("pull;\npull x;\n", { extensions: [throwing] });
    expect(problems(loaded.diagnostics)).toEqual([
      ["E3006", "main.conf:0:0"],
      ["test/bad-pull", "main.conf:1:5"],
    ]);
    expect(loaded.unreadable.map((u) => u.kind)).toEqual(["extension", "extension"]);
  });

  it("reports an included file's syntax error once and keeps an unreadable entry at each place", async () => {
    const files = { "main.conf": 'a "open\na { include "p.conf"; }\nb { include "p.conf"; }\n', "p.conf": "x 1;\ny x\"z\";\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(loaded.diagnostics.map((d) => [d.code, d.at.resolvedPath])).toEqual([
      ["E1001", "main.conf"],
      ["E2009", "p.conf"],
    ]);
    expect(loaded.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([["syntax", "main.conf:0:0"]]);
    const [a, b] = loaded.body;
    expect(a?.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([["syntax", "p.conf:1:0 < extension include main.conf:1:4"]]);
    expect(b?.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([["syntax", "p.conf:1:0 < extension include main.conf:2:4"]]);
  });
});

describe("rule 9: limits and cycles", () => {
  it("gives E5006 at the use that closes a cycle", async () => {
    const loaded = await loadText("snippet a { use b; }\nsnippet b { use a; }\nuse a;\nz;\n");
    expect(problems(loaded.diagnostics)).toEqual([["E5006", "main.conf:1:12 < use b main.conf:0:12 < use a main.conf:2:0"]]);
    expect(addresses(loaded)).toEqual(["z"]);
    const self = await loadText("snippet a { x; use a; }\nuse a;\n");
    expect(problems(self.diagnostics)).toEqual([["E5006", "main.conf:0:15 < use a main.conf:1:0"]]);
    expect(addresses(self)).toEqual(["x"]);
  });

  it("gives E5006 at the include that closes a cycle, the root counted", async () => {
    const files = { "main.conf": 'include "a.conf";\n', "a.conf": 'include "b.conf";\n', "b.conf": 'include "a.conf";\nb;\n' };
    const loaded = await loadFiles(files, INCLUDE);
    expect(problems(loaded.diagnostics)).toEqual([["E5006", "b.conf:0:0 < extension include a.conf:0:0 < extension include main.conf:0:0"]]);
    expect(addresses(loaded)).toEqual(["b"]);
  });

  it("allows 16 nested includes and gives E5007 at the 17th", async () => {
    const chain = (levels: number): Record<string, string> => {
      const files: Record<string, string> = { "main.conf": 'include "1.conf";\n' };
      for (let i = 1; i <= levels; i++) files[`${String(i)}.conf`] = i < levels ? `include "${String(i + 1)}.conf";\n` : "leaf;\n";
      return files;
    };
    const sixteen = await loadFiles(chain(16), INCLUDE);
    expect(sixteen.diagnostics).toEqual([]);
    expect(addresses(sixteen)).toEqual(["leaf"]);
    const seventeen = await loadFiles(chain(17), INCLUDE);
    expect(seventeen.diagnostics.map((d) => [d.code, d.at.resolvedPath, d.via.length])).toEqual([["E5007", "16.conf", 16]]);
    expect(addresses(seventeen)).toEqual([]);
  });

  it("gives E5007 for snippets nested deeper than 16 uses", async () => {
    const chain = (levels: number): string => {
      let text = "snippet s0 { leaf; }\n";
      for (let i = 1; i < levels; i++) text += `snippet s${String(i)} { use s${String(i - 1)}; }\n`;
      return `${text}use s${String(levels - 1)};\n`;
    };
    expect((await loadText(chain(16))).diagnostics).toEqual([]);
    expect((await loadText(chain(17))).diagnostics.map((d) => d.code)).toEqual(["E5007"]);
  });

  it("gives E5008 past 100,000 directives and stops expanding there", async () => {
    const ten = (name: string, line: string): string => `snippet ${name} {\n${`  ${line}\n`.repeat(10)}}\n`;
    const text = `${ten("a", "x;")}${ten("b", "use a;")}${ten("c", "use b;")}${ten("d", "use c;")}${ten("e", "use d;")}first;\nuse e;\nnever;\n`;
    const loaded = await loadText(text);
    // `first` and 99,999 of e's 100,000 x lines fit; the last x (each snippet's tenth line) is one too many.
    expect(problems(loaded.diagnostics)).toEqual([
      ["E5008", "main.conf:10:2 < use a main.conf:22:2 < use b main.conf:34:2 < use c main.conf:46:2 < use d main.conf:58:2 < use e main.conf:61:0"],
    ]);
    let count = 0;
    loaded.walk(() => {
      count++;
    });
    expect(count).toBe(100_000);
    expect(loaded.body.at(-1)?.name).toBe("x");
    expect(loaded.unreadable).toHaveLength(1);
  });
});

describe("rule 10: value rules checked at load", () => {
  it("keeps a directive with an unknown escape or a non-integer bound unreadable (kind value)", async () => {
    const loaded = await loadText('a "x\\qy";\nb c[1.5];\nd c[-3:-1] e[007];\nok "\\n";\n');
    expect(problems(loaded.diagnostics)).toEqual([
      ["E4003", "main.conf:0:2"],
      ["E4001", "main.conf:1:4"],
      ["E4001", "main.conf:2:13"],
    ]);
    expect(loaded.unreadable.map((u) => u.kind)).toEqual(["value", "value", "value"]);
    expect(addresses(loaded)).toEqual(["ok"]);
  });

  it("refuses a bound outside the safe integer range", async () => {
    const loaded = await loadText("a c[9007199254740993];\nb c[9007199254740991];\n");
    expect(problems(loaded.diagnostics)).toEqual([["E4001", "main.conf:0:4"]]);
    expect(texts(only(loaded.body))).toEqual(["c[9007199254740991]"]);
  });
});

describe("rules 11 and 12: unreadable statements and diagnostics order", () => {
  it("keeps a bad line in its place without its block expanded, siblings kept", async () => {
    const loaded = await loadText("a {\n  b 1;\n  : x;\n  c $nope { d $nope2; }\n  e;\n}\n");
    expect(problems(loaded.diagnostics)).toEqual([
      ["E2001", "main.conf:2:2"],
      ["E5001", "main.conf:3:4"],
    ]);
    const a = only(loaded.body);
    expect(a.unreadable.map((u) => [u.kind, originText(u.origin)])).toEqual([
      ["syntax", "main.conf:2:2"],
      ["expansion", "main.conf:3:2"],
    ]);
    expect(addresses(loaded)).toEqual(["a", "a > b", "a > e"]);
  });

  it("puts every file's syntax diagnostics first, in first-read order, then load diagnostics", async () => {
    const files = { "main.conf": 'x $nope;\ninclude "a.conf";\nb {\n', "a.conf": "y $nope;\nz x\"y\";\n" };
    const loaded = await loadFiles(files, INCLUDE);
    expect(loaded.diagnostics.map((d) => [d.code, d.at.resolvedPath])).toEqual([
      ["E2003", "main.conf"],
      ["E2009", "a.conf"],
      ["E5001", "main.conf"],
      ["E5001", "a.conf"],
    ]);
  });

  it("never rejects for broken text", async () => {
    for (const broken of ["a {", '"', "}", "a [", "\u0001", 'a "b\nc;', "$", "set", "use", "snippet s {", ""]) {
      const loaded = await loadText(broken);
      expect(Array.isArray(loaded.diagnostics), broken).toBe(true);
    }
  });
});
