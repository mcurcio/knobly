// The shared layer's member templates (errata A3): <knobly/knobly.hpp> includes this file in both modes, after
// errors.hpp, because a template cannot be compiled once: diagnostics::report and diagnostics::collect.
#ifndef KNOBLY_DETAIL_SHARED_TEMPLATES_HPP
#define KNOBLY_DETAIL_SHARED_TEMPLATES_HPP

#include <concepts>
#include <functional>
#include <optional>
#include <string_view>
#include <type_traits>

#include <knobly/knobly.hpp>

KNOBLY_NAMESPACE_BEGIN

template <::knobly::locatable At>
void diagnostics::report(const At& at, std::string_view message, ::knobly::program_code code) const {
    add(at.error(message, code).diagnostic());
}

/// std::optional of read's result, or bool for a void read (design.md 3.1): absent (false) when read raised a
/// diagnostic error, whose diagnostic is recorded. Its try is compiled only with exceptions on; without, a failing
/// read has already ended the program (design.md 2.2).
template <class F>
    requires std::invocable<F&>
auto diagnostics::collect(F&& read) const {
    using result = std::invoke_result_t<F&>;
#if KNOBLY_EXCEPTIONS
    try {
        if constexpr (std::is_void_v<result>) {
            std::invoke(read);
            return true;
        } else {
            return std::optional<result>(std::invoke(read));
        }
    } catch (const ::knobly::diagnostic_error& error) {
        add(error.diagnostic());
        if constexpr (std::is_void_v<result>) {
            return false;
        } else {
            return std::optional<result>();
        }
    }
#else
    if constexpr (std::is_void_v<result>) {
        std::invoke(read);
        return true;
    } else {
        return std::optional<result>(std::invoke(read));
    }
#endif
}

KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_TEMPLATES_HPP
