// The written layer's member templates (errata A3): <villanelle/written.hpp> includes this file in both modes, because
// a class template's members cannot be compiled once: resolution<Definition>'s members (slice W defines them over
// non-template VILLANELLE_API helpers, so the work itself is still compiled once), and the block_traits
// specializations support/block.hpp reads (frozen-m2.md 3.1; their static members are defined with the layer).
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_WRITTEN_TEMPLATES_HPP
#define VILLANELLE_DETAIL_WRITTEN_TEMPLATES_HPP

#include <optional>
#include <string_view>

#include <villanelle/detail/not_built.hpp>
#include <villanelle/written.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace written {

template <class Definition>
::villanelle::written::copy resolution<Definition>::copy() const {
    ::villanelle::detail::not_built("written::resolution::copy");
}

template <class Definition>
std::optional<Definition> resolution<Definition>::winner() const {
    ::villanelle::detail::not_built("written::resolution::winner");
}

template <class Definition>
::villanelle::sequence<Definition> resolution<Definition>::shadowed() const {
    ::villanelle::detail::not_built("written::resolution::shadowed");
}

}  // namespace written

namespace detail {

/// The written block's items are its statements (live: each call re-reads the document's current text).
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
