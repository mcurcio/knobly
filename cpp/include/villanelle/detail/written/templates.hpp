// The written layer's member templates (errata A3): <villanelle/written.hpp> includes this file in both modes, because
// a class template's members cannot be compiled once: resolution<Definition>'s members, thin over the non-template
// VILLANELLE_API helpers declared here (defined with the layer in variables.hpp, so the work is compiled once), and
// the block_traits specializations support/block.hpp reads (frozen-m2.md 3.1; their static members are defined with
// the layer: document.hpp and expansion.hpp).
#ifndef VILLANELLE_DETAIL_WRITTEN_TEMPLATES_HPP
#define VILLANELLE_DETAIL_WRITTEN_TEMPLATES_HPP

#include <optional>
#include <string_view>
#include <vector>

#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace written {

namespace detail {
/// A resolution's copy, winner (a variable's or a snippet line's node) and shadowed definitions, in order.
VILLANELLE_API ::villanelle::written::copy resolution_copy(const ::villanelle::detail::view& v);
VILLANELLE_API std::optional<::villanelle::detail::view> resolution_winner(const ::villanelle::detail::view& v);
VILLANELLE_API std::vector<::villanelle::detail::view> resolution_shadowed(const ::villanelle::detail::view& v);
}  // namespace detail

template <class Definition>
::villanelle::written::copy resolution<Definition>::copy() const {
    return detail::resolution_copy(view_);
}

template <class Definition>
std::optional<Definition> resolution<Definition>::winner() const {
    std::optional<::villanelle::detail::view> found = detail::resolution_winner(view_);
    if (!found) {
        return std::nullopt;
    }
    return ::villanelle::detail::access::make<Definition>(std::move(*found));
}

template <class Definition>
::villanelle::sequence<Definition> resolution<Definition>::shadowed() const {
    std::vector<Definition> out;
    for (::villanelle::detail::view& each : detail::resolution_shadowed(view_)) {
        out.push_back(::villanelle::detail::access::make<Definition>(std::move(each)));
    }
    return out;
}

}  // namespace written

namespace detail {

/// The written block's items are its statements (live: each call re-reads the document's current parse).
template <>
struct block_traits<::villanelle::written::statement> {
    using directive = ::villanelle::written::written_directive;
    VILLANELLE_API static ::villanelle::sequence<::villanelle::written::statement> items(const view& block);
    VILLANELLE_API static std::optional<directive> as_directive(const ::villanelle::written::statement& item,
                                                                std::optional<std::string_view> name);
    VILLANELLE_API static std::optional<view> block_of(const ::villanelle::written::statement& item);
};

/// The expansion block's items are directive expansions (a snapshot of one working-out).
template <>
struct block_traits<::villanelle::written::directive_expansion> {
    using directive = ::villanelle::written::directive_expansion;
    VILLANELLE_API static ::villanelle::sequence<::villanelle::written::directive_expansion> items(const view& block);
    VILLANELLE_API static std::optional<directive> as_directive(const ::villanelle::written::directive_expansion& item,
                                                                std::optional<std::string_view> name);
    VILLANELLE_API static std::optional<view> block_of(const ::villanelle::written::directive_expansion& item);
};

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_WRITTEN_TEMPLATES_HPP
