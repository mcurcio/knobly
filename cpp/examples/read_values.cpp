// Sample "read_values" (examples/samples.json): one typed reader per kind of value. ctest examples_read_values
// compares what it prints with examples/expected/read_values.txt.
// --8<-- [start:main]
#include <knobly/files.hpp>
#include <knobly/rendered.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <variant>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

int main() {
    const vw::processor config({.source = vl::files::file_source()});
    const vr::rendered tree = vr::render(config.load("values.conf"));
    const auto first_value = [&tree](std::string_view name) {
        return tree.block().directives(name).at(0).values().at(0);
    };

    std::cout << "name " << first_value("name").word() << '\n';
    std::cout << "host " << first_value("host").string() << '\n';
    std::cout << "path " << first_value("path").string() << '\n';  // a raw string: no escapes
    std::cout << "fps " << first_value("fps").number() << '\n';
    std::cout << "count " << first_value("count").integer() << '\n';
    std::cout << "enabled " << std::boolalpha << first_value("enabled").boolean() << '\n';
    std::cout << "gains";
    for (const vw::expanded_value& gain : first_value("gains").list()) {
        std::cout << ' ' << gain.number();
    }
    std::cout << '\n';
    for (const char* name : {"pixels", "first"}) {
        const std::variant<vw::slice_value, vw::index_value> read = first_value(name).slice();
        if (const auto* slice = std::get_if<vw::slice_value>(&read)) {
            std::cout << name << " slice " << slice->name() << ' ' << slice->start().value() << '~'
                      << slice->end().value() << '\n';
        } else if (const auto* index = std::get_if<vw::index_value>(&read)) {
            std::cout << name << " index " << index->name() << ' ' << index->index() << '\n';
        }
    }
}
// --8<-- [end:main]
