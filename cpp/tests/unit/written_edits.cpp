// Edits (spec 6.4 to 6.7; frozen-m2.md 3.3 rule 4): each edit's refusal leaves the text and every handle unchanged
// (the strong guarantee), and a bad text error's diagnostics are in the positions of the text the edit was given.
#include <knobly/written.hpp>

#include <cstdint>
#include <string>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

namespace {

/// Every handle of a document's tree and the text, to compare before and after a refused edit.
struct state {
    std::string text;
    std::vector<vw::statement> statements;
    std::vector<vw::written_value> values;
    std::vector<std::string> texts;
};

state capture(const vw::document_graph& graph) {
    state out{graph.root().text(), {}, {}, {}};
    for (const vw::statement& s : graph.root().block().walk()) {
        out.statements.push_back(s);
        out.texts.push_back(s.text());
        if (auto d = s.as<vw::written_directive>()) {
            for (const vw::written_value& v : d->values()) {
                out.values.push_back(v);
                out.texts.push_back(v.text());
            }
        }
    }
    return out;
}

/// The same text, the same handles (identity), each still live with the same text.
void unchanged(const vw::document_graph& graph, const state& before) {
    const state after = capture(graph);
    CHECK(after.text == before.text);
    CHECK(after.statements == before.statements);
    CHECK(after.values == before.values);
    CHECK(after.texts == before.texts);
    CHECK(graph.root().saved_text() == before.text);
}

/// The bad text error's diagnostics as [code, line, column], or empty when nothing was raised.
std::vector<std::vector<std::int64_t>> refusal(auto&& edit) {
    try {
        edit();
    } catch (const vl::bad_text_error& error) {
        std::vector<std::vector<std::int64_t>> out;
        for (const vl::diagnostic& d : error.diagnostics()) {
            out.push_back({static_cast<std::int64_t>(d.code()), d.span().start().line(), d.span().start().column()});
        }
        return out;
    }
    return {};
}

constexpr auto e2001 = static_cast<std::int64_t>(vl::diagnostic_code::unexpected_token);
constexpr auto e5002 = static_cast<std::int64_t>(vl::diagnostic_code::variable_set_twice);
constexpr auto e2004 = static_cast<std::int64_t>(vl::diagnostic_code::expected_closing_bracket);

const char* const source = "@set $a 1;\nx [1, 2] {\n    y 3;\n}\nz $a;\n";

}  // namespace

TEST_CASE("every refused edit changes nothing", "[edits]") {
    const vw::document_graph graph = fixture::load(source);
    const state before = capture(graph);
    const vw::statement set = fixture::top(graph, 0);
    const vw::written_directive x = *fixture::top(graph, 1).as<vw::written_directive>();
    const vw::written_value list = x.values().at(0);
    const vw::written_value item = list.as<vw::list>()->items().at(0);
    const vw::written_block block = *x.block();

    CHECK_THROWS_AS(x.set(vl::text("1; y")), vl::bad_text_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(x.rename("2bad"), vl::misuse_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(set.as<vw::set_line>()->variable().rename("no way"), vl::misuse_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(set.replace_with_text(vl::text("x {")), vl::bad_text_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(set.insert_after(vl::text("@set $a 2;")), vl::bad_text_error);  // E5002 by the text alone
    unchanged(graph, before);
    CHECK_THROWS_AS(block.insert_statements(0, vl::text("}")), vl::bad_text_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(block.insert_statements(5, vl::text("w;")), vl::index_out_of_range);
    unchanged(graph, before);
    CHECK_THROWS_AS(block.insert_statements(-1, vl::text("w;")), vl::index_out_of_range);
    unchanged(graph, before);
    CHECK_THROWS_AS(list.set(vl::text("1 2")), vl::bad_text_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(item.replace_with_text(vl::text("1;")), vl::bad_text_error);
    unchanged(graph, before);
    CHECK_THROWS_AS(graph.set_override("a", vl::text("$b")), vl::bad_text_error);
    CHECK_THROWS_AS(graph.set_override("not a name", vl::text("1")), vl::misuse_error);
    unchanged(graph, before);
    CHECK(graph.overrides().empty());
}

TEST_CASE("a bad text error is placed in the text the edit was given", "[edits]") {
    const vw::document_graph graph = fixture::load(source);
    const vw::written_directive x = *fixture::top(graph, 1).as<vw::written_directive>();
    // The entry rule's first problem, at its token in the given text.
    CHECK(refusal([&] { x.set(vl::text("1; y")); }) == std::vector<std::vector<std::int64_t>>{{e2001, 0, 1}});
    CHECK(refusal([&] { x.set(vl::text("ok\n[1 # c")); }) == std::vector<std::vector<std::int64_t>>{{e2004, 1, 6}});
    // A text-alone rule broken by what the caller gave: located in its text, at the offending $name.
    CHECK(refusal([&] { fixture::top(graph, 0).insert_after(vl::text("w 1;\n@set $a 2;")); }) ==
          std::vector<std::vector<std::int64_t>>{{e5002, 1, 5}});
    // A text with no value is E2001 at its start.
    CHECK(refusal([&] { x.set(vl::text("# only a comment\n")); }) ==
          std::vector<std::vector<std::int64_t>>{{e2001, 0, 0}});
}

TEST_CASE("an accepted edit keeps the handles outside the replaced range", "[edits]") {
    const vw::document_graph graph = fixture::load(source);
    const vw::statement set = fixture::top(graph, 0);
    const vw::written_directive x = *fixture::top(graph, 1).as<vw::written_directive>();
    const vw::statement y = x.block()->at(0);
    const vw::statement z = fixture::top(graph, 2);
    const vl::sequence<vw::statement> made = x.block()->add_statements(vl::text("w 4;\nv 5;"));
    CHECK(made.size() == 2);
    CHECK(made.at(0).text() == "w 4;");
    CHECK(graph.root().text() == "@set $a 1;\nx [1, 2] {\n    y 3;\n    w 4;\n    v 5;\n}\nz $a;\n");
    CHECK(fixture::top(graph, 0) == set);
    CHECK(x.block()->at(0) == y);
    CHECK(fixture::top(graph, 2) == z);
    x.rename("renamed");
    CHECK(x.name() == "renamed");
    CHECK(fixture::top(graph, 1) == vw::statement(x));
    set.as<vw::set_line>()->variable().rename("b");
    CHECK(graph.root().text() == "@set $b 1;\nrenamed [1, 2] {\n    y 3;\n    w 4;\n    v 5;\n}\nz $a;\n");
    z.remove();
    CHECK(graph.root().text() == "@set $b 1;\nrenamed [1, 2] {\n    y 3;\n    w 4;\n    v 5;\n}\n");
    CHECK_THROWS_AS(z.text(), vl::detached_error);
}
