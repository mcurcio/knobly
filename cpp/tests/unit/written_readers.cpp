// The expanded value's readers (spec 2.9; contract 3): each reader on its kinds, a wrong kind as a located
// diagnostic_error (E4002, and E4004 to E4006 for a word that is no number, integer or boolean), slices and indexes
// with negative bounds, and a value's links back to what was written.
#include <knobly/written.hpp>

#include <cmath>
#include <cstdint>
#include <string>
#include <variant>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = knobly;
namespace vw = knobly::written;

namespace {

/// The expanded values of the root's directive at `index`.
vl::sequence<vw::expanded_value> values_of(const vw::document_graph& graph, std::size_t index) {
    return graph.expand().block().at(index).values();
}

/// The code a reader's diagnostic error carries, and where.
std::string code_of(auto&& read) {
    try {
        read();
    } catch (const vl::diagnostic_error& error) {
        const auto code = error.diagnostic().code();
        return vl::to_string(std::get<vl::diagnostic_code>(code)) + "@" + vl::to_string(error.diagnostic().place());
    }
    return "none";
}

}  // namespace

TEST_CASE("each reader reads its own kinds", "[readers]") {
    const vw::document_graph graph =
        fixture::load("x word \"str\\n\" 'raw\\n' 42 -7 2.5e1 -0 true [1, [2]] s[1~3] i[2];\n");
    const vl::sequence<vw::expanded_value> v = values_of(graph, 0);
    REQUIRE(v.size() == 11);
    CHECK(v.at(0).word() == "word");
    CHECK(v.at(0).string() == "word");  // a word reads as a string too
    CHECK(v.at(1).string() == "str\n");
    CHECK(v.at(1).text() == "\"str\\n\"");  // the canonical text
    CHECK(v.at(2).string() == "raw\\n");    // single quotes are raw
    CHECK(v.at(3).integer() == 42);
    CHECK(v.at(3).number() == 42.0);
    CHECK(v.at(4).integer() == -7);
    CHECK(v.at(5).number() == 25.0);
    CHECK(v.at(6).integer() == 0);
    CHECK_FALSE(std::signbit(v.at(6).number()));  // zero has one sign
    CHECK(v.at(7).boolean());
    const vl::sequence<vw::expanded_value> list = v.at(8).list();
    REQUIRE(list.size() == 2);
    CHECK(list.at(0).integer() == 1);
    CHECK(list.at(1).list().at(0).integer() == 2);
    CHECK(v.at(8).text() == "[1, [2]]");
    CHECK(v.at(8).as<vw::expanded_list>()->items().size() == 2);
    const auto slice = std::get<vw::slice_value>(v.at(9).slice());
    CHECK(slice.name() == "s");
    CHECK(slice.start() == 1);
    CHECK(slice.end() == 3);
    const auto index = std::get<vw::index_value>(v.at(10).slice());
    CHECK(index.name() == "i");
    CHECK(index.index() == 2);
    CHECK(v.at(10).as<vw::expanded_index>()->index() == 2);
}

TEST_CASE("slices and indexes with negative and absent bounds", "[readers]") {
    const vw::document_graph graph = fixture::load("@set $n -2;\nx s[-3~-1] t[~-1] u[-2~] w[-1] v[$n];\n");
    const vl::sequence<vw::expanded_value> v = values_of(graph, 0);
    REQUIRE(v.size() == 5);
    const auto s = std::get<vw::slice_value>(v.at(0).slice());
    CHECK(s.start() == -3);
    CHECK(s.end() == -1);
    CHECK(v.at(0).text() == "s[-3~-1]");
    const auto t = std::get<vw::slice_value>(v.at(1).slice());
    CHECK_FALSE(t.start().has_value());
    CHECK(t.end() == -1);
    CHECK(v.at(1).text() == "t[~-1]");
    const auto u = v.at(2).as<vw::expanded_slice>();
    CHECK(u->start() == -2);
    CHECK_FALSE(u->end().has_value());
    CHECK(std::get<vw::index_value>(v.at(3).slice()).index() == -1);
    CHECK(std::get<vw::index_value>(v.at(4).slice()).index() == -2);  // through a variable
    CHECK(v.at(4).text() == "v[-2]");
}

