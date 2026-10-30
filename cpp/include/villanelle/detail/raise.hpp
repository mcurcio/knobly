// The one throw site (design.md 2.2, D30; frozen-m1.md section 5): with exceptions it throws `error`; without, it
// writes the error's what() to standard error and calls std::abort(), as the standard library does under
// -fno-exceptions. Every villanelle throw goes through it; no other file writes `throw`.
// SKELETON: declaration only; Slice T defines it.
#ifndef VILLANELLE_DETAIL_RAISE_HPP
#define VILLANELLE_DETAIL_RAISE_HPP

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

template <class Error>
[[noreturn]] void raise(const Error& error);

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RAISE_HPP
