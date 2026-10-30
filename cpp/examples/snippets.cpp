// Sample "snippets" (examples/samples.json): a snippet used by two nodes, and where each rendered directive was
// written and how it got there. ctest examples_snippets compares what it prints with examples/expected/snippets.txt.
// --8<-- [start:main]
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
    files->insert_or_assign("main.conf",
                            "@snippet twinkle $source {\n"
                            "    seed 11337;\n"
                            "    connect $source;\n"
                            "}\n"
                            "\n"
                            "node TwinkleEffect twinkle { @use twinkle rgb_150; }\n"
                            "node TwinkleEffect white_twinkle { @use twinkle white_150; }\n");
    const vw::processor config({.source = vl::memory_source(files)});
    const vr::rendered tree = vr::render(config.load("main.conf"));
    for (const vr::directive& node : tree.block().directives("node")) {
        const vr::rendered_block body = node.block().value();  // named: a loop over a temporary's member dangles
        for (const vr::directive& d : body) {
            std::cout << node.values().at(1).text() << ": " << d.name();
            for (const vw::expanded_value& value : d.values()) {
                std::cout << ' ' << value.text();
            }
            std::string via;
            for (const vl::step& step : d.origin().via()) {
                via += (via.empty() ? "" : "; ") + vl::to_string(step);
            }
            std::cout << " (written at " << vl::to_string(d.origin().place()) << ", via " << via << ")\n";
        }
    }
}
// --8<-- [end:main]
