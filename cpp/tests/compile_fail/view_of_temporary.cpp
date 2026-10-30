// What C++ refuses at compile time (frozen-m3.md 4; design.md 2.6): view() of a temporary config_text is deleted
// (the const&& overload), so a view that would dangle at the end of the statement does not compile. Building this
// file must fail; with KNOBLY_CONTROL it must build.
#include <knobly/knobly.hpp>

#include <cstddef>

namespace vl = knobly;

std::size_t refused() {
#ifndef KNOBLY_CONTROL
    return vl::text("x").view().size();
#else
    const vl::config_text kept = vl::text("x");
    return kept.view().size();
#endif
}
