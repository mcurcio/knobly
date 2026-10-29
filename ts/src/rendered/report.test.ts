/**
 * The Diagnostics sink, program codes and formatDiagnostic, through the public processor.
 */

import { describe, expect, it } from "vitest";

import { include } from "../include.js";
import { formatDiagnostic } from "../written/index.js";
import { loadFiles, loadText, only, problems } from "./testing.js";
import { DiagnosticCode, DiagnosticError, Diagnostics, type LocatedDiagnostic, MisuseError, type ProgramCode } from "../index.js";

describe("Diagnostics", () => {
  it("starts with the load's problems and records add and report in order", async () => {
    const loaded = await loadText("a $nope;\nnode x;\n");
    const sink = new Diagnostics(loaded.diagnostics);
    const node = only(loaded.block);
    sink.report(node, "no such node", "rasl/unknown-node");
    sink.report(only(node.values), "bad id", "rasl/bad-id");
    sink.report(loaded, "no graph", "rasl/no-graph");
    const extra: LocatedDiagnostic = { code: "rasl/x", message: "x", place: loaded.origin.place, via: [] };
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
    for (const code of ["E5001", "nope", "/x", "x/", "", "rasl/ bad name", "a b/c"] as ProgramCode[]) {
      expect(() => directive.error("m", code), code).toThrow(MisuseError);
      expect(() => arg.error("m", code), code).toThrow(MisuseError);
      expect(() => loaded.error("m", code), code).toThrow(MisuseError);
      expect(() => new Diagnostics().report(directive, "m", code), code).toThrow(MisuseError);
    }
    const error = directive.error("m", "rasl/ok");
    expect(error).toBeInstanceOf(DiagnosticError);
    expect(error.diagnostic.code).toBe("rasl/ok");
  });

  it("places a program's error on an override at the $name that used it", async () => {
    const loaded = await loadText("@set $host h;\nouter { target $host; }\n", { overrides: { host: "given" } });
    const arg = only(only(only(loaded.block).block).values);
    expect(problems([arg.error("unreachable", "rasl/host").diagnostic])).toEqual([["rasl/host", "main.conf:1:15"]]);
  });
});

describe("formatDiagnostic", () => {
  it("prints path:line:col: code: message 1-based, the source line, a caret and one via line per step", async () => {
    const files = { "main.conf": '@include "x.conf";\n', "x.conf": "a 1;\nport c[0~$n];\n" };
    const loaded = await loadFiles(files, { extensions: [include()] });
    expect(formatDiagnostic(only(loaded.diagnostics), loaded.graph)).toBe(
      ["x.conf:2:10: E5001: unknown variable: $n", "port c[0~$n];", "         ^^", "  via extension include at main.conf:1:1"].join("\n"),
    );
  });

  it("prints the via lines for a problem reached through a use", async () => {
    const loaded = await loadText("@snippet s {\n\tx $nope;\n}\n@use s;\n");
    expect(formatDiagnostic(loaded.diagnostics[0] as LocatedDiagnostic, loaded.graph)).toBe(
      ["main.conf:2:4: E5001: unknown variable: $nope", "\tx $nope;", "\t  ^^^^^", "  via use s at main.conf:4:1"].join("\n"),
    );
  });

  it("prints only the first line without the file in the graph", async () => {
    const loaded = await loadText("x $nope;\n");
    expect(formatDiagnostic(loaded.diagnostics[0] as LocatedDiagnostic)).toBe("main.conf:1:3: E5001: unknown variable: $nope");
  });

  it("keeps a lone carriage return in the source line (spec/contract.md 1)", async () => {
    const loaded = await loadText("x $nope; # a\rb\n");
    const unknown = loaded.diagnostics.find((d) => d.code === DiagnosticCode.UnknownVariable);
    expect(formatDiagnostic(unknown as LocatedDiagnostic, loaded.graph).split("\n")).toEqual([
      "main.conf:1:3: E5001: unknown variable: $nope",
      "x $nope; # a\rb",
      "  ^^^^^",
    ]);
  });
});
