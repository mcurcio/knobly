/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
import type { IAstDirective } from "../ast/ast.js";
import type { IDocumentGraph } from "./graph.js";

/**
 * Every directive of the graph in include-expanded order (port of reference iterate.ts): depth-first from the
 * root; an include directive is not yielded, its targets' directives are yielded in its place. A document
 * already being expanded is skipped, so cycles terminate.
 */
export function iterateDirectives(graph: IDocumentGraph): Generator<IAstDirective> {
  throw new Error("not implemented");
}
