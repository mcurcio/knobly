/**
 * The extension port (spec 5): an extension owns one directive name and turns each use of it into specs of files to
 * splice in its place. It belongs to the low level, the one owner of expansion (vil-umh.8): an extension is pure, and
 * it sees the low level's expanded values, never a rendered type.
 */

import type { IDirectiveOrigin } from "../origin.js";
import type { ExpandedValue } from "./value.js";

/** One use of an extension directive, as the extension sees it. */
export interface IExtensionUse {
  /** The directive's values, expanded, with their links. */
  readonly values: readonly ExpandedValue[];
  readonly origin: IDirectiveOrigin;
}

/**
 * An extension (R20): owns one directive name and turns each use of it into specs of files to splice in its place.
 * Pure: the load resolves and reads the specs through its document source, parses each file once, applies the
 * use's block of `set` lines to the spliced files, and enforces depth, cycles and limits. While registered, the
 * name is reserved at a line's start, as `set`, `snippet` and `use` are.
 */
export interface IExtension {
  readonly directive: string;
  /**
   * The specs for one use, in splice order. Throw a DiagnosticError (from a value's or the use's place) for a
   * located failure; any other exception, or a result that is not an array of strings, becomes E3006 at the
   * directive.
   */
  specs(use: IExtensionUse): readonly string[];
}
