/**
 * What differs between two renders, by address (spec 7.6; round 12 D4: addresses under the caller's key rule, from
 * `Rendered.addresses`). Package-internal; programs call `Rendered.diff`.
 */

import type { Address, Change, Directive, KeyOptions, Rendered } from "../gen/api/rendered.js";
import type { UnreadableExpansion } from "../gen/api/written.js";
import { ChangeKind, WalkControl } from "../gen/api/kinds.js";

/** A directive's own state for "changed": its values' canonical texts and whether it has a block. */
function sameOwn(before: Directive, after: Directive): boolean {
  return (
    (before.block === undefined) === (after.block === undefined) &&
    before.values.length === after.values.length &&
    before.values.every((value, i) => value.text === after.values[i]?.text)
  );
}

/** Every directive of a render by address text, and each directive's address. */
function byAddress(rendered: Rendered, options: KeyOptions | undefined): [ReadonlyMap<string, Directive>, ReadonlyMap<Directive, Address>] {
  const addresses = rendered.addresses(options);
  const map = new Map<string, Directive>();
  for (const [directive, address] of addresses) map.set(address.text, directive);
  return [map, addresses];
}

/** The address `addresses()` gave a directive of its render. */
function addressOf(addresses: ReadonlyMap<Directive, Address>, directive: Directive): Address {
  const address = addresses.get(directive);
  if (address === undefined) throw new Error("a directive without an address");
  return address;
}

/**
 * Removed and unknown in `before`'s walk order, then added and changed in `after`'s. A directive only on one side
 * is listed alone (its block is not walked); one on both sides has its block compared at its own addresses.
 */
export function diff(before: Rendered, after: Rendered, options?: KeyOptions): readonly Change[] {
  const [beforeMap, beforeAddresses] = byAddress(before, options);
  const [afterMap, afterAddresses] = byAddress(after, options);
  const changes: Change[] = [];
  /** The unreadable statements of the container a `before` directive would stand in, in `after`. */
  const unreadableAfter = (directive: Directive): readonly UnreadableExpansion[] => {
    const parent = directive.parent;
    if (parent === undefined) return after.unreadable;
    return afterMap.get(addressOf(beforeAddresses, parent).text)?.unreadable ?? [];
  };
  before.block.walk((directive) => {
    const address = addressOf(beforeAddresses, directive);
    if (afterMap.has(address.text)) return undefined;
    // The container may hold the line that is broken now: whether the directive is gone is unknown.
    if (unreadableAfter(directive).length > 0) changes.push({ kind: ChangeKind.Unknown, address, before: directive });
    else changes.push({ kind: ChangeKind.Removed, address, before: directive });
    return WalkControl.Skip;
  });
  after.block.walk((directive) => {
    const address = addressOf(afterAddresses, directive);
    const old = beforeMap.get(address.text);
    if (old === undefined) {
      changes.push({ kind: ChangeKind.Added, address, after: directive });
      return WalkControl.Skip;
    }
    if (!sameOwn(old, directive)) changes.push({ kind: ChangeKind.Changed, address, before: old, after: directive });
    return undefined;
  });
  return changes;
}
