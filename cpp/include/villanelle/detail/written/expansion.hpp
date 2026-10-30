// The expansion and expanded values with their readers (spec 2.9, 6.10).
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP
#define VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace written {

VILLANELLE_API ::villanelle::written::expansion_block expansion::block() const {
    ::villanelle::detail::not_built("written::expansion::block");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> expansion::unreadable() const {
    ::villanelle::detail::not_built("written::expansion::unreadable");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> expansion::diagnostics() const {
    ::villanelle::detail::not_built("written::expansion::diagnostics");
}

VILLANELLE_API bool operator==(const ::villanelle::written::expansion&, const ::villanelle::written::expansion&) {
    ::villanelle::detail::not_built("operator== of expansion");
}

VILLANELLE_API ::villanelle::written::written_directive directive_expansion::written() const {
    ::villanelle::detail::not_built("written::directive_expansion::written");
}

VILLANELLE_API ::villanelle::directive_origin directive_expansion::origin() const {
    ::villanelle::detail::not_built("written::directive_expansion::origin");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> directive_expansion::values() const {
    ::villanelle::detail::not_built("written::directive_expansion::values");
}

VILLANELLE_API std::optional<::villanelle::written::expansion_block> directive_expansion::block() const {
    ::villanelle::detail::not_built("written::directive_expansion::block");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> directive_expansion::unreadable()
    const {
    ::villanelle::detail::not_built("written::directive_expansion::unreadable");
}

VILLANELLE_API bool operator==(const ::villanelle::written::directive_expansion&,
                               const ::villanelle::written::directive_expansion&) {
    ::villanelle::detail::not_built("operator== of directive_expansion");
}

VILLANELLE_API ::villanelle::written::statement unreadable_expansion::written() const {
    ::villanelle::detail::not_built("written::unreadable_expansion::written");
}

VILLANELLE_API ::villanelle::unreadable_reason unreadable_expansion::reason() const {
    ::villanelle::detail::not_built("written::unreadable_expansion::reason");
}

VILLANELLE_API ::villanelle::directive_origin unreadable_expansion::origin() const {
    ::villanelle::detail::not_built("written::unreadable_expansion::origin");
}

VILLANELLE_API bool operator==(const ::villanelle::written::unreadable_expansion&,
                               const ::villanelle::written::unreadable_expansion&) {
    ::villanelle::detail::not_built("operator== of unreadable_expansion");
}

VILLANELLE_API ::villanelle::value_kind expanded_value::kind() const noexcept {
    ::villanelle::detail::not_built("written::expanded_value::kind");
}

VILLANELLE_API std::string expanded_value::text() const {
    ::villanelle::detail::not_built("written::expanded_value::text");
}

VILLANELLE_API ::villanelle::origin expanded_value::origin() const {
    ::villanelle::detail::not_built("written::expanded_value::origin");
}

VILLANELLE_API ::villanelle::written::written_value expanded_value::written() const {
    ::villanelle::detail::not_built("written::expanded_value::written");
}

VILLANELLE_API std::optional<::villanelle::written::written_value> expanded_value::definition() const {
    ::villanelle::detail::not_built("written::expanded_value::definition");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::reference_resolution> expanded_value::chain() const {
    ::villanelle::detail::not_built("written::expanded_value::chain");
}

VILLANELLE_API std::string expanded_value::word() const {
    ::villanelle::detail::not_built("written::expanded_value::word");
}

VILLANELLE_API std::string expanded_value::string() const {
    ::villanelle::detail::not_built("written::expanded_value::string");
}

VILLANELLE_API double expanded_value::number() const {
    ::villanelle::detail::not_built("written::expanded_value::number");
}

VILLANELLE_API std::int64_t expanded_value::integer() const {
    ::villanelle::detail::not_built("written::expanded_value::integer");
}

VILLANELLE_API bool expanded_value::boolean() const {
    ::villanelle::detail::not_built("written::expanded_value::boolean");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> expanded_value::list() const {
    ::villanelle::detail::not_built("written::expanded_value::list");
}

VILLANELLE_API std::variant<::villanelle::written::slice_value, ::villanelle::written::index_value>
expanded_value::slice() const {
    ::villanelle::detail::not_built("written::expanded_value::slice");
}

VILLANELLE_API ::villanelle::diagnostic_error expanded_value::error(std::string_view,
                                                                    ::villanelle::program_code) const {
    ::villanelle::detail::not_built("written::expanded_value::error");
}

VILLANELLE_API bool operator==(const ::villanelle::written::expanded_value&,
                               const ::villanelle::written::expanded_value&) {
    ::villanelle::detail::not_built("operator== of expanded_value");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> expanded_list::items() const {
    ::villanelle::detail::not_built("written::expanded_list::items");
}

VILLANELLE_API std::string expanded_slice::name() const {
    ::villanelle::detail::not_built("written::expanded_slice::name");
}

VILLANELLE_API std::optional<std::int64_t> expanded_slice::start() const {
    ::villanelle::detail::not_built("written::expanded_slice::start");
}

VILLANELLE_API std::optional<std::int64_t> expanded_slice::end() const {
    ::villanelle::detail::not_built("written::expanded_slice::end");
}

VILLANELLE_API std::string expanded_index::name() const {
    ::villanelle::detail::not_built("written::expanded_index::name");
}

VILLANELLE_API std::int64_t expanded_index::index() const {
    ::villanelle::detail::not_built("written::expanded_index::index");
}

}  // namespace written

namespace detail {

VILLANELLE_API ::villanelle::sequence<::villanelle::written::directive_expansion>
block_traits<::villanelle::written::directive_expansion>::items(const view&) {
    not_built("block_traits<written::directive_expansion>::items");
}
VILLANELLE_API std::optional<block_traits<::villanelle::written::directive_expansion>::directive>
block_traits<::villanelle::written::directive_expansion>::as_directive(
    const ::villanelle::written::directive_expansion&, std::optional<std::string_view>) {
    not_built("block_traits<written::directive_expansion>::as_directive");
}
VILLANELLE_API std::optional<view> block_traits<::villanelle::written::directive_expansion>::block_of(
    const ::villanelle::written::directive_expansion&) {
    not_built("block_traits<written::directive_expansion>::block_of");
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_EXPANSION_HPP
