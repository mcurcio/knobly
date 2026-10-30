# Sample "syntax_tree" (examples/samples.json): parse text into tokens and a lossless syntax tree. The user guide
# includes the regions between the --8<-- markers; py/tests/test_examples.py runs this file and compares what it
# prints with examples/expected/syntax_tree.txt.
# --8<-- [start:main]
from knobly import syntax

text = "server {\n    port 8080; # the port\n}\n"
# --8<-- [start:parse]
tree = syntax.parse(text)
print(f"tokens {len(tree.tokens)}, problems {len(tree.diagnostics)}")
# --8<-- [end:parse]


# --8<-- [start:tree]
def show(node: syntax.Node, depth: int = 0) -> None:
    first = tree.tokens[node.start]
    print(f'{"  " * depth}{node.kind} tokens {node.start}-{node.end} from {first.kind} "{first.text}"')
    for child in node.children:
        show(child, depth + 1)


show(tree.root)
# --8<-- [end:tree]
print(f"comment {' '.join(t.text for t in tree.tokens if t.kind == syntax.TokenKind.COMMENT)}")
print(f"lossless {str(''.join(t.text for t in tree.tokens) == text).lower()}")
for problem in syntax.parse('a 1;\nb "open;\nc 3;\n').diagnostics:
    start = problem.span.start
    print(f"{problem.code} at line {start.line + 1}, column {start.column + 1}")
# --8<-- [end:main]
