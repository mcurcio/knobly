// What C++ refuses at compile time (frozen-m3.md 4; errata R3): a key rule returns text or absent
// (std::optional<std::string>), so a rule returning an int does not compile, where the other bindings raise the
// argument type error from addresses and diff at run time. Building this file must fail; with KNOBLY_CONTROL it
// must build.
#include <knobly/rendered.hpp>

#include <optional>
#include <string>

namespace vr = knobly::rendered;

std::size_t refused(const vr::rendered& tree) {
#ifndef KNOBLY_CONTROL
    return tree.addresses({.key = [](const vr::directive&) { return 1; }}).size();
#else
    return tree.addresses({.key = [](const vr::directive&) { return std::optional<std::string>("1"); }}).size();
#endif
}
