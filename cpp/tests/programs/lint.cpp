// Design program 4.3 (.claude/design/cpp/design.md section 4.3), verbatim: a third-party lint walks blocks for its own
// upstream schema and reports diagnostics with places; std::format of a place and an unreadable reason comes from
// <villanelle/format.hpp>. Built with -Wsign-conversion (and -Wdangling on Clang); the programs_lint test runs it in a
// fresh copy of tests/programs/lint/ and compares its output and exit status with tests/programs/lint_expected/. Kept
// as the design writes it, so clang-format leaves it alone.
// clang-format off
#include <villanelle/villanelle.hpp>
#include <villanelle/format.hpp>                    // std::format of a place and an unreadable reason
#include <villanelle/files.hpp>
#include <villanelle/written.hpp>
#include <villanelle/rendered.hpp>

#include <format>
#include <iostream>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

template <class... F> struct overloaded : F... { using F::operator()...; };

void check_server(const vr::directive& server, vl::diagnostics& problems) {
    if (!server.closest([](const vr::directive& d) { return d.name() == "upstream"; })) {
        problems.report(server, "server outside an upstream block", "lb/server-outside");
        return;
    }
    auto values = server.values();
    if (values.size() < 2) {
        problems.report(server, "server needs a host and a weight", "lb/server-arity");
        return;
    }
    problems.collect([&] { return values.at(0).string(); });
    values.at(1).visit(overloaded{
        [&](const vw::expanded_word& w) {
            if (auto weight = problems.collect([&] { return w.integer(); }); weight && *weight <= 0) {
                problems.report(w, std::format("weight must be positive, got {}", *weight),
                                "lb-upstreams/weight-must-be-positive");   // any length: consteval, checked
            }
        },
        [&](const vw::expanded_value& other) {
            problems.report(other, std::format("weight must be a bare integer, got {}", other.text()), "lb/weight");
        },
    });
}

int main(int argc, char** argv) {
    vw::processor config({.source = vl::files::file_source()});
    vw::document_graph graph = config.load(argc > 1 ? argv[1] : "lb.conf");
    vr::rendered tree = vr::render(graph);

    vl::diagnostics problems(tree.diagnostics());
    for (vr::directive d : tree.block().walk()) {
        if (d.name() == "upstream" && (!d.block() || d.block()->directives("server").empty())) {
            problems.report(d, "upstream has no server", "lb/empty-upstream");
        } else if (d.name() == "server") {
            check_server(d, problems);
        }
    }
    for (vw::unreadable_expansion u : tree.unreadable()) {
        std::cerr << std::format("{}: skipped ({})\n", u.origin().place(), u.reason());
    }
    for (const vl::located_diagnostic& d : problems) {
        std::cout << vw::format_diagnostic(d, graph) << '\n';
        // lb.conf:7:9: lb/weight: weight must be a bare integer, got [1, 2]
        //     server "10.0.0.2" [1, 2];
        //                       ^^^^^^
    }
    return problems.empty() ? 0 : 1;
}
// clang-format on
