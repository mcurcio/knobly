// Sample "diagnostics" (examples/samples.json): print every problem of a config with its source line, a caret under
// it and the steps that led there. ctest examples_diagnostics compares what it prints with
// examples/expected/diagnostics.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vw::document_graph graph = config.load("main.conf");
    const vr::rendered tree = vr::render(graph);
    // --8<-- [start:print]
    for (const vl::located_diagnostic& d : tree.diagnostics()) {
        std::cout << vw::format_diagnostic(d, graph) << '\n';
    }
    // --8<-- [end:print]
}
// --8<-- [end:main]
