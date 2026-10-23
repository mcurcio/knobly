/**
 * The include graph: the root document plus every document its includes resolve to. Read-only.
 */

import type { IAstDirective, IAstDocument } from "../ast/ast.js";
import type { IDiagnostic } from "../diagnostics.js";
import type { INode } from "../syntax/cst.js";

/** What one `include` directive resolved to. */
export interface IDocumentEdge {
  /** The include directive, in the including document. */
  readonly directive: IAstDirective;
  /** The decoded string literal: the include's path or glob. */
  readonly spec: string;
  /** The documents it resolved to, sorted by resolvedPath in code-point order (vil-bgz.1); empty on failure. */
  readonly targets: readonly IDocumentNode[];
}

/** One document of the graph. */
export interface IDocumentNode {
  /** Unique identity of the document in the graph; its meaning is the loader's. */
  readonly resolvedPath: string;
  /** The text as loaded. */
  readonly source: string;
  readonly document: IAstDocument;
  /** The resolution of each include directive of this document, keyed by the directive's CST node. */
  readonly includes: ReadonlyMap<INode, IDocumentEdge>;
}

/** A diagnostic and the document it is located in. */
export interface IGraphDiagnostic extends IDiagnostic {
  /** The document whose text `span` points into. */
  readonly resolvedPath: string;
}

export interface IDocumentGraph {
  readonly root: IDocumentNode;
  /** Every document, by resolvedPath, the root included. A one-node graph when there are no includes. */
  readonly nodes: ReadonlyMap<string, IDocumentNode>;
  /**
   * All diagnostics in the order found: a document's syntax diagnostics when it is parsed, then each include's
   * diagnostics as that include is resolved, depth-first.
   */
  readonly diagnostics: readonly IGraphDiagnostic[];
}
