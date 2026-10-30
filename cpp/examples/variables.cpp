// Sample "variables" (examples/samples.json): which files were read and from where, and for every variable where it
// is written and where it wins or is shadowed. ctest examples_variables compares what it prints with
// examples/expected/variables.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;

std::string line_of(const vl::place& place) {
    return place.resolved_path() + ':' + std::to_string(place.span().start().line() + 1);
}

std::string written_at(const vw::variable& v) {
    if (const auto set = v.as<vw::set_variable>()) return line_of(set->place());
    if (const auto parameter = v.as<vw::parameter>()) return line_of(parameter->place());
    return "override";  // an override has no place in a file
}

template <class Items, class Place>
std::string places(const Items& items, Place place_of) {
    std::string out;
    for (const auto& item : items) {
        out += (out.empty() ? "" : ", ") + line_of(place_of(item));
    }
    return '[' + out + ']';
}

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vw::document_graph graph = config.load("main.conf", {.overrides = {{"leds_host", vl::quote("10.0.70.1")}}});
    for (const auto& [path, document] : graph.documents()) {
        const auto copy_line = [](const vw::document_edge& e) { return e.copy().statement().place(); };
        std::cout << "file " << path << " included at " << places(document.included_by(), copy_line) << '\n';
    }
    const auto use_place = [](const vw::reference_resolution& r) { return r.reference().place(); };
    for (const vw::variable& v : graph.variables()) {
        std::cout << '$' << v.name() << ' ' << vl::to_string(v.kind()) << ' ' << written_at(v) << " wins at "
                  << places(v.wins(), use_place) << " shadowed at " << places(v.shadowed_at(), use_place) << '\n';
    }
}
// --8<-- [end:main]
