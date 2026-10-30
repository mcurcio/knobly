// Design program 4.1 (.claude/design/cpp/design.md section 4.1), verbatim: an app loads a rasl config with includes
// and name=value overrides, renders it, reads every DdpSink node and reports every value problem at once. Built with
// -Wsign-conversion (and -Wdangling on Clang); the programs_sinks test runs it in a fresh copy of tests/programs/sinks/
// and compares its output and exit status with tests/programs/sinks_expected/. Kept as the design writes it, so
// clang-format leaves it alone.
// clang-format off
#include <knobly/knobly.hpp>
#include <knobly/files.hpp>
#include <knobly/extensions.hpp>
#include <knobly/written.hpp>
#include <knobly/rendered.hpp>

#include <cstdint>
#include <cstdlib>
#include <format>
#include <iostream>
#include <span>
#include <string>
#include <vector>

namespace vl = knobly;
namespace vw = knobly::written;
namespace vr = knobly::rendered;

struct sink {
    std::string name;
    std::string host;
    double fps = 0;
    std::int64_t max_count = 0;
};

int main(int argc, char** argv) {
    vw::load_options options;
    for (std::string_view arg : std::span(argv + 1, static_cast<std::size_t>(argc - 1))) {
        auto eq = arg.find('=');
        std::string name(arg.substr(0, eq));
        if (eq == std::string_view::npos || !vw::is_variable_name(name)) {    // a user's typo, not a program bug
            std::cerr << "usage: sinks name=value...\n";
            return 2;
        }
        options.overrides.insert_or_assign(name, vl::text(arg.substr(eq + 1)));
    }

    vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    vw::document_graph graph = [&] {
        try {
            return config.load("main.conf", options);
        } catch (const vl::read_error& e) {        // the root file could not be read: no graph at all
            std::cerr << e.what() << '\n';
            std::exit(2);
        }
    }();

    vr::rendered tree = vr::render(graph);
    vl::diagnostics problems(tree.diagnostics());  // the language's problems first: the graph's one list
    std::vector<sink> sinks;

    // Descend only into "graph" blocks; read every DdpSink node.
    auto descend = [](const vr::directive& d) { return d.name() == "graph"; };
    for (vr::directive node : tree.block().walk(descend)) {
        auto values = node.values();               // one shared list: name it once
        if (node.name() != "node" || values.empty() || values.at(0).text() != "DdpSink") continue;
        if (values.size() < 2) {
            problems.report(node, "a DdpSink node needs an id", "rasl/node-arity");
            continue;
        }
        sink s;
        s.name = problems.collect([&] { return values.at(1).word(); }).value_or("?");
        if (auto body = node.block()) {
            for (vr::directive field : body->directives()) {
                if (field.values().empty()) {
                    problems.report(field, "missing value", "rasl/missing-value");
                    continue;
                }
                vw::expanded_value v = field.values().front();       // by value: nothing to dangle
                if (field.name() == "target") {
                    s.host = problems.collect([&] { return v.string(); }).value_or("");
                } else if (field.name() == "fps") {
                    s.fps = problems.collect([&] { return v.number(); }).value_or(0);   // "20hz": E4004, located
                } else if (field.name() == "max_count") {
                    s.max_count = problems.collect([&] { return v.integer(); }).value_or(0);
                }
            }
        }
        sinks.push_back(std::move(s));
    }

    for (const vl::located_diagnostic& d : problems) {
        std::cerr << vw::format_diagnostic(d, graph) << '\n';   // place, source line, carets, each via step
    }
    for (const sink& s : sinks) {
        std::cout << std::format("{} -> {} ({} leds at {} fps)\n", s.name, s.host, s.max_count, s.fps);
    }
    return problems.empty() ? 0 : 1;
}
// clang-format on
