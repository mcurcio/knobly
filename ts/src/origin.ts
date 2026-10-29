/**
 * Where text was written, and how it got to where a program reads it (spec 2.2). Shared: every located diagnostic,
 * expanded value and rendered directive carries one of these. Plain data, each record with its people form
 * (`toString()`, spec/contract.md 2); made through the factories below, the one home of each record's shape.
 */

import type { StepKind } from "./gen/api/kinds.js";
import { overrideForm, placeForm, stepForm } from "./people.js";
import type { ISourceSpan } from "./span.js";

export type { PlaceKind, StepKind } from "./gen/api/kinds.js";

/** A range of one file's text. */
export interface IPlace {
  readonly kind: "file";
  /** The file's identity, as the document source gave it. */
  readonly resolvedPath: string;
  readonly span: ISourceSpan;
  /** `path:line:col` at the span's start, 1-based: `sink.conf:4:5`. */
  toString(): string;
}

/** A value the program passed in as an override at load (`rasl --set host=10.0.60.30`): written in no file. */
export interface IOverride {
  readonly kind: "override";
  /** The variable's name, without `$`. */
  readonly variable: string;
  /** `override <variable>`. */
  toString(): string;
}

/** One expansion a directive or value went through to reach where it is read. */
export interface IStep {
  readonly kind: StepKind;
  /** The variable (without `$`), snippet or extension directive name. */
  readonly name: string;
  /** Where the reference was written: the `$pixels` token, the `use` line's name, the `include` line's name. */
  readonly place: IPlace;
  /** `<kind> <name> at <place>`: `variable pixels at main.conf:7:15`. */
  toString(): string;
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

class Place implements IPlace {
  readonly kind = "file";

  constructor(
    readonly resolvedPath: string,
    readonly span: ISourceSpan,
  ) {}

  toString(): string {
    return placeForm(this);
  }
}

class Override implements IOverride {
  readonly kind = "override";

  constructor(readonly variable: string) {}

  toString(): string {
    return overrideForm(this);
  }
}

class Step implements IStep {
  constructor(
    readonly kind: StepKind,
    readonly name: string,
    readonly place: IPlace,
  ) {}

  toString(): string {
    return stepForm(this);
  }
}

/** A place in a file. Package-internal. */
export function makePlace(resolvedPath: string, span: ISourceSpan): IPlace {
  return new Place(resolvedPath, span);
}

/** An override's place. Package-internal. */
export function makeOverride(variable: string): IOverride {
  return new Override(variable);
}

/** One step of an origin. Package-internal. */
export function makeStep(kind: StepKind, name: string, place: IPlace): IStep {
  return new Step(kind, name, place);
}
