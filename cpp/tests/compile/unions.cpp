// The generated as<V>() and visit(f) of every union, instantiated for each variant (frozen-m2.md 3.2): compiled, never
// run. A variant missing from a body, or a visit whose branches disagree, fails to compile here.
#include <optional>

#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

namespace vw = knobly::written;
namespace vr = knobly::rendered;

namespace {

template <class Root, class... Variants>
int use(const Root& root) {
    int found = static_cast<int>(root.template as<Root>().has_value());
    ((found += static_cast<int>(root.template as<Variants>().has_value())), ...);
    return found + root.visit([](const auto& variant) { return static_cast<int>(sizeof(variant)); });
}

}  // namespace

int unions_compile(const vw::statement& s, const vw::written_value& v, const vw::variable& var,
                   const vw::expanded_value& e, const vr::change& c) {
    return use<vw::statement, vw::written_directive, vw::extension_line, vw::set_line, vw::snippet_line, vw::use_line,
               vw::unreadable_line>(s) +
           use<vw::written_value, vw::word, vw::string, vw::list, vw::slice, vw::index, vw::reference>(v) +
           use<vw::variable, vw::set_variable, vw::parameter, vw::override_variable>(var) +
           use<vw::expanded_value, vw::expanded_word, vw::expanded_string, vw::expanded_list, vw::expanded_slice,
               vw::expanded_index>(e) +
           use<vr::change, vr::added, vr::removed, vr::changed, vr::unknown>(c);
}
