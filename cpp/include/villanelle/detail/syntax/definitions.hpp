// The syntax definitions' entry point: <villanelle/syntax.hpp> includes it at its end in header-only mode, and
// <villanelle/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// VILLANELLE_API (or is a template).
#ifndef VILLANELLE_DETAIL_SYNTAX_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_SYNTAX_DEFINITIONS_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/syntax/parse.hpp>
#include <villanelle/syntax.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace syntax {

namespace detail {

/// The start of each token, then the end of the text: positions[i] is token i's start, positions[n] the text's end.
/// Offsets and columns in bytes; a line ends after each line feed (spec 2.1).
VILLANELLE_API std::vector<::villanelle::source_position> token_positions(std::string_view text,
                                                                          const std::vector<raw_token>& tokens) {
    std::vector<::villanelle::source_position> positions;
    positions.reserve(tokens.size() + 1);
    std::int64_t line = 0;
    std::size_t line_start = 0;
    const auto here = [&](std::size_t offset) {
        return ::villanelle::source_position(static_cast<std::int64_t>(offset), line,
                                             static_cast<std::int64_t>(offset - line_start));
    };
    for (const raw_token& token : tokens) {
        positions.push_back(here(token.start));
        for (std::size_t i = token.start; i < token.end; ++i) {
            if (text[i] == '\n') {
                ++line;
                line_start = i + 1;
            }
        }
    }
    positions.push_back(here(text.size()));
    return positions;
}

VILLANELLE_API ::villanelle::syntax::node to_node(const raw_node& raw) {
    std::vector<::villanelle::syntax::node> children;
    children.reserve(raw.children.size());
    for (const raw_node& child : raw.children) {
        children.push_back(to_node(child));
    }
    return {static_cast<std::int64_t>(raw.start), static_cast<std::int64_t>(raw.end), raw.kind, std::move(children)};
}

/// Raises index_out_of_range unless 0 <= start <= end <= count.
VILLANELLE_API void check_range(const ::villanelle::syntax::syntax& syntax,
                                const ::villanelle::syntax::token_range& range) {
    const auto count = static_cast<std::int64_t>(syntax.tokens().size());
    if (range.start() < 0 || range.end() > count || range.start() > range.end()) {
        ::villanelle::detail::raise(::villanelle::index_out_of_range(
            "token range [" + std::to_string(range.start()) + ", " + std::to_string(range.end()) + ") is outside [0, " +
            std::to_string(count) + "]"));
    }
}

}  // namespace detail

VILLANELLE_API ::villanelle::syntax::syntax parse(std::string_view text) {
    const std::vector<detail::raw_token> raw_tokens = detail::lex(text);
    const std::vector<::villanelle::source_position> positions = detail::token_positions(text, raw_tokens);
    const std::size_t count = raw_tokens.size();

    std::vector<::villanelle::syntax::token> tokens;
    tokens.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        const detail::raw_token& raw = raw_tokens[i];
        tokens.emplace_back(static_cast<::villanelle::token_kind>(raw.kind),
                            std::string(text.substr(raw.start, raw.end - raw.start)),
                            ::villanelle::source_span(positions[i], positions[i + 1]));
    }

    detail::raw_node root;
    std::vector<detail::raw_diagnostic> raw_diagnostics;
    if (const std::size_t too_deep = detail::nesting_overflow(raw_tokens); too_deep != detail::npos) {
        // The depth guard runs first: the recursive parser never sees text nested past the limit.
        root = {::villanelle::node_kind::document, 0, count, {{::villanelle::node_kind::error, 0, count, {}}}};
        const auto code = ::villanelle::diagnostic_code::nesting_too_deep;
        raw_diagnostics.push_back({code, too_deep, ::villanelle::describe(code).message});
    } else {
        detail::parser parser(text, raw_tokens);
        parser.r_document();
        root = parser.take_root();
        raw_diagnostics = parser.take_diagnostics();
    }
    root.start = 0;
    root.end = count;

    // Each diagnostic covers its token, or is zero-width at the end of the text.
    std::vector<::villanelle::diagnostic> diagnostics;
    diagnostics.reserve(raw_diagnostics.size());
    for (detail::raw_diagnostic& raw : raw_diagnostics) {
        const std::size_t end = raw.at < count ? raw.at + 1 : count;
        diagnostics.emplace_back(raw.code, std::move(raw.message),
                                 ::villanelle::source_span(positions[raw.at], positions[end]));
    }
    return {std::move(tokens), detail::to_node(root), std::move(diagnostics)};
}

VILLANELLE_API ::villanelle::source_span span_of(const ::villanelle::syntax::syntax& syntax,
                                                 const ::villanelle::syntax::token_range& range) {
    detail::check_range(syntax, range);
    const ::villanelle::sequence<::villanelle::syntax::token> tokens = syntax.tokens();
    const auto at = [&](std::int64_t i) {
        if (static_cast<std::size_t>(i) < tokens.size()) {
            return tokens.at(static_cast<std::size_t>(i)).span().start();
        }
        return tokens.empty() ? ::villanelle::source_position(0, 0, 0) : tokens.back().span().end();
    };
    const ::villanelle::source_position start = at(range.start());
    if (range.start() == range.end()) {
        return {start, start};
    }
    return {start, tokens.at(static_cast<std::size_t>(range.end() - 1)).span().end()};
}

VILLANELLE_API std::string text_of(const ::villanelle::syntax::syntax& syntax,
                                   const ::villanelle::syntax::token_range& range) {
    detail::check_range(syntax, range);
    const ::villanelle::sequence<::villanelle::syntax::token> tokens = syntax.tokens();
    std::string text;
    for (auto i = range.start(); i < range.end(); ++i) {
        text += tokens.at(static_cast<std::size_t>(i)).text();
    }
    return text;
}

}  // namespace syntax
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SYNTAX_DEFINITIONS_HPP
