/**
 * The binding (design rule 3; slices.md S1 "Internal contract: the binding"): one derivation of the graph's
 * current texts, handed-in values and read ledger. It walks the copies (the root, then each include and `use`
 * spliced in place), decides per copy what each `$name` and `use` reads, and expands written values for the
 * extension lines (an include's path) and for `render`. It is the one home of the name-lookup rule: `render`
 * walks `items` and calls `argumentsAt`, and never looks a name up. Private to the package; pure (no I/O).
 */

import type { UnreadableKind } from "../load/directive.js";
import type { IExtension } from "../load/processor.js";
import type { ILocatedDiagnostic } from "../load/report.js";
import type { Argument } from "../load/tree.js";
import type {
  ICopy,
  IDocument,
  IDocumentEdge,
  IReference,
  IReferenceResolution,
  IResolution,
  ISnippetLine,
  IUseLine,
  IVariable,
  Statement,
  WrittenValue,
} from "./model.js";

/**
 * The walk's limits and the reserved names. S1 moves their definitions here from load/expand.ts (which it deletes);
 * until then they are re-exported, so each has one home.
 */
export { MAX_DEPTH, MAX_DIRECTIVES, RESERVED } from "../load/expand.js";

/** What one container (the root's top level, or a directive's block) holds at one copy, in walk order. */
export type BoundItem = IBoundDirective | IBoundUnreadable;

/** One copy of a directive statement (kind "directive"), with its block's items at that copy. */
export interface IBoundDirective {
  readonly kind: "directive";
  readonly copy: ICopy;
  /** Undefined when written without a block. */
  readonly children: readonly BoundItem[] | undefined;
}

/**
 * One copy of a statement that cannot be read there: a syntax error, a malformed or repeated `set`/`snippet`/`use`,
 * an unknown snippet or wrong arity, an include that failed, a cycle, too deep, too many directives.
 */
export interface IBoundUnreadable {
  readonly kind: "unreadable";
  readonly copy: ICopy;
  readonly reason: UnreadableKind;
  /** Undefined when the problem is already one of a document's syntax diagnostics. */
  readonly diagnostic: ILocatedDiagnostic | undefined;
}

/** A written value that cannot be expanded at a copy (E5001, E4001, E4003): the statement is unreadable there. */
export class BindingProblem extends Error {
  constructor(
    readonly kind: UnreadableKind,
    readonly diagnostic: ILocatedDiagnostic,
  ) {
    super(diagnostic.message);
    this.name = "BindingProblem";
  }
}

/** Which files were read: the one piece of state besides the texts (design rule 1). */
export interface IReadLedger {
  /** The paths `spec` resolved to from `parentPath`, the Error the source rejected with, or undefined: not resolved yet. */
  resolved(parentPath: string, spec: string): readonly string[] | Error | undefined;
  /** The document read at `resolvedPath`, the Error its read rejected with, or undefined: not read yet. */
  read(resolvedPath: string): IDocument | Error | undefined;
}

/** A handed-in value: its variable handle and its values, already read (as PR 3's `readHanded`). */
export interface IHandedInput {
  readonly variable: IVariable;
  readonly values: readonly Argument[];
}

/** The inputs of one derivation. */
export interface IBindingInput {
  readonly root: IDocument;
  readonly extensions: ReadonlyMap<string, IExtension>;
  readonly handed: ReadonlyMap<string, IHandedInput>;
  readonly reads: IReadLedger;
}

/** One derivation. Immutable; the graph makes a new one after any edit, `setHanded` or read. */
export interface IBinding {
  /** The root document's top level at the root copy, includes and uses spliced in place. */
  readonly items: readonly BoundItem[];
  /** Every copy of every extension line, in walk order (a failed or unread one included). */
  readonly edges: readonly IDocumentEdge[];
  /** The edges with a spec not resolved, or a target not read, in the ledger. */
  readonly unread: readonly IDocumentEdge[];
  /** Every diagnostic the walk found, in walk order, render's codes included (the graph filters them). */
  readonly diagnostics: readonly ILocatedDiagnostic[];
  /** Every copy of `statement`, in walk order. */
  copiesOf(statement: Statement): readonly ICopy[];
  /** One per copy of the reference's statement, in walk order. */
  resolutionsOf(reference: IReference): readonly IReferenceResolution[];
  /** Every resolution, in walk order: what `IVariable.reaches()` and `overridden()` filter. */
  resolutions(): readonly IReferenceResolution[];
  /** One per copy of the `use` line, in walk order. */
  snippetsOf(use: IUseLine): readonly IResolution<ISnippetLine>[];
  /** The edges whose `targets` include `resolvedPath`. */
  edgesInto(resolvedPath: string): readonly IDocumentEdge[];
  /**
   * One written value at one copy of its statement, expanded with PR 3's origins: a `$name` becomes all its winner's
   * values (each with the variable step, then the copy's steps); a list's items expand the same way.
   * @throws BindingProblem E5001 (nothing visible), E4001 (slice bound), E4003 (escape)
   */
  argumentsAt(value: WrittenValue, copy: ICopy): readonly Argument[];
}

/** Derive the binding of these inputs. Pure and synchronous. */
export function bind(input: IBindingInput): IBinding {
  void input;
  throw new Error("not implemented: bind (slices.md S1)");
}
