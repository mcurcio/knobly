/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
import type { IDocumentGraph } from "./graph.js";
import type { IDocumentWriter } from "./io.js";

/**
 * Write back every document whose syntax text (`textOf(syntax, syntax.root)`) differs from the source it was
 * loaded from, one writer call per changed document, in `nodes` order.
 */
export function save(graph: IDocumentGraph, writer: IDocumentWriter): Promise<void> {
  throw new Error("not implemented");
}
