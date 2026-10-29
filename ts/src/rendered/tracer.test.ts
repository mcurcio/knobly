import { describe, expect, it } from "vitest";

import type { IDirective } from "./model.js";
import type { IRendered } from "./model.js";
import { render } from "./render.js";
import { villanelle } from "../written/processor.js";
import { memorySource } from "../source.js";

const RASL = "set $pixels 2284;\ngraph {\n  node DdpSink leds { max_count $pixels; }\n}\n";

async function load(text: string, overrides?: Record<string, string>): Promise<IRendered> {
  const processor = villanelle({ source: memorySource({ "main.conf": text }) });
  return render(await processor.load("main.conf", overrides === undefined ? undefined : { overrides }));
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
    const leds = only(only(loaded.block).block);
    const maxCount = only(leds.block);
    expect(maxCount.name).toBe("max_count");
    const [value] = maxCount.values;
    expect(maxCount.values).toHaveLength(1);
    expect(value?.text).toBe("2284");
    expect(value?.origin.place).toMatchObject({ kind: "file", resolvedPath: "main.conf", span: { start: { line: 0, column: 12 } } });
    expect(value?.origin.via).toEqual([
      {
        kind: "variable",
        name: "pixels",
        place: { kind: "file", resolvedPath: "main.conf", span: { start: { offset: 58, line: 2, column: 32 }, end: { offset: 65, line: 2, column: 39 } } },
      },
    ]);
  });

  it("keeps a directive with an unknown variable as unreadable, with one located E5001", async () => {
    const loaded = await load(RASL.replace("max_count $pixels", "max_count $pixel"));
    expect(loaded.diagnostics.map((d) => [d.code, d.place.resolvedPath, d.place.span.start.line, d.place.span.start.column])).toEqual([
      ["E5001", "main.conf", 2, 32],
    ]);
    const leds = only(only(loaded.block).block);
    expect(leds.block).toEqual([]);
    expect(leds.unreadable).toHaveLength(1);
    expect(leds.unreadable[0]?.reason).toBe("expansion");
    expect(leds.unreadable[0]?.origin.place.span.start).toMatchObject({ line: 2, column: 22 });
  });

  it("lets an override win over the file's set (L3)", async () => {
    const loaded = await load('set $host "10.0.0.1";\ntarget $host;', { host: '"10.0.0.2"' });
    expect(loaded.diagnostics).toEqual([]);
    const [value] = only(loaded.block).values;
    expect(value?.text).toBe('"10.0.0.2"');
    expect(value?.origin.place).toEqual({ kind: "override", variable: "host" });
  });
});
