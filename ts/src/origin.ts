/**
 * Where text was written, and how it got to where a program reads it (spec 2.2). Shared: every located diagnostic,
 * expanded value and rendered directive carries one of these. Pure data.
 */

import type { ISourceSpan } from "./span.js";

export type { StepKind } from "./gen/api/kinds.js";
import type { StepKind } from "./gen/api/kinds.js";

/** A range of one file's text. */
export interface IPlace {
  readonly kind: "file";
  /** The file's identity, as the document source gave it. */
  readonly resolvedPath: string;
  readonly span: ISourceSpan;
}

/** A value the program passed in as an override at load (`rasl --set host=10.0.60.30`): written in no file. */
export interface IOverride {
  readonly kind: "override";
  /** The variable's name, without `$`. */
  readonly variable: string;
}

/** One expansion a directive or value went through to reach where it is read. */
export interface IStep {
  readonly kind: StepKind;
  /** The variable (without `$`), snippet or extension directive name. */
  readonly name: string;
  /** Where the reference was written: the `$pixels` token, the `use` line's name, the `include` line's name. */
  readonly place: IPlace;
}

/**
 * Where a value was written, and how it got here. For a value from a variable, `place` is the value's text in its
 * `set` (the definition) or the override, and `via[0]` is the `$name` (the use site).
 */
export interface IOrigin {
  readonly place: IPlace | IOverride;
  /** Innermost first. Empty when the text is read where it was written. */
  readonly via: readonly IStep[];
}

/** A directive's origin: its name is always written in a file, never an override. */
export interface IDirectiveOrigin extends IOrigin {
  readonly place: IPlace;
}
