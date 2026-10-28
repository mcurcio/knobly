import { describe, expect, it } from "vitest";

import type { IDirective } from "./directive.js";
import { type ILoaded, villanelle } from "./processor.js";
import { memorySource } from "./source.js";

const RASL = "set $pixels 2284;\ngraph {\n  node DdpSink leds { max_count $pixels; }\n}\n";

async function load(text: string, variables?: Record<string, string>): Promise<ILoaded> {
  const processor = villanelle({ source: memorySource({ "main.conf": text }) });
  return processor.load("main.conf", variables === undefined ? undefined : { variables });
}

function only(directives: readonly IDirective[] | undefined): IDirective {
  expect(directives).toHaveLength(1);
  const [directive] = directives ?? [];
  if (directive === undefined) throw new Error("no directive");
  return directive;
}

describe("the load tracer (set and $name)", () => {
  it("replaces a variable by its value, with the definition and the use site in its origin", async () => {
    const loaded = await load(RASL);
    expect(loaded.diagnostics).toEqual([]);
    const leds = only(only(loaded.body).body);
    const maxCount = only(leds.body);
    expect(maxCount.name).toBe("max_count");
    const [value] = maxCount.args;
    expect(maxCount.args).toHaveLength(1);
    expect(value?.text).toBe("2284");
    expect(value?.origin.written).toMatchObject({ kind: "file", resolvedPath: "main.conf", span: { start: { line: 0, column: 12 } } });
    expect(value?.origin.via).toEqual([
      {
        kind: "variable",
        name: "pixels",
        at: { kind: "file", resolvedPath: "main.conf", span: { start: { offset: 58, line: 2, column: 32 }, end: { offset: 65, line: 2, column: 39 } } },
      },
    ]);
  });

  it("keeps a directive with an unknown variable as unreadable, with one located E5001", async () => {
    const loaded = await load(RASL.replace("max_count $pixels", "max_count $pixel"));
    expect(loaded.diagnostics.map((d) => [d.code, d.at.resolvedPath, d.at.span.start.line, d.at.span.start.column])).toEqual([
      ["E5001", "main.conf", 2, 32],
    ]);
    const leds = only(only(loaded.body).body);
    expect(leds.body).toEqual([]);
    expect(leds.unreadable).toHaveLength(1);
    expect(leds.unreadable[0]?.kind).toBe("expansion");
    expect(leds.unreadable[0]?.origin.written.span.start).toMatchObject({ line: 2, column: 22 });
  });

  it("lets a handed-in value win over the file's set (L3)", async () => {
    const loaded = await load('set $host "10.0.0.1";\ntarget $host;', { host: '"10.0.0.2"' });
    expect(loaded.diagnostics).toEqual([]);
    const [value] = only(loaded.body).args;
    expect(value?.text).toBe('"10.0.0.2"');
    expect(value?.origin.written).toEqual({ kind: "handed", variable: "host" });
  });
});
