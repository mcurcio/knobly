// knobly::block<Item, Directive> over the written layer (frozen-m2.md 3.1): a random-access iterator over one
// snapshot taken at begin(), size() and at() on a fresh one (at past the end raising index_out_of_range), and
// directives by name.
#include <knobly/written.hpp>

#include <algorithm>
#include <iterator>
#include <ranges>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

static_assert(std::random_access_iterator<vw::written_block::iterator>);
static_assert(std::ranges::random_access_range<vw::written_block>);
static_assert(std::is_same_v<std::iter_reference_t<vw::written_block::iterator>, vw::statement>);
static_assert(std::ranges::random_access_range<vw::expansion_block>);
static_assert(std::input_iterator<vl::walk_view<vw::statement>::iterator>);
static_assert(std::sentinel_for<vl::walk_view<vw::statement>::sentinel, vl::walk_view<vw::statement>::iterator>);

TEST_CASE("size, at and the iterator", "[block]") {
    const vw::document_graph graph = fixture::load("a 1;\n@set $v 2;\nb 3;\na 4;\n");
    const vw::written_block block = graph.root().block();
    CHECK(block.size() == 4);
    CHECK(block.at(1).kind() == vl::statement_kind::set);
    CHECK_THROWS_AS(block.at(4), vl::index_out_of_range);
    const auto first = block.begin();
    const auto last = block.end();
    CHECK(last - first == 4);
    CHECK(first[2].text() == "b 3;");
    CHECK((*(first + 3)).text() == "a 4;");
}

TEST_CASE("directives, all or by name, in written order", "[block]") {
    const vw::document_graph graph = fixture::load("a 1;\n@set $v 2;\nb 3;\na 4;\n");
    const vw::written_block block = graph.root().block();
    CHECK(block.directives().size() == 3);
    const vl::sequence<vw::written_directive> named = block.directives("a");
    REQUIRE(named.size() == 2);
    CHECK(named.at(0).values().at(0).text() == "1");
    CHECK(named.at(1).values().at(0).text() == "4");
    CHECK(block.directives("none").empty());
}

TEST_CASE("the iterator holds its snapshot; size() reads a fresh one", "[block]") {
    const vw::document_graph graph = fixture::load("a;\nb;\n");
    const vw::written_block block = graph.root().block();
    auto it = block.begin();
    block.add_statements(vl::text("c;"));
    CHECK(block.size() == 3);
    CHECK(std::distance(it, block.end()) == 2);  // positions count from the snapshot's end
    std::vector<std::string> seen;
    for (; it != block.end(); ++it) {
        seen.push_back((*it).text());
    }
    CHECK(seen == std::vector<std::string>{"a;", "b;"});
}

TEST_CASE("the expansion block shares the shape", "[block]") {
    const vw::document_graph graph = fixture::load("a 1 {\n    b 2;\n}\nc;\n");
    const vw::expansion_block block = graph.expand().block();
    CHECK(block.size() == 2);
    CHECK(block.directives("c").size() == 1);
    std::vector<std::string> names;
    for (const vw::directive_expansion& d : block.walk()) {
        names.push_back(d.written().name());
    }
    CHECK(names == std::vector<std::string>{"a", "b", "c"});
    CHECK_THROWS_AS(block.at(2), vl::index_out_of_range);
}
