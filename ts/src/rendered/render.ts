/**
 * `render (graph)` (spec 7.0): the rendered layer's entry point, and the one home of the render algorithm. It builds
 * on the low level's public objects only (owner, 2026-10-29: "The middle layer of objects can build on the lower
 * layer domains"): `graph.expand()`, the graph's own expansion, and `graph.root.resolvedPath`. Each directive
 * expansion becomes a directive that holds the expansion's own objects (vil-umh.8: nothing is copied); it never
 * looks a name up (the low level is the one home of that rule), reads no file, and names nothing: addresses come
 * from `IRendered.addresses` under the caller's key rule (D4). The low level never calls in here (spec 5, "Layer
 * direction").
 */

import { makePlace } from "../origin.js";
import type { IDirectiveExpansion, IDocumentGraph } from "../written/index.js";
import type { IDirective, IRendered } from "./model.js";
import { Directive, Rendered } from "./tree.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/**
 * The rendered tree of the graph's current texts and overrides. Pure and synchronous: reads no file; an unread
 * include copy is an unreadable with reason "unread" (its edge is in `graph.unread()`). Takes any object with the
 * document graph's public members.
 */
export function render(graph: IDocumentGraph): IRendered {
  const expansion = graph.expand();
  const block = build(expansion.block, undefined);
  const origin = { place: makePlace(graph.root.resolvedPath, { start: START, end: START }), via: [] };
  return new Rendered(block, expansion.unreadable, origin, expansion.diagnostics, graph);
}

/** Each directive expansion as a directive on the expansion's own objects: its written, origin, values, unreadable. */
function build(directives: readonly IDirectiveExpansion[], parent: Directive | undefined): IDirective[] {
  return directives.map((item) => {
    const directive = new Directive(item.written.name, item.values, item.block !== undefined, item.unreadable, parent, item.origin, item.written);
    if (item.block !== undefined) directive.block?.push(...build(item.block, directive));
    return directive;
  });
}
