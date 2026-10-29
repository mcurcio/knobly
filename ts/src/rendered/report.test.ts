/**
 * The Diagnostics sink, program codes and formatDiagnostic, through the public processor.
 */

import { describe, expect, it } from "vitest";

import { DiagnosticError } from "../diagnostics.js";
import { include } from "../include.js";
import { Diagnostics, type ILocatedDiagnostic, type ProgramCode } from "../report.js";
import { formatDiagnostic } from "../written/format.js";
import { loadFiles, loadText, only, problems } from "./testing.js";

describe("Diagnostics", () => {
  it("starts with the load's problems and records add and report in order", async () => {
    const loaded = await loadText("a $nope;\nnode x;\n");
    const sink = new Diagnostics(loaded.diagnostics);
    const node = only(loaded.block);
    sink.report(node, "no such node", "rasl/unknown-node");
    sink.report(only(node.values), "bad id", "rasl/bad-id");
    sink.report(loaded, "no graph", "rasl/no-graph");
    const extra: ILocatedDiagnostic = { code: "rasl/x", message: "x", place: loaded.origin.place, via: [] };
    sink.add(extra);
    expect(sink.length).toBe(5);
    expect(problems(sink)).toEqual([
      ["E5001", "main.conf:0:2"],
      ["rasl/unknown-node", "main.conf:1:0"],
      ["rasl/bad-id", "main.conf:1:5"],
      ["rasl/no-graph", "main.conf:0:0"],
      ["rasl/x", "main.conf:0:0"],
    ]);
    expect(sink.toArray().map((d) => d.message)).toEqual([expect.stringContaining("$nope"), "no such node", "bad id", "no graph", "x"]);
    expect(new Diagnostics().length).toBe(0);
  });

  it("collect records a DiagnosticError and returns undefined; passes anything else through", async () => {
    const loaded = await loadText("port eighty;\n");
    const sink = new Diagnostics();
    const port = only(only(loaded.block).values);
    expect(sink.collect(() => port.integer())).toBeUndefined();
    expect(sink.collect(() => port.word())).toBe("eighty");
    expect(problems(sink)).toEqual([["E4005", "main.conf:0:5"]]);
    const bug = new RangeError("program bug");
    expect(() =>
      sink.collect(() => {
        throw bug;
      }),
    ).toThrow(bug);
    expect(sink.length).toBe(1);
  });

  it("refuses a program code without a namespace in every error() and in report()", async () => {
    const loaded = await loadText("a x;\n");
    const directive = only(loaded.block);
    const arg = only(directive.values);
    for (const code of ["E5001", "nope", "/x", "x/", ""] as ProgramCode[]) {
      expect(() => directive.error("m", code), code).toThrow(TypeError);
      expect(() => arg.error("m", code), code).toThrow(TypeError);
      expect(() => loaded.error("m", code), code).toThrow(TypeError);
      expect(() => new Diagnostics().report(directive, "m", code), code).toThrow(TypeError);
    }
    const error = directive.error("m", "rasl/ok");
    expect(error).toBeInstanceOf(DiagnosticError);
    expect(error.diagnostic.code).toBe("rasl/ok");
  });

  it("places a program's error on an override at the $name that used it", async () => {
    const loaded = await loadText("set $host h;\nouter { target $host; }\n", { overrides: { host: "given" } });
    const arg = only(only(only(loaded.block).block).values);
    expect(problems([arg.error("unreachable", "rasl/host").diagnostic])).toEqual([["rasl/host", "main.conf:1:15"]]);
  });
});

describe("formatDiagnostic", () => {
  it("prints path:line:col: code: message 1-based, the source line, a caret and one via line per step", async () => {
    const files = { "main.conf": 'include "x.conf";\n', "x.conf": "a 1;\nport c[0:$n];\n" };
    const loaded = await loadFiles(files, { extensions: [include()] });
    expect(formatDiagnostic(only(loaded.diagnostics), loaded.graph)).toBe(
      ["x.conf:2:10: E5001: unknown variable: $n", "port c[0:$n];", "         ^^", "  via extension include at main.conf:1:1"].join("\n"),
    );
  });

  it("prints the via lines for a problem reached through a use", async () => {
    const loaded = await loadText("snippet s {\n\tx $nope;\n}\nuse s;\n");
    expect(formatDiagnostic(loaded.diagnostics[0] as ILocatedDiagnostic, loaded.graph)).toBe(
      ["main.conf:2:4: E5001: unknown variable: $nope", "\tx $nope;", "\t  ^^^^^", "  via use s at main.conf:4:1"].join("\n"),
    );
  });

  it("prints only the first line without the file in the graph", async () => {
    const error: unknown = await loadFiles({}, {}, "gone.conf").catch((e: unknown) => e);
    const { diagnostic } = error as DiagnosticError;
    expect(formatDiagnostic(diagnostic)).toMatch(/^gone\.conf:1:1: E3004: include resolver failed: gone\.conf: [^\n]+$/);
  });
});
