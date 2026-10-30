// Sample "lost_update" (examples/samples.json): a save refused because the file changed on disk after it was read,
// then the same edit made on a fresh load. ctest examples_lost_update compares what it prints with
// examples/expected/lost_update.txt.
// --8<-- [start:main]
#include <villanelle/files.hpp>
#include <villanelle/written.hpp>

#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;

std::string read_file(const std::string& path) {
    std::ostringstream text;
    text << std::ifstream(path).rdbuf();
    return text.str();
}

void set_host(const vw::document_graph& graph) {
    const vw::written_block server = graph.root().block().directives("server").at(0).block().value();
    server.directives("host").at(0).set(vl::quote("0.0.0.0"));
}

int main() {
    const vw::processor config({.source = vl::files::file_source()});
    // --8<-- [start:conflict]
    const vw::document_graph graph = config.load("app.conf");
    std::string text = read_file("app.conf");  // someone else edits the file after it was read
    text.replace(text.find("debug false"), 11, "debug true");
    std::ofstream("app.conf") << text;
    set_host(graph);
    try {
        graph.save(vl::files::file_writer());
    } catch (const vl::lost_update_error& e) {
        for (const std::string& path : e.paths()) {
            std::cout << "changed on disk: " << path << '\n';
        }
    }
    // --8<-- [end:conflict]
    const vw::document_graph fresh = config.load("app.conf");
    set_host(fresh);
    for (const std::string& path : fresh.save(vl::files::file_writer())) {
        std::cout << "saved " << path << '\n';
    }
    std::cout << read_file("app.conf");
}
// --8<-- [end:main]
