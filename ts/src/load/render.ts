/**
 * Render (round 12 slices.md S1): the rendered tree (PR 3's loaded tree, renamed) built from one binding. It walks
 * `binding.items`, builds each directive with its arguments from `argumentsAt`, and names it among its siblings
 * with the key rule. It never looks a name up (design rule 3: the binding is the one home of that rule) and reads
 * no file. Private to the package.
 */

import { asDocument, type BoundItem } from "../written/bind.js";
import type { DocumentGraph } from "../written/graph.js";
import type { StatementHandle } from "../written/statements.js";
import type { IDirective, IKeyInput, IUnreadable, KeyRule } from "./directive.js";
import type { IDirectiveOrigin } from "./origin.js";
import { Address, type Argument, Directive, Rendered } from "./tree.js";

const START = { offset: 0, line: 0, column: 0 } as const;

/** The rendered tree of the graph's current texts and handed-in values. Whatever the key rule throws propagates. */
export function render(graph: DocumentGraph, key: KeyRule | undefined): Rendered {
  const binding = graph.binding();
  const keyInputs = new WeakMap<Directive, IKeyInput>();
  const body: IDirective[] = [];
  const unreadable: IUnreadable[] = [];

  const build = (items: readonly BoundItem[], parent: Directive | undefined, into: { body: IDirective[]; unreadable: IUnreadable[] }): void => {
    /** Same-name-and-key counts of the container, shared by everything spliced into it. */
    const occurrences = new Map<string, number>();
    for (const item of items) {
      const statement = item.copy.statement as unknown as StatementHandle;
      const doc = asDocument(statement.doc);
      if (item.kind === "unreadable") {
        const written = doc.place(doc.spanOf(statement.node));
        into.unreadable.push({ kind: item.reason, origin: { written, via: item.copy.via }, node: statement.node });
        continue;
      }
      const args: Argument[] = statement.valueList.flatMap((value) =>
        binding.argumentsAt(value as unknown as Parameters<typeof binding.argumentsAt>[0], item.copy),
      );
      const nameToken = doc.syntax.tokens[statement.node.start];
      if (nameToken === undefined) throw new Error("a directive node has no name token");
      const name = nameToken.text;
      const hasBlock = item.children !== undefined;
      const keyInput: IKeyInput = { name, args, hasBlock, parent: parent === undefined ? undefined : keyInputs.get(parent) };
      const keyText = key?.(keyInput);
      const slot = JSON.stringify([name, keyText ?? null]);
      const occurrence = occurrences.get(slot) ?? 0;
      occurrences.set(slot, occurrence + 1);
      const address = new Address(parent?.address, { name, key: keyText, occurrence });
      const origin: IDirectiveOrigin = { written: doc.place(nameToken.span), via: item.copy.via };
      const directive = new Directive(name, args, hasBlock, parent, address, origin, statement.node);
      keyInputs.set(directive, keyInput);
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
