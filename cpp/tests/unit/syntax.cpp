// The syntax layer (spec 3): parse is lossless and total, recovery follows spec 3.2 (the F16 and F17 inputs of
// design.md, where the TypeScript and Python bindings differ), and span_of and text_of check their range.
#include <knobly/syntax.hpp>

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <catch2/catch_test_macros.hpp>

using knobly::diagnostic_code;
using knobly::node_kind;
using knobly::token_kind;
namespace syntax = knobly::syntax;

namespace {

struct shape {
    node_kind kind;
    std::int64_t start;
    std::int64_t end;
    std::vector<shape> children;
    friend bool operator==(const shape&, const shape&) = default;
};

shape shape_of(const syntax::node& n) {
    std::vector<shape> children;
    for (const syntax::node& child : n.children()) {
        children.push_back(shape_of(child));
    }
    return {n.kind(), n.start(), n.end(), children};
}

std::vector<diagnostic_code> codes(const syntax::syntax& s) {
    std::vector<diagnostic_code> out;
    for (const knobly::diagnostic& d : s.diagnostics()) {
        out.push_back(d.code());
    }
    return out;
}

std::string joined(const syntax::syntax& s) {
    std::string out;
    for (const syntax::token& t : s.tokens()) {
        out += t.text();
    }
    return out;
}

}  // namespace

TEST_CASE("a valid text parses clean and losslessly, with byte positions", "[parse]") {
    const std::string text = "node \"caf\xc3\xa9\" {\r\n  max 3;\n}\n";
    const syntax::syntax s = syntax::parse(text);
    CHECK(s.diagnostics().empty());
    CHECK(joined(s) == text);
    CHECK(s.tokens().at(0).kind() == token_kind::WORD);
    const syntax::token string = s.tokens().at(2);
    CHECK(string.kind() == token_kind::STRING);
    CHECK(string.span().end().offset() == 12);  // bytes: é is two
    const syntax::token max = s.tokens().at(7);
    CHECK(max.text() == "max");
    CHECK(max.span().start().line() == 1);  // "\r\n" ends one line
    CHECK(max.span().start().column() == 2);
    const std::int64_t n = static_cast<std::int64_t>(s.tokens().size());
    const shape inner{node_kind::directive, 7, 11, {}};  // max 3;
    CHECK(
        shape_of(s.root()) ==
        shape{node_kind::document, 0, n, {{node_kind::directive, 0, n - 1, {{node_kind::block, 4, n - 1, {inner}}}}}});
    CHECK(syntax::text_of(s, s.root()) == text);
}

TEST_CASE("parse is total: the empty text, an invalid byte and a lone surrogate", "[parse]") {
    const syntax::syntax empty = syntax::parse("");
    CHECK(empty.tokens().empty());
    CHECK(shape_of(empty.root()) == shape{node_kind::document, 0, 0, {}});

    const syntax::syntax bad = syntax::parse("a \xff;");
    CHECK(joined(bad) == "a \xff;");
    CHECK(bad.tokens().at(2).kind() == token_kind::BAD_CHAR);
    CHECK(bad.tokens().at(2).text() == "\xff");
    CHECK(codes(bad) == std::vector{diagnostic_code::unexpected_character});
    CHECK(bad.diagnostics().at(0).span().start().offset() == 2);
    CHECK(bad.diagnostics().at(0).span().end().offset() == 3);

    const syntax::syntax surrogate = syntax::parse("\xed\xa0\x80");
    CHECK(surrogate.tokens().size() == 1);
    CHECK(surrogate.tokens().at(0).kind() == token_kind::BAD_CHAR);
    CHECK(surrogate.tokens().at(0).text().size() == 3);
}

TEST_CASE("a diagnostic at the end of the text is zero-width there", "[parse]") {
    const syntax::syntax s = syntax::parse("a {\n  b;\n");
    CHECK(codes(s) == std::vector{diagnostic_code::expected_closing_brace});
    const knobly::source_span span = s.diagnostics().at(0).span();
    CHECK(span.start() == span.end());
    CHECK(span.start().offset() == 9);
    CHECK(span.start().line() == 2);
    CHECK(knobly::to_string(s.diagnostics().at(0)).rfind("3:1: E2003: ", 0) == 0);
}

TEST_CASE("F16: a bad statement inside a finished block hides no later statement", "[parse][recovery]") {
    const syntax::syntax s = syntax::parse("a { b [; }\n\"x\" 1;\nc 2;\nd ];\n");
    CHECK(shape_of(s.root()) ==
          shape{node_kind::document,
                0,
                26,
                {{node_kind::directive, 0, 10, {{node_kind::block, 2, 10, {{node_kind::error, 4, 9, {}}}}}},
                 {node_kind::error, 11, 15, {}},
                 {node_kind::directive, 16, 20, {}},
                 {node_kind::error, 21, 25, {}}}});
    CHECK(codes(s) == std::vector{diagnostic_code::unexpected_token, diagnostic_code::unexpected_token,
                                  diagnostic_code::expected_closing_bracket});
    CHECK(s.diagnostics().at(2).span().start().line() == 3);
}

