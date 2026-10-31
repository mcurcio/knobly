/**
 * `render (graph)` (spec 7.0): the rendered layer's entry point, and the one home of the render algorithm. It builds
 * on the low level's public objects only (owner, 2026-10-29: "The middle layer of objects can build on the lower
 * layer domains"): `graph.expand()`, the graph's own expansion, and `graph.root.resolvedPath`. Each directive
 * expansion becomes a directive that holds the expansion's own objects (kno-umh.8: nothing is copied); it never
 * looks a name up (the low level is the one home of that rule), reads no file, and names nothing: addresses come
 * from `Rendered.addresses` under the caller's key rule (D4). The low level never calls in here (spec 5, "Layer
 * direction").
 */

import { makePlace } from "../origin.js";
import { typeNameOf } from "../text.js";
import { Directive, Rendered, renderedBlock } from "./tree.js";
import type { DirectiveExpansion, DocumentGraph } from "../gen/api/written.js";
import type * as api from "../gen/api/rendered.js";

const START = { offset: 0, line: 0, column: 0 } as const;

export function render(graph: DocumentGraph): api.Rendered {
  const given: unknown = graph;
  if (typeof (given as Partial<DocumentGraph> | null)?.expand !== "function") {
    throw new TypeError(`render(): argument "graph" must be a document graph (an object with an expand method), not ${typeNameOf(given)}`);
  }
  const expansion = graph.expand();
  const block = renderedBlock(build(expansion.block, undefined));
  const origin = { place: makePlace(graph.root.resolvedPath, { start: START, end: START }), via: [] };
  return new Rendered(block, expansion.unreadable, origin, expansion.diagnostics, graph);
}

/**
 * Each directive expansion as a directive on the expansion's own objects: its written, origin, values, unreadable.
 * Each directive is made with its parent and an empty list, its block's directives, which the loop fills later. A
 * loop, not a recursion: the tree may be MAX_EXPANDED_NESTING deep (spec 2.5).
 */
function build(directives: Iterable<DirectiveExpansion>, parent: Directive | undefined): api.Directive[] {
  const top: api.Directive[] = [];
  const stack: [Iterable<DirectiveExpansion>, Directive | undefined, api.Directive[]][] = [[directives, parent, top]];
  for (let open = stack.pop(); open !== undefined; open = stack.pop()) {
    const [items, owner, into] = open;
    for (const item of items) {
      const children: api.Directive[] | undefined = item.block === undefined ? undefined : [];
      const directive = new Directive(item.written.name, item.values, children, item.unreadable, owner, item.origin, item.written);
      into.push(directive);
      if (item.block !== undefined && children !== undefined) stack.push([item.block, directive, children]);
    }
  }
  return top;
}
