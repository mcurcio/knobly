// What C++ refuses at compile time (frozen-m3.md 4; design.md 2.6): an edit takes config_text, made only by text()
// or quote(), so a plain std::string where config_text is taken does not compile. Building this file must fail; with
// VILLANELLE_CONTROL it must build.
#include <villanelle/villanelle.hpp>
#include <villanelle/written.hpp>

#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;

void refused(const vw::set_variable& pixels, const std::string& value) {
#ifndef VILLANELLE_CONTROL
    pixels.set(value);
#else
    pixels.set(vl::text(value));
#endif
}
