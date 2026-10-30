// <villanelle/format.hpp> (frozen-m3.md 3.1 and 4): std::format and operator<< of every people form give exactly its
// to_string, with a string's width, fill and alignment. The values come from a real load and render, so the people
// forms are the hand code's, not built here.
#include <villanelle/format.hpp>
#include <villanelle/rendered.hpp>
#include <villanelle/villanelle.hpp>
#include <villanelle/written.hpp>

#include <format>
#include <sstream>
#include <string>

#include <catch2/catch_test_macros.hpp>

#include "written_fixture.hpp"

namespace vl = villanelle;
namespace vw = villanelle::written;
namespace vr = villanelle::rendered;

namespace {

/// std::format("{}", value) and operator<< both give to_string(value).
template <class T>
void check_people_form(const T& value, const std::string& people) {
    CHECK(std::format("{}", value) == people);
    std::ostringstream out;
    out << value;
    CHECK(out.str() == people);
}

}  // namespace

TEST_CASE("a place formats as its to_string", "[format]") {
    const vw::document_graph graph = fixture::load("a 1;\nb 2;\n");
    const vl::place where = fixture::top(graph, 1).place();
    REQUIRE(to_string(where) == "main.conf:2:1");
    check_people_form(where, to_string(where));
}

TEST_CASE("a located diagnostic formats as its to_string", "[format]") {
    const vr::rendered tree = vr::render(fixture::load("fps $rate;\n"));
    const vl::sequence<vl::located_diagnostic> found = tree.diagnostics();
    REQUIRE(found.size() == 1);
    const vl::located_diagnostic& d = found.at(0);
    REQUIRE(to_string(d) == "main.conf:1:5: E5001: unknown variable: $rate");
    check_people_form(d, to_string(d));
}

TEST_CASE("an address from a real render formats as its to_string", "[format]") {
    const vr::rendered tree = vr::render(fixture::load("graph { node leds; }\nfps 20;\n"));
    const vl::ordered_map<vr::directive, vr::address> addresses = tree.addresses();
    REQUIRE(addresses.size() == 3);
    for (const auto& [directive, address] : addresses) {
        check_people_form(address, vr::to_string(address));
    }
}

TEST_CASE("a kind and a diagnostic code format as their to_string", "[format]") {
    CHECK(std::string(to_string(vl::value_kind::word)) == "word");
    check_people_form(vl::value_kind::word, "word");
    check_people_form(vl::diagnostic_code::not_a_number, "E4004");
}

TEST_CASE("width, fill and alignment work as for a string", "[format]") {
    CHECK(std::format("[{:>8}]", vl::value_kind::word) == "[    word]");
    CHECK(std::format("[{:*<7}]", vl::diagnostic_code::not_a_number) == "[E4004**]");
    CHECK(std::format("[{:^9}]", vl::value_kind::word) == "[  word   ]");
}
