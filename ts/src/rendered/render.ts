/**
 * `render (graph)` (spec 7.0): the rendered layer's entry point, and the one home of the render algorithm. It walks
 * the graph's binding (`binding.items`, package-internal, so the low level's work is not done twice) and builds each
 * directive with its arguments from `argumentsAt`. It never looks a name up (design rule 3: the binding is the one
 * home of that rule), reads no file, and names nothing: addresses come from `IRendered.addresses` under the
 * caller's key rule (D4). The low level never calls in here (spec 5, "Layer direction").
 */

import { asDocument, type BoundItem } from "../written/bind.js";
import { DocumentGraph } from "../written/graph.js";
import type { IDocumentGraph, IWrittenDirective } from "../written/model.js";
import type { StatementHandle } from "../written/statements.js";
import type { IDirective, IRendered, IUnreadable } from "./model.js";
import type { IDirectiveOrigin } from "../origin.js";
import { Argument, Directive, Rendered } from "./tree.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/**
 * The rendered tree of the graph's current texts and overrides. Pure and synchronous: reads no file; an unread
 * include copy renders as nothing (its edge is in `graph.unread()`).
 * @throws TypeError for a graph this package did not make
 */
export function render(graph: IDocumentGraph): IRendered {
  if (!(graph instanceof DocumentGraph)) throw new TypeError("render takes a document graph from a processor's load");
  const binding = graph.binding();
  const block: IDirective[] = [];
  const unreadable: IUnreadable[] = [];

  const build = (items: readonly BoundItem[], parent: Directive | undefined, into: { block: IDirective[]; unreadable: IUnreadable[] }): void => {
    for (const item of items) {
      const statement = item.copy.statement as unknown as StatementHandle;
      const doc = asDocument(statement.doc);
      if (item.kind === "unreadable") {
        const place = doc.place(doc.spanOf(statement.node));
        into.unreadable.push({ reason: item.reason, origin: { place, via: item.copy.via }, written: item.copy.statement });
        continue;
      }
      const values = statement.valueList.flatMap((value) =>
        binding.argumentsAt(value as unknown as Parameters<typeof binding.argumentsAt>[0], item.copy).map((bound) => new Argument(bound)),
      );
      const nameToken = doc.syntax.tokens[statement.node.start];
      if (nameToken === undefined) throw new Error("a directive node has no name token");
      const origin: IDirectiveOrigin = { place: doc.place(nameToken.span), via: item.copy.via };
      const directive = new Directive(nameToken.text, values, item.children !== undefined, parent, origin, item.copy.statement as IWrittenDirective);
      into.block.push(directive);
      if (item.children !== undefined && directive.block !== undefined) {
        build(item.children, directive, { block: directive.block, unreadable: directive.unreadable });
      }
    }
  };

  build(binding.items, undefined, { block, unreadable });
  const origin: IDirectiveOrigin = { place: graph.root.place({ start: START, end: START }), via: [] };
  return new Rendered(block, unreadable, origin, [...graph.syntaxDiagnostics(), ...binding.diagnostics], graph);
}
