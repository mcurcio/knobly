// Sample "addresses" (examples/samples.json): every rendered directive's address, by position and by a key rule of
// the program's own. ctest examples_addresses compares what it prints with examples/expected/addresses.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <optional>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vr::rendered tree = vr::render(config.load("main.conf"));
    const auto print_targets = [&tree](const vl::ordered_map<vr::directive, vr::address>& addresses) {
        for (const vr::directive& d : tree.block().walk()) {
            if (d.name() == "target") {
                std::cout << "  " << vr::to_string(addresses.at(d)) << " = " << d.values().at(0).text() << '\n';
            }
        }
    };
    std::cout << "by position:\n";
    print_targets(tree.addresses());
    // --8<-- [start:key]
    const vr::key_rule node_id = [](const vr::directive& d) -> std::optional<std::string> {
        if (d.name() == "node" && d.values().size() > 1) return d.values().at(1).text();
        return std::nullopt;  // every other directive: by position
    };
    std::cout << "by node id:\n";
    print_targets(tree.addresses({.key = node_id}));
    // --8<-- [end:key]
}
// --8<-- [end:main]
