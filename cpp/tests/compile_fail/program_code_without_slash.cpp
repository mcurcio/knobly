// What C++ refuses at compile time (frozen-m3.md 4; design.md 2.6): a literal program code is checked by a consteval
// constructor, so a code without '/' does not compile, where the other bindings raise the misuse error at run time.
// Building this file must fail; with KNOBLY_CONTROL it must build.
#include <knobly/knobly.hpp>
#include <knobly/rendered.hpp>

namespace vl = knobly;
namespace vr = knobly::rendered;

void refused(const vl::diagnostics& problems, const vr::directive& d) {
#ifndef KNOBLY_CONTROL
    problems.report(d, "m", "nodash");
#else
    problems.report(d, "m", "lint/dash");
#endif
}
