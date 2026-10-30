// The grammar's entry rules (spec 2.8): an edit's or override's text parsed with the rule for where it goes, its
// first problem as its one diagnostic (ts/src/syntax/parse.ts parseEntry). Built on the syntax layer's generated
// parser and its hooks; package-internal.
#ifndef KNOBLY_DETAIL_WRITTEN_ENTRY_HPP
#define KNOBLY_DETAIL_WRITTEN_ENTRY_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <knobly/detail/syntax/definitions.hpp>
#include <knobly/detail/written/core.hpp>
#include <knobly/syntax.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written::detail {

/// The grammar's entry rules (grammar/Knobly.g4 lines 31-37).
enum class entry_rule : std::uint8_t {
    statements_text,
    values_text,
    value_text,
    items_text,
    bound_text,
    slice_name_text,
    name_text
};

/// A document's text, parsed whole.
inline parsed_text parse_document(std::string text) {
    ::knobly::syntax::syntax parsed = ::knobly::syntax::parse(text);
    return {std::move(text), std::move(parsed)};
}

/// The text parsed with one entry rule: its tokens, a document node holding the lists and slices (and statements) the
/// rule built, and at most one diagnostic, the first.
inline parsed_text parse_entry(std::string_view text, entry_rule rule) {
    namespace sd = ::knobly::syntax::detail;
    const std::vector<sd::raw_token> raw_tokens = sd::lex(text);
    const std::vector<::knobly::source_position> positions = sd::token_positions(text, raw_tokens);
    const std::size_t count = raw_tokens.size();
    std::vector<::knobly::syntax::token> tokens;
    tokens.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        const sd::raw_token& raw = raw_tokens[i];
        tokens.emplace_back(static_cast<::knobly::token_kind>(raw.kind),
                            std::string(text.substr(raw.start, raw.end - raw.start)),
                            ::knobly::source_span(positions[i], positions[i + 1]));
    }
    sd::raw_node root{::knobly::node_kind::document, 0, count, {}};
    std::vector<sd::raw_diagnostic> diagnostics;
    if (const std::size_t too_deep = sd::nesting_overflow(raw_tokens); too_deep != sd::npos) {
        const auto code = ::knobly::diagnostic_code::nesting_too_deep;
        diagnostics.push_back({code, too_deep, ::knobly::describe(code).message});
    } else {
        sd::parser parser(text, raw_tokens);
        parser.open_node(::knobly::node_kind::document);
        bool done = false;
        switch (rule) {
            case entry_rule::statements_text:
                done = parser.r_statementsText();
                break;
            case entry_rule::values_text:
                done = parser.r_valuesText();
                break;
            case entry_rule::value_text:
                done = parser.r_valueText();
                break;
            case entry_rule::items_text:
                done = parser.r_itemsText();
                break;
            case entry_rule::bound_text:
                done = parser.r_boundText();
                break;
            case entry_rule::slice_name_text:
                done = parser.r_sliceNameText();
                break;
            case entry_rule::name_text:
                done = parser.r_nameText();
                break;
        }
        diagnostics = parser.take_diagnostics();
        if (done && diagnostics.empty()) {
            parser.close_node();
            root = parser.take_root();
        }
        root.start = 0;
        root.end = count;
    }
    std::vector<::knobly::diagnostic> located;
    if (!diagnostics.empty()) {
        sd::raw_diagnostic& first = diagnostics.front();
        if (rule != entry_rule::statements_text && first.code != ::knobly::diagnostic_code::nesting_too_deep) {
            // An entry rule's statement is the whole text (spec 2.8; recovery.ts statementStart): its error is
            // classified from token 0, outside any block. The syntax layer's hooks classify from the statement being
            // parsed, which only a statements list has (a follow-up for the syntax layer: an entry mode there).
            const ::knobly::diagnostic_code code = sd::classify(raw_tokens, first.at, 0, false);
            const std::string what =
                first.at < count ? sd::quoted(text.substr(raw_tokens[first.at].start,
                                                          raw_tokens[first.at].end - raw_tokens[first.at].start))
                                 : std::string("end of input");
            first = {code, first.at, ::knobly::describe(code, what).message};
        }
        const std::size_t end = first.at < count ? first.at + 1 : count;
        located.emplace_back(first.code, std::move(first.message),
                             ::knobly::source_span(positions[first.at], positions[end]));
    }
    return {std::string(text), ::knobly::syntax::syntax(std::move(tokens), sd::to_node(root), std::move(located))};
}

}  // namespace written::detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_ENTRY_HPP
