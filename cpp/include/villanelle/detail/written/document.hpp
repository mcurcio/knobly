// Documents, copies, edges and the written block (spec 6.4, 6.5, 2.11).
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP
#define VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API std::string document::resolved_path() const {
    ::villanelle::detail::not_built("written::document::resolved_path");
}

VILLANELLE_API std::string document::saved_text() const {
    ::villanelle::detail::not_built("written::document::saved_text");
}

VILLANELLE_API std::string document::text() const { ::villanelle::detail::not_built("written::document::text"); }

VILLANELLE_API ::villanelle::syntax::syntax document::syntax() const {
    ::villanelle::detail::not_built("written::document::syntax");
}

VILLANELLE_API ::villanelle::written::written_block document::block() const {
    ::villanelle::detail::not_built("written::document::block");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::document_edge> document::included_by() const {
    ::villanelle::detail::not_built("written::document::included_by");
}

VILLANELLE_API void document::replace_with_text(::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::document::replace_with_text");
}

VILLANELLE_API bool operator==(const ::villanelle::written::document&, const ::villanelle::written::document&) {
    ::villanelle::detail::not_built("operator== of document");
}

VILLANELLE_API ::villanelle::written::copy document_edge::copy() const {
    ::villanelle::detail::not_built("written::document_edge::copy");
}

VILLANELLE_API ::villanelle::sequence<std::string> document_edge::specs() const {
    ::villanelle::detail::not_built("written::document_edge::specs");
}

VILLANELLE_API ::villanelle::sequence<std::string> document_edge::targets() const {
    ::villanelle::detail::not_built("written::document_edge::targets");
}

VILLANELLE_API bool operator==(const ::villanelle::written::document_edge&,
                               const ::villanelle::written::document_edge&) {
    ::villanelle::detail::not_built("operator== of document_edge");
}

VILLANELLE_API ::villanelle::written::statement copy::statement() const {
    ::villanelle::detail::not_built("written::copy::statement");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::step> copy::via() const {
    ::villanelle::detail::not_built("written::copy::via");
}

VILLANELLE_API bool operator==(const ::villanelle::written::copy&, const ::villanelle::written::copy&) {
    ::villanelle::detail::not_built("operator== of copy");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> written_block::insert_statements(
    std::int64_t, ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::written_block::insert_statements");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement> written_block::add_statements(
    ::villanelle::config_text) const {
    ::villanelle::detail::not_built("written::written_block::add_statements");
}

}  // namespace written

namespace detail {

VILLANELLE_API ::villanelle::sequence<::villanelle::written::statement>
block_traits<::villanelle::written::statement>::items(const view&) {
    not_built("block_traits<written::statement>::items");
}
VILLANELLE_API std::optional<block_traits<::villanelle::written::statement>::directive>
block_traits<::villanelle::written::statement>::as_directive(const ::villanelle::written::statement&,
                                                             std::optional<std::string_view>) {
    not_built("block_traits<written::statement>::as_directive");
}
VILLANELLE_API std::optional<view> block_traits<::villanelle::written::statement>::block_of(
    const ::villanelle::written::statement&) {
    not_built("block_traits<written::statement>::block_of");
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_DOCUMENT_HPP
