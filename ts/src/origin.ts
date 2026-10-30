/**
 * Where text was written, and how it got to where a program reads it (spec 2.2). Shared: every located diagnostic,
 * expanded value and rendered directive carries one of these. Plain data, each record with its people form
 * (`toString()`, spec/contract.md 2); made through the factories below, the one home of each record's shape. The
 * types are generated (gen/api/shared.ts).
 */

import type * as api from "./gen/api/shared.js";
import { overrideForm, placeForm, stepForm } from "./people.js";
import { PlaceKind, type StepKind } from "./gen/api/kinds.js";

class Place implements api.Place {
  readonly kind = PlaceKind.File;

  constructor(
    readonly resolvedPath: string,
    readonly span: api.SourceSpan,
  ) {}

  toString(): string {
    return placeForm(this);
  }
}

class Override implements api.Override {
  readonly kind = PlaceKind.Override;

  constructor(readonly variable: string) {}

  toString(): string {
    return overrideForm(this);
  }
}

class Step implements api.Step {
  constructor(
    readonly kind: StepKind,
    readonly name: string,
    readonly place: api.Place,
  ) {}

  toString(): string {
    return stepForm(this);
  }
}

/** A place in a file. Package-internal. */
export function makePlace(resolvedPath: string, span: api.SourceSpan): api.Place {
  return new Place(resolvedPath, span);
}

/** An override's place. Package-internal. */
export function makeOverride(variable: string): api.Override {
  return new Override(variable);
}

/** One step of an origin. Package-internal. */
export function makeStep(kind: StepKind, name: string, place: api.Place): api.Step {
  return new Step(kind, name, place);
}
