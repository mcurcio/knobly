// Sample "load_render" (examples/samples.json): load a config split over two files, list the files read, render it
// and walk the nodes. ctest examples_load_render compares what it prints with examples/expected/load_render.txt.
// --8<-- [start:main]
#include <villanelle/extensions.hpp>
#include <villanelle/files.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <iostream>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    // --8<-- [start:processor]
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vw::document_graph graph = config.load("main.conf");
    for (const auto& [path, document] : graph.documents()) {
        std::cout << "read " << path << '\n';
    }
    // --8<-- [end:processor]
    // --8<-- [start:walk]
    const vr::rendered tree = vr::render(graph);
    const auto into_graph = [](const vr::directive& d) { return d.name() == "graph"; };
    for (const vr::directive& d : tree.block().walk(into_graph)) {
        if (d.name() != "node") continue;
        std::cout << "node";
        for (const vw::expanded_value& value : d.values()) {
            std::cout << ' ' << value.text();
        }
        std::cout << " (" << vl::to_string(d.origin().place()) << ")\n";
    }
    // --8<-- [end:walk]
}
// --8<-- [end:main]
