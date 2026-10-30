// A stale variant view (finding F4, D16; frozen-m2.md 3.3 rule 3): a value's set keeps its handle and the node takes
// the new kind, so kind() and as<V>() follow it; a member only the old variant has raises misuse_error, and the
// shared members work.
#include <villanelle/written.hpp>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = villanelle;
namespace vw = villanelle::written;

TEST_CASE("a list set to a word: the list view's own members raise misuse_error", "[stale]") {
    const vw::document_graph graph = fixture::load("x [1, 2] tail;\n");
    const vw::written_value value = fixture::top(graph, 0).as<vw::written_directive>()->values().at(0);
    const vw::list list = *value.as<vw::list>();
    CHECK(list.items().size() == 2);
    value.set(vl::text("word"));
    CHECK(graph.root().text() == "x word tail;\n");
    // The same handle, now a word.
    CHECK(value.kind() == vl::value_kind::word);
    CHECK(list.kind() == vl::value_kind::word);
    CHECK(value.as<vw::word>().has_value());
    CHECK_FALSE(value.as<vw::list>().has_value());
    CHECK(value == fixture::top(graph, 0).as<vw::written_directive>()->values().at(0));
    // The old variant's own member is a misuse; the shared ones follow the node.
    CHECK_THROWS_AS(list.items(), vl::misuse_error);
    CHECK(list.text() == "word");
    CHECK(list.place().span().start().column() == 2);
    CHECK_FALSE(list.list_().has_value());
}

TEST_CASE("a word set to a slice and back: each variant view knows its kind", "[stale]") {
    const vw::document_graph graph = fixture::load("x a;\n");
    const vw::written_value value = fixture::top(graph, 0).as<vw::written_directive>()->values().at(0);
    value.set(vl::text("s[1~2]"));
    const vw::slice slice = *value.as<vw::slice>();
    CHECK(slice.name().text() == "s");
    CHECK(slice.start()->text() == "1");
    value.set(vl::text("i[3]"));
    CHECK(value.kind() == vl::value_kind::index);
    CHECK_THROWS_AS(slice.name(), vl::misuse_error);
    CHECK_THROWS_AS(slice.start(), vl::misuse_error);
    CHECK_THROWS_AS(slice.end(), vl::misuse_error);
    const vw::index index = *value.as<vw::index>();
    CHECK(index.index_().text() == "3");
    value.set(vl::text("$r"));
    CHECK_THROWS_AS(index.name(), vl::misuse_error);
    const vw::reference reference = *value.as<vw::reference>();
    CHECK(reference.name() == "r");
    CHECK_FALSE(reference.declaration().has_value());
    value.set(vl::text("\"s\""));
    CHECK_THROWS_AS(reference.name(), vl::misuse_error);
    CHECK_THROWS_AS(reference.resolutions(), vl::misuse_error);
    CHECK(reference.text() == "\"s\"");
    CHECK(value.visit([](const auto& v) { return v.kind(); }) == vl::value_kind::string);
}
