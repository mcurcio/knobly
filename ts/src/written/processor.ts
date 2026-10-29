/**
 * The processor (spec 6.2): the factory of the low level. It is made once with its document source and extensions,
 * as `postcss([plugins])` is, and `load` is its only operation: it reads a root file and everything it includes into
 * a document graph (the files as written). Every later operation is a method of the graph (`read`, `save`); going up
 * to the rendered tree is the rendered layer's `render (graph)`. It returns only low-level objects.
 */

import { RESERVED } from "../gen/api/limits.js";
import type { ConfigText } from "../gen/api/shared.js";
import type { DocumentGraph as DocumentGraphApi, Extension, ProcessorOptions } from "../gen/api/written.js";
import { requireText } from "../text.js";
import { DocumentGraph } from "./graph.js";
import { checkDirectiveName } from "./names.js";
import { readRoot } from "./read.js";
import { MisuseError } from "../gen/api/errors.js";

/**
 * Load's options (spec 6.2). Written by hand, not taken from gen/api/written.ts: the generated `LoadOptions` spells
 * `overrides` as a `ReadonlyMap`, where spec/codegen.md section 3 gives a map passed in a `Readonly<Record>`, as this
 * binding has always taken it (milestone 6 errata). It goes, with `Processor` below, when the emitter spells an
 * options record's map as a parameter's.
 */
export interface LoadOptions {
  /**
   * Overrides, by name without `$`, each as villanelle text: "8080 443" is two values. An override wins over every
   * `set` of its name, which acts as the default (L3). Each goes through the check of an override (spec 6.3), one by
   * one, in order, before any file is read; the first refusal rejects the load.
   */
  readonly overrides?: Readonly<Record<string, ConfigText>>;
}

/** The factory; load is its only operation (spec 6.2). By hand for `LoadOptions`' sake (above). */
export interface Processor {
  /**
   * Read the root file at `path` (resolved through the source, as an included file's spec is, so the root has one
   * path in the graph) and every file its include lines name, once each (R21), repeating until nothing new is named.
   * Never rejects for anything in the text.
   * @throws (rejects) ReadError (`paths` = `[path]`, the source's rejection as `cause`) when the source cannot resolve
   * the root to exactly one file or read it; MisuseError for an override name that is not letters, digits and `_`;
   * TypeError for a text that is not a string; BadTextError for an override's text the check of an override refuses
   */
  load(path: string, options?: LoadOptions): Promise<DocumentGraphApi>;
}

/**
 * Make a processor once, with its document source and extensions. An extension's name is written after `@`
 * (`@include`), so it must be a word the grammar's `nameText` takes, and not a language statement's name.
 * @throws TypeError for an extension name that is not a string; MisuseError for one that is not a word, then for one
 * that is reserved (`set`, `snippet`, `use`) or already taken
 */
export function villanelle(options: ProcessorOptions): Processor {
  const { source } = options;
  const extensions = new Map<string, Extension>();
  for (const extension of options.extensions ?? []) {
    const name: unknown = extension.directive;
    requireText(name, "villanelle", "directive");
    checkDirectiveName(name);
    if (RESERVED.has(name) || extensions.has(name)) throw new MisuseError(`extension directive name taken: ${JSON.stringify(name)}`);
    extensions.set(name, extension);
  }
  return {
    async load(path, loadOptions) {
      const graph = new DocumentGraph(source, extensions, loadOptions?.overrides ?? {});
      await readRoot(graph, source, path);
      return graph;
    },
  };
}
