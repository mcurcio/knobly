// The statement handles (spec 6.4, 6.5; ts/src/written/statements.ts): one node per written statement for the graph's
// life; the document re-points it at its tokens after each edit, or detaches it. Every member but kind() checks that
// the statement is live first (contract 4.3).
#ifndef KNOBLY_DETAIL_WRITTEN_STATEMENTS_HPP
#define KNOBLY_DETAIL_WRITTEN_STATEMENTS_HPP

#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <knobly/detail/written/core.hpp>
#include <knobly/detail/written/document.hpp>
#include <knobly/detail/written/edits.hpp>
#include <knobly/detail/written/host.hpp>
#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN

namespace written {

namespace detail {

/// The live statement a handle shows. @throws knobly::detached_error
template <class Handle>
statement_node* live_statement(const Handle& handle) {
    return live(node_of<statement_node>(handle));
}

/// A statement's name token's text.
inline std::string name_text(const statement_node* s) { return std::string(s->doc->parsed.text_at(s->tree.start())); }

inline std::optional<::knobly::written::written_block> block_handle(const statement_node* s) {
    if (s->block == nullptr) {
        return std::nullopt;
    }
    return make_handle<::knobly::written::written_block>(s->block);
}

}  // namespace detail

KNOBLY_API ::knobly::statement_kind statement::kind() const noexcept {
    return detail::node_of<detail::statement_node>(*this)->kind;
}

KNOBLY_API ::knobly::written::document statement::document() const {
    return detail::make_handle<::knobly::written::document>(detail::live_statement(*this)->doc);
}

KNOBLY_API std::optional<::knobly::written::statement> statement::parent() const {
    detail::statement_node* s = detail::live_statement(*this);
    if (s->parent == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::statement>(s->parent);
}

KNOBLY_API ::knobly::place statement::place() const {
    detail::statement_node* s = detail::live_statement(*this);
    const detail::parsed_text& p = s->doc->parsed;
    const detail::token_span range = detail::owned_range(p, s->tree);
    return {s->doc->path, p.span_of(range.first, range.second)};
}

KNOBLY_API std::string statement::text() const {
    detail::statement_node* s = detail::live_statement(*this);
    const detail::token_span range = detail::owned_range(s->doc->parsed, s->tree);
    return s->doc->parsed.text_of(range.first, range.second);
}

KNOBLY_API ::knobly::sequence<::knobly::written::copy> statement::copies() const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::binding_core* binding = detail::binding_of(s->doc->graph);
    const auto found = binding->copies.find(s);
    if (found == binding->copies.end()) {
        return {};
    }
    return detail::handles_of<::knobly::written::copy>(found->second);
}

KNOBLY_API ::knobly::sequence<::knobly::written::statement> statement::replace_with_text(
    ::knobly::config_text text) const {
    return detail::handles_of<::knobly::written::statement>(
        detail::replace_statement(detail::live_statement(*this), text.view()));
}

KNOBLY_API void statement::remove() const { detail::remove_statement(detail::live_statement(*this)); }

KNOBLY_API ::knobly::sequence<::knobly::written::statement> statement::insert_before(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::block_node* block = detail::containing_block(s);
    const std::int64_t at = detail::position_of(block->handles, s);
    return detail::handles_of<::knobly::written::statement>(
        detail::insert_statements(block, static_cast<std::size_t>(at), text.view()));
}

KNOBLY_API ::knobly::sequence<::knobly::written::statement> statement::insert_after(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::block_node* block = detail::containing_block(s);
    const std::int64_t at = detail::position_of(block->handles, s);
    return detail::handles_of<::knobly::written::statement>(
        detail::insert_statements(block, static_cast<std::size_t>(at + 1), text.view()));
}

// ---- a directive and an extension line: a name, values and an optional block

KNOBLY_API std::string written_directive::name() const { return detail::name_text(detail::live_statement(*this)); }

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> written_directive::values() const {
    return detail::handles_of<::knobly::written::written_value>(detail::live_statement(*this)->values);
}

KNOBLY_API std::optional<::knobly::written::written_block> written_directive::block() const {
    return detail::block_handle(detail::live_statement(*this));
}

KNOBLY_API void written_directive::rename(std::string_view name) const {
    detail::rename_statement(detail::live_statement(*this), name);
}

KNOBLY_API void written_directive::set(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::replace_values(s, s->tree.start(), text.view());
}

/// Its name without @.
KNOBLY_API std::string extension_line::name() const {
    return detail::name_text(detail::live_statement(*this)).substr(1);
}

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> extension_line::values() const {
    return detail::handles_of<::knobly::written::written_value>(detail::live_statement(*this)->values);
}

KNOBLY_API std::optional<::knobly::written::written_block> extension_line::block() const {
    return detail::block_handle(detail::live_statement(*this));
}

KNOBLY_API void extension_line::set(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::replace_values(s, s->tree.start(), text.view());
}

// ---- language statements

KNOBLY_API ::knobly::written::set_variable set_line::variable() const {
    return detail::make_handle<::knobly::written::set_variable>(detail::live_statement(*this)->variable);
}

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> set_line::values() const {
    return detail::handles_of<::knobly::written::written_value>(detail::live_statement(*this)->values);
}

KNOBLY_API void set_line::set(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::replace_values(s, detail::first_arg_token(s), text.view());
}

KNOBLY_API std::string snippet_line::name() const {
    detail::statement_node* s = detail::live_statement(*this);
    return std::string(s->doc->parsed.text_at(detail::first_arg_token(s)));
}

KNOBLY_API ::knobly::sequence<::knobly::written::parameter> snippet_line::parameters() const {
    return detail::handles_of<::knobly::written::parameter>(detail::live_statement(*this)->parameters);
}

KNOBLY_API ::knobly::written::written_block snippet_line::block() const {
    detail::statement_node* s = detail::live_statement(*this);
    return detail::make_handle<::knobly::written::written_block>(s->block);
}

KNOBLY_API std::string use_line::snippet_name() const {
    detail::statement_node* s = detail::live_statement(*this);
    return std::string(s->doc->parsed.text_at(detail::first_arg_token(s)));
}

/// The snippet line of its name nearest above it, by where it is written.
KNOBLY_API std::optional<::knobly::written::snippet_line> use_line::snippet() const {
    detail::statement_node* s = detail::live_statement(*this);
    const std::string name = snippet_name();
    detail::statement_node* found = detail::above(s, [&](detail::statement_node* candidate) {
        return candidate->kind == ::knobly::statement_kind::snippet &&
               candidate->doc->parsed.text_at(detail::first_arg_token(candidate)) == name;
    });
    if (found == nullptr) {
        return std::nullopt;
    }
    return detail::make_handle<::knobly::written::snippet_line>(found);
}

KNOBLY_API ::knobly::sequence<::knobly::written::resolution<::knobly::written::snippet_line>> use_line::snippets()
    const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::binding_core* binding = detail::binding_of(s->doc->graph);
    const auto found = binding->by_use.find(s);
    if (found == binding->by_use.end()) {
        return {};
    }
    return detail::handles_of<::knobly::written::resolution<::knobly::written::snippet_line>>(found->second);
}

KNOBLY_API ::knobly::sequence<::knobly::written::written_value> use_line::values() const {
    return detail::handles_of<::knobly::written::written_value>(detail::live_statement(*this)->values);
}

KNOBLY_API void use_line::set(::knobly::config_text text) const {
    detail::statement_node* s = detail::live_statement(*this);
    detail::replace_values(s, detail::first_arg_token(s), text.view());
}

}  // namespace written

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_STATEMENTS_HPP
