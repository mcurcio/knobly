/**
 * Test helpers for the load layer's tests: loads through the public processor over `memorySource`. Not shipped
 * (tsconfig.build.json leaves it out).
 */

import type { IDirective, KeyRule } from "./directive.js";
import type { IOrigin, IPlace, IStep } from "./origin.js";
import { type IExtension, type ILoaded, type IProcessor, villanelle } from "./processor.js";
import type { ILocatedDiagnostic } from "./report.js";
import { type IDocumentSource, memorySource } from "./source.js";

export interface ITestOptions {
  readonly variables?: Readonly<Record<string, string>>;
  readonly key?: KeyRule;
  readonly extensions?: readonly IExtension[];
}

/** A processor over these files. */
export function processorOf(files: Readonly<Record<string, string>>, options: ITestOptions = {}): IProcessor {
  return villanelle({
    source: memorySource(files),
    ...(options.extensions === undefined ? {} : { extensions: options.extensions }),
    ...(options.key === undefined ? {} : { key: options.key }),
  });
}

/** Load `main.conf` (or `root`) from these files. */
export function loadFiles(files: Readonly<Record<string, string>>, options: ITestOptions = {}, root = "main.conf"): Promise<ILoaded> {
  return processorOf(files, options).load(root, options.variables === undefined ? undefined : { variables: options.variables });
}

/** Load one text as `main.conf`. */
export function loadText(text: string, options: ITestOptions = {}): Promise<ILoaded> {
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
export function placeText(at: IPlace): string {
  return `${at.resolvedPath}:${String(at.span.start.line)}:${String(at.span.start.column)}`;
}

/** An origin as the load conformance format writes it. */
export function originText({ written, via }: { readonly written: IOrigin["written"]; readonly via: readonly IStep[] }): string {
  const head = written.kind === "handed" ? `handed ${written.variable}` : placeText(written);
  return head + via.map((step) => ` < ${step.kind} ${step.name} ${placeText(step.at)}`).join("");
}

/** Each diagnostic as `[code, origin]`. */
export function problems(diagnostics: Iterable<ILocatedDiagnostic>): [string, string][] {
  return [...diagnostics].map((d) => [d.code, originText({ written: d.at, via: d.via })]);
}

/** Every directive's people address in walk order. */
export function addresses(loaded: ILoaded): string[] {
  const out: string[] = [];
  loaded.walk((d: IDirective) => {
    out.push(d.address.toString());
  });
  return out;
}

/** Each of the directive's values' canonical text. */
export function texts(directive: IDirective | undefined): string[] {
  return directive?.args.map((a) => a.text) ?? [];
}
