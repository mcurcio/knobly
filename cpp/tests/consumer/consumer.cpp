// A program as a consumer writes it, built two ways by CI's C++ package job: against an installed villanelle found
// with find_package (CMakeLists.txt here), and against the single header alone (-DVILLANELLE_SINGLE_HEADER, the
// release asset villanelle.hpp on the include path and nothing else). It loads two texts from memory with an include
// and a variable, renders them and prints one line per sink; it exits 0 only when the output is the expected one.
#ifdef VILLANELLE_SINGLE_HEADER
#include <villanelle.hpp>
#else
#include <villanelle/extensions.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/villanelle.hpp>
#include <villanelle/written.hpp>
#endif

#include <iostream>
#include <memory>
#include <string>

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

int main() {
    auto files = std::make_shared<vl::ordered_map<std::string, std::string>>();
    files->insert_or_assign("main.conf", "@set $host \"10.0.0.5\";\n@include \"sink.conf\" { @set $name left; }\n");
    files->insert_or_assign("sink.conf", "node $name { target $host; }\n");

    const vw::processor config({vl::memory_source(files), {vl::extensions::include()}});
    const vw::document_graph graph = config.load("main.conf");
    for (const vl::located_diagnostic& d : graph.diagnostics()) {
        std::cerr << vw::format_diagnostic(d, graph) << '\n';
    }
    std::string out;
    for (const vr::directive& d : vr::render(graph).block().walk()) {
        if (d.name() == "node") {
            out += d.values().at(0).word();
        } else if (d.name() == "target") {
            out += " -> " + d.values().at(0).string() + "\n";
        }
    }
    std::cout << out;
    return graph.diagnostics().empty() && out == "left -> 10.0.0.5\n" ? 0 : 1;
}
