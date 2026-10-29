/**
 * `graph.expand()` (spec 6.10): the binding's walk as public snapshots, the one surface the rendered layer builds on
 * (spec 7.0; owner, 2026-10-29: "The middle layer of objects can build on the lower layer domains"). It turns the
 * binding's items into directive and unreadable expansions and each written value at each copy into value
 * expansions. Package-internal; programs see IExpansion.
 */

import { makePlace } from "../origin.js";
import type { ILocatedDiagnostic } from "../report.js";
import type { BoundItem, IBinding } from "./bind.js";
import type { IDirectiveExpansion, IExpansion, IUnreadableExpansion, IWrittenDirective } from "./model.js";
import type { StatementHandle } from "./statements.js";

interface IContainer {
  readonly block: IDirectiveExpansion[];
  readonly unreadable: IUnreadableExpansion[];
}

/** The expansion of one binding, `diagnostics` first (the documents' syntax diagnostics, then the walk's). */
export function expansionOf(binding: IBinding, syntaxDiagnostics: readonly ILocatedDiagnostic[]): IExpansion {
  const top: IContainer = { block: [], unreadable: [] };
  fill(binding, binding.items, top);
  return { block: top.block, unreadable: top.unreadable, diagnostics: [...syntaxDiagnostics, ...binding.diagnostics] };
}

function fill(binding: IBinding, items: readonly BoundItem[], into: IContainer): void {
  for (const item of items) {
    const statement = item.copy.statement as unknown as StatementHandle;
    const { doc } = statement;
    if (item.kind === "unreadable") {
      const place = makePlace(doc.resolvedPath, doc.spanOf(statement.node));
      into.unreadable.push({ statement: item.copy.statement, reason: item.reason, origin: { place, via: item.copy.via } });
      continue;
    }
    const nameToken = doc.syntax.tokens[statement.node.start];
    if (nameToken === undefined) throw new Error("a directive node has no name token");
    const written = item.copy.statement as IWrittenDirective;
    const values = written.values.flatMap((value) => binding.argumentsAt(value, item.copy).map((bound) => bound.expansion()));
    const inner: IContainer | undefined = item.children === undefined ? undefined : { block: [], unreadable: [] };
    if (item.children !== undefined && inner !== undefined) fill(binding, item.children, inner);
    into.block.push({
      statement: written,
      origin: { place: makePlace(doc.resolvedPath, nameToken.span), via: item.copy.via },
      values,
      block: inner?.block,
      unreadable: inner?.unreadable ?? [],
    });
  }
}
