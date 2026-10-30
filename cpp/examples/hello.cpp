// Sample "hello" (examples/samples.json): load one file, render it, read one string. The user guide includes the
// region between the --8<-- markers; cpp/examples/CMakeLists.txt builds this file and ctest runs it (examples_hello),
// comparing what it prints with examples/expected/hello.txt.
// --8<-- [start:main]
#include <villanelle/files.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <iostream>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    const vw::processor config({.source = vl::files::file_source()});
    const vr::rendered tree = vr::render(config.load("hello.conf"));
    const vw::expanded_value greeting = tree.block().directives("greeting").at(0).values().at(0);
    std::cout << greeting.string() << '\n';
}
// --8<-- [end:main]
