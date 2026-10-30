// What C++ refuses at compile time (frozen-m3.md 4; design.md 2.6): an edit takes config_text, made only by text()
// or quote(), so a plain std::string where config_text is taken does not compile. Building this file must fail; with
// KNOBLY_CONTROL it must build.
#include <knobly/knobly.hpp>
#include <knobly/written.hpp>

#include <string>

namespace vl = knobly;
namespace vw = knobly::written;

void refused(const vw::set_variable& pixels, const std::string& value) {
#ifndef KNOBLY_CONTROL
    pixels.set(value);
#else
    pixels.set(vl::text(value));
#endif
}
