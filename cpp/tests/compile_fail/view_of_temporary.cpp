// What C++ refuses at compile time (frozen-m3.md 4; design.md 2.6): view() of a temporary config_text is deleted
// (the const&& overload), so a view that would dangle at the end of the statement does not compile. Building this
// file must fail; with VILLANELLE_CONTROL it must build.
#include <villanelle/villanelle.hpp>

#include <cstddef>

namespace vl = villanelle;

std::size_t refused() {
#ifndef VILLANELLE_CONTROL
    return vl::text("x").view().size();
#else
    const vl::config_text kept = vl::text("x");
    return kept.view().size();
#endif
}
