// The shared definitions' entry point: <villanelle/villanelle.hpp> includes it at its end in header-only mode, and
// <villanelle/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// VILLANELLE_API (or is a template).
#ifndef VILLANELLE_DETAIL_SHARED_DEFINITIONS_HPP
#define VILLANELLE_DETAIL_SHARED_DEFINITIONS_HPP

#include <cstddef>
#include <string>

#include <villanelle/detail/raise.hpp>
#include <villanelle/detail/shared/people.hpp>
#include <villanelle/villanelle.hpp>

VILLANELLE_NAMESPACE_BEGIN
namespace detail {

[[noreturn]] VILLANELLE_API void raise_index_out_of_range(std::size_t index, std::size_t size) {
    raise(::villanelle::index_out_of_range("index " + std::to_string(index) + " is outside a sequence of " +
                                           std::to_string(size)));
}

}  // namespace detail
VILLANELLE_NAMESPACE_END

#endif  // VILLANELLE_DETAIL_SHARED_DEFINITIONS_HPP
