/**
 * What differs between two renders, by address (slices.md §1.5; round 12 D4: addresses under the caller's key rule,
 * from `IRendered.addresses`). Private to the load layer; programs call `IProcessor.diff`, which first checks both
 * renders came from that processor.
 */

import type { IAddress, IDirective, IUnreadable } from "./directive.js";
import type { Change, IKeyOptions, IRendered } from "./processor.js";

/** A directive's own state for "changed": its values' canonical texts and whether it has a block. */
function sameOwn(before: IDirective, after: IDirective): boolean {
  return (
    (before.body === undefined) === (after.body === undefined) &&
    before.args.length === after.args.length &&
    before.args.every((arg, i) => arg.text === after.args[i]?.text)
  );
}

/** Every directive of a render by address text, and each directive's address. */
function byAddress(rendered: IRendered, options: IKeyOptions | undefined): [ReadonlyMap<string, IDirective>, ReadonlyMap<IDirective, IAddress>] {
  const addresses = rendered.addresses(options);
  const map = new Map<string, IDirective>();
  for (const [directive, address] of addresses) map.set(address.text, directive);
  return [map, addresses];
}

/** The address `addresses()` gave a directive of its render. */
function addressOf(addresses: ReadonlyMap<IDirective, IAddress>, directive: IDirective): IAddress {
  const address = addresses.get(directive);
  if (address === undefined) throw new Error("a directive without an address");
  return address;
}

/**
 * Removed and unknown in `before`'s walk order, then added and changed in `after`'s. A directive only on one side
 * is listed alone (its block is not walked); one on both sides has its block compared at its own addresses.
 */
export function diff(before: IRendered, after: IRendered, options?: IKeyOptions): readonly Change[] {
  const [beforeMap, beforeAddresses] = byAddress(before, options);
  const [afterMap, afterAddresses] = byAddress(after, options);
  const changes: Change[] = [];
  /** The unreadable statements of the container a `before` directive would stand in, in `after`. */
  const unreadableAfter = (directive: IDirective): readonly IUnreadable[] => {
    const parent = directive.parent;
    if (parent === undefined) return after.unreadable;
    return afterMap.get(addressOf(beforeAddresses, parent).text)?.unreadable ?? [];
  };
  before.walk((directive) => {
    const address = addressOf(beforeAddresses, directive);
    if (afterMap.has(address.text)) return undefined;
    // The container may hold the line that is broken now: whether the directive is gone is unknown.
    if (unreadableAfter(directive).length > 0) changes.push({ kind: "unknown", address, before: directive });
    else changes.push({ kind: "removed", address, before: directive });
    return "skip";
  });
  after.walk((directive) => {
    const address = addressOf(afterAddresses, directive);
    const old = beforeMap.get(address.text);
    if (old === undefined) {
      changes.push({ kind: "added", address, after: directive });
      return "skip";
    }
    if (!sameOwn(old, directive)) changes.push({ kind: "changed", address, before: old, after: directive });
    return undefined;
  });
  return changes;
}
