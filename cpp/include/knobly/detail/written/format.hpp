// format_diagnostic (spec 2.3, 7.7; ts/src/written/format.ts): a located diagnostic as text for people, with its
// source line and carets when a graph holds its file. Columns and carets count bytes (design.md 2.4).
#ifndef VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP
#define VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP

#include <algorithm>
#include <cstdint>
#include <string>
#include <string_view>

#include <villanelle/detail/written/core.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

namespace detail {

inline std::string format_with(const ::villanelle::located_diagnostic& diagnostic, const document_node* doc) {
    std::string out = to_string(diagnostic);
    const ::villanelle::place place = diagnostic.place();
    if (doc != nullptr) {
        const std::string_view source = doc->parsed.text;
        const ::villanelle::source_position start = place.span().start();
        const ::villanelle::source_position end = place.span().end();
        const auto line_start = static_cast<std::size_t>(
            std::clamp<std::int64_t>(start.offset() - start.column(), 0, static_cast<std::int64_t>(source.size())));
        std::size_t line_end = source.find('\n', line_start);
        if (line_end == std::string_view::npos) {
            line_end = source.size();
        } else if (line_end > line_start && source[line_end - 1] == '\r') {
            --line_end;
        }
        const std::string_view text = source.substr(line_start, line_end - line_start);
        const std::int64_t width = end.line() == start.line() ? end.column() - start.column()
                                                              : static_cast<std::int64_t>(text.size()) - start.column();
        // Tabs stay tabs so the caret lines up under the same characters.
        std::string pad(text.substr(
            0,
            std::min<std::size_t>(static_cast<std::size_t>(std::max<std::int64_t>(start.column(), 0)), text.size())));
        for (char& c : pad) {
            if (c != '\t') {
                c = ' ';
            }
        }
        out += '\n';
        out += text;
        out += '\n';
        out += pad;
        out += std::string(static_cast<std::size_t>(std::max<std::int64_t>(1, width)), '^');
    }
    for (const ::villanelle::step& step : diagnostic.via()) {
        out += "\n  via ";
        out += to_string(step);
    }
    return out;
}

}  // namespace detail

VILLANELLE_API std::string format_diagnostic(const ::villanelle::located_diagnostic& diagnostic) {
    return detail::format_with(diagnostic, nullptr);
}

VILLANELLE_API std::string format_diagnostic(const ::villanelle::located_diagnostic& diagnostic,
                                             const ::villanelle::written::document_graph& graph) {
    return detail::format_with(
        diagnostic, detail::node_of<detail::graph_core>(graph)->document(diagnostic.place().resolved_path()));
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_FORMAT_HPP
