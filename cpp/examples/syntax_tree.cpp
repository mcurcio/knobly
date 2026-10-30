// Sample "syntax_tree" (examples/samples.json): parse text into the lossless syntax tree, walk it, and read the
// problems of text that does not parse. ctest examples_syntax_tree compares what it prints with
// examples/expected/syntax_tree.txt.
// --8<-- [start:main]
#include <villanelle/syntax.hpp>

#include <iostream>
#include <string>

namespace vl = villanelle;

// --8<-- [start:tree]
void print_tree(const vl::syntax::syntax& tree, const vl::syntax::node& node, int depth) {
    const vl::syntax::token first = tree.tokens().at(static_cast<std::size_t>(node.start()));
    std::cout << std::string(2 * depth, ' ') << vl::to_string(node.kind()) << " tokens " << node.start() << '-'
              << node.end() << " from " << vl::to_string(first.kind()) << " \"" << first.text() << "\"\n";
    for (const vl::syntax::node& child : node.children()) {
        print_tree(tree, child, depth + 1);
    }
}
// --8<-- [end:tree]

int main() {
    // --8<-- [start:parse]
    const std::string text = "server {\n    port 8080; # the port\n}\n";
    const vl::syntax::syntax tree = vl::syntax::parse(text);
    std::cout << "tokens " << tree.tokens().size() << ", problems " << tree.diagnostics().size() << '\n';
    // --8<-- [end:parse]
    print_tree(tree, tree.root(), 0);
    std::string comments;
    std::string all;
    for (const vl::syntax::token& token : tree.tokens()) {
        if (token.kind() == vl::token_kind::COMMENT) comments += token.text();
        all += token.text();
    }
    std::cout << "comment " << comments << '\n';
    std::cout << "lossless " << std::boolalpha << (all == text) << '\n';  // every byte is in a token

    for (const vl::diagnostic& d : vl::syntax::parse("a 1;\nb \"open;\nc 3;\n").diagnostics()) {
        const vl::source_position at = d.span().start();
        std::cout << vl::to_string(d.code()) << " at line " << at.line() + 1 << ", column " << at.column() + 1 << '\n';
    }
}
// --8<-- [end:main]
