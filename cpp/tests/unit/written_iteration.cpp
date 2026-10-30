// Edits during iteration (design.md 2.3, finding F8; frozen-m2.md 3.1): a for over a block reads the snapshot taken
// at begin(), and a walk takes each block's snapshot when it enters it, both ways: a statement removed after the
// snapshot is still yielded (kind() works, other members raise detached_error) and not descended; one inserted into a
// block already entered is not visited, one inserted into a block not yet entered is.
#include <knobly/written.hpp>

#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

namespace {

std::string name_of(const vw::statement& s) {
    if (auto d = s.as<vw::written_directive>()) {
        return d->name();
    }
    return "?";
}

}  // namespace

TEST_CASE("a for over a block keeps the snapshot taken at begin()", "[iteration]") {
    const vw::document_graph graph = fixture::load("a 1;\nb 2;\nc 3;\n");
    const vw::written_block block = graph.root().block();
    std::vector<std::string> seen;
    std::vector<vl::statement_kind> kinds;
    std::size_t at = 0;
    for (const vw::statement& s : block) {
        kinds.push_back(s.kind());
        if (at++ == 0) {
            // Remove the next statement and add one at the end: neither changes what this loop visits.
            block.at(1).remove();
            block.add_statements(vl::text("d 4;"));
            seen.push_back(name_of(s));
        } else if (at == 2) {
            CHECK_THROWS_AS(s.text(), vl::detached_error);  // b, removed after the snapshot
            seen.push_back("detached");
        } else {
            seen.push_back(name_of(s));
        }
    }
    CHECK(seen == std::vector<std::string>{"a", "detached", "c"});
    CHECK(kinds.size() == 3);
    CHECK(graph.root().text() == "a 1;\nc 3;\nd 4;\n");
    CHECK(block.size() == 3);  // a fresh snapshot sees the edits
}

TEST_CASE("a statement inserted before the loop's position is not visited, and nothing is visited twice",
          "[iteration]") {
    const vw::document_graph graph = fixture::load("a;\nb;\n");
    const vw::written_block block = graph.root().block();
    int visits = 0;
    for (const vw::statement& s : block) {
        ++visits;
        s.insert_before(vl::text("x;"));
    }
    CHECK(visits == 2);
    CHECK(graph.root().text() == "x;\na;\nx;\nb;\n");
}

TEST_CASE("a walk takes each block's snapshot when it enters it", "[iteration][walk]") {
    const vw::document_graph graph = fixture::load("outer {\n    inner 1;\n}\nlast {\n    deep 1;\n}\n");
    const vw::written_block block = graph.root().block();
    std::vector<std::string> seen;
    for (const vw::statement& s : block.walk()) {
        const std::string name = name_of(s);
        seen.push_back(name);
        if (name == "outer") {
            // The walk has not entered outer's block yet: an item added there is visited.
            s.as<vw::written_directive>()->block()->add_statements(vl::text("added 1;"));
            // The top-level block was entered: a statement added there is not.
            block.add_statements(vl::text("later 1;"));
            // last's block is not entered yet: its removed item is not visited.
            block.at(1).as<vw::written_directive>()->block()->at(0).remove();
        }
    }
    CHECK(seen == std::vector<std::string>{"outer", "inner", "added", "last"});
}

TEST_CASE("a walk yields a statement removed after its block's snapshot, and does not descend into it",
          "[iteration][walk]") {
    const vw::document_graph graph = fixture::load("a;\nb {\n    c;\n}\n");
    const vw::written_block block = graph.root().block();
    std::vector<vl::statement_kind> kinds;
    int detached = 0;
    for (const vw::statement& s : block.walk()) {
        kinds.push_back(s.kind());
        if (kinds.size() == 1) {
            block.at(1).remove();  // b, with its block, after the top-level snapshot
            continue;
        }
        CHECK_THROWS_AS(s.text(), vl::detached_error);
        ++detached;
    }
    CHECK(kinds.size() == 2);  // a and the removed b; c is not visited
    CHECK(detached == 1);
}

TEST_CASE("walk(descend) enters only the blocks the predicate allows", "[iteration][walk]") {
    const vw::document_graph graph = fixture::load("keep {\n    one;\n}\nskip {\n    two;\n}\n");
    std::vector<std::string> seen;
    for (const vw::statement& s :
         graph.root().block().walk([](const vw::statement& s) { return name_of(s) != "skip"; })) {
        seen.push_back(name_of(s));
    }
    CHECK(seen == std::vector<std::string>{"keep", "one", "skip"});
}
