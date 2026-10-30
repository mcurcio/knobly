/**
 * The objects a render builds: addresses, directives, their blocks and the rendered result. Package-internal;
 * programs see them through the generated interfaces (gen/api/rendered.ts).
 */

import { SnapshotBlock } from "../block.js";
import type { DiagnosticError } from "../gen/api/errors.js";
import type { AddressStep, Change, KeyOptions, RenderedBlock } from "../gen/api/rendered.js";
import type { DirectiveOrigin, LocatedDiagnostic, ProgramCode } from "../gen/api/shared.js";
import type { DocumentGraph, ExpandedValue, UnreadableExpansion, WrittenDirective } from "../gen/api/written.js";
import type * as api from "../gen/api/rendered.js";
import { programError } from "../locate.js";
import { diff } from "./diff.js";

export class Address implements api.Address {
  readonly steps: readonly AddressStep[];
  readonly text: string;

  constructor(
    readonly parent: Address | undefined,
    step: AddressStep,
  ) {
    this.steps = [...(parent?.steps ?? []), step];
    this.text = JSON.stringify(this.steps.map((s) => [s.name, s.key ?? null, s.occurrence]));
  }

  toString(): string {
    return this.steps
      .map((s) => `${s.name}${s.key === undefined ? "" : ` ${JSON.stringify(s.key)}`}${s.occurrence === 0 ? "" : ` #${String(s.occurrence)}`}`)
      .join(" > ");
  }
}

/** A rendered block (spec 2.11) over directives the render is still adding while it builds the tree. */
export function renderedBlock(directives: readonly api.Directive[]): RenderedBlock {
  return new SnapshotBlock(directives, (directive) => directive.name);
}

export class Directive implements api.Directive {
  readonly block: RenderedBlock | undefined;

  constructor(
    readonly name: string,
    readonly values: readonly ExpandedValue[],
    /** Its block's directives, which the render fills while it builds the tree; undefined when written without one. */
    children: readonly api.Directive[] | undefined,
    readonly unreadable: readonly UnreadableExpansion[],
    readonly parent: Directive | undefined,
    readonly origin: DirectiveOrigin,
    readonly written: WrittenDirective,
  ) {
    this.block = children === undefined ? undefined : renderedBlock(children);
  }

  closest(predicate: (directive: api.Directive) => boolean): api.Directive | undefined {
    return predicate(this) ? this : this.parent?.closest(predicate);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }
}

export class Rendered implements api.Rendered {
  constructor(
    readonly block: RenderedBlock,
    readonly unreadable: readonly UnreadableExpansion[],
    readonly origin: DirectiveOrigin,
    readonly diagnostics: readonly LocatedDiagnostic[],
    readonly graph: DocumentGraph,
  ) {}

  addresses(options?: KeyOptions): ReadonlyMap<api.Directive, api.Address> {
    const key = options?.key;
    const out = new Map<api.Directive, api.Address>();
    const name = (block: Iterable<api.Directive>, parent: Address | undefined): void => {
      const occurrences = new Map<string, number>();
      for (const directive of block) {
        const keyText: unknown = key?.(directive);
        if (keyText !== undefined && typeof keyText !== "string") {
          throw new TypeError(`a key rule returns a string or undefined, not ${typeof keyText}: ${directive.name}`);
        }
        const slot = JSON.stringify([directive.name, keyText ?? null]);
        const occurrence = occurrences.get(slot) ?? 0;
        occurrences.set(slot, occurrence + 1);
        const address = new Address(parent, { name: directive.name, key: keyText, occurrence });
        out.set(directive, address);
        name(directive.block ?? [], address);
      }
    };
    name(this.block, undefined);
    return out;
  }

  diff(after: api.Rendered, options?: KeyOptions): readonly Change[] {
    return diff(this, after, options);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }
}
