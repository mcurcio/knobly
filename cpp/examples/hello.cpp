// Sample "hello" (examples/samples.json): load one file, render it, read one string. The user guide includes the
// region between the --8<-- markers; cpp/examples/CMakeLists.txt builds this file and ctest runs it (examples_hello),
// comparing what it prints with examples/expected/hello.txt.
// --8<-- [start:main]
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const vw::processor config({.source = vl::files::file_source()});
    const vr::rendered tree = vr::render(config.load("hello.conf"));
    const vw::expanded_value greeting = tree.block().directives("greeting").at(0).values().at(0);
    std::cout << greeting.string() << '\n';
}
// --8<-- [end:main]
