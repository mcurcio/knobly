/**
 * The processor (spec 6.2): the factory of the low level. It is made once with its document source and extensions,
 * as `postcss([plugins])` is, and `load` is its only operation: it reads a root file and everything it includes into
 * a document graph (the files as written). Every later operation is a method of the graph (`read`, `save`); going up
 * to the rendered tree is the rendered layer's `render (graph)`. It returns only low-level objects.
 */

import { MisuseError } from "../errors.js";
import { RESERVED } from "../gen/api/limits.js";
import type { IDocumentSource } from "../source.js";
import type { IExtension } from "./extension.js";
import { DocumentGraph } from "./graph.js";
import type { IDocumentGraph } from "./model.js";
import { readRoot } from "./read.js";

export interface IProcessorOptions {
  readonly source: IDocumentSource;
  readonly extensions?: readonly IExtension[];
}

export interface ILoadOptions {
  /**
   * Overrides, by name without `$`, each as villanelle text: "8080 443" is two values. An override wins over every
   * `set` of its name, which acts as the default (L3). Each goes through the check of an override (spec 6.3), one by
   * one, in order, before any file is read; the first refusal rejects the load.
   */
  readonly overrides?: Readonly<Record<string, string>>;
}

export interface IProcessor {
  /**
   * The processor's only operation. Read the root file at `path` (resolved through the source, as an included
   * file's spec is, so the root has one path in the graph) and every file its include lines name, once each (R21),
   * repeating until nothing new is named. Never rejects for anything in the text.
   * @throws (rejects) ReadError (`paths` = `[path]`, the source's rejection as `cause`) when the source cannot resolve
   * the root to exactly one file or read it; MisuseError for an override name that is not letters, digits and `_`; TypeError
   * for a text that is not a string;
   * BadTextError for an override's text the check of an override refuses
   */
  load(path: string, options?: ILoadOptions): Promise<IDocumentGraph>;
}

/** Make a processor once, with its document source and extensions. @throws MisuseError for a reserved or repeated extension name */
export function villanelle(options: IProcessorOptions): IProcessor {
  const { source } = options;
  const extensions = new Map<string, IExtension>();
  for (const extension of options.extensions ?? []) {
    if (RESERVED.has(extension.directive) || extensions.has(extension.directive)) {
      throw new MisuseError(`extension directive name taken: ${JSON.stringify(extension.directive)}`);
    }
    extensions.set(extension.directive, extension);
  }
  return {
    async load(path, loadOptions) {
      const graph = new DocumentGraph(source, extensions, loadOptions?.overrides ?? {});
      await readRoot(graph, source, path);
      return graph;
    },
  };
}
