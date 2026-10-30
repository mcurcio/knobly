// Statements and their edits (spec 6.5): the union and one class per kind.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_STATEMENTS_HPP
#define VILLANELLE_DETAIL_WRITTEN_STATEMENTS_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API ::villanelle::statement_kind statement::kind() const noexcept {
    ::villanelle::detail::not_built("written::statement::kind");
}

VILLANELLE_API ::villanelle::written::document statement::document() const {
    ::villanelle::detail::not_built("written::statement::document");
}

VILLANELLE_API std::optional<::villanelle::written::statement> statement::parent() const {
    ::villanelle::detail::not_built("written::statement::parent");
}

VILLANELLE_API ::villanelle::place statement::place() const {
    ::villanelle::detail::not_built("written::statement::place");
}

VILLANELLE_API std::string statement::text() const { ::villanelle::detail::not_built("written::statement::text"); }

VILLANELLE_API ::villanelle::sequence<::villanelle::written::copy> statement::copies() const {
    ::villanelle::detail::not_built("written::statement::copies");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> statement::replace_with_text(
    ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::statement::replace_with_text");
}

VILLANELLE_API void statement::remove() const { ::villanelle::detail::not_built("written::statement::remove"); }

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> statement::insert_before(
    ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::statement::insert_before");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> statement::insert_after(
    ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::statement::insert_after");
}

VILLANELLE_API bool operator==(const ::villanelle::written::statement&, const ::villanelle::written::statement&) {
    ::villanelle::detail::not_built("operator== of statement");
}

VILLANELLE_API std::string written_directive::name() const {
    ::villanelle::detail::not_built("written::written_directive::name");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> written_directive::values() const {
    ::villanelle::detail::not_built("written::written_directive::values");
}

VILLANELLE_API std::optional<::villanelle::written::written_block> written_directive::block() const {
    ::villanelle::detail::not_built("written::written_directive::block");
}

VILLANELLE_API void written_directive::rename(std::string_view) const {
    ::villanelle::detail::not_built("written::written_directive::rename");
}

VILLANELLE_API void written_directive::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::written_directive::set");
}

VILLANELLE_API std::string extension_line::name() const {
    ::villanelle::detail::not_built("written::extension_line::name");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> extension_line::values() const {
    ::villanelle::detail::not_built("written::extension_line::values");
}

VILLANELLE_API std::optional<::villanelle::written::written_block> extension_line::block() const {
    ::villanelle::detail::not_built("written::extension_line::block");
}

VILLANELLE_API void extension_line::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::extension_line::set");
}

VILLANELLE_API ::villanelle::written::set_variable set_line::variable() const {
    ::villanelle::detail::not_built("written::set_line::variable");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> set_line::values() const {
    ::villanelle::detail::not_built("written::set_line::values");
}

VILLANELLE_API void set_line::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::set_line::set");
}

VILLANELLE_API std::string snippet_line::name() const {
    ::villanelle::detail::not_built("written::snippet_line::name");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::parameter> snippet_line::parameters() const {
    ::villanelle::detail::not_built("written::snippet_line::parameters");
}

VILLANELLE_API ::villanelle::written::written_block snippet_line::block() const {
    ::villanelle::detail::not_built("written::snippet_line::block");
}

VILLANELLE_API std::string use_line::snippet_name() const {
    ::villanelle::detail::not_built("written::use_line::snippet_name");
}

VILLANELLE_API std::optional<::villanelle::written::snippet_line> use_line::snippet() const {
    ::villanelle::detail::not_built("written::use_line::snippet");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::resolution<::villanelle::written::snippet_line>>
use_line::snippets() const {
    ::villanelle::detail::not_built("written::use_line::snippets");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::written_value> use_line::values() const {
    ::villanelle::detail::not_built("written::use_line::values");
}

VILLANELLE_API void use_line::set(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::use_line::set");
}

}  // namespace written

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_STATEMENTS_HPP
