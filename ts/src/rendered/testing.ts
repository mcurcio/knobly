/**
 * Test helpers for the rendered layer's tests: loads through the public processor over `memorySource`, then
 * `render (graph)`. Not shipped (tsconfig.build.json leaves it out).
 */

import type { IOrigin, IPlace, IStep } from "../origin.js";
import type { ILocatedDiagnostic } from "../report.js";
import { type IDocumentSource, memorySource } from "../source.js";
import { type ConfigText, text } from "../text.js";
import { type IExtension, type IProcessor, villanelle } from "../written/index.js";
import type { IDirective, IKeyOptions, IRendered } from "./model.js";
import { render } from "./render.js";

/** Plain test strings as config text, each through `text()` (spec 6.9). */
export function configTexts(texts: Readonly<Record<string, string>>): Record<string, ConfigText> {
  return Object.fromEntries(Object.entries(texts).map(([name, given]) => [name, text(given)]));
}

export interface ITestOptions {
  readonly overrides?: Readonly<Record<string, string>>;
  readonly extensions?: readonly IExtension[];
}

/** A processor over these files. */
export function processorOf(files: Readonly<Record<string, string>>, options: ITestOptions = {}): IProcessor {
  return villanelle({
    source: memorySource(files),
    ...(options.extensions === undefined ? {} : { extensions: options.extensions }),
  });
}

/** `render(await processor.load(path, options))`. */
export async function rendered(processor: IProcessor, path: string, options?: { readonly overrides?: Readonly<Record<string, ConfigText>> }): Promise<IRendered> {
  return render(await processor.load(path, options));
}

/** Load `main.conf` (or `root`) from these files, and render it. */
export async function loadFiles(files: Readonly<Record<string, string>>, options: ITestOptions = {}, root = "main.conf"): Promise<IRendered> {
  const processor = processorOf(files, options);
  return render(await processor.load(root, options.overrides === undefined ? undefined : { overrides: configTexts(options.overrides) }));
}

/** Load one text as `main.conf`, and render it. */
export function loadText(text: string, options: ITestOptions = {}): Promise<IRendered> {
  return loadFiles({ "main.conf": text }, options);
}

/** A source that counts each `read` per path. */
export function countingSource(files: Readonly<Record<string, string>>): { source: IDocumentSource; reads: Map<string, number> } {
  const inner = memorySource(files);
  const reads = new Map<string, number>();
  return {
    reads,
    source: {
      resolve: (spec, context) => inner.resolve(spec, context),
      read: (path) => {
        reads.set(path, (reads.get(path) ?? 0) + 1);
        return inner.read(path);
      },
    },
  };
}

/** The one element of a list; fails the test otherwise. */
export function only<T>(list: readonly T[] | undefined): T {
  if (list?.length !== 1) throw new Error(`expected one element, found ${String(list?.length)}`);
  return list[0] as T;
}

/** `path:line:col`, 0-based, as the load conformance format writes it. */
export function placeText(place: IPlace): string {
  return `${place.resolvedPath}:${String(place.span.start.line)}:${String(place.span.start.column)}`;
}

/** An origin as the load conformance format writes it. */
export function originText({ place, via }: { readonly place: IOrigin["place"]; readonly via: readonly IStep[] }): string {
  const head = place.kind === "override" ? `override ${place.variable}` : placeText(place);
  return head + via.map((step) => ` < ${step.kind} ${step.name} ${placeText(step.place)}`).join("");
}

/** Each diagnostic as `[code, origin]`. */
export function problems(diagnostics: Iterable<ILocatedDiagnostic>): [string, string][] {
  return [...diagnostics].map((d) => [d.code, originText(d)]);
}

/** Every directive's people address in walk order, under `options.key`. */
export function addresses(rendered: IRendered, options?: IKeyOptions): string[] {
  return [...rendered.addresses(options).values()].map((address) => address.toString());
}

/** One directive's people address under `options.key`. */
export function addressOf(rendered: IRendered, directive: IDirective, options?: IKeyOptions): string {
  return rendered.addresses(options).get(directive)?.toString() ?? "";
}

/** Each of the directive's values' canonical text. */
export function texts(directive: IDirective | undefined): string[] {
  return directive?.values.map((a) => a.text) ?? [];
}
