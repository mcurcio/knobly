// Sample "syntax_tree" (examples/samples.json): parse one text into its lossless syntax tree: tokens, nodes, comments
// and syntax problems. ts/examples/examples.test.ts runs this file and compares what it prints with
// examples/expected/syntax_tree.txt.
// --8<-- [start:main]
import { parse, TokenKind, type Node } from "knobly/syntax";

// --8<-- [start:parse]
const text = "server {\n    port 8080; # the port\n}\n";
const syntax = parse(text);
console.log(`tokens ${syntax.tokens.length}, problems ${syntax.diagnostics.length}`);
// --8<-- [end:parse]

// --8<-- [start:tree]
function show(node: Node, depth: number): void {
  const first = syntax.tokens[node.start];
  console.log(`${"  ".repeat(depth)}${node.kind} tokens ${node.start}-${node.end} from ${first?.kind} "${first?.text}"`);
  for (const child of node.children) show(child, depth + 1);
}
show(syntax.root, 0);
// --8<-- [end:tree]

const comments = syntax.tokens.filter((token) => token.kind === TokenKind.COMMENT);
console.log(`comment ${comments.map((token) => token.text).join(" ")}`);
console.log(`lossless ${syntax.tokens.map((token) => token.text).join("") === text}`);

for (const { code, span } of parse('a 1;\nb "open;\nc 3;\n').diagnostics) {
  console.log(`${code} at line ${span.start.line + 1}, column ${span.start.column + 1}`);
}
// --8<-- [end:main]
