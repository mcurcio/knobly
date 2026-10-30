// The rendered definitions' entry point: <villanelle/rendered.hpp> includes it at its end in header-only mode,
// and <villanelle/implementation.hpp> in compiled mode. Every definition here carries VILLANELLE_API (or is a
// template). STUBS (frozen-m2.md): each body is not_built until slice R defines it.
#ifndef VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP

#include <villanelle/detail/not_built.hpp>
#include <villanelle/rendered.hpp>

VILLANELLE_NAMESPACE_BEGIN

namespace rendered {

VILLANELLE_API ::villanelle::rendered::rendered_block rendered::block() const {
    ::villanelle::detail::not_built("rendered::rendered::block");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> rendered::unreadable() const {
    ::villanelle::detail::not_built("rendered::rendered::unreadable");
}

VILLANELLE_API ::villanelle::directive_origin rendered::origin() const {
    ::villanelle::detail::not_built("rendered::rendered::origin");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::located_diagnostic> rendered::diagnostics() const {
    ::villanelle::detail::not_built("rendered::rendered::diagnostics");
}

VILLANELLE_API ::villanelle::written::document_graph rendered::graph() const {
    ::villanelle::detail::not_built("rendered::rendered::graph");
}

VILLANELLE_API ::villanelle::diagnostic_error rendered::error(std::string_view, ::villanelle::program_code) const {
    ::villanelle::detail::not_built("rendered::rendered::error");
}

VILLANELLE_API ::villanelle::ordered_map<::villanelle::rendered::directive, ::villanelle::rendered::address>
rendered::addresses() const {
    ::villanelle::detail::not_built("rendered::rendered::addresses");
}

VILLANELLE_API ::villanelle::ordered_map<::villanelle::rendered::directive, ::villanelle::rendered::address>
rendered::addresses(::villanelle::rendered::key_options) const {
    ::villanelle::detail::not_built("rendered::rendered::addresses");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::change> rendered::diff(
    const ::villanelle::rendered::rendered&) const {
    ::villanelle::detail::not_built("rendered::rendered::diff");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::change> rendered::diff(
    const ::villanelle::rendered::rendered&, ::villanelle::rendered::key_options) const {
    ::villanelle::detail::not_built("rendered::rendered::diff");
}

VILLANELLE_API bool operator==(const ::villanelle::rendered::rendered&, const ::villanelle::rendered::rendered&) {
    ::villanelle::detail::not_built("operator== of rendered");
}

VILLANELLE_API std::string directive::name() const { ::villanelle::detail::not_built("rendered::directive::name"); }

VILLANELLE_API ::villanelle::sequence<::villanelle::written::expanded_value> directive::values() const {
    ::villanelle::detail::not_built("rendered::directive::values");
}

VILLANELLE_API std::optional<::villanelle::rendered::rendered_block> directive::block() const {
    ::villanelle::detail::not_built("rendered::directive::block");
}

VILLANELLE_API ::villanelle::sequence<::villanelle::written::unreadable_expansion> directive::unreadable() const {
    ::villanelle::detail::not_built("rendered::directive::unreadable");
}

VILLANELLE_API std::optional<::villanelle::rendered::directive> directive::parent() const {
    ::villanelle::detail::not_built("rendered::directive::parent");
}

VILLANELLE_API ::villanelle::directive_origin directive::origin() const {
    ::villanelle::detail::not_built("rendered::directive::origin");
}

VILLANELLE_API ::villanelle::written::written_directive directive::written() const {
    ::villanelle::detail::not_built("rendered::directive::written");
}

VILLANELLE_API std::optional<::villanelle::rendered::directive> directive::closest(
    std::function<bool(const ::villanelle::rendered::directive&)>) const {
    ::villanelle::detail::not_built("rendered::directive::closest");
}

VILLANELLE_API ::villanelle::diagnostic_error directive::error(std::string_view, ::villanelle::program_code) const {
    ::villanelle::detail::not_built("rendered::directive::error");
}

VILLANELLE_API bool operator==(const ::villanelle::rendered::directive&, const ::villanelle::rendered::directive&) {
    ::villanelle::detail::not_built("operator== of directive");
}

VILLANELLE_API std::string to_string(const ::villanelle::rendered::address&) {
    ::villanelle::detail::not_built("rendered::to_string");
}

VILLANELLE_API ::villanelle::change_kind change::kind() const noexcept {
    ::villanelle::detail::not_built("rendered::change::kind");
}

VILLANELLE_API ::villanelle::rendered::address change::address() const {
    ::villanelle::detail::not_built("rendered::change::address");
}

VILLANELLE_API bool operator==(const ::villanelle::rendered::change&, const ::villanelle::rendered::change&) {
    ::villanelle::detail::not_built("operator== of change");
}

VILLANELLE_API ::villanelle::rendered::directive added::after() const {
    ::villanelle::detail::not_built("rendered::added::after");
}

VILLANELLE_API ::villanelle::rendered::directive removed::before() const {
    ::villanelle::detail::not_built("rendered::removed::before");
}

VILLANELLE_API ::villanelle::rendered::directive changed::before() const {
    ::villanelle::detail::not_built("rendered::changed::before");
}

VILLANELLE_API ::villanelle::rendered::directive changed::after() const {
    ::villanelle::detail::not_built("rendered::changed::after");
}

VILLANELLE_API ::villanelle::rendered::directive unknown::before() const {
    ::villanelle::detail::not_built("rendered::unknown::before");
}

VILLANELLE_API ::villanelle::rendered::rendered render(const ::villanelle::written::document_graph&) {
    ::villanelle::detail::not_built("rendered::render");
}

}  // namespace rendered

namespace detail {

VILLANELLE_API ::villanelle::sequence<::villanelle::rendered::directive>
block_traits<::villanelle::rendered::directive>::items(const view&) {
    not_built("block_traits<rendered::directive>::items");
}
VILLANELLE_API std::optional<block_traits<::villanelle::rendered::directive>::directive>
block_traits<::villanelle::rendered::directive>::as_directive(const ::villanelle::rendered::directive&,
                                                              std::optional<std::string_view>) {
    not_built("block_traits<rendered::directive>::as_directive");
}
VILLANELLE_API std::optional<view> block_traits<::villanelle::rendered::directive>::block_of(
    const ::villanelle::rendered::directive&) {
    not_built("block_traits<rendered::directive>::block_of");
}

}  // namespace detail

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RENDERED_DEFINITIONS_HPP
