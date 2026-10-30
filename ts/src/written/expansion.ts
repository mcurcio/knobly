/**
 * `graph.expand()` (spec 6.10): the binding's walk as public snapshots, the one surface the rendered layer builds on
 * (spec 7.0; owner, 2026-10-29: "The middle layer of objects can build on the lower layer domains"). It turns the
 * binding's items into directive and unreadable expansions, whose values are the binding's own expanded values (the
 * same objects a rendered directive holds). Package-internal; programs see Expansion.
 */

import { SnapshotBlock } from "../block.js";
import { makePlace } from "../origin.js";
import type { BoundItem, Binding } from "./bind.js";
import type { StatementHandle } from "./statements.js";
import { ExpandedRecord } from "./value.js";
import type { LocatedDiagnostic } from "../gen/api/shared.js";
import type { DirectiveExpansion, Expansion, ExpansionBlock, UnreadableExpansion, WrittenDirective } from "../gen/api/written.js";

interface Container {
  readonly block: DirectiveExpansion[];
  readonly unreadable: UnreadableExpansion[];
}

/** The expansion of one binding, with the graph's one diagnostics list. */
export function expansionOf(binding: Binding, diagnostics: readonly LocatedDiagnostic[]): Expansion {
  const top: Container = { block: [], unreadable: [] };
  fill(binding, binding.items, top);
  return { block: expansionBlock(top.block), unreadable: top.unreadable, diagnostics };
}

/** An expansion block (spec 2.11): directive expansions, named by their written directive's name. */
function expansionBlock(items: readonly DirectiveExpansion[]): ExpansionBlock {
  return new SnapshotBlock(items, (item) => item.written.name);
}

function fill(binding: Binding, items: readonly BoundItem[], into: Container): void {
  for (const item of items) {
    const statement = item.copy.statement as unknown as StatementHandle;
    const { doc } = statement;
    if (item.tag === "unreadable") {
      const place = makePlace(doc.resolvedPath, doc.spanOf(statement.node));
      into.unreadable.push({ reason: item.reason, written: item.copy.statement, origin: { place, via: item.copy.via } });
      continue;
    }
    const nameToken = doc.syntax.tokens[statement.node.start];
    if (nameToken === undefined) throw new Error("a directive node has no name token");
    const written = item.copy.statement as WrittenDirective;
    const values = written.values.flatMap((value) => binding.valuesAt(value, item.copy).map((record) => ExpandedRecord.asValue(record)));
    const inner: Container | undefined = item.children === undefined ? undefined : { block: [], unreadable: [] };
    if (item.children !== undefined && inner !== undefined) fill(binding, item.children, inner);
    into.block.push({
      written,
      origin: { place: makePlace(doc.resolvedPath, nameToken.span), via: item.copy.via },
      values,
      block: inner === undefined ? undefined : expansionBlock(inner.block),
      unreadable: inner?.unreadable ?? [],
    });
  }
}
