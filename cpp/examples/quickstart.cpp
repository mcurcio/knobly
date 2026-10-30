// Sample "quickstart" (examples/samples.json): load a config, read a string, an integer and a boolean, and count the
// problems. ctest examples_quickstart compares what it prints with examples/expected/quickstart.txt.
// --8<-- [start:main]
#include <villanelle/files.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <iostream>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    // --8<-- [start:load]
    const vw::processor config({.source = vl::files::file_source()});
    const vr::rendered tree = vr::render(config.load("app.conf"));
    // --8<-- [end:load]
    // --8<-- [start:read]
    const vr::rendered_block server = tree.block().directives("server").at(0).block().value();
    const auto first_value = [&server](std::string_view name) { return server.directives(name).at(0).values().at(0); };
    std::cout << "host " << first_value("host").string() << '\n';
    std::cout << "port " << first_value("port").integer() << '\n';  // $port is 8080
    std::cout << "debug " << std::boolalpha << first_value("debug").boolean() << '\n';
    std::cout << "problems " << tree.diagnostics().size() << '\n';
    // --8<-- [end:read]
}
// --8<-- [end:main]