TEST_CASE("a reader on the wrong kind raises a located diagnostic_error", "[readers]") {
    const vw::document_graph graph = fixture::load("x word \"s\" [1] s[1~2] 1.5 maybe;\n");
    const vl::sequence<vw::expanded_value> v = values_of(graph, 0);
    CHECK(code_of([&] { v.at(1).word(); }) == "E4002@main.conf:1:8");
    CHECK(code_of([&] { v.at(2).string(); }) == "E4002@main.conf:1:12");
    CHECK(code_of([&] { v.at(0).list(); }) == "E4002@main.conf:1:3");
    CHECK(code_of([&] { v.at(0).slice(); }) == "E4002@main.conf:1:3");
    CHECK(code_of([&] { v.at(3).integer(); }) == "E4002@main.conf:1:16");
    CHECK(code_of([&] { v.at(0).number(); }) == "E4004@main.conf:1:3");
    CHECK(code_of([&] { v.at(4).integer(); }) == "E4005@main.conf:1:23");
    CHECK(code_of([&] { v.at(5).boolean(); }) == "E4006@main.conf:1:27");
    CHECK(code_of([&] { v.at(1).integer(); }) == "E4002@main.conf:1:8");
    CHECK(v.at(4).number() == 1.5);
}

TEST_CASE("a value read through a variable knows its way back", "[readers]") {
    const vw::document_graph graph = fixture::load("@set $port 8080;\nlisten $port;\n");
    const vw::expanded_value v = values_of(graph, 0).at(0);
    CHECK(v.integer() == 8080);
    const vl::origin origin = v.origin();
    CHECK(vl::to_string(std::get<vl::place>(origin.place())) == "main.conf:1:12");
    REQUIRE(origin.via().size() == 1);
    CHECK(vl::to_string(origin.via().at(0)) == "variable port at main.conf:2:8");
    CHECK(v.definition()->text() == "8080");
    CHECK(v.written().text() == "$port");
    REQUIRE(v.chain().size() == 1);
    CHECK(v.chain().at(0).winner()->name() == "port");
    // A program's own problem, placed where the value is written, with its steps.
    const vl::diagnostic_error error = v.error("port taken", "app/port");
    CHECK(vl::to_string(error.diagnostic()) == "main.conf:1:12: app/port: port taken");
    CHECK(error.diagnostic().via().size() == 1);
    // A reader's problem is placed the same way.
    CHECK(code_of([&] { v.boolean(); }) == "E4006@main.conf:1:12");
}

TEST_CASE("an override's value is placed on the $name that used it", "[readers]") {
    vw::load_options options;
    options.overrides.insert_or_assign("port", vl::text("abc"));
    const vw::document_graph graph =
        fixture::load(fixture::files({{"main.conf", "listen $port;\n"}}), "main.conf", options);
    const vw::expanded_value v = values_of(graph, 0).at(0);
    CHECK(std::holds_alternative<vl::override>(v.origin().place()));
    CHECK_FALSE(v.definition().has_value());
    CHECK(code_of([&] { v.integer(); }) == "E4005@main.conf:1:8");
    const vl::program_code code(std::string("app/x"));
    CHECK(std::string(code.view()) == "app/x");
    CHECK_THROWS_AS(vl::program_code(std::string("nocode")), vl::misuse_error);
}

TEST_CASE("number reads a JSON number, rounded to the nearest double, never negative zero", "[readers]") {
    const vw::document_graph graph = fixture::load("x 1e400 -1e-400 1e-310 0.1 -0.0 01;\n");
    const vl::sequence<vw::expanded_value> v = values_of(graph, 0);
    CHECK(code_of([&] { v.at(0).number(); }) == "E4004@main.conf:1:3");  // beyond the double range
    CHECK(v.at(1).number() == 0.0);
    CHECK_FALSE(std::signbit(v.at(1).number()));
    CHECK(v.at(2).number() == 1e-310);  // a subnormal is kept
    CHECK(v.at(3).number() == 0.1);
    CHECK_FALSE(std::signbit(v.at(4).number()));
    CHECK(code_of([&] { v.at(5).number(); }) == "E4004@main.conf:1:33");  // a leading zero is no NumberText
}