TEST_CASE("F17: two adjacent bad statements are two error nodes", "[parse][recovery]") {
    const syntax::syntax s = syntax::parse("];];\nok 1;\n");
    CHECK(shape_of(s.root()) ==
          shape{node_kind::document,
                0,
                10,
                {{node_kind::error, 0, 2, {}}, {node_kind::error, 2, 4, {}}, {node_kind::directive, 5, 9, {}}}});
    CHECK(codes(s) ==
          std::vector{diagnostic_code::expected_closing_bracket, diagnostic_code::expected_closing_bracket});
}

TEST_CASE("nesting past the limit is one error node and E2010 at the first bracket past it", "[parse]") {
    const std::size_t limit = static_cast<std::size_t>(syntax::max_nesting);
    const syntax::syntax at_limit = syntax::parse("a " + std::string(limit, '[') + std::string(limit, ']') + ";");
    CHECK(at_limit.diagnostics().empty());

    const syntax::syntax deep = syntax::parse("a " + std::string(limit + 1, '[') + ";");
    const std::int64_t n = static_cast<std::int64_t>(deep.tokens().size());
    CHECK(shape_of(deep.root()) == shape{node_kind::document, 0, n, {{node_kind::error, 0, n, {}}}});
    CHECK(codes(deep) == std::vector{diagnostic_code::nesting_too_deep});
    CHECK(deep.diagnostics().at(0).span().start().offset() == static_cast<std::int64_t>(2 + limit));
}

TEST_CASE("the nesting guard counts the blocks recovery opens, and nothing it skips", "[parse]") {
    const std::size_t limit = static_cast<std::size_t>(syntax::max_nesting);
    const auto recovered = [](std::size_t n) {  // n blocks nested through recovery, each holding a stray ']'
        std::string text;
        for (std::size_t i = 0; i < n; ++i) {
            text += "a { ] ; ";
        }
        return text;
    };
    const syntax::syntax at_limit = syntax::parse(recovered(limit));
    CHECK(codes(at_limit).size() == limit + 1);  // each ']' is E2004, then the unclosed blocks' one E2003
    CHECK(codes(at_limit).back() == diagnostic_code::expected_closing_brace);
    for (const std::size_t n : {limit + 1, std::size_t{100'000}}) {
        const syntax::syntax deep = syntax::parse(recovered(n));
        const std::int64_t count = static_cast<std::int64_t>(deep.tokens().size());
        CHECK(shape_of(deep.root()) == shape{node_kind::document, 0, count, {{node_kind::error, 0, count, {}}}});
        CHECK(codes(deep) == std::vector{diagnostic_code::nesting_too_deep});
        CHECK(deep.diagnostics().at(0).span().start().offset() == static_cast<std::int64_t>(8 * limit + 2));
    }
    // Brackets and braces a bad statement's recovery skips open nothing: the statement's first error is its diagnostic.
    CHECK(codes(syntax::parse(std::string(500, ']') + std::string(limit + 1, '['))) ==
          std::vector{diagnostic_code::expected_closing_bracket});
    CHECK(codes(syntax::parse(std::string(100'000, '{'))) == std::vector{diagnostic_code::unexpected_token});
}

TEST_CASE("span_of and text_of take a range within the tokens, or raise index_out_of_range", "[span]") {
    const syntax::syntax s = syntax::parse("a b;");  // a, SPACE, b, ;
    CHECK(syntax::text_of(s, syntax::token_range(1, 3)) == " b");
    const knobly::source_span span = syntax::span_of(s, syntax::token_range(1, 3));
    CHECK(span.start().offset() == 1);
    CHECK(span.end().offset() == 3);
    const knobly::source_span at_end = syntax::span_of(s, syntax::token_range(4, 4));
    CHECK(at_end.start().offset() == 4);
    CHECK(at_end.start() == at_end.end());
    CHECK(syntax::span_of(syntax::parse(""), syntax::token_range(0, 0)).start().offset() == 0);

    CHECK_THROWS_AS(syntax::span_of(s, syntax::token_range(-1, 1)), knobly::index_out_of_range);
    CHECK_THROWS_AS(syntax::span_of(s, syntax::token_range(0, 5)), knobly::index_out_of_range);
    CHECK_THROWS_AS(syntax::span_of(s, syntax::token_range(3, 2)), knobly::index_out_of_range);
    CHECK_THROWS_AS(syntax::text_of(s, syntax::token_range(0, 5)), knobly::index_out_of_range);
    CHECK_THROWS_AS(syntax::text_of(s, syntax::token_range(2, 1)), knobly::index_out_of_range);
}
