// The written layer's member templates (errata A3): <knobly/written.hpp> includes this file in both modes, because
// a class template's members cannot be compiled once: resolution<Definition>'s members, thin over the non-template
// KNOBLY_API helpers declared here (defined with the layer in variables.hpp, so the work is compiled once), and
// the block_traits specializations support/block.hpp reads (frozen-m2.md 3.1; their static members are defined with
// the layer: document.hpp and expansion.hpp).
#ifndef KNOBLY_DETAIL_WRITTEN_TEMPLATES_HPP
#define KNOBLY_DETAIL_WRITTEN_TEMPLATES_HPP

#include <optional>
#include <string_view>
#include <vector>

#include <knobly/written.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace written {

namespace detail {
/// A resolution's copy, winner (a variable's or a snippet line's node) and shadowed definitions, in order.
KNOBLY_API ::knobly::written::copy resolution_copy(const ::knobly::detail::view& v);
KNOBLY_API std::optional<::knobly::detail::view> resolution_winner(const ::knobly::detail::view& v);
KNOBLY_API std::vector<::knobly::detail::view> resolution_shadowed(const ::knobly::detail::view& v);
}  // namespace detail

template <class Definition>
::knobly::written::copy resolution<Definition>::copy() const {
    return detail::resolution_copy(view_);
}

template <class Definition>
std::optional<Definition> resolution<Definition>::winner() const {
    std::optional<::knobly::detail::view> found = detail::resolution_winner(view_);
    if (!found) {
        return std::nullopt;
    }
    return ::knobly::detail::access::make<Definition>(std::move(*found));
}

template <class Definition>
::knobly::sequence<Definition> resolution<Definition>::shadowed() const {
    std::vector<Definition> out;
    for (::knobly::detail::view& each : detail::resolution_shadowed(view_)) {
        out.push_back(::knobly::detail::access::make<Definition>(std::move(each)));
    }
    return out;
}

}  // namespace written

namespace detail {

/// The written block's items are its statements (live: each call re-reads the document's current parse).
template <>
struct block_traits<::knobly::written::statement> {
    using directive = ::knobly::written::written_directive;
    KNOBLY_API static ::knobly::sequence<::knobly::written::statement> items(const view& block);
    KNOBLY_API static std::size_t size(const view& block);
    KNOBLY_API static ::knobly::written::statement at(const view& block, std::size_t index);
    KNOBLY_API static std::optional<directive> as_directive(const ::knobly::written::statement& item,
                                                            std::optional<std::string_view> name);
    KNOBLY_API static std::optional<view> block_of(const ::knobly::written::statement& item);
};

/// The expansion block's items are directive expansions (a snapshot of one working-out).
template <>
struct block_traits<::knobly::written::directive_expansion> {
    using directive = ::knobly::written::directive_expansion;
    KNOBLY_API static ::knobly::sequence<::knobly::written::directive_expansion> items(const view& block);
    KNOBLY_API static std::size_t size(const view& block);
    KNOBLY_API static ::knobly::written::directive_expansion at(const view& block, std::size_t index);
    KNOBLY_API static std::optional<directive> as_directive(const ::knobly::written::directive_expansion& item,
                                                            std::optional<std::string_view> name);
    KNOBLY_API static std::optional<view> block_of(const ::knobly::written::directive_expansion& item);
};

}  // namespace detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_WRITTEN_TEMPLATES_HPP
