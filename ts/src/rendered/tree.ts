/**
 * The objects a render builds: arguments, addresses, directives and the rendered result. Package-internal; programs
 * see them through the interfaces of model.ts.
 */

import type { DiagnosticError } from "../diagnostics.js";
import { programError } from "../locate.js";
import type { IDirectiveOrigin } from "../origin.js";
import type { ILocatedDiagnostic, ProgramCode } from "../report.js";
import { ExpandedValue } from "../value.js";
import type { Bound } from "../written/expanded.js";
import type { IDocumentGraph, IReferenceResolution, IWrittenDirective, WrittenValue } from "../written/model.js";
import { diff } from "./diff.js";
import type { Change, IAddress, IAddressStep, IArgument, IDirective, IKeyOptions, IRendered, IUnreadable, WalkControl } from "./model.js";

/** A rendered value: the shared expanded value and its readers, plus its links to the low level (spec 7.3). */
export class Argument extends ExpandedValue<Argument> implements IArgument {
  readonly written: WrittenValue;
  readonly definition: WrittenValue | undefined;
  readonly chain: readonly IReferenceResolution[];

  /** The argument of one value the low level's binding expanded. */
  constructor(bound: Bound) {
    super(
      bound.dataWith((item) => new Argument(item)),
      bound.origin,
    );
    this.written = bound.written;
    this.definition = bound.definition;
    this.chain = bound.chain;
  }
}

export class Address implements IAddress {
  readonly steps: readonly IAddressStep[];
  readonly text: string;

  constructor(
    readonly parent: Address | undefined,
    step: IAddressStep,
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

/** Visit `block` and the blocks below it depth-first; false when a visit returned "stop". */
function walkBlock(block: readonly IDirective[], visit: (directive: IDirective) => WalkControl | void): boolean {
  for (const directive of block) {
    const control = visit(directive);
    if (control === "stop") return false;
    if (control !== "skip" && !walkBlock(directive.block ?? [], visit)) return false;
  }
  return true;
}

export class Directive implements IDirective {
  /** Filled by the render while it builds the block; undefined when written without one. */
  readonly block: IDirective[] | undefined;
  readonly unreadable: IUnreadable[] = [];

  constructor(
    readonly name: string,
    readonly values: readonly IArgument[],
    hasBlock: boolean,
    readonly parent: Directive | undefined,
    readonly origin: IDirectiveOrigin,
    readonly written: IWrittenDirective,
  ) {
    this.block = hasBlock ? [] : undefined;
  }

  walk(visit: (directive: IDirective) => WalkControl | void): void {
    walkBlock(this.block ?? [], visit);
  }

  closest(predicate: (directive: IDirective) => boolean): IDirective | undefined {
    return predicate(this) ? this : this.parent?.closest(predicate);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }
}

export class Rendered implements IRendered {
  constructor(
    readonly block: readonly IDirective[],
    readonly unreadable: readonly IUnreadable[],
    readonly origin: IDirectiveOrigin,
    readonly diagnostics: readonly ILocatedDiagnostic[],
    readonly graph: IDocumentGraph,
  ) {}

  walk(visit: (directive: IDirective) => WalkControl | void): void {
    walkBlock(this.block, visit);
  }

  /**
   * The one home of the address rule (D4): each directive is named by its name, what the key rule returns for it,
   * and its occurrence among the earlier directives of its container (a block, or the top level, spliced files and
   * snippets included) with that name and key. The key rule is called once per directive, parents first.
   */
  addresses(options?: IKeyOptions): ReadonlyMap<IDirective, IAddress> {
    const key = options?.key;
    const out = new Map<IDirective, IAddress>();
    const name = (block: readonly IDirective[], parent: Address | undefined): void => {
      const occurrences = new Map<string, number>();
      for (const directive of block) {
        const keyText = key?.(directive);
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

  diff(after: IRendered, options?: IKeyOptions): readonly Change[] {
    return diff(this, after, options);
  }

  error(message: string, code: ProgramCode): DiagnosticError {
    return programError(this.origin, message, code);
  }
}
