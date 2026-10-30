// Sample "overrides" (examples/samples.json): load the same config twice, the second time with a value of the
// program's own for one variable. ctest examples_overrides compares what it prints with
// examples/expected/overrides.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

void print_targets(const vw::document_graph& graph) {
    std::string names;
    for (const auto& [name, text] : graph.overrides()) {
        names += (names.empty() ? "" : ", ") + name;
    }
    std::cout << "overrides: " << (names.empty() ? "none" : names) << '\n';
    const vr::rendered tree = vr::render(graph);
    const auto into_nodes = [](const vr::directive& d) { return d.name() == "graph" || d.name() == "node"; };
    for (const vr::directive& d : tree.block().walk(into_nodes)) {
        if (d.name() == "target") {
            const vr::directive node = d.parent().value();
            std::cout << "  " << node.values().at(1).text() << " -> " << d.values().at(0).string() << '\n';
        }
    }
}

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    // --8<-- [start:load]
    print_targets(config.load("main.conf"));
    print_targets(config.load("main.conf", {.overrides = {{"leds_host", vl::quote("10.0.70.1")}}}));
    // --8<-- [end:load]
}
// --8<-- [end:main]
