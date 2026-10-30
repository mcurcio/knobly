// Design program 4.2 (.claude/design/cpp/design.md section 4.2), verbatim: an editor changes a variable and a
// directive's values, then saves with lost-update protection. Built with -Wsign-conversion (and -Wdangling on Clang);
// the programs_editor test runs it in a fresh copy of tests/programs/editor/ and compares both files after. Kept as
// the design writes it, so clang-format leaves it alone.
// clang-format off
#include <knobly/knobly.hpp>
#include <knobly/files.hpp>
#include <knobly/extensions.hpp>
#include <knobly/written.hpp>

#include <iostream>
#include <string>

namespace vl = knobly;
namespace vw = knobly::written;

struct edits {                                       // kept as data so they can be applied again after a reload
    std::string pixels;
    std::string fps;
};

void apply(const vw::document_graph& graph, const edits& e) {
    for (vw::variable v : graph.variables("pixels")) {
        if (auto set = v.as<vw::set_variable>()) set->set(vl::text(e.pixels));
    }
    // One line in the included file, shared by both include copies. Paths are as written: "sink.conf".
    if (auto sink = graph.documents().find("sink.conf")) {
        for (vw::statement s : sink->block().walk()) {       // editing during a walk is allowed (2.3)
            if (auto d = s.as<vw::written_directive>(); d && d->name() == "fps") {
                d->set(vl::text(e.fps));                     // "fps 20hz;" becomes "fps 30;", comments kept
            }
        }
    }
}

int main() {
    vw::processor config({
        .source = vl::files::file_source(),
        .extensions = {vl::extensions::include()},
    });
    const edits wanted{.pixels = "2400", .fps = "30"};

    vw::document_graph graph = config.load("main.conf");
    apply(graph, wanted);

    for (int attempt = 0; attempt < 2; ++attempt) {
        try {
            for (const std::string& path : graph.save(vl::files::file_writer())) std::cout << "saved " << path << '\n';
            return 0;
        } catch (const vl::lost_update_error& e) {
            for (const std::string& path : e.paths()) std::cerr << path << " changed on disk\n";
            graph = config.load("main.conf");        // nothing was written: their changes, then ours again
            apply(graph, wanted);
        } catch (const vl::save_error& e) {
            std::cerr << e.what() << '\n';
            try {
                std::rethrow_if_nested(e);           // the writer's own failure
            } catch (const std::exception& cause) {
                std::cerr << "  because: " << cause.what() << '\n';
            }
            return 1;
        }
    }
    return 1;
}
// clang-format on
