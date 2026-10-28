/**
 * What differs between two loads, by address (slices.md §1.5). Private to the load layer; programs call
 * `IProcessor.diff`, which first checks both loads came from that processor.
 */

import type { IDirective, IUnreadable } from "./directive.js";
import type { Change, ILoaded } from "./processor.js";

/** A directive's own state for "changed": its values' canonical texts and whether it has a block. */
function sameOwn(before: IDirective, after: IDirective): boolean {
  return (
    (before.body === undefined) === (after.body === undefined) &&
    before.args.length === after.args.length &&
    before.args.every((arg, i) => arg.text === after.args[i]?.text)
  );
}

/** Every directive of a load by address text. */
function byAddress(loaded: ILoaded): ReadonlyMap<string, IDirective> {
  const map = new Map<string, IDirective>();
  loaded.walk((directive) => {
    map.set(directive.address.text, directive);
  });
  return map;
}

/**
 * Removed and unknown in `before`'s walk order, then added and changed in `after`'s. A directive only on one side
 * is listed alone (its block is not walked); one on both sides has its block compared at its own addresses.
 */
export function diff(before: ILoaded, after: ILoaded): readonly Change[] {
  const beforeMap = byAddress(before);
  const afterMap = byAddress(after);
  const changes: Change[] = [];
  /** The unreadable statements of the container a `before` directive would stand in, in `after`. */
  const unreadableAfter = (directive: IDirective): readonly IUnreadable[] => {
    const parent = directive.parent;
    if (parent === undefined) return after.unreadable;
    return afterMap.get(parent.address.text)?.unreadable ?? [];
  };
  before.walk((directive) => {
    if (afterMap.has(directive.address.text)) return undefined;
    const { address } = directive;
    // The container may hold the line that is broken now: whether the directive is gone is unknown.
    if (unreadableAfter(directive).length > 0) changes.push({ kind: "unknown", address, before: directive });
    else changes.push({ kind: "removed", address, before: directive });
    return "skip";
  });
  after.walk((directive) => {
    const old = beforeMap.get(directive.address.text);
    const { address } = directive;
    if (old === undefined) {
      changes.push({ kind: "added", address, after: directive });
      return "skip";
    }
    if (!sameOwn(old, directive)) changes.push({ kind: "changed", address, before: old, after: directive });
    return undefined;
  });
  return changes;
}
