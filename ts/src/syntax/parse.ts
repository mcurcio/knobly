/* eslint-disable @typescript-eslint/no-unused-vars -- M1 skeleton (vil-g7n.1): the slice that fills the bodies deletes this line. */
/**
 * The adapter: the only module that touches the ANTLR runtime and the generated parser (src/gen/, made by
 * tools/gen.sh). Everything it returns is ours: IToken, INode, IDiagnostic.
 */

import type { ISyntax } from "./cst.js";

/**
 * Parse one text. Synchronous, pure and total: it never throws for any input string, and never reads files.
 * Errors are reported in `diagnostics`; the tree still covers every token.
 */
export function parse(text: string): ISyntax {
  throw new Error("not implemented");
}
