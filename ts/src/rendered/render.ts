/**
 * `render (graph)` (spec 7.0): the rendered layer's entry point, and the one home of the render algorithm. It builds
 * on the low level's public objects only (owner, 2026-10-29: "The middle layer of objects can build on the lower
 * layer domains"): `graph.expand()`, the graph's own expansion, and `graph.root.resolvedPath`. Each directive
 * expansion becomes a directive with its arguments; it never looks a name up (the low level is the one home of that
 * rule), reads no file, and names nothing: addresses come from `IRendered.addresses` under the caller's key rule
 * (D4). The low level never calls in here (spec 5, "Layer direction").
 */

import { makePlace } from "../origin.js";
import type { IDirectiveExpansion, IDocumentGraph, IUnreadableExpansion } from "../written/index.js";
import type { IDirective, IRendered, IUnreadable } from "./model.js";
import { argumentOf, Directive, Rendered } from "./tree.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/**
 * The rendered tree of the graph's current texts and overrides. Pure and synchronous: reads no file; an unread
 * include copy renders as nothing (its edge is in `graph.unread()`). Takes any object with the document graph's
 * public members.
 */
export function render(graph: IDocumentGraph): IRendered {
  const expansion = graph.expand();
  const block: IDirective[] = [];
  const unreadable: IUnreadable[] = [];
  build(expansion.block, expansion.unreadable, undefined, { block, unreadable });
  const origin = { place: makePlace(graph.root.resolvedPath, { start: START, end: START }), via: [] };
  return new Rendered(block, unreadable, origin, expansion.diagnostics, graph);
}

function build(
  directives: readonly IDirectiveExpansion[],
  unreadables: readonly IUnreadableExpansion[],
  parent: Directive | undefined,
  into: { readonly block: IDirective[]; readonly unreadable: IUnreadable[] },
): void {
  for (const item of unreadables) into.unreadable.push({ reason: item.reason, origin: item.origin, written: item.statement });
  for (const item of directives) {
    const values = item.values.map(argumentOf);
    const directive = new Directive(item.statement.name, values, item.block !== undefined, parent, item.origin, item.statement);
    into.block.push(directive);
    if (item.block !== undefined && directive.block !== undefined) {
      build(item.block, item.unreadable, directive, { block: directive.block, unreadable: directive.unreadable });
    }
  }
}
