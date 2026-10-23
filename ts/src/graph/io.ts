/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * The I/O ports of the include graph. The core performs no I/O; effects live in loaders and writers supplied by
 * the caller (./node and ./browser give ready-made ones).
 */

/** Where an include spec is being resolved from. */
export interface ILoadContext {
  /** `resolvedPath` of the including document. */
  readonly parentPath: string;
  /** Include depth of the including document (the root is 0). */
  readonly depth: number;
}

/** One document a loader found. */
export interface ILoadedDocument {
  readonly source: string;
  /** Stable identity of the document (file path, URL); its meaning is the loader's. */
  readonly resolvedPath: string;
}

/**
 * Resolve an include spec (a path, or a glob with * and ?) to zero or more documents, in any order. An empty
 * result means "not found". A loader may reject; parseGraph turns that into E3004.
 */
export type DocumentLoader = (spec: string, context: ILoadContext) => Promise<readonly ILoadedDocument[]>;

/** Persist one document's text. */
export interface IDocumentWriter {
  write(resolvedPath: string, source: string): Promise<void>;
}

/**
 * One loader from several. A spec without * or ? goes to each loader in turn and the first non-empty result wins;
 * a glob goes to every loader and the results are merged, the last one for a `resolvedPath` winning.
 */
export function composeLoaders(loaders: readonly DocumentLoader[]): DocumentLoader {
  throw new Error("not implemented");
}
