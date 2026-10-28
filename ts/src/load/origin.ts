/**
 * Where text was written, and how it got to where a program reads it (round 11, slices.md §Shared primitives).
 * Pure data: every directive, value and diagnostic of the load layer carries one of these.
 */

import type { ISourceSpan } from "../span.js";

/** A range of one file's text. */
export interface IPlace {
  readonly kind: "file";
  /** The file's identity, as the document source gave it. */
  readonly resolvedPath: string;
  readonly span: ISourceSpan;
}

/** A value the program handed in at load (`rasl --set host=10.0.60.30`): written in no file. */
export interface IHanded {
  readonly kind: "handed";
  /** The variable's name, without `$`. */
  readonly variable: string;
}

export const StepKind = {
  /** `$pixels` was replaced by its value. */
  Variable: "variable",
  /** `use twinkle rgb_150;` spliced a snippet's body. */
  Use: "use",
  /** An extension directive (`include "palettes.conf";`) spliced files. */
  Extension: "extension",
} as const;
export type StepKind = (typeof StepKind)[keyof typeof StepKind];

/** One expansion a directive or value went through to reach where it is read. */
export interface IStep {
  readonly kind: StepKind;
  /** The variable (without `$`), snippet or extension directive name. */
  readonly name: string;
  /** Where the reference was written: the `$pixels` token, the `use` line's name, the `include` line's name. */
  readonly at: IPlace;
}

/**
 * Where a value was written, and how it got here. For a value from a variable, `written` is the value's text in
 * its `set` (the definition) or the handed-in variable, and `via[0]` is the `$name` (the use site).
 */
export interface IOrigin {
  readonly written: IPlace | IHanded;
  /** Innermost first. Empty when the text is read where it was written. */
  readonly via: readonly IStep[];
}

/** A directive's origin: its name is always written in a file, never handed in. */
export interface IDirectiveOrigin extends IOrigin {
  readonly written: IPlace;
}
