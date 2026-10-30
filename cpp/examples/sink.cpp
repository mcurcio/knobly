// Sample "sink" (examples/samples.json): gather the language's problems and the program's own checks in one list.
// ctest examples_sink compares what it prints with examples/expected/sink.txt.
// --8<-- [start:main]
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <cstdint>
#include <iostream>
#include <memory>
#include <optional>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    files->insert_or_assign("main.conf", "port eighty;\nnode Mystery m;\nfps $x;\n");
    const vw::processor config({.source = vl::memory_source(files)});
    const vr::rendered tree = vr::render(config.load("main.conf"));
    const vl::diagnostics problems(tree.diagnostics());
    // --8<-- [start:collect]
    const std::optional<std::int64_t> port =
        problems.collect([&tree] { return tree.block().directives("port").at(0).values().at(0).integer(); });
    if (!port) {
        std::cout << "port unset\n";
    }
    // --8<-- [end:collect]
    // --8<-- [start:report]
    for (const vr::directive& node : tree.block().directives("node")) {
        problems.report(node, "unknown node type " + node.values().at(0).text(), "app/unknown-node");
    }
    // --8<-- [end:report]
    for (const vl::located_diagnostic& d : problems) {
        std::cout << vl::to_string(d) << '\n';
    }
}
// --8<-- [end:main]
