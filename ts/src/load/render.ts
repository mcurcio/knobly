/**
 * Render (round 12 slices.md S1, S2): the rendered tree (PR 3's loaded tree, renamed) built from one binding. It
 * walks `binding.items` and builds each directive with its arguments from `argumentsAt`. It never looks a name up
 * (design rule 3: the binding is the one home of that rule), reads no file, and names nothing: addresses come from
 * `IRendered.addresses` under the caller's key rule (D4). Private to the package.
 */

import { asDocument, type BoundItem } from "../written/bind.js";
import type { DocumentGraph } from "../written/graph.js";
import type { IWrittenDirective } from "../written/model.js";
import type { StatementHandle } from "../written/statements.js";
import type { IDirective, IUnreadable } from "./directive.js";
import type { IDirectiveOrigin } from "./origin.js";
import { type Argument, Directive, Rendered } from "./tree.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/** The rendered tree of the graph's current texts and handed-in values. */
export function render(graph: DocumentGraph): Rendered {
  const binding = graph.binding();
  const body: IDirective[] = [];
  const unreadable: IUnreadable[] = [];

  const build = (items: readonly BoundItem[], parent: Directive | undefined, into: { body: IDirective[]; unreadable: IUnreadable[] }): void => {
    for (const item of items) {
      const statement = item.copy.statement as unknown as StatementHandle;
      const doc = asDocument(statement.doc);
      if (item.kind === "unreadable") {
        const written = doc.place(doc.spanOf(statement.node));
        into.unreadable.push({ kind: item.reason, origin: { written, via: item.copy.via }, written: item.copy.statement });
        continue;
      }
      const args: Argument[] = statement.valueList.flatMap((value) =>
        binding.argumentsAt(value as unknown as Parameters<typeof binding.argumentsAt>[0], item.copy),
      );
      const nameToken = doc.syntax.tokens[statement.node.start];
      if (nameToken === undefined) throw new Error("a directive node has no name token");
      const origin: IDirectiveOrigin = { written: doc.place(nameToken.span), via: item.copy.via };
      const directive = new Directive(nameToken.text, args, item.children !== undefined, parent, origin, item.copy.statement as IWrittenDirective);
      into.body.push(directive);
      if (item.children !== undefined && directive.body !== undefined) {
        build(item.children, directive, { body: directive.body, unreadable: directive.unreadable });
      }
    }
  };

  build(binding.items, undefined, { body, unreadable });
  const root = graph.root;
  const origin: IDirectiveOrigin = { written: root.place({ start: START, end: START }), via: [] };
  return new Rendered(body, unreadable, origin, [...graph.syntaxDiagnostics(), ...binding.diagnostics], graph);
}
