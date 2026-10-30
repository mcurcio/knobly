// Sample "include_read" (examples/samples.json): an include line added by an edit is not read until read() is
// called. ctest examples_include_read compares what it prints with examples/expected/include_read.txt.
// --8<-- [start:main]
#include <villanelle/extensions.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <iostream>
#include <memory>
#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    const auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    files->insert_or_assign("main.conf", "name main;\n");
    files->insert_or_assign("extra.conf", "name extra;\n");
    const vw::processor config({.source = vl::memory_source(files), .extensions = {vl::extensions::include()}});
    const vw::document_graph graph = config.load("main.conf");
    graph.root().block().add_statements(vl::text(R"(@include "extra.conf";)"));

    const auto print_unread = [&graph] {
        const vr::rendered tree = vr::render(graph);
        std::string names;
        for (const vr::directive& name : tree.block().directives("name")) {
            names += (names.empty() ? "" : ", ") + name.values().at(0).text();
        }
        std::cout << "unread " << graph.unread().size() << ": " << names << '\n';
        return tree;
    };
    for (const vl::located_diagnostic& d : print_unread().diagnostics()) {
        std::cout << vl::to_string(d) << '\n';
    }
    graph.read();
    print_unread();
}
// --8<-- [end:main]
