// Sample "edit_save" (examples/samples.json): change a variable's value in the written layer, save it to disk and
// render the result. ctest examples_edit_save compares what it prints with examples/expected/edit_save.txt.
// --8<-- [start:main]
#include <villanelle/extensions.hpp>
#include <villanelle/files.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <fstream>
#include <iostream>
#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vw::document_graph graph = config.load("main.conf");
    // --8<-- [start:edit]
    for (const vw::variable& pixels : graph.variables("pixels")) {
        if (const auto set = pixels.as<vw::set_variable>()) {
            set->set(vl::text("2400"));
        }
    }
    // --8<-- [end:edit]
    // --8<-- [start:save]
    for (const std::string& path : graph.save(vl::files::file_writer())) {
        std::cout << "saved " << path << '\n';
    }
    // --8<-- [end:save]
    std::ifstream on_disk("main.conf");
    for (std::string line; std::getline(on_disk, line);) {
        if (line.find("$pixels") != std::string::npos) {
            std::cout << line << '\n';
        }
    }
    const vr::rendered tree = vr::render(graph);
    for (const vr::directive& d : tree.block().walk()) {
        if (d.name() == "max_count") {
            const vr::directive node = d.parent().value();
            std::cout << node.values().at(1).text() << " max_count " << d.values().at(0).integer() << '\n';
        }
    }
}
// --8<-- [end:main]
