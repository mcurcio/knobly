// The shared layer's member templates (errata A3): <villanelle/villanelle.hpp> includes this file in both modes, after
// errors.hpp, because a template cannot be compiled once. diagnostics::report and diagnostics::collect.
// STUBS (frozen-m2.md): each body is not_built until slice W defines it.
#ifndef VILLANELLE_DETAIL_SHARED_TEMPLATES_HPP
#define VILLANELLE_DETAIL_SHARED_TEMPLATES_HPP

#include <concepts>
#include <optional>
#include <string_view>
#include <type_traits>

#include <villanelle/detail/not_built.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN

template <::villanelle::locatable At>
void diagnostics::report(const At&, std::string_view, ::villanelle::program_code) const {
    ::villanelle::detail::not_built("diagnostics::report");
}

/// std::optional of read's result, or bool for a void read (design.md 3.1).
template <class F>
    requires std::invocable<F&>
auto diagnostics::collect(F&&) const {
    using result = std::invoke_result_t<F&>;
    ::villanelle::detail::not_built("diagnostics::collect");
    if constexpr (std::is_void_v<result>) {
        return false;
    } else {
        return std::optional<result>{};
    }
}

VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_TEMPLATES_HPP
