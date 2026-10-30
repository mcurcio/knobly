// The rendered layer (spec 7; frozen-m2.md 6): a walk whose descend skips a subtree, closest, addresses under a key
// rule, each kind of diff change, and a render that a directive keeps alive after every other handle is gone.
#include <villanelle/rendered.hpp>
#include <villanelle/written.hpp>

#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

namespace {

vr::rendered render_text(const std::string& text) { return vr::render(fixture::load(text)); }

/// The rasl rule of conformance/keys.json, written as a program writes a key rule: a node under graph by its second
/// value, a connect by its values joined.
std::optional<std::string> rasl_key(const vr::directive& d) {
    const vl::sequence<vw::expanded_value> values = d.values();
    if (d.name() == "node") {
        const std::optional<vr::directive> parent = d.parent();
        if (parent && parent->name() == "graph" && values.size() > 1) {
            return values.at(1).text();
        }
        return std::nullopt;
    }
    if (d.name() == "connect") {
        std::string joined;
        for (std::size_t i = 0; i < values.size(); ++i) {
            joined += (i == 0 ? "" : " ") + values.at(i).text();
        }
        return joined;
    }
    return std::nullopt;
}

std::vector<std::pair<vl::change_kind, std::string>> changes(const vl::sequence<vr::change>& list) {
    std::vector<std::pair<vl::change_kind, std::string>> out;
    for (const vr::change& c : list) {
        out.emplace_back(c.kind(), vr::to_string(c.address()));
    }
    return out;
}

}  // namespace

TEST_CASE("a walk visits every directive depth first, and descend skips a subtree", "[rendered][walk]") {
    const vr::rendered r = render_text("a { b { c; } d; }\ne { f; }\n");
    std::vector<std::string> all;
    for (const vr::directive& d : r.block().walk()) {
        all.push_back(d.name());
    }
    CHECK(all == std::vector<std::string>{"a", "b", "c", "d", "e", "f"});

    std::vector<std::string> pruned;
    for (const vr::directive& d : r.block().walk([](const vr::directive& d) { return d.name() != "b"; })) {
        pruned.push_back(d.name());
    }
    CHECK(pruned == std::vector<std::string>{"a", "b", "d", "e", "f"});  // b yielded, c skipped
}

TEST_CASE("closest is the directive itself or its nearest enclosing match", "[rendered][closest]") {
    const vr::rendered r = render_text("graph { node a { fill 1; } }\n");
    const vr::directive fill = r.block().at(0).block()->at(0).block()->at(0);
    REQUIRE(fill.name() == "fill");
    CHECK(fill.closest([](const vr::directive& d) { return d.name() == "fill"; }) == fill);
    const std::optional<vr::directive> graph = fill.closest([](const vr::directive& d) { return d.name() == "graph"; });
    REQUIRE(graph);
    CHECK(*graph == r.block().at(0));
    CHECK_FALSE(graph->parent());
    CHECK_FALSE(fill.closest([](const vr::directive& d) { return d.name() == "none"; }));
}

TEST_CASE("addresses name each directive under the key rule, in walk order", "[rendered][addresses]") {
    const vr::rendered r =
        render_text("graph {\n  node led leds;\n  node led strip;\n  node led leds;\n}\nnode x y;\n");
    std::vector<std::pair<std::string, std::string>> got;
    for (const auto& [directive, address] : r.addresses(vr::key_options{rasl_key})) {
        got.emplace_back(address.text(), vr::to_string(address));
    }
    CHECK(got == std::vector<std::pair<std::string, std::string>>{
                     {R"([["graph",null,0]])", "graph"},
                     {R"([["graph",null,0],["node","leds",0]])", R"(graph > node "leds")"},
                     {R"([["graph",null,0],["node","strip",0]])", R"(graph > node "strip")"},
                     {R"([["graph",null,0],["node","leds",1]])", R"(graph > node "leds" #1)"},
                     {R"([["node",null,0]])", "node"},  // not under graph: the rule's parent does not match
                 });

    // Without a key rule a directive is named by its position among same-name siblings.
    std::vector<std::string> plain;
    for (const auto& [directive, address] : r.addresses()) {
        plain.push_back(vr::to_string(address));
    }
    CHECK(plain == std::vector<std::string>{"graph", "graph > node", "graph > node #1", "graph > node #2", "node"});
    const vr::directive second = r.block().at(0).block()->at(1);
    REQUIRE(r.addresses().find(second));
    CHECK(r.addresses().find(second)->parent()->text() == R"([["graph",null,0]])");
}

TEST_CASE("diff reports added, removed, changed and unknown by address", "[rendered][diff]") {
    const vr::rendered before = render_text("a 1;\nb 2;\nc { d 3; }\ne { f 4; }\n");
    const vr::rendered after = render_text("a 1;\nb 5;\nc { d 3; g 6; }\ne { ? }\n");
    const auto got = changes(before.diff(after));
    CHECK(got == std::vector<std::pair<vl::change_kind, std::string>>{
                     {vl::change_kind::unknown, "e > f"},  // its block holds a line that cannot be read now
                     {vl::change_kind::changed, "b"},
                     {vl::change_kind::added, "c > g"},
                 });
    const auto removed = changes(after.diff(render_text("a 1;\n")));
    CHECK(removed == std::vector<std::pair<vl::change_kind, std::string>>{
                         {vl::change_kind::removed, "b"},
                         {vl::change_kind::removed, "c"},
                         {vl::change_kind::removed, "e"},
                     });

    const vl::sequence<vr::change> list = before.diff(after);
    const std::optional<vr::changed> changed = list.at(1).as<vr::changed>();
    REQUIRE(changed);
    CHECK(changed->before().values().at(0).text() == "2");
    CHECK(changed->after().values().at(0).text() == "5");
    CHECK_FALSE(list.at(1).as<vr::added>());
    CHECK(list.at(2).visit([](const auto& c) { return c.kind(); }) == vl::change_kind::added);
    CHECK(before.diff(before).empty());
}

TEST_CASE("a directive keeps its render and graph alive after every other handle is gone", "[rendered][lifetime]") {
    std::optional<vr::directive> kept;
    {
        const vw::document_graph graph = fixture::load("@set $n 7;\nouter { inner $n; }\n");
        const vr::rendered r = vr::render(graph);
        kept = r.block().at(0).block()->at(0);
    }
    REQUIRE(kept);
    CHECK(kept->name() == "inner");
    CHECK(kept->values().at(0).integer() == 7);
    CHECK(kept->parent()->name() == "outer");
    CHECK(kept->written().name() == "inner");
    CHECK(kept->origin().place().resolved_path() == "main.conf");
}

TEST_CASE("a moved-from graph is still the graph: a handle is never null", "[rendered][lifetime]") {
    vw::document_graph graph = fixture::load("a 1;\n");
    const vw::document_graph moved = std::move(graph);
    CHECK(graph == moved);                              // NOLINT(bugprone-use-after-move)
    CHECK(vr::render(graph).block().size() == 1);       // NOLINT(bugprone-use-after-move)
    CHECK(vr::render(moved).block().size() == 1);
}

TEST_CASE("error places a program's diagnostic on a directive or the root", "[rendered][errors]") {
    const vr::rendered r = render_text("a 1;\n");
    const vl::diagnostic_error on_a = r.block().at(0).error("bad a", "app/bad");
    CHECK(vl::to_string(on_a.diagnostic()) == "main.conf:1:1: app/bad: bad a");
    const vl::diagnostic_error on_root = r.error("missing b", "app/missing");
    CHECK(vl::to_string(on_root.diagnostic()) == "main.conf:1:1: app/missing: missing b");
}
