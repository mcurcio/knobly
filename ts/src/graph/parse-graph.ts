/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
import type { IDocumentGraph } from "./graph.js";
import type { DocumentLoader } from "./io.js";

/** Options for parseGraph. */
export interface IParseGraphOptions {
  /** Identity of the root document, passed to loaders as the first parentPath. Default "<root>". */
  readonly path?: string;
  /** Required: the core does no I/O. Several loaders are combined with composeLoaders. */
  readonly loader: DocumentLoader | readonly DocumentLoader[];
  /** Deepest include nesting allowed; an include deeper than this gives E3003 and an edge with no targets. Default 16. */
  readonly maxIncludeDepth?: number;
}

/**
 * Parse a root text and resolve its includes into a document graph (port of reference parse.ts).
 *
 * An include is a directive named `include` whose first value is a string literal (vil-bgz: include paths are
 * quoted); any other first value gives E2006. Include diagnostics (E2006, E3001-E3004) carry the span of the
 * include directive and the resolvedPath of the document that contains it. A document reached twice is parsed
 * once; a cycle gives E3002 and leaves that edge's target the already-open node.
 *
 * Never rejects for anything in the texts or for a loader failure; those become diagnostics.
 * @throws TypeError when `options.loader` is missing.
 */
export function parseGraph(source: string, options: IParseGraphOptions): Promise<IDocumentGraph> {
  throw new Error("not implemented");
}
