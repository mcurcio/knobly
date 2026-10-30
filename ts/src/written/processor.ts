/**
 * The processor (spec 6.2): the factory of the low level. It is made once with its document source and extensions,
 * as `postcss([plugins])` is, and `load` is its only operation: it reads a root file and everything it includes into
 * a document graph (the files as written). Every later operation is a method of the graph (`read`, `save`); going up
 * to the rendered tree is the rendered layer's `render (graph)`. It returns only low-level objects.
 */

import { RESERVED } from "../gen/api/limits.js";
import type { Extension, Processor, ProcessorOptions } from "../gen/api/written.js";
import { requireText } from "../text.js";
import { DocumentGraph } from "./graph.js";
import { checkDirectiveName } from "./names.js";
import { readRoot } from "./read.js";
import { MisuseError } from "../gen/api/errors.js";

export function knobly(options: ProcessorOptions): Processor {
  const { source } = options;
  const extensions = new Map<string, Extension>();
  for (const extension of options.extensions ?? []) {
    const name: unknown = extension.directive;
    requireText(name, "knobly", "directive");
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
