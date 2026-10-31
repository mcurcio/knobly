/**
 * The one block shape (spec 2.11; owner, 2026-10-29, "Yes, rename now"): iterated, counted and indexed in written
 * order, its directives by name, and a depth-first walk over its items at any depth (spec 7.5). The one home of those
 * members for the three blocks: the written block (written/document.ts, live), and the expansion and rendered blocks
 * (`SnapshotBlock`, snapshots of one working-out). Prior art: ES2022 `Array.prototype.at` and `Iterable`. Shared,
 * package-internal; programs see the generated `Block` interfaces.
 */

import type { Block } from "./gen/api/shared.js";
import { WalkControl } from "./gen/api/kinds.js";

/** A block over `contents()`, worked out each time it is asked (a live block re-reads its text). */
export abstract class BlockBase<TItem, TDirective extends TItem> implements Block<TItem, TDirective> {
  /** Its items, in written order. */
  protected abstract contents(): readonly TItem[];
  /** An item's own block, which `walk` visits below it; undefined when it has none. */
  protected abstract blockOf(item: TItem): Iterable<TItem> | undefined;
  /** Whether an item is one of its directives, of `name` when given. */
  protected abstract isDirective(item: TItem, name: string | undefined): item is TDirective;

  get length(): number {
    return this.contents().length;
  }

  at(index: number): TItem | undefined {
    return this.contents().at(index);
  }

  [Symbol.iterator](): Iterator<TItem> {
    return this.contents()[Symbol.iterator]();
  }

  directives(name?: string): readonly TDirective[] {
    return this.contents().filter((item): item is TDirective => this.isDirective(item, name));
  }

  walk(visit: (item: TItem) => WalkControl | void): void {
    // A loop over a stack of open blocks, not a recursion: the tree may be MAX_EXPANDED_NESTING deep (spec 2.5). Per
    // open block, its items left; an item's own block opens right after it is visited, unless the visit said skip.
    const stack: Iterator<TItem>[] = [this[Symbol.iterator]()];
    for (let open = stack.at(-1); open !== undefined; open = stack.at(-1)) {
      const next = open.next();
      if (next.done === true) {
        stack.pop();
        continue;
      }
      const control = visit(next.value);
      if (control === WalkControl.Stop) return;
      const inner = control === WalkControl.Skip ? undefined : this.blockOf(next.value);
      if (inner !== undefined) stack.push(inner[Symbol.iterator]());
    }
  }
}

/**
 * A snapshot block of directives that each may hold a block of their own: the expansion block (directive expansions)
 * and the rendered block (rendered directives). Its items are the array it is given, which its maker may still fill
 * while it builds the tree, never after.
 */
export class SnapshotBlock<TItem extends { readonly block: Iterable<TItem> | undefined }> extends BlockBase<TItem, TItem> {
  readonly #items: readonly TItem[];
  readonly #nameOf: (item: TItem) => string;

  constructor(items: readonly TItem[], nameOf: (item: TItem) => string) {
    super();
    this.#items = items;
    this.#nameOf = nameOf;
  }

  protected contents(): readonly TItem[] {
    return this.#items;
  }

  protected blockOf(item: TItem): Iterable<TItem> | undefined {
    return item.block;
  }

  protected isDirective(item: TItem, name: string | undefined): item is TItem {
    return name === undefined || this.#nameOf(item) === name;
  }
}
