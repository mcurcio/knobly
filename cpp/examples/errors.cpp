// Sample "errors" (examples/samples.json): the two errors a program expects, a file that cannot be read and a value
// of the wrong kind. ctest examples_errors compares what it prints with examples/expected/errors.txt.
// --8<-- [start:main]
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <string>
#include <variant>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const vw::processor config({.source = vl::files::file_source()});
    // --8<-- [start:read_error]
    try {
        config.load("missing.conf");
    } catch (const vl::read_error& e) {
        std::string paths;
        for (const std::string& path : e.paths()) {
            paths += (paths.empty() ? "" : ", ") + path;
        }
        std::cout << "cannot read: " << paths << '\n';
    }
    // --8<-- [end:read_error]
    // --8<-- [start:diagnostic_error]
    const vr::rendered tree = vr::render(config.load("main.conf"));
    try {
        const double fps = tree.block().directives("fps").at(0).values().at(0).number();
        std::cout << "fps " << fps << '\n';
    } catch (const vl::diagnostic_error& e) {
        const vl::located_diagnostic d = e.diagnostic();
        std::cout << "bad value: " << vl::to_string(std::get<vl::diagnostic_code>(d.code())) << " at "
                  << vl::to_string(d.place()) << '\n';
    }
    // --8<-- [end:diagnostic_error]
}
// --8<-- [end:main]
