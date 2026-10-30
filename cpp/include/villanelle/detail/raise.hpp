// The one throw site (design.md 2.2, D30; frozen-m1.md section 5): with exceptions it throws `error`; without, it
// writes the error's what() to standard error and calls std::abort(), as the standard library does under
// -fno-exceptions. Every villanelle throw goes through it; no other file writes `throw`.
#ifndef VILLANELLE_DETAIL_RAISE_HPP
#define VILLANELLE_DETAIL_RAISE_HPP

#include <cstddef>
#include <cstdio>
#include <cstdlib>

#include <villanelle/support/config.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

template <class Error>
[[noreturn]] void raise(const Error& error) {
#if VILLANELLE_EXCEPTIONS
    throw error;
#else
    std::fputs(error.what(), stderr);
    std::fputc('\n', stderr);
    std::abort();
#endif
}

/// Raises index_out_of_range for an index at or past size. Declared here for the support templates, which cannot
/// name the error class (errors.hpp includes them); defined with the shared layer (detail/shared/definitions.hpp).
[[noreturn]] VILLANELLE_API void raise_index_out_of_range(std::size_t index, std::size_t size);

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_RAISE_HPP
