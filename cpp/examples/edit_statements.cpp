// Sample "edit_statements" (examples/samples.json): edit a config in memory (set values, insert a line, rename a
// directive), see a bad edit refused, and save. ctest examples_edit_statements compares what it prints with
// examples/expected/edit_statements.txt.
// --8<-- [start:main]
#include <villanelle/written.hpp>

#include <iostream>
#include <memory>
#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;

int main() {
    const auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    files->insert_or_assign("main.conf", "server {\n    host a;\n    # the port\n    port 80;\n}\n");
    const vw::processor config({.source = vl::memory_source(files)});
    const vw::document_graph graph = config.load("main.conf");
    const vw::document main_conf = graph.root();
    // --8<-- [start:edit]
    const vw::written_directive server = main_conf.block().directives("server").at(0);
    const vw::written_block body = server.block().value();
    const vw::written_directive host = body.directives("host").at(0);
    host.set(vl::quote("10.0.60.31"));
    body.directives("port").at(0).values().at(0).set(vl::text("8080"));
    body.insert_statements(1, vl::text("timeout 30s;"));
    server.rename("listener");
    // --8<-- [end:edit]
    // --8<-- [start:refused]
    try {
        host.set(vl::text("1; x"));  // two statements where one value goes: nothing changes
    } catch (const vl::bad_text_error& e) {
        for (const vl::diagnostic& d : e.diagnostics()) {
            const vl::source_position at = d.span().start();
            std::cout << "refused: " << vl::to_string(d.code()) << " (line " << at.line() + 1 << ", column "
                      << at.column() + 1 << ")\n";
        }
    }
    // --8<-- [end:refused]
    std::cout << main_conf.text();
    std::cout << "unsaved " << std::boolalpha << (main_conf.text() != main_conf.saved_text()) << '\n';
    for (const std::string& path : graph.save(vl::memory_writer(files))) {
        std::cout << "saved " << path << '\n';
    }
    std::cout << "unsaved " << (main_conf.text() != main_conf.saved_text()) << '\n';
}
// --8<-- [end:main]
