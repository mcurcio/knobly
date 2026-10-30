// Sample "diff_reload" (examples/samples.json): reload a config after it changed on disk and list what changed.
// ctest examples_diff_reload compares what it prints with examples/expected/diff_reload.txt.
// --8<-- [start:main]
#include <knobly/extensions.hpp>
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

void edit_on_disk() {  // someone else edits the file
    std::ostringstream read;
    read << std::ifstream("main.conf").rdbuf();
    std::string text = read.str();
    text.replace(text.find("@set $pixels 2284;"), 18, "@set $pixels 2400;");
    const std::size_t start = text.find("    node Waveform hue_ramp {");
    text.erase(start, text.find("    }\n\n", start) + 7 - start);
    std::ofstream("main.conf") << text;
}

int main() {
    const vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const vr::rendered before = vr::render(config.load("main.conf"));
    edit_on_disk();
    const vr::rendered after = vr::render(config.load("main.conf"));
    // --8<-- [start:diff]
    const vr::key_rule node_id = [](const vr::directive& d) -> std::optional<std::string> {
        if (d.name() == "node" && d.values().size() > 1) return d.values().at(1).text();
        return std::nullopt;
    };
    for (const vr::change& change : before.diff(after, {.key = node_id})) {
        std::cout << vl::to_string(change.kind()) << ' ' << vr::to_string(change.address()) << '\n';
    }
    // --8<-- [end:diff]
}
// --8<-- [end:main]
