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

/**
 * The directive and unreadable expansions of `items`, into `top`. A loop over a stack of open blocks, not a
 * recursion: the expanded tree may be MAX_EXPANDED_NESTING deep (spec 2.5). A directive expansion with a block is
 * pushed once its block is made.
 */
function fill(binding: Binding, items: readonly BoundItem[], top: Container): void {
  interface Open extends Container {
    readonly items: Iterator<BoundItem>;
    /** The directive this block belongs to, made once the block is; undefined at the top level. */
    readonly owner?: Omit<DirectiveExpansion, "block" | "unreadable">;
  }
  const stack: Open[] = [{ ...top, items: items[Symbol.iterator]() }];
  for (let open = stack.at(-1); open !== undefined; open = stack.at(-1)) {
    const next = open.items.next();
    if (next.done === true) {
      stack.pop();
      const parent = stack.at(-1);
      if (open.owner !== undefined && parent !== undefined) {
        parent.block.push({ ...open.owner, block: expansionBlock(open.block), unreadable: open.unreadable });
      }
      continue;
    }
    const item = next.value;
    const statement = item.copy.statement as unknown as StatementHandle;
    const { doc } = statement;
    if (item.tag === "unreadable") {
      const place = makePlace(doc.resolvedPath, doc.spanOf(statement.node));
      open.unreadable.push({ reason: item.reason, written: item.copy.statement, origin: { place, via: item.copy.via } });
      continue;
    }
    const nameToken = doc.syntax.tokens[statement.node.start];
    if (nameToken === undefined) throw new Error("a directive node has no name token");
    const written = item.copy.statement as WrittenDirective;
    const values = written.values.flatMap((value) => binding.valuesAt(value, item.copy).map((record) => ExpandedRecord.asValue(record)));
    const owner = { written, origin: { place: makePlace(doc.resolvedPath, nameToken.span), via: item.copy.via }, values };
    if (item.children === undefined) open.block.push({ ...owner, block: undefined, unreadable: [] });
    else stack.push({ block: [], unreadable: [], items: item.children[Symbol.iterator](), owner });
  }
}
