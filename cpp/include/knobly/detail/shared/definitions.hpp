// The shared definitions' entry point: <knobly/knobly.hpp> includes it at its end in header-only mode, and
// <knobly/implementation.hpp> in compiled mode (frozen-m1.md section 5). Every definition here carries
// KNOBLY_API (or is a template).
#ifndef KNOBLY_DETAIL_SHARED_DEFINITIONS_HPP
#define KNOBLY_DETAIL_SHARED_DEFINITIONS_HPP

#include <cstddef>
#include <string>

#include <knobly/detail/raise.hpp>
#include <knobly/detail/shared/diagnostics.hpp>
#include <knobly/detail/shared/people.hpp>
#include <knobly/detail/shared/rules.hpp>
#include <knobly/detail/shared/values.hpp>
#include <knobly/knobly.hpp>
#include <knobly/support/view.hpp>

KNOBLY_NAMESPACE_BEGIN
namespace detail {

[[noreturn]] KNOBLY_API void raise_index_out_of_range(std::size_t index, std::size_t size) {
    raise(::knobly::index_out_of_range("index " + std::to_string(index) + " is outside a sequence of " +
                                       std::to_string(size)));
}

[[noreturn]] KNOBLY_API void raise_missing_key() {
    raise(::knobly::index_out_of_range("ordered_map::at: no such key"));
}

}  // namespace detail
KNOBLY_NAMESPACE_END

#endif  // KNOBLY_DETAIL_SHARED_DEFINITIONS_HPP
