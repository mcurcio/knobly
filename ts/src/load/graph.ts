/**
 * The file graph of one load: every file read, each read and parsed once however many places splice it in (R21),
 * and one edge per place an extension directive spliced files. Read-only.
 */

import type { ISyntax } from "../syntax/cst.js";
import type { IDirectiveOrigin } from "./origin.js";

/** One file read during a load. */
export interface IDocumentNode {
  /** The file's identity, as the document source gave it. */
  readonly resolvedPath: string;
  /** The text as read. */
  readonly source: string;
  /** Its tier-1 parse: tokens, lossless tree and this file's syntax diagnostics. */
  readonly syntax: ISyntax;
}

/** One place an extension directive spliced files in (a file included at two places has two edges). */
export interface IDocumentEdge {
  /** The extension's directive name: "include". */
  readonly directive: string;
  /** Where the extension directive was written, and the uses and includes that brought it to this place. */
  readonly origin: IDirectiveOrigin;
  /** The specs the extension gave, in its order. */
  readonly specs: readonly string[];
  /** resolvedPaths in splice order; empty when it failed (a diagnostic says why). */
  readonly targets: readonly string[];
}

export interface IDocumentGraph {
  readonly root: IDocumentNode;
  /** Every file read, by resolvedPath, the root included, in first-read order. */
  readonly nodes: ReadonlyMap<string, IDocumentNode>;
  /** Every extension place, in expansion order. */
  readonly edges: readonly IDocumentEdge[];
}
