/**
 * Writing edited files back. The core does no I/O: the writer is the program's ("villanelle/node" and
 * "villanelle/browser" give ready-made ones).
 */

import type { IDocumentGraph } from "../load/graph.js";
import { textOf } from "../syntax/cst.js";

/** Persist one file's text. */
export interface IDocumentWriter {
  write(resolvedPath: string, source: string): Promise<void>;
}

/**
 * Write back every file whose syntax text (`textOf(syntax, syntax.root)`) differs from the source it was read
 * from, one writer call per changed file, in `nodes` order.
 */
export async function save(graph: IDocumentGraph, writer: IDocumentWriter): Promise<void> {
  for (const node of graph.nodes.values()) {
    const { syntax } = node;
    const text = textOf(syntax, syntax.root);
    if (text !== node.source) await writer.write(node.resolvedPath, text);
  }
}
