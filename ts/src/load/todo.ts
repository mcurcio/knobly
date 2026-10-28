/**
 * Placeholder bodies for the round 11 interfaces (slices.md). Private; deleted by the slice that fills the last body.
 */

/** The error every unfilled body throws. The arguments are taken so the signatures stay checked by lint. */
export function notImplemented(what: string, ...args: readonly unknown[]): Error {
  return new Error(`not implemented: ${what} (${args.length} arguments)`);
}
